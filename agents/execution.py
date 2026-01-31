import logging
import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime

from models.actions import Action, ExecutedAction
from db.models import ActionDB, ExecutedActionDB
from tools.slack_client import SlackClient
from tools.github_client import GitHubClient
from tools.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class ExecutionAgent:
    """Execute approved actions with audit trail"""
    
    def __init__(
        self,
        slack_client: SlackClient,
        github_client: GitHubClient,
        llm_router: LLMRouter
    ):
        self.slack = slack_client
        self.github = github_client
        self.llm = llm_router
        logger.info("[ExecutionAgent] Initialized")
    
    def execute_action(self, action: Action, db: Session) -> ExecutedAction:
        """
        Execute an approved action with idempotency check and error handling
        
        Args:
            action: Action model to execute
            db: Database session
            
        Returns:
            ExecutedAction with execution details
        """
        # Check if already executed (idempotency)
        existing = db.query(ExecutedActionDB).filter(
            ExecutedActionDB.action_id == action.action_id
        ).first()
        
        if existing:
            logger.info(f"[ExecutionAgent] Action already executed: {action.action_id}")
            return self._db_to_pydantic(existing)
        
        # Check approval status
        db_action = db.query(ActionDB).filter(
            ActionDB.action_id == action.action_id
        ).first()
        
        if not db_action or db_action.status != "approved":
            raise ValueError(f"Action not approved: {action.action_id}")
        
        # Execute based on type
        logger.info(f"[ExecutionAgent] Executing {action.action_type}...")
        
        try:
            if action.action_type == "escalate_eng":
                result = self._execute_github_escalation(action)
            elif action.action_type == "proactive_comms":
                result = self._execute_merchant_communication(action)
            elif action.action_type == "docs_update":
                result = self._execute_docs_update(action)
            elif action.action_type == "support_guidance":
                result = self._execute_support_guidance(action)
            elif action.action_type == "mitigation":
                result = self._execute_mitigation(action)
            else:
                raise ValueError(f"Unknown action type: {action.action_type}")
            
            # Create execution record
            executed = ExecutedAction(
                execution_id=str(uuid4()),
                action_id=action.action_id,
                executed_at=datetime.utcnow(),
                executed_by="system",
                success=True,
                execution_log=result["log"],
                external_references=result.get("external_refs", {}),
                action_payload_snapshot=action.payload
            )
            
            # Update action status
            db_action.status = "completed"
            if "external_id" in result.get("external_refs", {}):
                db_action.external_id = result["external_refs"]["external_id"]
            
        except Exception as e:
            logger.error(f"[ExecutionAgent] Execution failed: {str(e)}")
            
            # Log failure
            executed = ExecutedAction(
                execution_id=str(uuid4()),
                action_id=action.action_id,
                executed_at=datetime.utcnow(),
                executed_by="system",
                success=False,
                execution_log="Execution failed",
                error_message=str(e),
                retry_count=0,
                external_references={},
                action_payload_snapshot=action.payload
            )
            
            db_action.status = "failed"
        
        # Store execution record
        db_executed = ExecutedActionDB(
            execution_id=executed.execution_id,
            action_id=executed.action_id,
            executed_at=executed.executed_at,
            executed_by=executed.executed_by,
            success=executed.success,
            execution_log=executed.execution_log,
            error_message=executed.error_message,
            retry_count=executed.retry_count,
            external_references=json.dumps(executed.external_references),
            action_payload_snapshot=json.dumps(executed.action_payload_snapshot)
        )
        db.add(db_executed)
        db.commit()
        
        status = "SUCCESS" if executed.success else "FAILED"
        logger.info(f"[ExecutionAgent] {action.action_type}: {status}")
        
        return executed
    
    def _execute_github_escalation(self, action: Action) -> Dict[str, Any]:
        """Create GitHub issue for engineering escalation"""
        payload = action.payload
        
        result = self.github.create_engineering_escalation(
            incident_title=payload.get("incident_title", "Incident escalation"),
            severity=payload.get("severity", "medium"),
            hypothesis=payload.get("hypothesis", "Unknown"),
            evidence=payload.get("evidence", []),
            affected_merchants=payload.get("affected_merchants", 0),
            blast_radius=payload.get("blast_radius", "Unknown"),
            incident_id=payload.get("incident_id", "unknown")
        )
        
        if result:
            # Also send Slack alert
            self.slack.send_simple_message(
                f"🔧 Created GitHub issue #{result['issue_number']} for incident\n"
                f"Link: {result['issue_url']}"
            )
            
            logger.info(f"[ExecutionAgent] Created GitHub issue #{result['issue_number']}")
            
            return {
                "log": f"Created GitHub issue #{result['issue_number']}",
                "external_refs": {
                    "github_issue": result['issue_number'],
                    "github_url": result['issue_url'],
                    "external_id": str(result['issue_number'])
                }
            }
        else:
            raise Exception("Failed to create GitHub issue")
    
    def _execute_merchant_communication(self, action: Action) -> Dict[str, Any]:
        """Generate draft merchant communication"""
        payload = action.payload
        
        # Generate email content using LLM
        prompt = f"""Generate a professional, empathetic merchant email.

Subject: {payload.get('subject', 'Important Update')}
Issue: {payload.get('hypothesis', 'Technical issue detected')}
Recommended Action: {payload.get('recommended_action', 'Please contact support')}

Write a clear, actionable email that:
1. Acknowledges the issue
2. Explains what happened
3. Provides clear next steps
4. Offers support

Keep it under 200 words."""
        
        email_body = self.llm.invoke(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=400
        )
        
        # Store draft
        draft = {
            "subject": payload.get("subject", "Important Update"),
            "body": email_body,
            "recipients": payload.get("merchant_ids", []),
            "created_at": datetime.utcnow().isoformat()
        }
        
        merchant_count = len(payload.get("merchant_ids", []))
        
        # Send Slack notification
        self.slack.send_simple_message(
            f"📧 Merchant communication draft created\n"
            f"Recipients: {merchant_count} merchants\n"
            f"Subject: {payload.get('subject', 'Important Update')}\n"
            f"Status: Awaiting support team review"
        )
        
        logger.info(f"[ExecutionAgent] Created merchant email draft for {merchant_count} recipients")
        
        return {
            "log": f"Created merchant email draft for {merchant_count} recipients",
            "external_refs": {
                "draft_id": str(uuid4()),
                "draft_content": draft
            }
        }
    
    def _execute_docs_update(self, action: Action) -> Dict[str, Any]:
        """Generate documentation patch suggestion"""
        payload = action.payload
        
        # Generate docs improvement using LLM
        prompt = f"""Generate a documentation improvement for:

Section: {payload.get('section', 'Unknown section')}
Issue: {payload.get('issue', 'Documentation gap')}
Suggested Improvement: {payload.get('suggested_improvement', 'Add clarity')}

Write:
1. The exact text to add/change
2. Where in the documentation it should go
3. Why this change helps

Format as markdown."""
        
        docs_patch = self.llm.invoke(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        
        # Store draft
        draft = {
            "section": payload.get("section", "Unknown"),
            "patch": docs_patch,
            "reason": payload.get("issue", "Documentation improvement"),
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Send Slack notification
        self.slack.send_simple_message(
            f"📝 Documentation patch created\n"
            f"Section: {payload.get('section', 'Unknown')}\n"
            f"Status: Awaiting docs team review"
        )
        
        logger.info(f"[ExecutionAgent] Created docs patch for {payload.get('section', 'Unknown')}")
        
        return {
            "log": f"Created docs patch for {payload.get('section', 'Unknown')}",
            "external_refs": {
                "patch_id": str(uuid4()),
                "patch_content": draft
            }
        }
    
    def _execute_support_guidance(self, action: Action) -> Dict[str, Any]:
        """Create internal support guidance"""
        payload = action.payload
        
        guidance = {
            "template_type": payload.get("template_type", "general"),
            "root_cause": payload.get("root_cause", "Unknown"),
            "suggested_steps": payload.get("suggested_steps", []),
            "created_at": datetime.utcnow().isoformat()
        }
        
        logger.info("[ExecutionAgent] Created support guidance template")
        
        return {
            "log": "Created support guidance template",
            "external_refs": {
                "guidance_id": str(uuid4()),
                "guidance": guidance
            }
        }
    
    def _execute_mitigation(self, action: Action) -> Dict[str, Any]:
        """Execute mitigation action"""
        payload = action.payload
        
        # In real system, this might toggle feature flags, rollback changes, etc.
        # For hackathon, we simulate by recording the mitigation
        
        mitigation_record = {
            "type": payload.get("mitigation_type", "unknown"),
            "applied_at": datetime.utcnow().isoformat(),
            "expected_impact": action.expected_impact,
            "rollback_plan": action.rollback_plan
        }
        
        # Send Slack notification
        self.slack.send_simple_message(
            f"⚙️ Mitigation applied\n"
            f"Type: {payload.get('mitigation_type', 'unknown')}\n"
            f"Impact: {action.expected_impact}"
        )
        
        logger.info(f"[ExecutionAgent] Applied mitigation: {payload.get('mitigation_type', 'unknown')}")
        
        return {
            "log": f"Applied mitigation: {payload.get('mitigation_type', 'unknown')}",
            "external_refs": {
                "mitigation_id": str(uuid4()),
                "mitigation": mitigation_record
            }
        }
    
    def _db_to_pydantic(self, db_executed: ExecutedActionDB) -> ExecutedAction:
        """Convert DB model to ExecutedAction"""
        return ExecutedAction(
            execution_id=db_executed.execution_id,
            action_id=db_executed.action_id,
            executed_at=db_executed.executed_at,
            executed_by=db_executed.executed_by,
            success=db_executed.success,
            execution_log=db_executed.execution_log,
            external_references=json.loads(db_executed.external_references or "{}"),
            error_message=db_executed.error_message,
            retry_count=db_executed.retry_count,
            action_payload_snapshot=json.loads(db_executed.action_payload_snapshot or "{}")
        )
