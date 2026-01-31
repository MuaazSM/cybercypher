from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional
from datetime import datetime
from uuid import UUID, uuid4


class InterventionImpactModel(BaseModel):
    """
    Predicted impact of an intervention/action before execution.
    
    Shows causal thinking - what will happen if we execute this action?
    Uses historical data to predict:
    - Direct impact (likelihood incident resolves)
    - Side effects (unintended consequences)
    - Spillover (impact on other merchant segments)
    - Temporal dynamics (how long until effect visible)
    """
    
    model_id: UUID = Field(default_factory=uuid4, description="Unique model ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Action being modeled
    action_id: UUID = Field(description="Action being modeled")
    action_type: str = Field(description="Type of action (escalate_eng, support_guidance, etc)")
    incident_id: UUID = Field(description="Incident this action addresses")
    
    # Success prediction
    expected_success_probability: float = Field(
        ge=0.0, le=1.0,
        description="Likelihood this action will help resolve incident (0.0-1.0)"
    )
    
    # Confidence in prediction
    confidence_in_prediction: float = Field(
        ge=0.0, le=1.0,
        description="How confident is this prediction (based on sample size)"
    )
    
    # Temporal impact
    expected_resolution_time_minutes: Optional[int] = Field(
        default=None,
        description="Estimated minutes until incident resolved after action"
    )
    
    # Risk assessment
    side_effects: List[str] = Field(
        default_factory=list,
        description="Potential unintended consequences of this action"
    )
    
    spillover_risks: List[str] = Field(
        default_factory=list,
        description="Could this action affect other merchant segments?"
    )
    
    # Monitoring
    monitoring_metrics: List[str] = Field(
        default_factory=list,
        description="Metrics to watch after action execution"
    )
    
    # Alternatives
    alternative_actions: List[str] = Field(
        default_factory=list,
        description="Alternative actions if this one has low success rate"
    )
    
    # Evidence
    sample_size: int = Field(
        description="Number of historical similar actions used for prediction"
    )
    
    historical_success_rate: float = Field(
        ge=0.0, le=1.0,
        description="Historical success rate for this action type"
    )
    
    # Reasoning
    reasoning: str = Field(
        description="Explanation of how prediction was calculated"
    )
    
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "example": {
                "action_id": "550e8400-e29b-41d4-a716-446655440010",
                "action_type": "escalate_eng",
                "expected_success_probability": 0.85,
                "confidence_in_prediction": 0.78,
                "expected_resolution_time_minutes": 240,
                "side_effects": [
                    "Engineering team will be pulled from other work",
                    "May take 4 hours to investigate"
                ],
                "spillover_risks": [
                    "If root cause is platform-wide, fix will help all merchants",
                    "If only affects Stage 2, other stages unaffected"
                ],
                "monitoring_metrics": ["event_rate", "ticket_volume", "merchant_feedback"],
                "sample_size": 15,
                "historical_success_rate": 0.87,
                "reasoning": "Similar webhook escalation actions succeeded 13/15 times. Median resolution: 4 hours."
            }
        }
    )
