from pydantic import BaseModel, Field, ConfigDict
from typing import List, Literal, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4


class Action(BaseModel):
    """
    A proposed action to address an incident.
    
    Represents one recommended step based on:
    - Hypothesis type and confidence
    - Incident severity and blast radius
    - Risk assessment and historical patterns
    """
    
    action_id: UUID = Field(default_factory=uuid4, description="Unique action ID")
    action_type: Literal[
        "support_guidance", 
        "proactive_comms", 
        "escalate_eng", 
        "mitigation", 
        "docs_update"
    ] = Field(description="Category of action")
    priority: int = Field(description="Priority ranking (1=highest)")
    rationale: str = Field(description="Why this action is recommended")
    expected_impact: str = Field(description="What the action should accomplish")
    risk_level: Literal["low", "medium", "high"] = Field(description="Risk level of this action")
    requires_approval: bool = Field(description="Whether human approval is required before execution")
    rollback_plan: str = Field(description="How to undo this action if it causes problems")
    payload: Dict[str, Any] = Field(description="Action-specific parameters and data")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action_id": "850e8400-e29b-41d4-a716-446655440031",
                "action_type": "proactive_comms",
                "priority": 1,
                "rationale": "Medium severity incident affecting 17 merchants - proactive guidance prevents support tickets",
                "expected_impact": "Reduce support tickets from 17 merchants by providing clear resolution steps",
                "risk_level": "medium",
                "requires_approval": True,
                "rollback_plan": "Send follow-up correction if guidance was incorrect",
                "payload": {
                    "merchant_ids": ["m_1001", "m_1002", "m_1003"],
                    "subject": "Action Required: Webhook Delivery Issue",
                    "recommended_action": "Please verify webhook registration in admin panel"
                }
            }
        }
    )


class ActionPlan(BaseModel):
    """
    Collection of actions planned for an incident.
    
    Represents the full response strategy including:
    - Prioritized action list
    - Risk assessment
    - Blast radius impact
    """
    
    plan_id: UUID = Field(default_factory=uuid4, description="Unique plan ID")
    incident_id: UUID = Field(description="Associated incident")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When plan was created")
    actions: List[Action] = Field(description="List of prioritized actions")
    hypothesis_id: Optional[UUID] = Field(default=None, description="Top hypothesis this plan is based on")
    total_risk_score: float = Field(description="Aggregate risk score of all actions")
    estimated_blast_radius: int = Field(description="Expected number of affected merchants")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "plan_id": "950e8400-e29b-41d4-a716-446655440032",
                "incident_id": "750e8400-e29b-41d4-a716-446655440030",
                "created_at": "2026-01-31T10:30:00Z",
                "actions": [],
                "hypothesis_id": "850e8400-e29b-41d4-a716-446655440031",
                "total_risk_score": 3.5,
                "estimated_blast_radius": 17
            }
        }
    )


class Approval(BaseModel):
    """
    Approval record for an action requiring human review.
    
    Tracks policy enforcement and approval workflow:
    - Which policies triggered approval requirement
    - Who approved/rejected and when
    - Why rejection occurred if applicable
    """
    
    approval_id: UUID = Field(default_factory=uuid4, description="Unique approval record ID")
    action_id: UUID = Field(description="Associated action")
    status: Literal["approved", "pending", "rejected"] = Field(description="Current approval status")
    requested_at: datetime = Field(description="When approval was requested")
    approved_by: Optional[str] = Field(default=None, description="Who approved (system_auto or user email)")
    approved_at: Optional[datetime] = Field(default=None, description="When approval occurred")
    rejection_reason: Optional[str] = Field(default=None, description="Reason for rejection if status=rejected")
    policy_checks: Dict[str, bool] = Field(description="Results of policy evaluations")
    required_approver_role: str = Field(description="Role that should approve (support_manager, engineering_lead, etc)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "approval_id": "a50e8400-e29b-41d4-a716-446655440033",
                "action_id": "850e8400-e29b-41d4-a716-446655440031",
                "status": "pending",
                "requested_at": "2026-01-31T10:30:00Z",
                "approved_by": None,
                "approved_at": None,
                "rejection_reason": None,
                "policy_checks": {
                    "external_communication": True,
                    "checkout_impact": False
                },
                "required_approver_role": "support_manager"
            }
        }
    )
