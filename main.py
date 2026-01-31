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
from agents.pattern_detection import PatternDetectionAgent
from agents.triage import IncidentTriageAgent
from agents.root_cause import RootCauseAnalystAgent
from agents.action_planner import ActionPlannerAgent
from agents.approval_gate import PolicyApprovalAgent
from agents.execution import ExecutionAgent
from agents.feedback import FeedbackLearningAgent
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
def approve_action(approval_id: str, approver: str, db: Session = Depends(get_db)):
    """Manually approve an action"""
    from uuid import UUID

    success = agents_config["approval_gate"].approve_action(
        UUID(approval_id), approver, db
    )
    if not success:
        raise HTTPException(status_code=404, detail="Approval not found or already processed")
    return {"status": "approved"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
