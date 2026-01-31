from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Literal
from datetime import datetime
from uuid import UUID, uuid4


class IncidentCluster(BaseModel):
    """
    Group of related events indicating a potential incident (Agent 3: Pattern Detection).
    
    Created by clustering events with similar signatures and detecting spikes.
    Represents a pattern across multiple merchants or a concentrated spike
    that warrants investigation.
    """
    
    cluster_id: UUID = Field(default_factory=uuid4, description="Unique cluster identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When cluster was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    # Cluster identity
    top_signatures: List[str] = Field(description="Most common signatures in cluster")
    primary_signature: str = Field(description="The dominant signature")
    
    # Affected scope
    affected_merchant_ids: List[str] = Field(description="List of affected merchant IDs")
    merchant_count: int = Field(description="Count of unique merchants affected")
    event_count: int = Field(description="Total events in cluster")
    
    # Pattern characteristics
    trend: str = Field(description="Trend status: spiking, stable, or declining")
    first_seen: datetime = Field(description="Earliest event in cluster")
    last_seen: datetime = Field(description="Most recent event in cluster")
    rate_per_hour: float = Field(description="Current rate of events per hour")
    baseline_rate: float = Field(description="Normal baseline rate for comparison")
    
    # Supporting evidence
    sample_event_ids: List[UUID] = Field(description="Representative event IDs from cluster")
    stage_distribution: Dict[int, int] = Field(description="Events by migration stage")
    component_distribution: Dict[str, int] = Field(description="Events by component")
    
    model_config = ConfigDict(
        frozen=True,  # Immutable after creation
        json_schema_extra={
            "example": {
                "cluster_id": "550e8400-e29b-41d4-a716-446655440010",
                "created_at": "2026-01-31T10:30:00Z",
                "updated_at": "2026-01-31T11:00:00Z",
                "top_signatures": [
                    "WEBHOOK::DELIVERY_FAIL::orders/create::STAGE2",
                    "WEBHOOK::DELIVERY_FAIL::orders/update::STAGE2"
                ],
                "primary_signature": "WEBHOOK::DELIVERY_FAIL::orders/create::STAGE2",
                "affected_merchant_ids": ["m_1001", "m_1021", "m_1045"],
                "merchant_count": 17,
                "event_count": 53,
                "trend": "spiking",
                "first_seen": "2026-01-31T10:30:00Z",
                "last_seen": "2026-01-31T11:00:00Z",
                "rate_per_hour": 15.3,
                "baseline_rate": 2.1,
                "sample_event_ids": ["550e8400-e29b-41d4-a716-446655440000"],
                "stage_distribution": {1: 2, 2: 48, 3: 3},
                "component_distribution": {"webhook": 53}
            }
        }
    )

class Incident(BaseModel):
    """
    Confirmed incident from a cluster (Agent 4: Incident Triage).
    
    Represents a validated incident that requires investigation and remediation.
    Includes severity, business impact assessment, and blast radius estimate.
    """
    
    incident_id: UUID = Field(default_factory=uuid4, description="Unique incident identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When incident was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    # Incident status
    status: Literal["open", "investigating", "resolved", "wontfix"] = Field(
        default="open", 
        description="Current status of incident"
    )
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="Severity level based on impact and rate"
    )
    
    # Description
    title: str = Field(description="Human-readable incident title")
    summary: str = Field(description="Short description of the incident")
    
    # Context
    cluster_id: UUID = Field(description="Source cluster ID")
    affected_merchants: List[str] = Field(description="List of affected merchant IDs")
    blast_radius_estimate: str = Field(description="Estimated blast radius (e.g., '17 merchants')")
    
    # Business impact
    impacts_checkout: bool = Field(description="Does this incident affect checkout flow?")
    impacts_revenue: bool = Field(description="Does this incident affect revenue?")
    customer_trust_risk: Literal["low", "medium", "high"] = Field(
        description="Risk to customer trust and platform reputation"
    )
    
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "example": {
                "incident_id": "650e8400-e29b-41d4-a716-446655440020",
                "created_at": "2026-01-31T10:35:00Z",
                "updated_at": "2026-01-31T10:35:00Z",
                "status": "open",
                "severity": "high",
                "title": "Webhook delivery failures in Stage 2 migration",
                "summary": "17 Stage 2 merchants experiencing webhook delivery failures. Rate is 7.3x baseline, affecting order notifications.",
                "cluster_id": "550e8400-e29b-41d4-a716-446655440010",
                "affected_merchants": ["m_1001", "m_1021", "m_1045"],
                "blast_radius_estimate": "17 merchants",
                "impacts_checkout": False,
                "impacts_revenue": True,
                "customer_trust_risk": "medium"
            }
        }
    )