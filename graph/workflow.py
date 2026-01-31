from typing import Optional
from datetime import datetime

from langgraph.graph import StateGraph, END

from graph.state import AgentState
from db.database import SessionLocal


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

        workflow.add_edge("act", "learn")
        workflow.add_edge("learn", END)

        return workflow.compile()

    def _observe_node(self, state: AgentState) -> AgentState:
        """Observe pipeline: ingest → normalize → detect patterns"""
        print("[Graph] OBSERVE stage")

        db = SessionLocal()
        try:
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
        """Decide pipeline: plan actions"""
        print("[Graph] DECIDE stage")

        action_plans = []

        db = SessionLocal()
        try:
            for incident, analysis in zip(state.get("incidents", []), state.get("analyses", [])):
                plan = self.agents["planner"].plan_actions(incident, analysis, db)
                action_plans.append(plan)
        finally:
            db.close()

        state["action_plans"] = action_plans
        state["current_stage"] = "decide"

        return state

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
