from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import and_
from models.incidents import IncidentCluster
from db.models import CleanEventDB, IncidentClusterDB
from uuid import uuid4
import json
import logging

logger = logging.getLogger(__name__)


class PatternDetectionAgent:
    """
    Detects incident patterns by clustering similar events and detecting spikes.
    
    Responsibilities:
    - Group clean events by signature
    - Calculate baseline rates for each signature
    - Detect spikes (current rate > baseline * threshold)
    - Create and update incident clusters
    - Calculate stage and component distributions
    - Generate cluster summaries for escalation
    
    Attributes:
        spike_threshold: Multiplier for spike detection (default 3.0x)
        min_events_for_cluster: Minimum events to form a cluster (default 5)
    """
    
    def __init__(self, knowledge_base=None):
        """
        Initialize pattern detection agent.
        
        Args:
            knowledge_base: Optional KnowledgeBase instance for RAG context
        """
        self.kb = knowledge_base
        self.spike_threshold = 3.0  # Current rate must be 3x baseline to spike
        self.min_events_for_cluster = 5
    
    def detect_patterns(
        self,
        db: Session,
        lookback_minutes: int = 60,
        detection_window_minutes: int = 30
    ) -> List[IncidentCluster]:
        """
        Detect incident patterns in recent events.
        
        Uses sliding window approach:
        - Baseline period: [now - lookback_minutes] to [now - detection_window_minutes]
        - Detection window: [now - detection_window_minutes] to [now]
        - If current rate > baseline_rate * spike_threshold, mark as spiking
        
        Args:
            db: SQLAlchemy session
            lookback_minutes: Duration of baseline period (default 60)
            detection_window_minutes: Duration of detection window (default 30)
        
        Returns:
            List of IncidentCluster objects (only spiking clusters)
        """
        now = datetime.utcnow()
        detection_start = now - timedelta(minutes=detection_window_minutes)
        lookback_start = now - timedelta(minutes=lookback_minutes)
        
        logger.info(
            f"[PatternDetectionAgent] Detecting patterns "
            f"(baseline: {lookback_minutes}m, window: {detection_window_minutes}m)"
        )
        
        # Get recent events (detection window)
        recent_events = db.query(CleanEventDB).filter(
            CleanEventDB.timestamp >= detection_start
        ).all()
        
        # Get baseline events (lookback period, excluding detection window)
        baseline_events = db.query(CleanEventDB).filter(
            and_(
                CleanEventDB.timestamp >= lookback_start,
                CleanEventDB.timestamp < detection_start
            )
        ).all()
        
        logger.info(
            f"[PatternDetectionAgent] Recent: {len(recent_events)} events, "
            f"Baseline: {len(baseline_events)} events"
        )
        
        # Group recent events by signature
        signature_groups = defaultdict(list)
        for event in recent_events:
            signature_groups[event.signature].append(event)
        
        # Calculate baseline rates by signature
        baseline_rates = self._calculate_baseline_rates(baseline_events, lookback_minutes)
        
        clusters = []
        
        # Process each signature group
        for signature, events in signature_groups.items():
            if len(events) < self.min_events_for_cluster:
                logger.debug(
                    f"[PatternDetectionAgent] Signature {signature}: "
                    f"Only {len(events)} events (below minimum {self.min_events_for_cluster})"
                )
                continue
            
            # Calculate current rate (events per hour)
            current_rate = (len(events) / detection_window_minutes) * 60
            baseline_rate = baseline_rates.get(signature, 0.1)  # Default very low
            
            # Detect spike
            is_spike = current_rate >= (baseline_rate * self.spike_threshold)
            trend = "spiking" if is_spike else "stable"
            
            logger.info(
                f"[PatternDetectionAgent] Signature: {signature} "
                f"Events: {len(events)}, Rate: {current_rate:.1f}/hr "
                f"(baseline: {baseline_rate:.1f}/hr, spike: {is_spike})"
            )
            
            # Create or update cluster
            if is_spike:
                cluster = self._create_cluster(
                    signature=signature,
                    events=events,
                    current_rate=current_rate,
                    baseline_rate=baseline_rate,
                    trend=trend,
                    db=db
                )
                clusters.append(cluster)
        
        logger.info(f"[PatternDetectionAgent] Detected {len(clusters)} spiking clusters")
        return clusters
    
    def _calculate_baseline_rates(
        self,
        baseline_events: List[CleanEventDB],
        window_minutes: int
    ) -> Dict[str, float]:
        """
        Calculate events per hour for each signature in baseline period.
        
        Args:
            baseline_events: List of events in baseline period
            window_minutes: Duration of baseline period
        
        Returns:
            Dictionary mapping signature → events_per_hour
        """
        signature_counts = defaultdict(int)
        
        # Count events by signature
        for event in baseline_events:
            signature_counts[event.signature] += 1
        
        # Convert counts to hourly rates
        rates = {}
        for signature, count in signature_counts.items():
            rates[signature] = (count / window_minutes) * 60
        
        logger.debug(f"[PatternDetectionAgent] Calculated baseline rates for {len(rates)} signatures")
        return rates
    
    def _create_cluster(
        self,
        signature: str,
        events: List[CleanEventDB],
        current_rate: float,
        baseline_rate: float,
        trend: str,
        db: Session
    ) -> IncidentCluster:
        """
        Create or update an incident cluster from grouped events.
        
        Checks if a recent cluster with same signature exists. If so, updates it.
        Otherwise creates a new cluster.
        
        Args:
            signature: Event signature
            events: List of CleanEventDB objects in this cluster
            current_rate: Current rate (events/hour)
            baseline_rate: Baseline rate (events/hour)
            trend: Trend status (spiking/stable/declining)
            db: SQLAlchemy session
        
        Returns:
            IncidentCluster Pydantic model
        """
        # Check if recent cluster exists (within last 2 hours)
        existing = db.query(IncidentClusterDB).filter(
            and_(
                IncidentClusterDB.primary_signature == signature,
                IncidentClusterDB.updated_at >= datetime.utcnow() - timedelta(hours=2)
            )
        ).first()
        
        merchant_ids = list(set(e.merchant_id for e in events))
        
        if existing:
            # Update existing cluster
            logger.info(
                f"[PatternDetectionAgent] Updating existing cluster for {signature}"
            )
            
            existing.event_count += len(events)
            existing.last_seen = max(e.timestamp for e in events)
            existing.updated_at = datetime.utcnow()
            existing.rate_per_hour = current_rate
            existing.trend = trend
            
            # Merge merchants
            existing_merchants = set(json.loads(existing.affected_merchant_ids))
            new_merchants = set(merchant_ids)
            all_merchants = existing_merchants | new_merchants
            
            existing.affected_merchant_ids = json.dumps(sorted(list(all_merchants)))
            existing.merchant_count = len(all_merchants)
            
            # Recalculate distributions
            existing.stage_distribution = json.dumps(self._get_stage_distribution(events))
            existing.component_distribution = json.dumps(self._get_component_distribution(events))
            
            db.commit()
            
            # Convert to Pydantic
            cluster = IncidentCluster(
                cluster_id=existing.cluster_id,
                created_at=existing.created_at,
                updated_at=existing.updated_at,
                top_signatures=[signature],
                primary_signature=signature,
                affected_merchant_ids=all_merchants,
                merchant_count=len(all_merchants),
                event_count=existing.event_count,
                trend=trend,
                first_seen=existing.first_seen,
                last_seen=existing.last_seen,
                rate_per_hour=current_rate,
                baseline_rate=baseline_rate,
                sample_event_ids=[e.event_id for e in events[:5]],
                stage_distribution=json.loads(existing.stage_distribution),
                component_distribution=json.loads(existing.component_distribution)
            )
            
            return cluster
        
        # Create new cluster
        logger.info(
            f"[PatternDetectionAgent] Creating new cluster for {signature} "
            f"({len(merchant_ids)} merchants, {len(events)} events)"
        )
        
        cluster = IncidentCluster(
            cluster_id=uuid4(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            top_signatures=[signature],
            primary_signature=signature,
            affected_merchant_ids=merchant_ids,
            merchant_count=len(merchant_ids),
            event_count=len(events),
            trend=trend,
            first_seen=min(e.timestamp for e in events),
            last_seen=max(e.timestamp for e in events),
            rate_per_hour=current_rate,
            baseline_rate=baseline_rate,
            sample_event_ids=[e.event_id for e in events[:5]],
            stage_distribution=self._get_stage_distribution(events),
            component_distribution=self._get_component_distribution(events)
        )
        
        # Store in database
        db_cluster = IncidentClusterDB(
            cluster_id=cluster.cluster_id,
            created_at=cluster.created_at,
            updated_at=cluster.updated_at,
            primary_signature=signature,
            top_signatures=json.dumps(cluster.top_signatures),
            affected_merchant_ids=json.dumps(cluster.affected_merchant_ids),
            merchant_count=cluster.merchant_count,
            event_count=cluster.event_count,
            trend=trend,
            first_seen=cluster.first_seen,
            last_seen=cluster.last_seen,
            rate_per_hour=current_rate,
            baseline_rate=baseline_rate,
            sample_event_ids=json.dumps([str(eid) for eid in cluster.sample_event_ids]),
            stage_distribution=json.dumps(cluster.stage_distribution),
            component_distribution=json.dumps(cluster.component_distribution)
        )
        
        db.add(db_cluster)
        db.commit()
        
        return cluster
    
    def _get_stage_distribution(self, events: List[CleanEventDB]) -> Dict[int, int]:
        """
        Get distribution of events by migration stage.
        
        Args:
            events: List of CleanEventDB objects
        
        Returns:
            Dictionary mapping stage → count
        """
        distribution = defaultdict(int)
        for event in events:
            distribution[event.migration_stage] += 1
        return dict(sorted(distribution.items()))
    
    def _get_component_distribution(self, events: List[CleanEventDB]) -> Dict[str, int]:
        """
        Get distribution of events by component.
        
        Args:
            events: List of CleanEventDB objects
        
        Returns:
            Dictionary mapping component → count
        """
        distribution = defaultdict(int)
        for event in events:
            distribution[event.component] += 1
        return dict(sorted(distribution.items()))
    
    def get_cluster_stats(self, db: Session) -> dict:
        """
        Get statistics about current clusters.
        
        Args:
            db: SQLAlchemy session
        
        Returns:
            Dictionary with cluster statistics
        """
        total = db.query(IncidentClusterDB).count()
        spiking = db.query(IncidentClusterDB).filter(
            IncidentClusterDB.trend == "spiking"
        ).count()
        stable = db.query(IncidentClusterDB).filter(
            IncidentClusterDB.trend == "stable"
        ).count()
        
        return {
            "total_clusters": total,
            "spiking": spiking,
            "stable": stable,
            "spiking_percent": f"{(spiking / total * 100):.1f}%" if total > 0 else "0%"
        }
