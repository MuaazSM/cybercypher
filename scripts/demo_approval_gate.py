import json
import logging
from datetime import datetime

from db.database import SessionLocal
from db.models import IncidentDB, ActionPlanDB, ActionDB, ApprovalDB
from agents.action_planner import ActionPlannerAgent
from agents.approval_gate import PolicyApprovalAgent
from tools.llm_router import LLMRouter, LLMConfig
from tools.knowledge_base import KnowledgeBase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_approval_gate():
    """Demo policy approval gate with action evaluation."""
    print("\n" + "=" * 80)
    print("POLICY & APPROVAL GATE DEMO (Agent 7)")
    print("=" * 80)
    
    # Initialize components
    print("\n[1] Initializing components...")
    llm_config = LLMConfig()
    
    if not any([llm_config.openai_api_key, llm_config.groq_api_key, llm_config.gemini_api_key]):
        print("✗ ERROR: No LLM API keys found!")
        return
    
    llm = LLMRouter(llm_config)
    kb = KnowledgeBase()
    KnowledgeBase.seed_knowledge_base(kb)
    
    planner = ActionPlannerAgent(llm, kb)
    gate = PolicyApprovalAgent()
    
    print("✓ LLM Router, Knowledge Base, and Policy Gate initialized")
    
    db = SessionLocal()
    
    try:
        # Step 1: Get latest incident and plan actions
        print("\n[2] Retrieving incident and action plan...")
        incident = db.query(IncidentDB).order_by(
            IncidentDB.created_at.desc()
        ).first()
        
        if not incident:
            print("✗ No incidents found. Run demo_triage.py first.")
            return
        
        print(f"✓ Found incident: {incident.title}")
        print(f"   Severity: {incident.severity}")
        
        # Get or create action plan
        plan = db.query(ActionPlanDB).filter(
            ActionPlanDB.incident_id == incident.incident_id
        ).order_by(ActionPlanDB.created_at.desc()).first()
        
        if not plan:
            print("\n   No action plan found, creating one...")
            
            # Get hypotheses and create analysis
            from db.models import IncidentHypothesisDB
            from models.incidents import Incident as IncidentModel
            from models.hypotheses import Hypothesis, RootCauseAnalysis
            
            hypotheses_db = db.query(IncidentHypothesisDB).filter(
                IncidentHypothesisDB.incident_id == incident.incident_id
            ).all()
            
            if not hypotheses_db:
                print("✗ No hypotheses found. Run demo_root_cause.py first.")
                return
            
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
                rag_sources_used=len(hypotheses_db) * 2
            )
            
            plan_result = planner.plan_actions(incident_pydantic, analysis, db)
            plan = db.query(ActionPlanDB).filter(
                ActionPlanDB.plan_id == plan_result.plan_id
            ).first()
            print("   ✓ Action plan created")
        
        # Step 2: Get actions and evaluate through policy gate
        print("\n[3] Evaluating actions through policy gate...")
        actions = db.query(ActionDB).filter(
            ActionDB.plan_id == plan.plan_id
        ).all()
        
        if not actions:
            print("✗ No actions found in plan")
            return
        
        print(f"✓ Found {len(actions)} actions to evaluate")
        
        # Step 3: Evaluate each action
        print("\n[4] Policy Evaluation Results")
        print("-" * 80)
        
        approvals = []
        auto_approved_count = 0
        pending_count = 0
        
        for action in actions:
            approval = gate.evaluate_action(
                action=Action_from_db(action),
                incident_severity=incident.severity,
                incident_impacts_checkout=incident.impacts_checkout,
                db=db
            )
            approvals.append(approval)
            
            status_icon = "✓" if approval.status == "approved" else "⏳"
            print(f"\n   {status_icon} {action.action_type} (Priority {action.priority})")
            print(f"      Risk Level: {action.risk_level}")
            print(f"      Rationale: {action.rationale[:60]}...")
            print(f"      Status: {approval.status}")
            
            if approval.policy_checks:
                triggered_policies = [k for k, v in approval.policy_checks.items() if v]
                if triggered_policies:
                    print(f"      Triggered Policies: {', '.join(triggered_policies)}")
            
            if approval.status == "approved":
                auto_approved_count += 1
            else:
                pending_count += 1
                print(f"      Requires: {approval.required_approver_role}")
        
        # Step 4: Show pending approvals
        print("\n[5] Pending Approvals Summary")
        print("-" * 80)
        
        pending_approvals = gate.get_pending_approvals(db)
        print(f"   Total pending: {len(pending_approvals)}")
        
        if pending_approvals:
            print("\n   Pending Actions:")
            for approval_info in pending_approvals[:5]:  # Show first 5
                print(f"     • {approval_info['action_type']} (Risk: {approval_info['risk_level']})")
                print(f"       Approver needed: {approval_info['required_approver_role']}")
            
            if len(pending_approvals) > 5:
                print(f"     ... and {len(pending_approvals) - 5} more")
        
        # Step 5: Manually approve a pending action (if any)
        if pending_approvals:
            print("\n[6] Manually Approving a Pending Action")
            print("-" * 80)
            
            first_pending = pending_approvals[0]
            approval_id = first_pending['approval_id']
            
            success = gate.approve_action(
                approval_id=approval_id,
                approver="demo_approver@company.com",
                db=db
            )
            
            if success:
                print(f"   ✓ Approved {first_pending['action_type']}")
                print(f"   Approved by: demo_approver@company.com")
                pending_count -= 1
                auto_approved_count += 1
            else:
                print(f"   ✗ Failed to approve action")
        
        # Step 6: Demonstrate rejection
        remaining_pending = gate.get_pending_approvals(db)
        if remaining_pending:
            print("\n[7] Rejecting a Pending Action")
            print("-" * 80)
            
            second_pending = remaining_pending[0]
            approval_id = second_pending['approval_id']
            
            success = gate.reject_action(
                approval_id=approval_id,
                approver="demo_reviewer@company.com",
                reason="Scope change needed - please coordinate with product team first",
                db=db
            )
            
            if success:
                print(f"   ✓ Rejected {second_pending['action_type']}")
                print(f"   Rejected by: demo_reviewer@company.com")
                print(f"   Reason: Scope change needed - please coordinate with product team first")
            else:
                print(f"   ✗ Failed to reject action")
        
        # Step 7: Show statistics
        print("\n[8] Approval Statistics")
        print("-" * 80)
        
        stats = gate.get_approval_stats(db)
        print(f"   • Total approvals: {stats.get('total_approvals', 0)}")
        print(f"   • Approved: {stats.get('approved', 0)}")
        print(f"   • Auto-approved: {stats.get('auto_approved', 0)}")
        print(f"   • Manual approved: {stats.get('manual_approved', 0)}")
        print(f"   • Rejected: {stats.get('rejected', 0)}")
        print(f"   • Pending: {stats.get('pending', 0)}")
        print(f"   • Approval rate: {stats.get('approval_rate', 0)}%")
        
        if stats.get('by_required_role'):
            print(f"   • By approver role:")
            for role, count in stats['by_required_role'].items():
                print(f"     - {role}: {count}")
        
        print("\n" + "=" * 80)
        print("✅ POLICY APPROVAL GATE DEMO COMPLETE")
        print("=" * 80)
        print("\nKey Takeaways:")
        print("  • Actions are evaluated against multiple policy rules")
        print("  • External communications always require approval")
        print("  • High/critical incidents escalate automatically")
        print("  • Low-risk internal actions are auto-approved")
        print("  • Approvers are assigned based on action type and severity")
        print("  • Rejections are tracked with reasoning for audit trail")
        print("  • Human oversight prevents unintended consequences")
        print("\n")
        
    finally:
        db.close()


def Action_from_db(action_db) -> 'Action':      #type: ignore
    """Convert ActionDB to Action Pydantic model."""
    from models.actions import Action
    
    return Action(
        action_id=action_db.action_id,
        action_type=action_db.action_type,
        priority=action_db.priority,
        rationale=action_db.rationale,
        expected_impact=action_db.expected_impact,
        risk_level=action_db.risk_level,
        requires_approval=action_db.requires_approval,
        rollback_plan=action_db.rollback_plan,
        payload=json.loads(action_db.payload)
    )


if __name__ == "__main__":
    demo_approval_gate()
