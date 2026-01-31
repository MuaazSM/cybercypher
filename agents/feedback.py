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

    def learn_from_approver_decisions(self, db: Session) -> dict:
        """
        Analyze approval patterns to improve future recommendations.
        
        Tracks:
        - Which actions do approvers accept vs reject?
        - Which confidence thresholds trigger approval?
        - Which hypothesis types are approved faster?
        - Approval rates by risk level
        
        Returns:
            Dict with approval patterns by action_type, risk_level, confidence
            Example:
            {
                "by_action_type": {
                    "escalate_eng": {"approved": 12, "rejected": 2, "rate": 0.857},
                    "proactive_comms": {"approved": 5, "rejected": 8, "rate": 0.385}
                },
                "by_risk_level": {
                    "low": {"approved": 15, "rejected": 1, "rate": 0.938},
                    "high": {"approved": 8, "rejected": 12, "rate": 0.400}
                },
                "by_confidence_range": {
                    "0.0-0.3": {"approved": 1, "rejected": 8, "rate": 0.111},
                    "0.3-0.6": {"approved": 8, "rejected": 5, "rate": 0.615},
                    "0.6-0.8": {"approved": 12, "rejected": 3, "rate": 0.800},
                    "0.8-1.0": {"approved": 15, "rejected": 0, "rate": 1.000}
                },
                "approval_speed": {
                    "fast_approve": {"avg_minutes": 5.2, "count": 18},
                    "delayed_review": {"avg_minutes": 45.1, "count": 8}
                },
                "rejection_reasons": {
                    "insufficient_confidence": 5,
                    "high_risk_too_broad": 4,
                    "alternative_preferred": 3
                }
            }
        """
        from db.models import ApprovalDB, ActionDB
        from collections import defaultdict
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info("[FeedbackLearning] Analyzing approver decision patterns...")
        
        # Get all approvals with decisions
        approvals = db.query(ApprovalDB).filter(
            ApprovalDB.status.in_(["approved", "rejected"])
        ).all()
        
        if not approvals:
            logger.warning("[FeedbackLearning] No approval decisions found")
            return {"error": "No approval data available"}
        
        logger.debug(f"[FeedbackLearning] Analyzing {len(approvals)} approval decisions")
        
        # Initialize pattern tracking
        approval_patterns = {
            "by_action_type": defaultdict(lambda: {"approved": 0, "rejected": 0, "rate": 0.0}),
            "by_risk_level": defaultdict(lambda: {"approved": 0, "rejected": 0, "rate": 0.0}),
            "by_confidence_range": {
                "0.0-0.3": {"approved": 0, "rejected": 0, "rate": 0.0},
                "0.3-0.6": {"approved": 0, "rejected": 0, "rate": 0.0},
                "0.6-0.8": {"approved": 0, "rejected": 0, "rate": 0.0},
                "0.8-1.0": {"approved": 0, "rejected": 0, "rate": 0.0}
            },
            "approval_speed": {"fast_approve": {"total_minutes": 0, "count": 0}, "delayed_review": {"total_minutes": 0, "count": 0}},
            "rejection_reasons": defaultdict(int),
            "total_approvals": len(approvals),
            "approval_rate_overall": 0.0
        }
        
        # Analyze each approval
        for approval in approvals:
            # Get action details
            action_db = db.query(ActionDB).filter(
                ActionDB.action_id == approval.action_id
            ).first()
            
            if not action_db:
                logger.warning(f"[FeedbackLearning] Action not found for approval {approval.approval_id}")
                continue
            
            action_type = action_db.action_type
            risk_level = action_db.risk_level
            approval_status = "approved" if approval.status == "approved" else "rejected"
            
            # Track by action type
            approval_patterns["by_action_type"][action_type][approval_status] += 1
            
            # Track by risk level
            approval_patterns["by_risk_level"][risk_level][approval_status] += 1
            
            # Track by confidence threshold (extract from policy_checks if available)
            confidence = self._extract_confidence_from_policy_checks(approval.policy_checks)
            if confidence is not None:
                confidence_range = self._get_confidence_range(confidence)
                approval_patterns["by_confidence_range"][confidence_range][approval_status] += 1
            
            # Track approval speed
            if approval.approved_at:
                time_to_approve = (approval.approved_at - approval.requested_at).total_seconds() / 60
                if time_to_approve <= 15:  # Fast approval
                    approval_patterns["approval_speed"]["fast_approve"]["total_minutes"] += time_to_approve
                    approval_patterns["approval_speed"]["fast_approve"]["count"] += 1
                else:  # Delayed review
                    approval_patterns["approval_speed"]["delayed_review"]["total_minutes"] += time_to_approve
                    approval_patterns["approval_speed"]["delayed_review"]["count"] += 1
            
            # Track rejection reasons
            if approval.status == "rejected" and approval.rejection_reason:
                reason = approval.rejection_reason.lower()
                if "confidence" in reason:
                    approval_patterns["rejection_reasons"]["insufficient_confidence"] += 1
                elif "risk" in reason or "blast" in reason:
                    approval_patterns["rejection_reasons"]["high_risk_too_broad"] += 1
                elif "alternative" in reason or "prefer" in reason:
                    approval_patterns["rejection_reasons"]["alternative_preferred"] += 1
                else:
                    approval_patterns["rejection_reasons"]["other"] += 1
        
        # Calculate rates
        for action_type, counts in approval_patterns["by_action_type"].items():
            total = counts["approved"] + counts["rejected"]
            if total > 0:
                counts["rate"] = counts["approved"] / total
        
        for risk_level, counts in approval_patterns["by_risk_level"].items():
            total = counts["approved"] + counts["rejected"]
            if total > 0:
                counts["rate"] = counts["approved"] / total
        
        for conf_range, counts in approval_patterns["by_confidence_range"].items():
            total = counts["approved"] + counts["rejected"]
            if total > 0:
                counts["rate"] = counts["approved"] / total
        
        # Calculate average approval speeds
        if approval_patterns["approval_speed"]["fast_approve"]["count"] > 0:
            approval_patterns["approval_speed"]["fast_approve"]["avg_minutes"] = (
                approval_patterns["approval_speed"]["fast_approve"]["total_minutes"] /
                approval_patterns["approval_speed"]["fast_approve"]["count"]
            )
            del approval_patterns["approval_speed"]["fast_approve"]["total_minutes"]
        
        if approval_patterns["approval_speed"]["delayed_review"]["count"] > 0:
            approval_patterns["approval_speed"]["delayed_review"]["avg_minutes"] = (
                approval_patterns["approval_speed"]["delayed_review"]["total_minutes"] /
                approval_patterns["approval_speed"]["delayed_review"]["count"]
            )
            del approval_patterns["approval_speed"]["delayed_review"]["total_minutes"]
        
        # Calculate overall approval rate
        total_approved = sum(c["approved"] for c in approval_patterns["by_action_type"].values())
        total_count = approval_patterns["total_approvals"]
        approval_patterns["approval_rate_overall"] = total_approved / total_count if total_count > 0 else 0.0
        
        # Log insights
        logger.info(
            f"[FeedbackLearning] Overall approval rate: {approval_patterns['approval_rate_overall']:.1%} "
            f"({total_approved}/{total_count})"
        )
        
        for action_type, counts in approval_patterns["by_action_type"].items():
            logger.info(
                f"[FeedbackLearning] {action_type}: {counts['approved']}/{counts['approved']+counts['rejected']} "
                f"approved ({counts['rate']:.1%})"
            )
        
        # Convert defaultdict to regular dict for JSON serialization
        approval_patterns["by_action_type"] = dict(approval_patterns["by_action_type"])
        approval_patterns["by_risk_level"] = dict(approval_patterns["by_risk_level"])
        approval_patterns["rejection_reasons"] = dict(approval_patterns["rejection_reasons"])
        
        return approval_patterns
    
    def _extract_confidence_from_policy_checks(self, policy_checks: dict) -> Optional[float]:
        """Extract confidence score from policy_checks JSON"""
        if not policy_checks:
            return None
        
        if isinstance(policy_checks, str):
            import json
            try:
                policy_checks = json.loads(policy_checks)
            except:
                return None
        
        # Look for confidence in various places
        if "confidence" in policy_checks:
            return policy_checks["confidence"]
        if "confidence_score" in policy_checks:
            return policy_checks["confidence_score"]
        
        return None
    
    def _get_confidence_range(self, confidence: float) -> str:
        """Map confidence score to range"""
        if confidence < 0.3:
            return "0.0-0.3"
        elif confidence < 0.6:
            return "0.3-0.6"
        elif confidence < 0.8:
            return "0.6-0.8"
        else:
            return "0.8-1.0"

