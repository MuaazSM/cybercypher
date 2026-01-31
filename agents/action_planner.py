from typing import List, Optional
from sqlalchemy.orm import Session
from models.incidents import Incident
from models.hypotheses import Hypothesis, RootCauseAnalysis
from models.actions import Action, ActionPlan
from db.models import (
    IncidentDB, IncidentHypothesisDB, ActionPlanDB, ActionDB
)
from tools.llm_router import LLMRouter
from tools.knowledge_base import KnowledgeBase
from uuid import uuid4
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class ActionPlannerAgent:
    """
    Action Planner Agent (Agent 6 in DECIDE pipeline).
    
    Generates prioritized action plans based on:
    - Incident characteristics (severity, blast radius, affected systems)
    - Root cause hypothesis (type, confidence, evidence)
    - Risk assessment and historical patterns
    
    Supports 5 action types:
    - support_guidance: Internal templates for support team
    - proactive_comms: Preemptive merchant communication
    - escalate_eng: Create engineering issue for investigation
    - mitigation: Temporary workaround or fix
    - docs_update: Documentation improvements
    """
    
    def __init__(self, llm_router: LLMRouter, knowledge_base: Optional[KnowledgeBase] = None):
        """
        Initialize action planner.
        
        Args:
            llm_router: LLMRouter for optional LLM-assisted planning
            knowledge_base: KnowledgeBase for retrieving successful past actions (optional)
        """
        self.llm = llm_router
        self.kb = knowledge_base
        
        logger.info("[ActionPlannerAgent] Initialized with LLM router and knowledge base")
    
    def plan_actions(
        self,
        incident: Incident,
        analysis: RootCauseAnalysis,
        db: Session
    ) -> ActionPlan:
        """
        Generate prioritized action plan based on incident and root cause analysis.
        
        Args:
            incident: The incident to plan actions for
            analysis: Root cause analysis with hypotheses
            db: Database session for storage
        
        Returns:
            ActionPlan with prioritized, risk-assessed actions
        """
        logger.info(f"[ActionPlannerAgent] Planning actions for: {incident.title}")
        
        # Get top hypothesis
        top_hypothesis = analysis.hypotheses[0] if analysis.hypotheses else None
        
        if not top_hypothesis:
            logger.warning("[ActionPlannerAgent] No hypotheses to plan from, creating minimal plan")
            return self._create_minimal_plan(incident, db)
        
        # Retrieve successful past actions (optional RAG enhancement)
        past_successful_actions = self._retrieve_successful_actions(incident, top_hypothesis)
        
        # Generate actions based on hypothesis and incident
        actions = self._generate_actions(
            incident=incident,
            hypothesis=top_hypothesis,
            past_actions=past_successful_actions
        )
        
        # Calculate total risk score
        total_risk = self._calculate_total_risk(actions, incident)
        
        # Parse blast radius estimate (may be string like "17 merchants")
        blast_radius = incident.blast_radius_estimate
        if isinstance(blast_radius, str):
            import re
            match = re.search(r'\d+', blast_radius)
            blast_radius = int(match.group(0)) if match else 0
        else:
            blast_radius = int(blast_radius)
        
        # Create action plan
        plan = ActionPlan(
            plan_id=uuid4(),
            incident_id=incident.incident_id,
            created_at=datetime.utcnow(),
            actions=actions,
            hypothesis_id=top_hypothesis.hypothesis_id,
            total_risk_score=total_risk,
            estimated_blast_radius=blast_radius
        )
        
        # Store in database
        self._store_action_plan(plan, db)
        
        logger.info(f"[ActionPlannerAgent] Created plan with {len(actions)} actions, total risk: {total_risk}")
        return plan
    
    def _retrieve_successful_actions(
        self,
        incident: Incident,
        hypothesis: Hypothesis
    ) -> List[dict]:
        """
        Retrieve past successful actions for similar incidents via RAG.
        
        Args:
            incident: Current incident
            hypothesis: Top hypothesis
        
        Returns:
            List of past action examples
        """
        if not self.kb:
            return []
        
        try:
            # Search knowledge base for successful actions
            query = f"{hypothesis.type} action resolved {incident.title}"
            results = self.kb.search(
                query=query,
                k=3
            )
            
            past_actions = []
            for doc in results:
                if hasattr(doc, 'metadata') and doc.metadata.get('type') == 'action':
                    past_actions.append({
                        "content": doc.page_content if hasattr(doc, 'page_content') else str(doc),
                        "action_type": doc.metadata.get("action_type"),
                        "outcome": doc.metadata.get("outcome")
                    })
            
            logger.info(f"[ActionPlannerAgent] Retrieved {len(past_actions)} successful past actions")
            return past_actions
        
        except Exception as e:
            logger.debug(f"[ActionPlannerAgent] Failed to retrieve past actions: {e}")
            return []
    
    def _generate_actions(
        self,
        incident: Incident,
        hypothesis: Hypothesis,
        past_actions: List[dict]
    ) -> List[Action]:
        """
        Generate prioritized list of actions based on hypothesis and incident.
        
        Action generation rules:
        - High/critical severity → Auto escalate to engineering
        - migration_misstep + 5+ merchants → Proactive communications
        - docs_gap hypothesis → Suggest documentation update
        - medium severity → Support guidance template
        - high risk → Require approval
        
        Args:
            incident: The incident
            hypothesis: Top hypothesis
            past_actions: Reference to successful past actions
        
        Returns:
            List of prioritized Action objects
        """
        actions = []
        merchant_count = len(incident.affected_merchants)
        
        # Rule 1: High/critical severity → Escalate to engineering
        if incident.severity in ["high", "critical"]:
            actions.append(Action(
                action_id=uuid4(),
                action_type="escalate_eng",
                priority=1,
                rationale=f"{incident.severity.upper()} severity incident affecting {merchant_count} merchants",
                expected_impact="Engineering investigation and fix",
                risk_level="medium",
                requires_approval=False,  # Auto-approve for high severity
                rollback_plan="Close GitHub issue if false positive",
                payload={
                    "incident_id": str(incident.incident_id),
                    "severity": incident.severity,
                    "title": incident.title,
                    "hypothesis": hypothesis.claim,
                    "evidence": hypothesis.evidence[:3],  # Top 3 evidence points
                    "affected_merchant_count": merchant_count,
                    "blast_radius": incident.blast_radius_estimate,
                    "impacts_checkout": incident.impacts_checkout,
                    "impacts_revenue": incident.impacts_revenue
                }
            ))
        
        # Rule 2: Migration misstep + 5+ merchants → Proactive comms
        if (hypothesis.type == "migration_misstep" and merchant_count >= 5):
            actions.append(Action(
                action_id=uuid4(),
                action_type="proactive_comms",
                priority=2,
                rationale=f"Proactive merchant guidance prevents {merchant_count} support tickets",
                expected_impact=f"Reduce support load by ~{merchant_count} tickets, improve merchant satisfaction",
                risk_level="medium",
                requires_approval=True,  # External comms require approval
                rollback_plan="Send follow-up correction email if guidance was incorrect",
                payload={
                    "merchant_ids": incident.affected_merchants,
                    "subject": f"Action Required: {incident.title}",
                    "hypothesis_type": hypothesis.type,
                    "root_cause": hypothesis.claim,
                    "recommended_steps": self._generate_merchant_guidance(hypothesis),
                    "escalation_path": "Contact support@company.com for assistance",
                    "urgency": "high" if incident.impacts_checkout else "medium"
                }
            ))
        
        # Rule 3: Docs gap → Suggest documentation update
        if (hypothesis.type == "docs_gap" or 
            (hypothesis.confidence > 0.6 and "documentation" in hypothesis.claim.lower())):
            actions.append(Action(
                action_id=uuid4(),
                action_type="docs_update",
                priority=3,
                rationale="Documentation improvement prevents future similar incidents",
                expected_impact="Reduce future incidents on this topic by improving clarity",
                risk_level="low",
                requires_approval=True,  # Doc changes need review
                rollback_plan="Revert documentation to previous version",
                payload={
                    "section": self._infer_doc_section(hypothesis),
                    "issue": hypothesis.claim,
                    "suggested_improvement": self._generate_doc_suggestion(hypothesis),
                    "priority": "high" if merchant_count > 10 else "medium",
                    "related_evidence": hypothesis.evidence[:2]
                }
            ))
        
        # Rule 4: Medium severity → Support guidance
        if incident.severity == "medium":
            actions.append(Action(
                action_id=uuid4(),
                action_type="support_guidance",
                priority=4,
                rationale="Provide support team with response template",
                expected_impact="Faster, consistent responses to merchant inquiries",
                risk_level="low",
                requires_approval=False,  # Internal guidance, no approval needed
                rollback_plan="N/A (internal guidance only)",
                payload={
                    "template_type": "merchant_response",
                    "root_cause": hypothesis.claim,
                    "confidence": hypothesis.confidence,
                    "suggested_steps": self._generate_support_steps(hypothesis),
                    "escalation_criteria": "If merchant still sees errors after following steps, escalate to engineering",
                    "evidence_summary": " | ".join(hypothesis.evidence[:3])
                }
            ))
        
        # Rule 5: High risk mitigation if applicable
        if incident.impacts_checkout or incident.impacts_revenue:
            # Check if we have suggested mitigations from past actions
            mitigation_found = False
            for past_action in past_actions:
                if past_action.get("action_type") == "mitigation":
                    actions.append(Action(
                        action_id=uuid4(),
                        action_type="mitigation",
                        priority=2 if incident.severity == "critical" else 3,
                        rationale="Temporary workaround to minimize revenue impact",
                        expected_impact="Reduce customer impact while permanent fix is developed",
                        risk_level="high",
                        requires_approval=True,  # High-risk actions need approval
                        rollback_plan="Disable workaround and revert to original behavior",
                        payload={
                            "description": past_action.get("content", "Implement temporary workaround"),
                            "estimated_time_to_deploy": "15-30 minutes",
                            "monitoring_needed": True,
                            "metrics_to_track": ["webhook_delivery_rate", "error_count", "merchant_tickets"],
                            "rollback_trigger": "If workaround causes new failures"
                        }
                    ))
                    mitigation_found = True
                    break
        
        # Sort by priority
        actions.sort(key=lambda a: a.priority)
        
        logger.info(f"[ActionPlannerAgent] Generated {len(actions)} actions for hypothesis: {hypothesis.type}")
        return actions
    
    def _generate_merchant_guidance(self, hypothesis: Hypothesis) -> List[str]:
        """
        Generate actionable guidance steps for merchants.
        
        Args:
            hypothesis: The root cause hypothesis
        
        Returns:
            List of recommended steps for merchants
        """
        if "webhook" in hypothesis.claim.lower():
            return [
                "1. Go to your admin panel → API settings",
                "2. Locate 'Webhook Configuration' section",
                "3. Verify webhook endpoint URL is correct and publicly accessible",
                "4. Confirm event types are subscribed (especially order.created)",
                "5. Test webhook delivery using 'Send Test Event' button",
                "6. Contact support if webhook test fails"
            ]
        
        if "auth" in hypothesis.claim.lower() or "token" in hypothesis.claim.lower():
            return [
                "1. Go to Account Settings → API Keys",
                "2. Regenerate your API key (old key will be deprecated in 24h)",
                "3. Update your integration code with the new key",
                "4. Redeploy your application",
                "5. Monitor error logs for auth failures",
                "6. Contact support if issues persist"
            ]
        
        if "migration" in hypothesis.claim.lower():
            return [
                "1. Review the Stage-specific migration checklist in your dashboard",
                "2. Verify all prerequisites are completed for your current stage",
                "3. Run through the configuration steps in order",
                "4. Test each component before proceeding to next step",
                "5. Contact our migration support for assistance"
            ]
        
        if "config" in hypothesis.claim.lower():
            return [
                "1. Review your current configuration in the admin panel",
                "2. Check the setup guide for your integration type",
                "3. Verify all required fields are populated",
                "4. Test the integration with a sample transaction",
                "5. Contact support if configuration issues persist"
            ]
        
        return [
            "Our team is investigating this issue.",
            "We'll provide an update within 2 hours.",
            "Please contact support@company.com if you need immediate assistance."
        ]
    
    def _generate_doc_suggestion(self, hypothesis: Hypothesis) -> str:
        """
        Suggest specific documentation improvements.
        
        Args:
            hypothesis: The root cause hypothesis
        
        Returns:
            Suggested documentation improvement
        """
        return (
            f"Add explicit troubleshooting section addressing: {hypothesis.claim[:80]}. "
            f"Include step-by-step verification checklist and common errors."
        )
    
    def _generate_support_steps(self, hypothesis: Hypothesis) -> List[str]:
        """
        Generate support response steps for the team.
        
        Args:
            hypothesis: The root cause hypothesis
        
        Returns:
            List of support response steps
        """
        return [
            "1. Acknowledge the issue and thank merchant for reporting",
            f"2. Explain likely cause: {hypothesis.claim}",
            "3. Provide step-by-step resolution instructions based on cause",
            "4. Offer to verify if merchant has questions about any step",
            "5. Follow up after 2 hours if issue is not resolved"
        ]
    
    def _infer_doc_section(self, hypothesis: Hypothesis) -> str:
        """
        Infer which documentation section needs update.
        
        Args:
            hypothesis: The root cause hypothesis
        
        Returns:
            Documentation section name
        """
        claim_lower = hypothesis.claim.lower()
        
        if "stage 1" in claim_lower or "stage1" in claim_lower:
            return "Migration Stage 1 Guide"
        if "stage 2" in claim_lower or "stage2" in claim_lower:
            return "Migration Stage 2 Guide"
        if "stage 3" in claim_lower or "stage3" in claim_lower:
            return "Migration Stage 3 Guide"
        if "webhook" in claim_lower:
            return "Webhook Configuration Guide"
        if "api" in claim_lower or "auth" in claim_lower:
            return "API Authentication Guide"
        if "checkout" in claim_lower:
            return "Checkout Integration Guide"
        
        return "General Migration Guide"
    
    def _calculate_total_risk(self, actions: List[Action], incident: Incident) -> float:
        """
        Calculate aggregate risk score for all actions.
        
        Risk calculation:
        - Base: Sum of individual action risk levels (low=1, medium=3, high=5)
        - Multiplier 1.5x if affects checkout
        - Multiplier 1.3x if affects revenue
        - Multiplier 1.2x if affects more than 20 merchants
        
        Args:
            actions: List of actions in the plan
            incident: The incident (for severity context)
        
        Returns:
            Calculated risk score (0-100 scale)
        """
        risk_weights = {"low": 1.0, "medium": 3.0, "high": 5.0}
        total = sum(risk_weights.get(action.risk_level, 1.0) for action in actions)
        
        # Amplify risk if affects critical systems
        if incident.impacts_checkout:
            total *= 1.5
            logger.debug("[ActionPlannerAgent] Amplified risk due to checkout impact")
        
        if incident.impacts_revenue:
            total *= 1.3
            logger.debug("[ActionPlannerAgent] Amplified risk due to revenue impact")
        
        # Extract numeric blast radius from string like "17 merchants"
        blast_radius = incident.blast_radius_estimate
        if isinstance(blast_radius, str):
            import re
            match = re.search(r'\d+', blast_radius)
            blast_radius = int(match.group(0)) if match else 0
        else:
            blast_radius = int(blast_radius)
        
        if blast_radius > 20:
            total *= 1.2
            logger.debug("[ActionPlannerAgent] Amplified risk due to large blast radius")
        
        # Cap at 100
        total = min(100.0, total)
        
        return round(total, 2)
    
    def _create_minimal_plan(self, incident: Incident, db: Session) -> ActionPlan:
        """
        Create a minimal fallback plan when analysis is incomplete.
        
        Args:
            incident: The incident
            db: Database session
        
        Returns:
            Minimal ActionPlan with only engineering escalation
        """
        action = Action(
            action_id=uuid4(),
            action_type="escalate_eng",
            priority=1,
            rationale="No clear hypothesis; escalating for immediate engineering investigation",
            expected_impact="Engineering team investigates root cause",
            risk_level="low",
            requires_approval=False,
            rollback_plan="Close GitHub issue if resolved or false positive",
            payload={
                "incident_id": str(incident.incident_id),
                "title": incident.title,
                "severity": incident.severity,
                "affected_merchants": len(incident.affected_merchants),
                "reason": "Analysis inconclusive; requires engineering expertise"
            }
        )
        
        plan = ActionPlan(
            plan_id=uuid4(),
            incident_id=incident.incident_id,
            created_at=datetime.utcnow(),
            actions=[action],
            hypothesis_id=None,
            total_risk_score=1.0,
            estimated_blast_radius=incident.blast_radius_estimate
        )
        
        self._store_action_plan(plan, db)
        return plan
    
    def _store_action_plan(self, plan: ActionPlan, db: Session):
        """
        Store action plan and associated actions in database.
        
        Args:
            plan: ActionPlan to store
            db: Database session
        """
        try:
            # Store plan
            db_plan = ActionPlanDB(
                plan_id=plan.plan_id,
                incident_id=plan.incident_id,
                hypothesis_id=plan.hypothesis_id,
                created_at=plan.created_at,
                total_risk_score=plan.total_risk_score,
                estimated_blast_radius=str(plan.estimated_blast_radius)
            )
            db.add(db_plan)
            db.flush()  # Flush to insert plan before adding foreign key dependent actions
            
            # Store individual actions
            for action in plan.actions:
                db_action = ActionDB(
                    action_id=action.action_id,
                    plan_id=plan.plan_id,
                    action_type=action.action_type,
                    priority=action.priority,
                    rationale=action.rationale,
                    expected_impact=action.expected_impact,
                    risk_level=action.risk_level,
                    requires_approval=action.requires_approval,
                    rollback_plan=action.rollback_plan,
                    payload=json.dumps(action.payload),
                    status="planned"
                )
                db.add(db_action)
            
            db.commit()
            
            logger.info(
                f"[ActionPlannerAgent] Stored action plan {plan.plan_id} "
                f"with {len(plan.actions)} actions for incident {plan.incident_id}"
            )
        
        except Exception as e:
            logger.error(f"[ActionPlannerAgent] Error storing action plan: {e}")
            db.rollback()
            raise
