"""
Pydantic models for events in the Agentic Self-Healing Support System.

These models define the data contracts for events as they flow through
the Observe pipeline (Agents 1-3).
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4


class RawEvent(BaseModel):
    """
    Unprocessed event from external sources (Agent 1: Ingestion).
    
    Raw events are ingested from:
    - Zendesk tickets
    - API error logs
    - Webhook delivery failures
    - Checkout monitoring systems
    
    The payload structure is flexible and depends on the event_type.
    Idempotency keys prevent duplicate processing.
    """
    
    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    event_type: Literal["ticket", "api_error", "webhook_fail", "checkout_fail"] = Field(
        description="Source type of the event"
    )
    merchant_id: str = Field(
        description="Affected merchant identifier"
    )
    timestamp: datetime = Field(
        description="When the event occurred"
    )
    payload: Dict[str, Any] = Field(
        description="Flexible payload structure depending on event_type"
    )
    source: str = Field(
        description="System that generated the event (zendesk, api_logs, webhook_service, checkout_monitor)"
    )
    idempotency_key: str = Field(
        description="Unique key for deduplication across retries"
    )
    
    model_config = ConfigDict(
        frozen=True,  # Immutable after creation
        json_schema_extra={
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "event_type": "webhook_fail",
                "merchant_id": "m_1021",
                "timestamp": "2026-01-31T10:30:00Z",
                "payload": {
                    "webhook_name": "orders/create",
                    "error_code": "DELIVERY_FAIL",
                    "retry_count": 3
                },
                "source": "webhook_service",
                "idempotency_key": "webhook_m_1021_20260131103000"
            }
        }
    )


class CleanEvent(BaseModel):
    """
    Normalized, enriched event with structured metadata (Agent 2: Normalization).
    
    Clean events are the output of the normalization pipeline. They contain:
    - Structured fields extracted from raw payloads
    - Event signatures for pattern detection
    - Merchant context (industry, framework, region, migration stage)
    - Severity hints for triage
    
    These are input to the pattern detection agent (Agent 3).
    """
    
    event_id: UUID = Field(
        description="Original event identifier"
    )
    signature: str = Field(
        description="Event signature pattern (e.g., WEBHOOK::DELIVERY_FAIL::orders/create::STAGE2)"
    )
    merchant_id: str = Field(
        description="Affected merchant identifier"
    )
    timestamp: datetime = Field(
        description="When the event occurred"
    )
    
    # Extracted structured fields
    component: Literal["checkout", "api", "webhook", "auth", "orders", "inventory"] = Field(
        description="Which system component is affected"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Structured error code if available"
    )
    severity_hint: Literal["low", "medium", "high"] = Field(
        description="Initial severity assessment from raw event"
    )
    
    # Enriched context
    migration_stage: int = Field(
        ge=1, le=4,
        description="Merchant migration stage (1, 2, 3, or 4)"
    )
    merchant_industry: Optional[str] = Field(
        default=None,
        description="Industry vertical (fashion, electronics, food, etc.)"
    )
    merchant_framework: Optional[str] = Field(
        default=None,
        description="Storefront framework (shopify, custom, react, etc.)"
    )
    merchant_region: Optional[str] = Field(
        default=None,
        description="Geographic region (US-WEST, EU-CENTRAL, APAC, etc.)"
    )
    
    # Text summary for RAG/LLM
    raw_text_summary: str = Field(
        description="Human-readable summary of the issue for LLM processing"
    )
    
    # Reference to original
    raw_event_id: UUID = Field(
        description="Reference back to original raw event"
    )
    
    model_config = ConfigDict(
        frozen=True,  # Immutable after creation
        json_schema_extra={
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440001",
                "signature": "WEBHOOK::DELIVERY_FAIL::orders/create::STAGE2",
                "merchant_id": "m_1021",
                "timestamp": "2026-01-31T10:30:00Z",
                "component": "webhook",
                "error_code": "DELIVERY_FAIL",
                "severity_hint": "high",
                "migration_stage": 2,
                "merchant_industry": "electronics",
                "merchant_framework": "custom",
                "merchant_region": "US-EAST",
                "raw_text_summary": "Orders webhook failing after headless cutover. Affects 17 Stage 2 merchants.",
                "raw_event_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }
    )
