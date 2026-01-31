import json
import logging
from datetime import datetime

from db.database import SessionLocal
from db.models import IncidentDB, IncidentHypothesisDB, ActionPlanDB, ActionDB
from agents.action_planner import ActionPlannerAgent
from tools.llm_router import LLMRouter, LLMConfig
from tools.knowledge_base import KnowledgeBase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_action_planning():
    """Demo action planning based on incident and root cause analysis."""
    print("\n" + "=" * 80)
    print("ACTION PLANNER AGENT DEMO (Agent 6)")
    print("=" * 80)
    
    # Initialize components
    print("\n[1] Initializing components...")
    llm_config = LLMConfig()
    
    if not any([llm_config.openai_api_key, llm_config.groq_api_key, llm_config.gemini_api_key]):
        print("✗ ERROR: No LLM API keys found!")
        print("\nAction Planning uses LLM for optional enhancements.")
        print("Set one of these environment variables:")
        print("  - OPENAI_API_KEY (https://platform.openai.com/api-keys)")
        print("  - GROQ_API_KEY (https://console.groq.com/keys)")
        print("  - GEMINI_API_KEY (https://aistudio.google.com/app/apikey)")
        print("\nOr create a .env file with your API key.")
        return
    
    llm = LLMRouter(llm_config)
    
    # Initialize knowledge base
    kb = KnowledgeBase()
    KnowledgeBase.seed_knowledge_base(kb)
    print("✓ LLM Router and Knowledge Base initialized")
    
    # Initialize action planner
    planner = ActionPlannerAgent(llm, kb)
    print("✓ Action Planner initialized")
    
    db = SessionLocal()
    
    try:
        # Step 1: Get latest incident
        print("\n[2] Getting incident to plan actions for...")
        incident = db.query(IncidentDB).order_by(
            IncidentDB.created_at.desc()
        ).first()
        
        if not incident:
            print("✗ No incidents found. Run demo_triage.py first.")
            return
        
        print(f"✓ Found incident: {incident.title}")
        print(f"   Severity: {incident.severity}")
        print(f"   Affected merchants: {len(json.loads(incident.affected_merchants))}")
        print(f"   Blast radius: {incident.blast_radius_estimate}")
        
        # Step 2: Get hypotheses for this incident
        print("\n[3] Retrieving root cause analysis...")
        hypotheses_db = db.query(IncidentHypothesisDB).filter(
            IncidentHypothesisDB.incident_id == incident.incident_id
        ).all()
        
        if not hypotheses_db:
            print("✗ No hypotheses found. Run demo_root_cause.py first.")
            return
        
        print(f"✓ Found {len(hypotheses_db)} hypotheses")
        
        # Convert to Pydantic models
        from models.incidents import Incident as IncidentModel
        from models.hypotheses import Hypothesis, RootCauseAnalysis
        
        incident_pydantic = IncidentModel(
            incident_id=incident.incident_id,
            created_at=incident.created_at,
            updated_at=incident.updated_at,
            status=incident.status,
            severity=incident.severity,
            title=incident.title,
            summary=incident.summary,
            cluster_id=incident.cluster_id,
            affected_merchants=json.loads(incident.affected_merchants),
            blast_radius_estimate=incident.blast_radius_estimate,
            impacts_checkout=incident.impacts_checkout,
            impacts_revenue=incident.impacts_revenue,
            customer_trust_risk=incident.customer_trust_risk
        )
        
        hypotheses = [
            Hypothesis(
                hypothesis_id=h.hypothesis_id,
                type=h.type,
                claim=h.claim,
                confidence=h.confidence,
                evidence=json.loads(h.evidence),
                counterevidence=json.loads(h.counterevidence or "[]"),
                unknowns=json.loads(h.unknowns or "[]"),
                similar_past_incidents=json.loads(h.similar_past_incidents or "[]"),
                relevant_docs=json.loads(h.relevant_docs or "[]")
            )
            for h in hypotheses_db
        ]
        
        analysis = RootCauseAnalysis(
            incident_id=incident.incident_id,
            analysis_timestamp=datetime.utcnow(),
            hypotheses=hypotheses,
            recommended_next_steps=[],
            rag_sources_used=len(hypotheses_db) * 2  # Estimate based on hypotheses
        )
        
        # Step 3: Plan actions
        print("\n[4] Planning actions...")
        plan = planner.plan_actions(incident_pydantic, analysis, db)
        
        print(f"✓ Action plan created with {len(plan.actions)} actions")
        print(f"✓ Total risk score: {plan.total_risk_score}")
        
        # Step 4: Display actions
        print("\n[5] Generated Actions (Prioritized)")
        print("-" * 80)
        
        for action in plan.actions:
            print(f"\n   Action {action.priority}: {action.action_type}")
            print(f"   Rationale: {action.rationale}")
            print(f"   Expected Impact: {action.expected_impact}")
            print(f"   Risk Level: {action.risk_level}")
            print(f"   Requires Approval: {action.requires_approval}")
            
            if action.action_type == "proactive_comms":
                merchants = action.payload.get("merchant_ids", [])
                print(f"   Merchants to Contact: {merchants[:3]}" + 
                      (f"... (+{len(merchants)-3})" if len(merchants) > 3 else ""))
                print(f"   Subject: {action.payload.get('subject', '')}")
            
            elif action.action_type == "docs_update":
                print(f"   Section: {action.payload.get('section', '')}")
                print(f"   Issue: {action.payload.get('issue', '')}")
            
            elif action.action_type == "escalate_eng":
                print(f"   Escalation: {action.payload.get('severity', '')} severity")
            
            elif action.action_type == "support_guidance":
                print(f"   Template: {action.payload.get('template_type', '')}")
        
        # Step 5: Verify storage
        print(f"\n[6] Verifying database storage...")
        stored_plans = db.query(ActionPlanDB).filter(
            ActionPlanDB.incident_id == incident.incident_id
        ).all()
        
        print(f"✓ Stored {len(stored_plans)} action plans in database")
        
        if stored_plans:
            first_plan = stored_plans[-1]  # Most recent
            stored_actions = db.query(ActionDB).filter(
                ActionDB.plan_id == first_plan.plan_id
            ).all()
            print(f"✓ Plan {first_plan.plan_id} contains {len(stored_actions)} actions")
        
        # Step 6: Statistics
        print(f"\n[7] Planning Statistics")
        print("-" * 80)
        
        total_actions = db.query(ActionDB).count()
        total_plans = db.query(ActionPlanDB).count()
        
        action_type_counts = {}
        for action in db.query(ActionDB).all():
            action_type_counts[action.action_type] = action_type_counts.get(action.action_type, 0) + 1
        
        risk_counts = {}
        for action in db.query(ActionDB).all():
            risk_counts[action.risk_level] = risk_counts.get(action.risk_level, 0) + 1
        
        approval_counts = {}
        for action in db.query(ActionDB).all():
            approval_counts["requires_approval" if action.requires_approval else "auto_approved"] = \
                approval_counts.get("requires_approval" if action.requires_approval else "auto_approved", 0) + 1
        
        print(f"   • Total action plans: {total_plans}")
        print(f"   • Total actions: {total_actions}")
        print(f"   • Action type distribution:")
        for action_type, count in sorted(action_type_counts.items()):
            print(f"     - {action_type}: {count}")
        print(f"   • Risk level distribution:")
        for risk_level, count in sorted(risk_counts.items()):
            print(f"     - {risk_level}: {count}")
        print(f"   • Approval requirements:")
        for status, count in approval_counts.items():
            print(f"     - {status}: {count}")
        
        print("\n" + "=" * 80)
        print("✅ ACTION PLANNING DEMO COMPLETE")
        print("=" * 80)
        print("\nNext Steps:")
        print("  • Actions are ranked by priority and risk")
        print("  • External communications require approval")
        print("  • Engineering escalations happen automatically for high/critical severity")
        print("  • Documentation updates prevent future similar incidents")
        print("  • Run demo_approval_gate.py to see policy enforcement")
        print("\n")
        
    finally:
        db.close()


if __name__ == "__main__":
    demo_action_planning()
