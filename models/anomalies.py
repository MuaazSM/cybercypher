from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Literal, Optional
from datetime import datetime
from uuid import UUID, uuid4


class AnomalySignal(BaseModel):
    """Early-warning signal for emerging anomalies"""
    
    signal_id: UUID = Field(default_factory=uuid4, description="Unique signal identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When anomaly detected")
    
    # Anomaly classification
    anomaly_type: Literal["rate", "velocity", "stage_concentration"] = Field(
        description="Type of anomaly detected"
    )
    
    # Affected signature
    signature: str = Field(description="Event signature showing anomaly")
    
    # Confidence and severity
    confidence: float = Field(
        ge=0.3, le=0.7,
        description="Confidence score (0.3-0.7 for early warnings)"
    )
    
    # Quantitative evidence
    current_value: float = Field(description="Current metric value")
    baseline_value: float = Field(description="Normal baseline value")
    deviation_factor: float = Field(description="Ratio of current to baseline")
    
    # Statistical details
    z_score: Optional[float] = Field(default=None, description="Z-score for rate anomalies")
    velocity: Optional[float] = Field(default=None, description="Rate of change (events/hour^2)")
    stage_concentration: Optional[Dict[int, float]] = Field(
        default=None,
        description="Percentage of anomalies per stage"
    )
    
    # Context
    event_count: int = Field(description="Number of events in this anomaly")
    merchant_count: int = Field(description="Number of affected merchants")
    time_window_minutes: int = Field(description="How many minutes back we're looking")
    
    # Severity assessment
    severity_estimate: Literal["low", "medium", "high"] = Field(
        description="Estimated severity if this becomes incident"
    )
    
    # Recommendation
    recommended_action: str = Field(
        description="What to monitor or consider doing"
    )
    
    # Reference
    sample_event_ids: List[UUID] = Field(
        default_factory=list,
        description="Representative event IDs from anomaly"
    )
    
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "example": {
                "signal_id": "550e8400-e29b-41d4-a716-446655440010",
                "created_at": "2026-02-01T10:30:00Z",
                "anomaly_type": "velocity",
                "signature": "WEBHOOK::DELIVERY_FAIL::orders/create::STAGE2",
                "confidence": 0.65,
                "current_value": 12.5,
                "baseline_value": 2.1,
                "deviation_factor": 5.95,
                "z_score": None,
                "velocity": 0.8,  # events/hour/hour
                "event_count": 25,
                "merchant_count": 8,
                "time_window_minutes": 30,
                "severity_estimate": "medium",
                "recommended_action": "Monitor closely; if continues 30 more minutes, escalate to incident detection",
                "sample_event_ids": ["uuid1", "uuid2", "uuid3"]
            }
        }
    )


class AnomalyReport(BaseModel):
    """Report of all anomalies detected in a scan"""
    
    report_id: UUID = Field(default_factory=uuid4)
    scan_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Detected signals
    signals: List[AnomalySignal] = Field(description="List of anomaly signals found")
    
    # Summary statistics
    total_signatures_scanned: int = Field(description="How many unique signatures analyzed")
    signatures_with_anomalies: int = Field(description="How many showed anomalies")
    
    # Risk assessment
    max_confidence: float = Field(description="Highest confidence anomaly found")
    high_severity_count: int = Field(description="Count of high-severity anomalies")
    
    # Recommendations
    escalation_recommended: bool = Field(
        description="Should operator review these signals?"
    )
    
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "example": {
                "signals": [
                    {
                        "anomaly_type": "velocity",
                        "signature": "WEBHOOK::DELIVERY_FAIL::orders/create::STAGE2",
                        "confidence": 0.65
                    }
                ],
                "total_signatures_scanned": 24,
                "signatures_with_anomalies": 3,
                "max_confidence": 0.68,
                "high_severity_count": 1,
                "escalation_recommended": True
            }
        }
    )
