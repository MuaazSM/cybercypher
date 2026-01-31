from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from models.actions import Action, Approval
from db.models import ActionDB, ApprovalDB
from datetime import datetime
from uuid import uuid4
import json
import logging

logger = logging.getLogger(__name__)


class PolicyApprovalAgent:
    """
    Policy & Approval Gate Agent (Agent 7 in DECIDE pipeline).
    
    CRITICAL FOR ETHICS - Enforces boundaries and requires human approval
    for risky actions that could impact customers or business.
    
    Policy Rules:
    1. External communications (merchant emails/broadcasts) → Always require approval
    2. Checkout/payment affecting actions → Always require approval
    3. High-risk mitigations → Require approval
    4. Engineering escalations → Auto-approve for high/critical severity
    5. Documentation updates → Require review approval
    6. Internal support guidance → Auto-approve (low risk)
    """
    
    def __init__(self):
        """Initialize policy approval agent with policy rules."""
        self.policies = {
            "external_communication": {
                "applies_to": ["proactive_comms"],
                "requires_approval": True,
                "reason": "External communication affects customer trust"
            },
            "checkout_impact": {
                "keyword_check": ["checkout", "payment", "cart", "transaction", "order"],
                "requires_approval": True,
                "reason": "Affects revenue-critical systems"
            },
            "high_merchant_count": {
                "threshold": 20,
                "requires_approval": True,
                "reason": "Large blast radius requires oversight"
            },
            "docs_changes": {
                "applies_to": ["docs_update"],
                "requires_approval": True,
                "reason": "Documentation changes need review for accuracy"
            },
            "high_risk_mitigation": {
                "applies_to": ["mitigation"],
                "risk_threshold": ["high"],
                "requires_approval": True,
                "reason": "High-risk mitigations need approval before deployment"
            },
            "auto_approve_escalation": {
                "applies_to": ["escalate_eng"],
                "severity_threshold": ["high", "critical"],
                "requires_approval": False,
                "reason": "Critical incidents need immediate escalation"
            },
            "auto_approve_internal": {
                "applies_to": ["support_guidance"],
                "risk_threshold": ["low"],
                "requires_approval": False,
                "reason": "Internal guidance is low-risk and auto-approved"
            }
        }
        
        logger.info("[PolicyApprovalAgent] Initialized with policy rules")
    
    def evaluate_action(
        self,
        action: Action,
        incident_severity: str,
        incident_impacts_checkout: bool = False,
        db: Optional[Session] = None
    ) -> Approval:
        """
        Evaluate action against policies and create approval record.
        
        Args:
            action: Action to evaluate
            incident_severity: Incident severity (low, medium, high, critical)
            incident_impacts_checkout: Whether incident affects checkout
            db: Database session for storage
        
        Returns:
            Approval record with status and policy results
        """
        logger.info(f"[PolicyApprovalAgent] Evaluating action: {action.action_type} (priority {action.priority})")
        
        # Run policy checks
        policy_results = self._run_policy_checks(
            action, incident_severity, incident_impacts_checkout
        )
        
        # Determine if approval is required
        requires_approval = action.requires_approval or any(policy_results.values())
        
        # Override: Auto-approve low-risk internal actions
        if (action.risk_level == "low" and 
            action.action_type in ["support_guidance"] and
            not any(policy_results.values())):
            requires_approval = False
            logger.debug("[PolicyApprovalAgent] Auto-approved low-risk internal action")
        
        # Create approval record
        approval = Approval(
            approval_id=uuid4(),
            action_id=action.action_id,
            status="approved" if not requires_approval else "pending",
            requested_at=datetime.utcnow(),
            requester="system",
            policy_checks=policy_results,
            required_approver_role=self._determine_approver_role(action, incident_severity)
        )
        
        # Auto-approve if no approval needed
        if not requires_approval:
            approval.approved_by = "system_auto"
            approval.approved_at = datetime.utcnow()
            logger.info(f"[PolicyApprovalAgent] Auto-approved {action.action_type}")
        else:
            logger.info(
                f"[PolicyApprovalAgent] Approval required for {action.action_type} "
                f"(approver: {approval.required_approver_role})"
            )
        
        # Store in database if session provided
        if db:
            self._store_approval(approval, db)
        
        return approval
    
    def _run_policy_checks(
        self,
        action: Action,
        incident_severity: str,
        incident_impacts_checkout: bool
    ) -> Dict[str, bool]:
        """
        Run all policy checks and return results.
        
        Args:
            action: Action to check
            incident_severity: Incident severity
            incident_impacts_checkout: Whether incident affects checkout
        
        Returns:
            Dictionary mapping policy names to whether they're triggered
        """
        checks = {}
        
        # Policy 1: External communication
        if action.action_type in self.policies["external_communication"]["applies_to"]:
            checks["external_communication"] = True
            logger.debug("[PolicyApprovalAgent] Policy triggered: external_communication")
        
        # Policy 2: Checkout impact
        payload_str = json.dumps(action.payload).lower()
        if (incident_impacts_checkout or
            any(kw in payload_str for kw in self.policies["checkout_impact"]["keyword_check"])):
            checks["checkout_impact"] = True
            logger.debug("[PolicyApprovalAgent] Policy triggered: checkout_impact")
        
        # Policy 3: High merchant count
        if "merchant_ids" in action.payload:
            merchant_count = len(action.payload.get("merchant_ids", []))
            if merchant_count >= self.policies["high_merchant_count"]["threshold"]:
                checks["high_merchant_count"] = True
                logger.debug(f"[PolicyApprovalAgent] Policy triggered: high_merchant_count ({merchant_count})")
        
        # Policy 4: Documentation changes
        if action.action_type in self.policies["docs_changes"]["applies_to"]:
            checks["docs_changes"] = True
            logger.debug("[PolicyApprovalAgent] Policy triggered: docs_changes")
        
        # Policy 5: High-risk mitigation
        if (action.action_type in self.policies["high_risk_mitigation"]["applies_to"] and
            action.risk_level in self.policies["high_risk_mitigation"]["risk_threshold"]):
            checks["high_risk_mitigation"] = True
            logger.debug("[PolicyApprovalAgent] Policy triggered: high_risk_mitigation")
        
        # Policy 6: Auto-approve escalations for critical severity
        if (action.action_type in self.policies["auto_approve_escalation"]["applies_to"] and
            incident_severity in self.policies["auto_approve_escalation"]["severity_threshold"]):
            checks["auto_approve_critical_escalation"] = False  # False = doesn't block
            logger.debug("[PolicyApprovalAgent] Auto-approve triggered: critical_escalation")
        
        return checks
    
    def _determine_approver_role(self, action: Action, incident_severity: str) -> str:
        """
        Determine who should approve this action.
        
        Args:
            action: Action to determine approver for
            incident_severity: Incident severity
        
        Returns:
            Required approver role name
        """
        # Priority 1: Critical incidents need engineering lead
        if incident_severity == "critical":
            return "engineering_lead"
        
        # Priority 2: External communications need support manager
        if action.action_type == "proactive_comms":
            return "support_manager"
        
        # Priority 3: Documentation updates need docs team
        if action.action_type == "docs_update":
            return "docs_team"
        
        # Priority 4: High-risk actions need engineering lead
        if action.risk_level == "high":
            return "engineering_lead"
        
        # Default: Support manager for other approvals
        return "support_manager"
    
    def approve_action(
        self,
        approval_id: uuid4,
        approver: str,
        db: Session
    ) -> bool:
        """
        Manually approve a pending action.
        
        Args:
            approval_id: ID of the approval record
            approver: Email or ID of the approver
            db: Database session
        
        Returns:
            True if approval succeeded, False otherwise
        """
        logger.info(f"[PolicyApprovalAgent] Approving action by {approver}")
        
        try:
            approval = db.query(ApprovalDB).filter(
                ApprovalDB.approval_id == approval_id
            ).first()
            
            if not approval:
                logger.error(f"[PolicyApprovalAgent] Approval record not found: {approval_id}")
                return False
            
            if approval.status != "pending":
                logger.warning(
                    f"[PolicyApprovalAgent] Approval already {approval.status}: {approval_id}"
                )
                return False
            
            # Update approval
            approval.status = "approved"
            approval.approved_by = approver
            approval.approved_at = datetime.utcnow()
            
            # Update action status
            action = db.query(ActionDB).filter(
                ActionDB.action_id == approval.action_id
            ).first()
            
            if action:
                action.status = "approved"
                logger.debug(f"[PolicyApprovalAgent] Updated action status to approved: {action.action_id}")
            
            db.commit()
            
            logger.info(
                f"[PolicyApprovalAgent] Action approved by {approver}: {approval.action_id}"
            )
            return True
        
        except Exception as e:
            logger.error(f"[PolicyApprovalAgent] Error approving action: {e}")
            db.rollback()
            return False
    
    def reject_action(
        self,
        approval_id: uuid4,
        approver: str,
        reason: str,
        db: Session
    ) -> bool:
        """
        Reject a pending action.
        
        Args:
            approval_id: ID of the approval record
            approver: Email or ID of the approver
            reason: Reason for rejection
            db: Database session
        
        Returns:
            True if rejection succeeded, False otherwise
        """
        logger.info(f"[PolicyApprovalAgent] Rejecting action by {approver}: {reason}")
        
        try:
            approval = db.query(ApprovalDB).filter(
                ApprovalDB.approval_id == approval_id
            ).first()
            
            if not approval:
                logger.error(f"[PolicyApprovalAgent] Approval record not found: {approval_id}")
                return False
            
            if approval.status != "pending":
                logger.warning(
                    f"[PolicyApprovalAgent] Cannot reject non-pending approval: {approval.status}"
                )
                return False
            
            # Update approval
            approval.status = "rejected"
            approval.approved_by = approver
            approval.approved_at = datetime.utcnow()
            approval.rejection_reason = reason
            
            # Update action status
            action = db.query(ActionDB).filter(
                ActionDB.action_id == approval.action_id
            ).first()
            
            if action:
                action.status = "rejected"
                logger.debug(f"[PolicyApprovalAgent] Updated action status to rejected: {action.action_id}")
            
            db.commit()
            
            logger.info(
                f"[PolicyApprovalAgent] Action rejected by {approver}: {approval.action_id}"
            )
            return True
        
        except Exception as e:
            logger.error(f"[PolicyApprovalAgent] Error rejecting action: {e}")
            db.rollback()
            return False
    
    def get_pending_approvals(self, db: Session) -> List[Dict]:
        """
        Get all pending approvals across all actions.
        
        Args:
            db: Database session
        
        Returns:
            List of pending approval records with action details
        """
        logger.info("[PolicyApprovalAgent] Fetching pending approvals")
        
        try:
            pending = db.query(ApprovalDB).filter(
                ApprovalDB.status == "pending"
            ).all()
            
            results = []
            for approval in pending:
                action = db.query(ActionDB).filter(
                    ActionDB.action_id == approval.action_id
                ).first()
                
                if action:
                    results.append({
                        "approval_id": approval.approval_id,
                        "action_id": action.action_id,
                        "action_type": action.action_type,
                        "priority": action.priority,
                        "risk_level": action.risk_level,
                        "rationale": action.rationale,
                        "required_approver_role": approval.required_approver_role,
                        "policy_checks": json.loads(approval.policy_checks or "{}"),
                        "requested_at": approval.requested_at
                    })
            
            logger.info(f"[PolicyApprovalAgent] Found {len(results)} pending approvals")
            return results
        
        except Exception as e:
            logger.error(f"[PolicyApprovalAgent] Error fetching pending approvals: {e}")
            return []
    
    def get_approval_stats(self, db: Session) -> Dict:
        """
        Get approval statistics across all actions.
        
        Args:
            db: Database session
        
        Returns:
            Dictionary with approval statistics
        """
        logger.info("[PolicyApprovalAgent] Computing approval statistics")
        
        try:
            all_approvals = db.query(ApprovalDB).count()
            approved = db.query(ApprovalDB).filter(ApprovalDB.status == "approved").count()
            rejected = db.query(ApprovalDB).filter(ApprovalDB.status == "rejected").count()
            pending = db.query(ApprovalDB).filter(ApprovalDB.status == "pending").count()
            
            auto_approved = db.query(ApprovalDB).filter(
                ApprovalDB.status == "approved",
                ApprovalDB.approved_by == "system_auto"
            ).count()
            
            # Count by required role
            role_counts = {}
            for approval in db.query(ApprovalDB).all():
                role = approval.required_approver_role
                role_counts[role] = role_counts.get(role, 0) + 1
            
            stats = {
                "total_approvals": all_approvals,
                "approved": approved,
                "rejected": rejected,
                "pending": pending,
                "auto_approved": auto_approved,
                "manual_approved": approved - auto_approved,
                "by_required_role": role_counts,
                "approval_rate": round(approved / all_approvals * 100, 2) if all_approvals > 0 else 0
            }
            
            logger.info(f"[PolicyApprovalAgent] Approval stats: {stats}")
            return stats
        
        except Exception as e:
            logger.error(f"[PolicyApprovalAgent] Error computing stats: {e}")
            return {}
    
    def _store_approval(self, approval: Approval, db: Session):
        """
        Store approval record in database.
        
        Args:
            approval: Approval to store
            db: Database session
        """
        try:
            db_approval = ApprovalDB(
                approval_id=approval.approval_id,
                action_id=approval.action_id,
                status=approval.status,
                requested_at=approval.requested_at,
                approved_by=approval.approved_by,
                approved_at=approval.approved_at,
                rejection_reason=approval.rejection_reason,
                policy_checks=json.dumps(approval.policy_checks),
                required_approver_role=approval.required_approver_role
            )
            db.add(db_approval)
            
            # Update action status immediately
            action = db.query(ActionDB).filter(
                ActionDB.action_id == approval.action_id
            ).first()
            
            if action:
                action.status = approval.status
            
            db.commit()
            
            logger.debug(
                f"[PolicyApprovalAgent] Stored approval: {approval.approval_id} "
                f"(status: {approval.status})"
            )
        
        except Exception as e:
            logger.error(f"[PolicyApprovalAgent] Error storing approval: {e}")
            db.rollback()
            raise
