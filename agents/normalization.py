from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from models.events import RawEvent, CleanEvent
from db.models import RawEventDB, CleanEventDB, MerchantProfileDB
import re
import logging

logger = logging.getLogger(__name__)


class NormalizationAgent:
    """
    Normalizes raw events into clean structured events.
    
    Responsibilities:
    - Extract structured fields from flexible payloads
    - Generate unique signatures for grouping similar events
    - Enrich with merchant context from database
    - Calculate severity hints for triage
    - Create human-readable summaries for LLM processing
    """
    
    def __init__(self):
        """Initialize with component keyword mappings."""
        self.component_mapping = {
            "webhook": ["webhook", "webhooks", "hook"],
            "api": ["api", "endpoint", "rest", "http"],
            "checkout": ["checkout", "payment", "cart", "transaction"],
            "auth": ["auth", "authentication", "token", "bearer", "oauth"],
            "orders": ["order", "orders", "purchase"],
            "inventory": ["inventory", "stock", "product", "catalog"]
        }
    
    def normalize_event(self, raw_event: RawEvent, db: Session) -> CleanEvent:
        """
        Transform raw event into clean structured event.
        
        Extracts component, error code, severity, and merchant context.
        Generates signature for pattern grouping.
        
        Args:
            raw_event: RawEvent model to normalize
            db: SQLAlchemy session for merchant lookup
        
        Returns:
            CleanEvent with structured fields and enrichment
        """
        # Extract structured fields
        component = self._extract_component(raw_event)
        error_code = self._extract_error_code(raw_event)
        severity_hint = self._calculate_severity(raw_event, component, error_code)
        
        # Get merchant context for enrichment
        merchant_profile = db.query(MerchantProfileDB).filter(
            MerchantProfileDB.merchant_id == raw_event.merchant_id
        ).first()
        
        migration_stage = merchant_profile.migration_stage if merchant_profile else 0
        merchant_industry = merchant_profile.industry if merchant_profile else None
        merchant_framework = merchant_profile.storefront_framework if merchant_profile else None
        merchant_region = merchant_profile.region if merchant_profile else None
        
        # Generate signature for pattern grouping
        signature = self._generate_signature(
            component=component,
            error_code=error_code,
            payload=raw_event.payload,
            stage=migration_stage
        )
        
        # Create human-readable summary for RAG/LLM
        raw_text_summary = self._create_summary(raw_event, component, error_code)
        
        # Create clean event
        clean_event = CleanEvent(
            event_id=raw_event.event_id,
            signature=signature,
            merchant_id=raw_event.merchant_id,
            timestamp=raw_event.timestamp,
            component=component,
            error_code=error_code,
            severity_hint=severity_hint,
            migration_stage=migration_stage,
            merchant_industry=merchant_industry,
            merchant_framework=merchant_framework,
            merchant_region=merchant_region,
            raw_text_summary=raw_text_summary,
            raw_event_id=raw_event.event_id
        )
        
        return clean_event
    
    def _extract_component(self, event: RawEvent) -> str:
        """
        Determine which system component is affected.
        
        Uses event type and payload inspection to classify into:
        webhook, api, checkout, auth, orders, inventory
        
        Args:
            event: RawEvent to inspect
        
        Returns:
            Component identifier (lowercase)
        """
        event_type = event.event_type.lower()
        payload = event.payload
        
        # Direct mapping from event type
        if "webhook" in event_type:
            return "webhook"
        if "api" in event_type:
            return "api"
        if "checkout" in event_type:
            return "checkout"
        
        # Infer from payload fields
        if "webhook_name" in payload:
            return "webhook"
        if "endpoint" in payload:
            return "api"
        if "cart_value" in payload or "payment" in str(payload).lower():
            return "checkout"
        if "token" in str(payload).lower() or "oauth" in str(payload).lower():
            return "auth"
        if "order" in str(payload).lower():
            return "orders"
        if "inventory" in str(payload).lower() or "stock" in str(payload).lower():
            return "inventory"
        
        # Keyword matching on full payload
        payload_str = str(payload).lower()
        for component, keywords in self.component_mapping.items():
            if any(kw in payload_str for kw in keywords):
                return component
        
        # Fallback: if no component detected, default to 'api' (most generic)
        logger.debug(f"Could not detect component for event {event.event_id}, defaulting to 'api'")
        return "api"
    
    def _extract_error_code(self, event: RawEvent) -> Optional[str]:
        """
        Extract error code from payload.
        
        Looks for error_code field, status codes, error messages, etc.
        
        Args:
            event: RawEvent to extract from
        
        Returns:
            Standardized error code or None
        """
        payload = event.payload
        
        # Try direct error_code field
        if "error_code" in payload:
            return payload["error_code"]
        
        # Try status_code (for API errors)
        if "status_code" in payload:
            return f"HTTP_{payload['status_code']}"
        
        # Try error message parsing
        if "error" in payload:
            error_msg = str(payload["error"]).upper()
            if "TIMEOUT" in error_msg:
                return "TIMEOUT"
            if "AUTH" in error_msg or "401" in error_msg or "UNAUTHORIZED" in error_msg:
                return "AUTH_FAIL"
            if "PERMISSION" in error_msg or "403" in error_msg or "FORBIDDEN" in error_msg:
                return "PERMISSION_DENIED"
            if "500" in error_msg or "INTERNAL" in error_msg:
                return "SERVER_ERROR"
            if "502" in error_msg or "BAD_GATEWAY" in error_msg:
                return "BAD_GATEWAY"
            if "503" in error_msg or "UNAVAILABLE" in error_msg:
                return "SERVICE_UNAVAILABLE"
        
        return "UNKNOWN"
    
    def _calculate_severity(
        self,
        event: RawEvent,
        component: str,
        error_code: Optional[str]
    ) -> str:
        """
        Determine severity hint based on event characteristics.
        
        High: Checkout, auth failures, critical keywords
        Medium: Server errors, order-related webhooks
        Low: Other webhooks, generic API errors
        
        Args:
            event: RawEvent to assess
            component: Extracted component
            error_code: Extracted error code
        
        Returns:
            Severity level: "low", "medium", or "high"
        """
        # Checkout and payment always high severity
        if component == "checkout":
            return "high"
        
        # Auth failures are high severity
        if error_code and ("AUTH" in error_code or "PERMISSION" in error_code):
            return "high"
        
        # 5xx errors are medium severity
        if error_code and ("500" in error_code or "SERVER" in error_code or "GATEWAY" in error_code):
            return "medium"
        
        # Webhook failures: medium for orders, low for others
        if component == "webhook":
            webhook_name = event.payload.get("webhook_name", "").lower()
            if "order" in webhook_name:
                return "medium"
            return "low"
        
        # Support tickets: check for urgent keywords
        if event.event_type == "ticket":
            subject = str(event.payload.get("subject", "")).lower()
            urgent_keywords = ["urgent", "critical", "down", "broken", "broken", "severe", "emergency"]
            if any(word in subject for word in urgent_keywords):
                return "high"
            priority = event.payload.get("priority", "").lower()
            if priority == "high":
                return "medium"
        
        return "low"
    
    def _generate_signature(
        self,
        component: str,
        error_code: Optional[str],
        payload: dict,
        stage: int
    ) -> str:
        """
        Generate unique signature for grouping similar events.
        
        Format: COMPONENT::ERROR_CODE::SPECIFIC_DETAIL::STAGE
        
        Examples:
        - WEBHOOK::DELIVERY_FAIL::orders/create::STAGE2
        - API::401::TOKEN_INVALID::STAGE3
        - CHECKOUT::PAYMENT_DECLINED::GENERAL::STAGE2
        
        Args:
            component: System component
            error_code: Error code extracted
            payload: Event payload dict
            stage: Migration stage (1-4)
        
        Returns:
            Signature string
        """
        parts = [component.upper()]
        
        # Add error code
        parts.append(error_code or "UNKNOWN")
        
        # Add specific detail based on component
        if component == "webhook" and "webhook_name" in payload:
            # Use webhook name directly (e.g., orders/create, inventory/update)
            parts.append(payload["webhook_name"])
        
        elif component == "api" and "endpoint" in payload:
            # Normalize endpoint to remove IDs
            endpoint = payload["endpoint"]
            normalized = self._normalize_endpoint(endpoint)
            parts.append(normalized)
        
        else:
            # Generic detail for other components
            parts.append("GENERAL")
        
        # Add stage
        parts.append(f"STAGE{stage}")
        
        return "::".join(parts)
    
    def _normalize_endpoint(self, endpoint: str) -> str:
        """
        Remove ID patterns from API endpoints for grouping.
        
        Converts:
        - /api/v1/orders/123 → /api/v1/orders/{id}
        - /api/v1/products/uuid-1234-5678 → /api/v1/products/{uuid}
        
        Args:
            endpoint: API endpoint path
        
        Returns:
            Normalized endpoint with placeholders for IDs
        """
        # Replace numeric IDs with {id}
        normalized = re.sub(r'/\d+', '/{id}', endpoint)
        
        # Replace UUID patterns with {uuid}
        uuid_pattern = r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        normalized = re.sub(uuid_pattern, '/{uuid}', normalized, flags=re.IGNORECASE)
        
        return normalized
    
    def _create_summary(
        self,
        event: RawEvent,
        component: str,
        error_code: Optional[str]
    ) -> str:
        """
        Create human-readable summary for RAG/LLM processing.
        
        Args:
            event: RawEvent to summarize
            component: Extracted component
            error_code: Extracted error code
        
        Returns:
            Summary string for LLM input
        """
        merchant = event.merchant_id
        
        # Support tickets: use subject directly
        if event.event_type == "ticket":
            subject = event.payload.get("subject", "Unknown issue")
            description = event.payload.get("description", "")
            if description:
                return f"Support ticket: {subject} - {description[:100]}"
            return f"Support ticket: {subject}"
        
        # Webhook failures
        if component == "webhook":
            webhook_name = event.payload.get("webhook_name", "unknown webhook")
            return f"Webhook {webhook_name} failing for merchant {merchant} with error {error_code}"
        
        # API errors
        if component == "api":
            endpoint = event.payload.get("endpoint", "unknown endpoint")
            response_time = event.payload.get("response_time_ms")
            if response_time:
                return f"API error on {endpoint} for {merchant}: {error_code} (response time: {response_time}ms)"
            return f"API error on {endpoint} for {merchant}: {error_code}"
        
        # Checkout failures
        if component == "checkout":
            cart_value = event.payload.get("cart_value")
            if cart_value:
                return f"Checkout failure for {merchant} (cart value: ${cart_value}): {error_code}"
            return f"Checkout failure for {merchant}: {error_code}"
        
        # Auth failures
        if component == "auth":
            return f"Authentication failure for {merchant}: {error_code}"
        
        # Default
        return f"{component} issue for {merchant}: {error_code}"
    
    def process_raw_events(self, db: Session, limit: int = 100) -> int:
        """
        Process unprocessed raw events into clean events.
        
        Finds raw events that haven't been normalized yet and creates
        CleanEvent entries with all enrichment.
        
        Args:
            db: SQLAlchemy session
            limit: Max events to process in one batch
        
        Returns:
            Count of events successfully normalized
        """
        # Find raw events that haven't been normalized yet
        # (raw events without corresponding clean events)
        raw_events = db.query(RawEventDB).outerjoin(
            CleanEventDB,
            RawEventDB.event_id == CleanEventDB.raw_event_id
        ).filter(
            CleanEventDB.event_id == None
        ).limit(limit).all()
        
        if not raw_events:
            logger.info("[NormalizationAgent] No unprocessed events found")
            return 0
        
        processed = 0
        failed = 0
        
        logger.info(f"[NormalizationAgent] Processing {len(raw_events)} raw events")
        
        for raw_db_event in raw_events:
            try:
                # Convert DB model to Pydantic
                raw_event = RawEvent(
                    event_id=raw_db_event.event_id,
                    event_type=raw_db_event.event_type,
                    merchant_id=raw_db_event.merchant_id,
                    timestamp=raw_db_event.timestamp,
                    payload=raw_db_event.payload,
                    source=raw_db_event.source,
                    idempotency_key=raw_db_event.idempotency_key
                )
                
                # Normalize
                clean_event = self.normalize_event(raw_event, db)
                
                # Store in database
                db_clean = CleanEventDB(**clean_event.model_dump())
                db.add(db_clean)
                processed += 1
                
            except Exception as e:
                logger.error(
                    f"[NormalizationAgent] Failed to normalize event {raw_db_event.event_id}: {str(e)}"
                )
                failed += 1
                continue
        
        # Commit all at once
        try:
            db.commit()
            logger.info(
                f"[NormalizationAgent] Successfully normalized {processed} events "
                f"({failed} failed)"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[NormalizationAgent] Commit failed: {str(e)}")
            return 0
        
        return processed
    
    def get_normalization_stats(self, db: Session) -> dict:
        """
        Get statistics about normalization progress.
        
        Args:
            db: SQLAlchemy session
        
        Returns:
            Dictionary with processing stats
        """
        raw_count = db.query(RawEventDB).count()
        clean_count = db.query(CleanEventDB).count()
        unprocessed = db.query(RawEventDB).outerjoin(
            CleanEventDB,
            RawEventDB.event_id == CleanEventDB.raw_event_id
        ).filter(
            CleanEventDB.event_id == None
        ).count()
        
        return {
            "raw_events": raw_count,
            "clean_events": clean_count,
            "unprocessed": unprocessed,
            "normalization_rate": f"{(clean_count / raw_count * 100):.1f}%" if raw_count > 0 else "0%"
        }
