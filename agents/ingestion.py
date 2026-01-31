from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.events import RawEvent
from db.models import RawEventDB
import logging

logger = logging.getLogger(__name__)


class SignalIngestionAgent:
    """
    Ingests raw events from external sources into the database.
    
    Responsibilities:
    - Accept events from multiple sources (Zendesk, API logs, webhooks, etc.)
    - Check for duplicates using idempotency keys
    - Store events with audit trail
    - Return status for monitoring
    
    Attributes:
        name: Agent identifier for logging
        processed_keys: In-memory cache of recent idempotency keys (for performance)
    """
    
    def __init__(self):
        self.name = "SignalIngestionAgent"
        self.processed_keys = set()  # In-memory dedup cache (production: use Redis)
    
    def ingest_event(self, event: RawEvent, db: Session) -> bool:
        """
        Ingest a single event with idempotency checking.
        
        Checks both in-memory cache and database for duplicates before storing.
        Uses database idempotency_key unique constraint as final guarantee.
        
        Args:
            event: RawEvent model to ingest
            db: SQLAlchemy session for database operations
        
        Returns:
            True if event was stored (new event)
            False if event was duplicate
        
        Raises:
            IntegrityError: If database constraint violation occurs
        """
        # Quick check in-memory cache
        if event.idempotency_key in self.processed_keys:
            logger.info(
                f"[{self.name}] Duplicate detected (memory): {event.idempotency_key}"
            )
            return False
        
        # Query database for existing event
        existing = db.query(RawEventDB).filter(
            RawEventDB.idempotency_key == event.idempotency_key
        ).first()
        
        if existing:
            logger.info(
                f"[{self.name}] Duplicate detected (database): {event.idempotency_key}"
            )
            self.processed_keys.add(event.idempotency_key)
            return False
        
        # Store new event
        try:
            db_event = RawEventDB(
                event_id=event.event_id,
                event_type=event.event_type,
                merchant_id=event.merchant_id,
                timestamp=event.timestamp,
                payload=event.payload,
                source=event.source,
                idempotency_key=event.idempotency_key
            )
            
            db.add(db_event)
            db.commit()
            
            # Cache the key
            self.processed_keys.add(event.idempotency_key)
            
            logger.info(
                f"[{self.name}] Stored new event: {event.event_id} "
                f"({event.event_type}) from {event.source}"
            )
            return True
            
        except IntegrityError as e:
            # Race condition: event was inserted by another process
            db.rollback()
            logger.warning(
                f"[{self.name}] Idempotency violation (race condition): "
                f"{event.idempotency_key}"
            )
            self.processed_keys.add(event.idempotency_key)
            return False
        
        except Exception as e:
            db.rollback()
            logger.error(
                f"[{self.name}] Failed to ingest event {event.event_id}: {str(e)}"
            )
            raise
    
    def ingest_batch(self, events: List[RawEvent], db: Session) -> int:
        """
        Ingest multiple events in batch.
        
        Processes each event individually to maintain idempotency guarantees,
        but commits in a single transaction for efficiency.
        
        Args:
            events: List of RawEvent models to ingest
            db: SQLAlchemy session for database operations
        
        Returns:
            Count of new events successfully stored
        """
        if not events:
            logger.info(f"[{self.name}] Empty batch received")
            return 0
        
        new_count = 0
        failed_count = 0
        duplicate_count = 0
        
        logger.info(f"[{self.name}] Starting batch ingestion ({len(events)} events)")
        
        for event in events:
            if self.ingest_event(event, db):
                new_count += 1
            else:
                # Could be duplicate or error
                if event.idempotency_key in self.processed_keys:
                    duplicate_count += 1
                else:
                    failed_count += 1
        
        # Log batch summary
        logger.info(
            f"[{self.name}] Batch complete: "
            f"{new_count} new, {duplicate_count} duplicates, {failed_count} failed "
            f"(total: {len(events)})"
        )
        
        return new_count
    
    def get_pending_event_count(self, db: Session) -> int:
        """
        Get count of raw events that haven't been normalized yet.
        
        Useful for monitoring pipeline status and backlog.
        
        Args:
            db: SQLAlchemy session
        
        Returns:
            Count of unprocessed raw events
        """
        from db.models import CleanEventDB
        
        unprocessed = db.query(RawEventDB).outerjoin(
            CleanEventDB,
            RawEventDB.event_id == CleanEventDB.raw_event_id
        ).filter(
            CleanEventDB.event_id == None
        ).count()
        
        return unprocessed
    
    def get_event_count_by_type(self, db: Session) -> dict:
        """
        Get count of events by type for monitoring.
        
        Args:
            db: SQLAlchemy session
        
        Returns:
            Dictionary with event type counts
        """
        from sqlalchemy import func
        
        results = db.query(
            RawEventDB.event_type,
            func.count(RawEventDB.event_id).label('count')
        ).group_by(RawEventDB.event_type).all()
        
        return {row[0]: row[1] for row in results}
    
    def get_event_count_by_source(self, db: Session) -> dict:
        """
        Get count of events by source for monitoring.
        
        Args:
            db: SQLAlchemy session
        
        Returns:
            Dictionary with source counts
        """
        from sqlalchemy import func
        
        results = db.query(
            RawEventDB.source,
            func.count(RawEventDB.event_id).label('count')
        ).group_by(RawEventDB.source).all()
        
        return {row[0]: row[1] for row in results}
