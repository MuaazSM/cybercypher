from typing import Optional
from datetime import datetime
import logging

from langgraph.graph import StateGraph, END

from graph.state import AgentState
from db.database import SessionLocal
from models.actions import ConfidenceTier, confidence_to_tier
from models.hypotheses import Hypothesis
from models.incidents import Incident

logger = logging.getLogger(__name__)


class AgenticWorkflow:
    def __init__(self, agents_config: dict):
        """Initialize workflow with all agents"""
        self.agents = agents_config
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Construct the LangGraph workflow"""
        workflow = StateGraph(AgentState)

        # Add nodes (agents)
        workflow.add_node("observe", self._observe_node)
        workflow.add_node("reason", self._reason_node)
        workflow.add_node("decide", self._decide_node)
        workflow.add_node("approve", self._approve_node)
        workflow.add_node("act", self._act_node)
        workflow.add_node("merchant_response", self._merchant_response_node)
        workflow.add_node("learn", self._learn_node)

        # Define edges (flow)
        workflow.set_entry_point("observe")
        workflow.add_edge("observe", "reason")
        workflow.add_edge("reason", "decide")
        workflow.add_edge("decide", "approve")

        # Conditional edge: approval gate
        workflow.add_conditional_edges(
            "approve",
            self._should_execute,
            {
                "execute": "act",
                "wait": END,
                "skip": END
            }
        )

        workflow.add_edge("act", "merchant_response")
        workflow.add_edge("merchant_response", "learn")
        workflow.add_edge("learn", END)

        return workflow.compile()

    def _observe_node(self, state: AgentState) -> AgentState:
        """Observe pipeline: anomaly detection → normalization → pattern detection"""
        print("[Graph] OBSERVE stage")

        db = SessionLocal()
        try:
            # Early anomaly detection (proactive sensing)
            anomaly_report = self.agents["anomaly_detection"].scan_for_anomalies(db, lookback_minutes=120)
            state["anomaly_signals"] = anomaly_report.signals
            
            # Normalization
            self.agents["normalization"].process_raw_events(db, limit=200)

            # Pattern detection
            clusters = self.agents["pattern_detection"].detect_patterns(db)

            state["clusters"] = clusters
            state["current_stage"] = "observe"
        finally:
            db.close()

        return state

    def _reason_node(self, state: AgentState) -> AgentState:
        """Reason pipeline: triage → root cause analysis"""
        print("[Graph] REASON stage")

        incidents = []
        analyses = []

        db = SessionLocal()
        try:
            for cluster in state.get("clusters", []):
                # Triage
                incident = self.agents["triage"].triage_cluster(cluster, db)

                if incident:
                    incidents.append(incident)

                    # Root cause analysis
                    analysis = self.agents["root_cause"].analyze_root_cause(incident, db)
                    analyses.append(analysis)
        finally:
            db.close()

        state["incidents"] = incidents
        state["analyses"] = analyses
        state["current_stage"] = "reason"

        return state

    def _decide_node(self, state: AgentState) -> AgentState:
        """
        Decide pipeline: plan actions with confidence-based graduated response.
        
        Priority 8 Enhancement: Confidence-Based Escalation
        """
        print("[Graph] DECIDE stage")

        action_plans = []

        db = SessionLocal()
        try:
            for incident, analysis in zip(state.get("incidents", []), state.get("analyses", [])):
                # Priority 8: Apply graduated response based on confidence
                top_hypothesis = analysis.hypotheses[0] if analysis.hypotheses else None
                
                if top_hypothesis:
                    confidence_tier = confidence_to_tier(top_hypothesis.confidence)
                    
                    logger.info(
                        f"[Workflow] Confidence {top_hypothesis.confidence:.2f} → {confidence_tier.value} tier"
                    )
                    
                    # Apply graduated response
                    filtered_plan = self.graduated_response_based_on_confidence(
                        incident=incident,
                        analysis=analysis,
                        confidence_tier=confidence_tier,
                        db=db
                    )
                    
                    if filtered_plan:
                        action_plans.append(filtered_plan)
                else:
                    # No hypotheses - default to normal planning
                    plan = self.agents["planner"].plan_actions(incident, analysis, db)
                    action_plans.append(plan)
        finally:
            db.close()

        state["action_plans"] = action_plans
        state["current_stage"] = "decide"

        return state

    def graduated_response_based_on_confidence(
        self,
        incident: Incident,
        analysis,  # RootCauseAnalysis
        confidence_tier: ConfidenceTier,
        db
    ):
        """
        Apply graduated response strategy based on confidence tier.
        
        Priority 8 Enhancement: Risk-Aware Decision-Making
        
        Tiers:
        - WAIT (0.0-0.3): Don't act, gather more data
        - MONITOR (0.3-0.6): Support guidance only, no escalation
        - ACT (0.6-0.8): Normal escalation and communications
        - URGENT (0.8-1.0): Fast-track all actions, auto-approve safe ones
        
        Args:
            incident: The incident requiring actions
            analysis: Root cause analysis with hypotheses
            confidence_tier: Computed confidence tier
            db: Database session
        
        Returns:
            Filtered ActionPlan based on confidence tier, or None if WAIT
        """
        logger.info(
            f"[Workflow] Applying {confidence_tier.value} tier response for incident {incident.incident_id}"
        )
        
        # Generate baseline action plan
        plan = self.agents["planner"].plan_actions(incident, analysis, db)
        
        if confidence_tier == ConfidenceTier.WAIT:
            # WAIT: Don't act, gather more evidence
            logger.warning(
                f"[Workflow] Confidence too low ({analysis.hypotheses[0].confidence:.2f}) → "
                "WAIT tier → Gathering more evidence, no actions"
            )
            
            # Return empty plan with special status
            plan.actions = []
            plan.execution_strategy = "gathering_more_evidence"
            
            return plan
        
        elif confidence_tier == ConfidenceTier.MONITOR:
            # MONITOR: Support guidance only, no external actions
            logger.info(
                f"[Workflow] Confidence moderate ({analysis.hypotheses[0].confidence:.2f}) → "
                "MONITOR tier → Support guidance only, skipping escalation"
            )
            
            # Filter to only support_guidance
            plan.actions = [
                action for action in plan.actions
                if action.action_type == "support_guidance"
            ]
            
            # Add confidence tier to payload
            for action in plan.actions:
                action.payload["confidence_tier"] = confidence_tier.value
                action.payload["reason"] = "Confidence in MONITOR range - low-risk action only"
            
            logger.info(
                f"[Workflow] MONITOR tier: {len(plan.actions)} support guidance actions retained"
            )
            
            return plan
        
        elif confidence_tier == ConfidenceTier.ACT:
            # ACT: Normal action plan
            logger.info(
                f"[Workflow] Confidence good ({analysis.hypotheses[0].confidence:.2f}) → "
                "ACT tier → Normal escalation and communications"
            )
            
            # Add confidence tier to all actions
            for action in plan.actions:
                action.payload["confidence_tier"] = confidence_tier.value
            
            return plan
        
        else:  # ConfidenceTier.URGENT
            # URGENT: Fast-track, high priority, auto-approve safe actions
            logger.warning(
                f"[Workflow] Confidence very high ({analysis.hypotheses[0].confidence:.2f}) → "
                "URGENT tier → Fast-tracking all actions"
            )
            
            # Boost all action priorities
            for idx, action in enumerate(plan.actions):
                action.priority = min(action.priority, 2)  # Top 2 priorities
                action.payload["confidence_tier"] = confidence_tier.value
                action.payload["fast_track"] = True
                action.payload["reason"] = "High confidence - urgent response required"
                
                # Auto-approve low-risk actions in URGENT tier
                if action.risk_level == "low" and incident.severity in ["high", "critical"]:
                    action.requires_approval = False
                    action.payload["auto_approved_reason"] = "URGENT tier + high severity + low risk"
                    logger.info(
                        f"[Workflow] URGENT tier: Auto-approving low-risk {action.action_type}"
                    )
            
            return plan

    def _approve_node(self, state: AgentState) -> AgentState:
        """Approval gate: check policies"""
        print("[Graph] APPROVE stage")

        approvals = []
        requires_human = False

        db = SessionLocal()
        try:
            for plan in state.get("action_plans", []):
                for action in plan.actions:
                    # Get incident severity
                    incident = next(
                        (i for i in state.get("incidents", []) if i.incident_id == plan.incident_id),
                        None
                    )
                    severity = incident.severity if incident else "medium"

                    approval = self.agents["approval_gate"].evaluate_action(
                        action, severity, db
                    )
                    approvals.append(approval)

                    if approval.status == "pending":
                        requires_human = True
        finally:
            db.close()

        state["approvals"] = approvals
        state["requires_human_approval"] = requires_human
        state["current_stage"] = "approve"

        return state

    def _should_execute(self, state: AgentState) -> str:
        """Decide if we can execute or need to wait for approval"""
        if state.get("auto_execute", False):
            return "execute"

        if state.get("requires_human_approval", False):
            pending = [a for a in state.get("approvals", []) if a.status == "pending"]
            if pending:
                print(f"[Graph] Waiting for {len(pending)} approvals")
                return "wait"

        rejected = [a for a in state.get("approvals", []) if a.status == "rejected"]
        if rejected and not any(a.status == "approved" for a in state.get("approvals", [])):
            print("[Graph] All actions rejected")
            return "skip"

        return "execute"

    def _act_node(self, state: AgentState) -> AgentState:
        """Act pipeline: execute approved actions"""
        print("[Graph] ACT stage")

        executed = []

        db = SessionLocal()
        try:
            for plan in state.get("action_plans", []):
                for action in plan.actions:
                    approval = next(
                        (a for a in state.get("approvals", []) if a.action_id == action.action_id),
                        None
                    )

                    if approval and approval.status == "approved":
                        try:
                            result = self.agents["executor"].execute_action(action, db)
                            executed.append(result)
                        except Exception as e:
                            print(f"[Graph] Execution failed: {e}")
                            state.setdefault("errors", []).append(str(e))
        finally:
            db.close()

        state["executed_actions"] = executed
        state["current_stage"] = "act"

        return state

    def _merchant_response_node(self, state: AgentState) -> AgentState:
        """
        Merchant Response pipeline: Agent 11
        - Classify issue as technical vs non-technical
        - Send responses to affected merchants
        - Monitor support tickets for resolution
        """
        print("[Graph] MERCHANT RESPONSE stage")

        merchant_responses = []
        support_monitoring = []

        db = SessionLocal()
        try:
            for incident in state.get("incidents", []):
                try:
                    # Classify incident
                    classification = self.agents["merchant_response"].classify_issue_type(incident, db)
                    
                    # If non-technical, generate and send response
                    if classification.get("requires_merchant_response"):
                        response = self.agents["merchant_response"].generate_merchant_response(
                            incident, classification, db
                        )
                        
                        if response:
                            # Send to merchants
                            send_result = self.agents["merchant_response"].send_merchant_responses(
                                [response], incident, db
                            )
                            response["send_result"] = send_result
                            merchant_responses.append(response)
                            
                            logger.info(
                                f"[Workflow] Sent merchant responses for {incident.incident_id}: "
                                f"{send_result['responses_sent']} sent, {send_result['responses_failed']} failed"
                            )
                    
                    # Monitor support tickets
                    monitoring = self.agents["merchant_response"].monitor_support_tickets(incident, db)
                    support_monitoring.append(monitoring)
                    
                    # If tickets resolved, close them
                    if monitoring.get("resolved_tickets"):
                        resolution_summary = f"Incident {incident.incident_id} resolved. " \
                                           f"Avg resolution time: {monitoring['avg_resolution_time']:.1f}h. " \
                                           f"Satisfaction: {monitoring['customer_satisfaction_score']:.1f}/5"
                        
                        close_result = self.agents["merchant_response"].close_support_tickets(
                            incident, resolution_summary, db
                        )
                        monitoring["close_result"] = close_result
                        logger.info(
                            f"[Workflow] Closed {close_result['tickets_closed']} support tickets for {incident.incident_id}"
                        )
                        
                except Exception as e:
                    logger.error(f"[Workflow] Merchant response error for incident: {e}")
                    state.setdefault("errors", []).append(f"Merchant response error: {e}")
        finally:
            db.close()

        state["merchant_responses"] = merchant_responses
        state["support_monitoring"] = support_monitoring
        state["current_stage"] = "merchant_response"

        return state

    def _learn_node(self, state: AgentState) -> AgentState:
        """Learn pipeline: measure outcomes"""
        print("[Graph] LEARN stage")

        outcomes = []

        db = SessionLocal()
        try:
            for executed_action in state.get("executed_actions", []):
                try:
                    outcome = self.agents["feedback"].measure_outcome(
                        executed_action, db, measurement_delay_minutes=30
                    )
                    outcomes.append(outcome)
                except Exception as e:
                    print(f"[Graph] Outcome measurement failed: {e}")
                    state.setdefault("errors", []).append(str(e))
        finally:
            db.close()

        state["outcomes"] = outcomes
        state["current_stage"] = "learn"
        state["loop_count"] = state.get("loop_count", 0) + 1

        return state

    def run(self, initial_state: Optional[AgentState] = None) -> AgentState:
        """Execute the workflow"""
        if initial_state is None:
            initial_state = AgentState(
                raw_events=[],
                clean_events=[],
                clusters=[],
                incidents=[],
                analyses=[],
                action_plans=[],
                approvals=[],
                executed_actions=[],
                merchant_responses=[],
                support_monitoring=[],
                outcomes=[],
                current_stage="observe",
                current_incident_id=None,
                requires_human_approval=False,
                approval_status=None,
                processing_start=datetime.utcnow(),
                loop_count=0,
                errors=[],
                auto_execute=False
            )

        final_state = self.graph.invoke(initial_state)
        return final_state
