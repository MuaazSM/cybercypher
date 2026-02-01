from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv
from db.database import get_db
from graph.workflow import AgenticWorkflow
from tools.llm_router import LLMRouter, LLMConfig
from tools.knowledge_base import KnowledgeBase
from tools.slack_client import SlackClient
from tools.github_client import GitHubClient
from agents.ingestion import SignalIngestionAgent
from agents.normalization import NormalizationAgent
from agents.anomaly_detector import AnomalyDetectionAgent
from agents.pattern_detection import PatternDetectionAgent
from agents.triage import IncidentTriageAgent
from agents.root_cause import RootCauseAnalystAgent
from agents.action_planner import ActionPlannerAgent
from agents.approval_gate import PolicyApprovalAgent
from agents.execution import ExecutionAgent
from agents.feedback import FeedbackLearningAgent
from models.actions import Action
from models.incidents import Incident
from uuid import uuid4, UUID
from typing import List, Dict, Any
import logging
import uvicorn

load_dotenv()

# Initialize app
app = FastAPI(title="Agentic Support System")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize tools
llm_config = LLMConfig(
    openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    groq_api_key=os.getenv("GROQ_API_KEY", ""),
    gemini_api_key=os.getenv("GEMINI_API_KEY", "")
)
llm = LLMRouter(llm_config)

kb = KnowledgeBase(persist_directory=Path("data/knowledge_base"))
slack = SlackClient(webhook_url=os.getenv("SLACK_WEBHOOK_URL", ""))
github = GitHubClient(
    token=os.getenv("GITHUB_TOKEN", ""),
    repo_owner=os.getenv("GITHUB_REPO_OWNER", ""),
    repo_name=os.getenv("GITHUB_REPO_NAME", "")
)

# Initialize agents
agents_config = {
    "ingestion": SignalIngestionAgent(),
    "normalization": NormalizationAgent(),
    "anomaly_detection": AnomalyDetectionAgent(),
    "pattern_detection": PatternDetectionAgent(kb),
    "triage": IncidentTriageAgent(llm),
    "root_cause": RootCauseAnalystAgent(llm, kb),
    "planner": ActionPlannerAgent(llm, kb),
    "approval_gate": PolicyApprovalAgent(),
    "executor": ExecutionAgent(slack, github, llm),
    "feedback": FeedbackLearningAgent(kb)
}

# Initialize workflow
workflow = AgenticWorkflow(agents_config)
logger = logging.getLogger(__name__)


@app.get("/")
def root():
    return {"status": "ok", "service": "Agentic Support System"}


@app.post("/workflow/run")
def run_workflow(auto_execute: bool = False):
    """Trigger full workflow execution"""
    from graph.state import AgentState

    initial_state = AgentState(
        raw_events=[],
        clean_events=[],
        anomaly_signals=[],
        clusters=[],
        incidents=[],
        analyses=[],
        action_plans=[],
        approvals=[],
        executed_actions=[],
        outcomes=[],
        current_stage="observe",
        current_incident_id=None,
        requires_human_approval=False,
        approval_status=None,
        processing_start=datetime.utcnow(),
        loop_count=0,
        errors=[],
        auto_execute=auto_execute
    )

    final_state = workflow.run(initial_state)

    return {
        "status": "completed",
        "stage": final_state["current_stage"],
        "incidents_detected": len(final_state["incidents"]),
        "actions_executed": len(final_state["executed_actions"]),
        "requires_approval": final_state["requires_human_approval"]
    }


@app.get("/incidents")
def list_incidents(db: Session = Depends(get_db)):
    """List all incidents"""
    from db.models import IncidentDB

    incidents = db.query(IncidentDB).all()
    return {"count": len(incidents), "incidents": incidents}


@app.get("/approvals/pending")
def pending_approvals(db: Session = Depends(get_db)):
    """Get pending approvals"""
    from db.models import ApprovalDB

    pending = db.query(ApprovalDB).filter(ApprovalDB.status == "pending").all()
    return {"count": len(pending), "approvals": pending}


@app.post("/approvals/{approval_id}/approve")
def approve_action(approval_id: str, db: Session = Depends(get_db), approver: str = "dashboard-user"):
    """Manually approve an action"""
    from uuid import UUID

    success = agents_config["approval_gate"].approve_action(
        UUID(approval_id), approver, db
    )
    if not success:
        raise HTTPException(status_code=404, detail="Approval not found or already processed")
    return {"status": "approved"}


from pydantic import BaseModel


class SimulationRequest(BaseModel):
    """Simulation request body"""
    action: Action


