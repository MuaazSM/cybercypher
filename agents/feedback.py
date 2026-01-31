from typing import Optional
from sqlalchemy.orm import Session
from models.outcomes import ActionOutcome
from models.actions import ExecutedAction
from db.models import (
    ExecutedActionDB, ActionOutcomeDB, CleanEventDB,
    IncidentDB, KnownPatternDB
)
from tools.knowledge_base import KnowledgeBase
from datetime import datetime, timedelta
from uuid import uuid4
import json


class FeedbackLearningAgent:
    def __init__(self, knowledge_base: KnowledgeBase):
        self.kb = knowledge_base
    
    def measure_outcome(
        self,
        executed_action: ExecutedAction,
        db: Session,
        measurement_delay_minutes: int = 30
    ) -> ActionOutcome:
        """
        Measure the effectiveness of an executed action
        """
        print(f"[Feedback] Measuring outcome for action: {executed_action.action_id}")
        
        # Check if already measured
        existing = db.query(ActionOutcomeDB).filter(
            ActionOutcomeDB.execution_id == executed_action.execution_id
        ).first()
        
        if existing:
            return self._db_to_pydantic(existing)
        
        # Get the incident and action details
        from db.models import ActionDB
        action_db = db.query(ActionDB).filter(
            ActionDB.action_id == executed_action.action_id
        ).first()
        
        if not action_db:
            raise ValueError("Action not found")
        
        # Get incident
        from db.models import ActionPlanDB
        plan_db = db.query(ActionPlanDB).filter(
            ActionPlanDB.plan_id == action_db.plan_id
        ).first()
        
        incident_db = db.query(IncidentDB).filter(
            IncidentDB.incident_id == plan_db.incident_id
        ).first()
        
        # Measure based on action type
        if action_db.action_type == "escalate_eng":
            outcome_result = self._measure_escalation_outcome(
                executed_action, incident_db, db
            )
        elif action_db.action_type in ["proactive_comms", "support_guidance"]:
            outcome_result = self._measure_communication_outcome(
                executed_action, incident_db, db, measurement_delay_minutes
            )
        elif action_db.action_type == "docs_update":
            outcome_result = self._measure_docs_outcome(
                executed_action, incident_db, db
            )
        else:
            outcome_result = self._measure_generic_outcome(
                executed_action, incident_db, db, measurement_delay_minutes
            )
        
        # Create outcome record
        outcome = ActionOutcome(
            outcome_id=uuid4(),
            execution_id=executed_action.execution_id,
            measured_at=datetime.utcnow(),
            outcome=outcome_result["outcome"],
            ticket_volume_before=outcome_result.get("volume_before", 0),
            ticket_volume_after=outcome_result.get("volume_after", 0),
            incident_resolved=outcome_result.get("resolved", False),
            merchant_feedback=outcome_result.get("feedback"),
            confidence_score=outcome_result.get("confidence", 0.5),
            should_update_patterns=outcome_result["outcome"] == "helped"
        )
        
        # Store outcome
        db_outcome = ActionOutcomeDB(**outcome.model_dump())
        db.add(db_outcome)
        db.commit()
        
        # Update incident status if resolved
        if outcome.incident_resolved and incident_db:
            incident_db.status = "resolved"
            db.commit()
        
        # Update knowledge base if successful
        if outcome.should_update_patterns:
            self._update_knowledge_base(
                executed_action=executed_action,
                action_db=action_db,
                incident_db=incident_db,
                outcome=outcome,
                db=db
            )
        
        print(f"[Feedback] Outcome: {outcome.outcome} (confidence: {outcome.confidence_score:.2f})")
        return outcome
    
    def _measure_communication_outcome(
        self,
        executed_action: ExecutedAction,
        incident_db: IncidentDB,
        db: Session,
        delay_minutes: int
    ) -> dict:
        """Measure if communication reduced ticket volume"""
        
        # Get cluster signature
        from db.models import IncidentClusterDB
        cluster = db.query(IncidentClusterDB).filter(
            IncidentClusterDB.cluster_id == incident_db.cluster_id
        ).first()
        
        signature = cluster.primary_signature if cluster else None
        
        if not signature:
            return {"outcome": "neutral", "confidence": 0.3}
        
        # Count events before action
        before_window_start = executed_action.executed_at - timedelta(minutes=delay_minutes)
        before_window_end = executed_action.executed_at
        
        events_before = db.query(CleanEventDB).filter(
            CleanEventDB.signature == signature,
            CleanEventDB.timestamp >= before_window_start,
            CleanEventDB.timestamp < before_window_end
        ).count()
        
        # Count events after action
        after_window_start = executed_action.executed_at
        after_window_end = executed_action.executed_at + timedelta(minutes=delay_minutes)
        
        events_after = db.query(CleanEventDB).filter(
            CleanEventDB.signature == signature,
            CleanEventDB.timestamp >= after_window_start,
            CleanEventDB.timestamp < after_window_end
        ).count()
        
        # Determine outcome
        if events_before == 0:
            outcome = "neutral"
            confidence = 0.3
        elif events_after < events_before * 0.5:  # 50%+ reduction
            outcome = "helped"
            confidence = 0.8
        elif events_after < events_before * 0.8:  # Some reduction
            outcome = "helped"
            confidence = 0.6
        elif events_after > events_before * 1.2:  # Increased
            outcome = "harmed"
            confidence = 0.7
        else:
            outcome = "neutral"
            confidence = 0.5
        
        resolved = events_after == 0 and events_before > 0
        
        return {
            "outcome": outcome,
            "volume_before": events_before,
            "volume_after": events_after,
            "resolved": resolved,
            "confidence": confidence
        }
    
    def _measure_escalation_outcome(
        self,
        executed_action: ExecutedAction,
        incident_db: IncidentDB,
        db: Session
    ) -> dict:
        """Measure engineering escalation outcome"""
        
        # For hackathon: assume escalations help
        # In production: would track GitHub issue status
        
        github_issue = executed_action.external_references.get("github_issue")
        
        if github_issue:
            return {
                "outcome": "helped",
                "confidence": 0.7,
                "resolved": False,  # Engineering needs time to fix
                "feedback": f"Created GitHub issue #{github_issue}"
            }
        else:
            return {
                "outcome": "neutral",
                "confidence": 0.4
            }
    
    def _measure_docs_outcome(
        self,
        executed_action: ExecutedAction,
        incident_db: IncidentDB,
        db: Session
    ) -> dict:
        """Measure documentation update outcome"""
        
        # Docs changes take time to show impact
        # For hackathon: assume they help
        
        return {
            "outcome": "helped",
            "confidence": 0.5,
            "resolved": False,
            "feedback": "Documentation updated (long-term impact)"
        }
    
    def _measure_generic_outcome(
        self,
        executed_action: ExecutedAction,
        incident_db: IncidentDB,
        db: Session,
        delay_minutes: int
    ) -> dict:
        """Generic outcome measurement"""
        
        return {
            "outcome": "neutral",
            "confidence": 0.5
        }
    
    def _update_knowledge_base(
        self,
        executed_action: ExecutedAction,
        action_db,
        incident_db: IncidentDB,
        outcome: ActionOutcome,
        db: Session
    ):
        """Update RAG knowledge base with successful pattern"""
        
        # Get cluster signature
        from db.models import IncidentClusterDB, IncidentHypothesisDB
        cluster = db.query(IncidentClusterDB).filter(
            IncidentClusterDB.cluster_id == incident_db.cluster_id
        ).first()
        
        if not cluster:
            return
        
        signature = cluster.primary_signature
        
        # Get hypothesis
        from db.models import ActionPlanDB
        plan = db.query(ActionPlanDB).filter(
            ActionPlanDB.plan_id == action_db.plan_id
        ).first()
        
        hypothesis = None
        if plan and plan.hypothesis_id:
            hypothesis = db.query(IncidentHypothesisDB).filter(
                IncidentHypothesisDB.hypothesis_id == plan.hypothesis_id
            ).first()
        
        # Update known patterns table
        known_pattern = db.query(KnownPatternDB).filter(
            KnownPatternDB.signature == signature,
            KnownPatternDB.successful_action_type == action_db.action_type
        ).first()
        
        if known_pattern:
            # Update existing pattern
            known_pattern.success_count += 1
            known_pattern.total_attempts += 1
            known_pattern.success_rate = known_pattern.success_count / known_pattern.total_attempts
            known_pattern.last_seen = datetime.utcnow()
        else:
            # Create new pattern
            known_pattern = KnownPatternDB(
                pattern_id=uuid4(),
                signature=signature,
                root_cause_type=hypothesis.type if hypothesis else "unknown",
                successful_action_type=action_db.action_type,
                success_count=1,
                total_attempts=1,
                success_rate=1.0,
                last_seen=datetime.utcnow()
            )
            db.add(known_pattern)
        
        db.commit()
        
        # Index into FAISS for RAG
        incident_doc = {
            "incident_id": str(incident_db.incident_id),
            "title": incident_db.title,
            "signature": signature,
            "migration_stage": cluster.stage_distribution if cluster else {},
            "confirmed_cause": hypothesis.type if hypothesis else "unknown",
            "resolution_summary": f"Resolved by {action_db.action_type}",
            "merchant_count": incident_db.blast_radius_estimate,
            "outcome": outcome.outcome,
            "status": "resolved"
        }
        
        try:
            self.kb.index_incidents([incident_doc])
            self.kb.save()
            print(f"[Feedback] Updated knowledge base with successful pattern")
        except Exception as e:
            print(f"[Feedback] Failed to update knowledge base: {e}")
    
    def _db_to_pydantic(self, db_outcome: ActionOutcomeDB) -> ActionOutcome:
        """Convert DB model to Pydantic"""
        return ActionOutcome(
            outcome_id=db_outcome.outcome_id,
            execution_id=db_outcome.execution_id,
            measured_at=db_outcome.measured_at,
            outcome=db_outcome.outcome,
            ticket_volume_before=db_outcome.ticket_volume_before,
            ticket_volume_after=db_outcome.ticket_volume_after,
            incident_resolved=db_outcome.incident_resolved,
            merchant_feedback=db_outcome.merchant_feedback,
            confidence_score=db_outcome.confidence_score,
            should_update_patterns=db_outcome.should_update_patterns
        )
