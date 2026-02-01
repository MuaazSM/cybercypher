from typing import TypedDict, List, Optional
from datetime import datetime
from uuid import UUID

from models.events import RawEvent, CleanEvent
from models.incidents import IncidentCluster, Incident
from models.hypotheses import RootCauseAnalysis
from models.actions import ActionPlan, Approval, ExecutedAction
from models.outcomes import ActionOutcome
from models.anomalies import AnomalySignal


class AgentState(TypedDict):
    """State that flows through the agent graph"""

    # Data pipeline
    raw_events: List[RawEvent]
    clean_events: List[CleanEvent]
    anomaly_signals: List[AnomalySignal]  # Early warnings from Agent 10
    clusters: List[IncidentCluster]
    incidents: List[Incident]
    analyses: List[RootCauseAnalysis]
    action_plans: List[ActionPlan]
    approvals: List[Approval]
    executed_actions: List[ExecutedAction]
    outcomes: List[ActionOutcome]
    merchant_responses: List[dict]  # Agent 11: Merchant communication logs
    support_monitoring: List[dict]  # Agent 11: Support ticket monitoring and resolution tracking
    support_ticket_status: Optional[dict]  # Agent 11: Support ticket monitoring

    # Control flow
    current_stage: str
    current_incident_id: Optional[UUID]
    requires_human_approval: bool
    approval_status: Optional[str]

    # Metadata
    processing_start: datetime
    loop_count: int
    errors: List[str]

    # Configuration
    auto_execute: bool