@app.post("/incidents/{incident_id}/simulate-action")
def simulate_action(incident_id: str, request: SimulationRequest, db: Session = Depends(get_db)):
    """
    Simulate an action without executing it.
    Returns impact predictions, scenario outcomes, and comparisons to alternatives.
    """
    from db.models import IncidentDB, ActionSimulationDB

    # Fetch incident
    try:
        incident_uuid = UUID(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid incident_id") from exc

    incident_db = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_uuid).first()
    if not incident_db:
        raise HTTPException(status_code=404, detail="Incident not found")

    if not incident_db.cluster_id:
        raise HTTPException(status_code=400, detail="Incident missing cluster_id, cannot simulate")

    incident = Incident(
        incident_id=incident_db.incident_id,
        status=incident_db.status,
        severity=incident_db.severity,
        title=incident_db.title,
        summary=incident_db.summary,
        cluster_id=incident_db.cluster_id,
        affected_merchants=incident_db.affected_merchants,
        blast_radius_estimate=incident_db.blast_radius_estimate,
        impacts_checkout=incident_db.impacts_checkout,
        impacts_revenue=incident_db.impacts_revenue,
        customer_trust_risk=incident_db.customer_trust_risk
    )

    planner = agents_config["planner"]
    action = request.action

    logger.info(
        f"[Simulation] Running simulation for incident {incident.incident_id} "
        f"and action {action.action_type}"
    )

    # Base impact model
    impact_model = planner.model_intervention_impact(action, incident, db)

    # Monte Carlo-style scenario generation (percentile approximations)
    base_success = impact_model.expected_success_probability
    base_time = impact_model.expected_resolution_time_minutes or 120

    predicted_outcomes = {
        "best_case": {
            "success": min(0.95, base_success + 0.15),
            "resolution_time": max(30, int(base_time * 0.5))
        },
        "expected_case": {
            "success": round(base_success, 2),
            "resolution_time": int(base_time)
        },
        "worst_case": {
            "success": max(0.10, base_success - 0.25),
            "resolution_time": int(base_time * 1.8)
        }
    }

    # Scenario branching
    alternative_outcomes = [
        "If action succeeds → incident resolves, tickets decrease",
        "If action fails → incident continues, need alternative",
        "If action partially works → follow-up action required"
    ]

    # Compare to alternative actions
    alternative_action_types = planner._suggest_alternatives(action.action_type)
    candidate_types = [action.action_type] + [a for a in alternative_action_types if a != action.action_type]

    comparisons: List[Dict[str, Any]] = []
    for candidate_type in candidate_types:
        candidate_action = Action(
            action_id=uuid4(),
            action_type=candidate_type,
            priority=action.priority,
            rationale=f"Simulation candidate: {candidate_type}",
            expected_impact=action.expected_impact,
            risk_level=action.risk_level,
            requires_approval=action.requires_approval,
            rollback_plan=action.rollback_plan,
            payload=action.payload
        )
        candidate_model = planner.model_intervention_impact(candidate_action, incident, db)
        resolution_time = candidate_model.expected_resolution_time_minutes or 120
        score = candidate_model.expected_success_probability * (1 / max(resolution_time, 1))
        comparisons.append({
            "action_type": candidate_type,
            "success": round(candidate_model.expected_success_probability, 2),
            "resolution_time": int(resolution_time),
            "score": round(score, 6)
        })

    ranked = sorted(comparisons, key=lambda x: x["score"], reverse=True)

    response = {
        "simulation_id": str(uuid4()),
        "action": action.model_dump(),
        "predicted_outcomes": predicted_outcomes,
        "confidence_in_prediction": round(impact_model.confidence_in_prediction, 2),
        "side_effects": impact_model.side_effects,
        "alternative_outcomes": alternative_outcomes,
        "comparison_to_alternatives": [
            f"{r['action_type']}: {int(r['success']*100)}% success, {r['resolution_time']}m resolution"
            for r in ranked
        ]
    }

    # Persist simulation
    simulation_id = uuid4()
    db.add(ActionSimulationDB(
        simulation_id=simulation_id,
        incident_id=incident.incident_id,
        action_id=action.action_id,
        action_type=action.action_type,
        action_payload=action.payload,
        predicted_outcomes=predicted_outcomes,
        confidence_in_prediction=impact_model.confidence_in_prediction,
        side_effects=impact_model.side_effects,
        alternative_outcomes=alternative_outcomes,
        comparison_to_alternatives=comparisons,
        ranked_alternatives=ranked
    ))
    db.commit()

    response["simulation_id"] = str(simulation_id)
    logger.info(f"[Simulation] Stored simulation {simulation_id}")
    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
