from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID, uuid4


class ActionOutcome(BaseModel):
    """
    Outcome measurement for an executed action.
    """

    outcome_id: UUID = Field(default_factory=uuid4, description="Unique outcome ID")
    execution_id: UUID = Field(description="Executed action ID")
    measured_at: datetime = Field(default_factory=datetime.utcnow, description="When outcome was measured")
    outcome: Literal["helped", "neutral", "harmed"] = Field(description="Impact of the action")
    ticket_volume_before: int = Field(description="Ticket volume before action")
    ticket_volume_after: int = Field(description="Ticket volume after action")
    incident_resolved: bool = Field(description="Whether incident is resolved")
    merchant_feedback: Optional[str] = Field(default=None, description="Merchant feedback summary")
    confidence_score: float = Field(description="Confidence score for outcome")
    should_update_patterns: bool = Field(description="Whether to update known patterns")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "outcome_id": "d50e8400-e29b-41d4-a716-446655440034",
                "execution_id": "c50e8400-e29b-41d4-a716-446655440033",
                "measured_at": "2026-01-31T11:00:00Z",
                "outcome": "helped",
                "ticket_volume_before": 120,
                "ticket_volume_after": 40,
                "incident_resolved": False,
                "merchant_feedback": "Merchants report webhook delivery restored",
                "confidence_score": 0.75,
                "should_update_patterns": True
            }
        }
    )
