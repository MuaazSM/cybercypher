from typing import Optional
from sqlalchemy.orm import Session
from db.database import SessionLocal
from db.models import ApprovalDB, PolicyThresholdDB
from agents.feedback import FeedbackLearningAgent
from agents.approval_gate import PolicyApprovalAgent
from tools.knowledge_base import KnowledgeBase
from datetime import datetime, timedelta
import logging
from pathlib import Path

# Configure logging
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "policy_learning.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class PolicyLearningTask:
    """Background task for continuous policy learning"""
    
    def __init__(self):
        """Initialize task with agents"""
        self.kb = KnowledgeBase(
            persist_directory=str(Path(__file__).parent.parent / "data" / "knowledge_base")
        )
        self.feedback_agent = FeedbackLearningAgent(self.kb)
        self.approval_agent = PolicyApprovalAgent()
        self.last_analysis_time = None
        self.approval_count_at_last_analysis = 0
    
    def should_run(self, db: Session) -> bool:
        """
        Determine if learning task should run based on:
        - 24 hours have passed since last analysis
        - 20+ new approvals since last analysis
        
        Args:
            db: Database session
        
        Returns:
            True if task should run, False otherwise
        """
        # Check time-based trigger
        if self.last_analysis_time is None:
            # First run
            logger.info("[PolicyLearning] First run - will execute")
            return True
        
        time_since_last = datetime.utcnow() - self.last_analysis_time
        if time_since_last > timedelta(hours=24):
            logger.info(
                f"[PolicyLearning] 24 hours elapsed ({time_since_last.total_seconds()/3600:.1f}h) - will execute"
            )
            return True
        
        # Check approval count-based trigger
        total_approvals = db.query(ApprovalDB).filter(
            ApprovalDB.status.in_(["approved", "rejected"])
        ).count()
        
        new_approvals = total_approvals - self.approval_count_at_last_analysis
        if new_approvals >= 20:
            logger.info(
                f"[PolicyLearning] {new_approvals} new approvals since last analysis - will execute"
            )
            return True
        
        # Not yet time to run
        logger.debug(
            f"[PolicyLearning] Conditions not met: {time_since_last.total_seconds()/3600:.1f}h elapsed, "
            f"{new_approvals} new approvals"
        )
        return False
    
    def execute(self, db: Optional[Session] = None) -> dict:
        """
        Execute policy learning task:
        1. Analyze approver patterns
        2. Update policy thresholds
        3. Log changes for audit
        4. Notify on significant changes
        
        Args:
            db: Optional database session (creates new if not provided)
        
        Returns:
            Dict with analysis results and updates
        """
        if db is None:
            db = SessionLocal()
            close_session = True
        else:
            close_session = False
        
        try:
            logger.info("="*80)
            logger.info("[PolicyLearning] STARTING POLICY LEARNING ANALYSIS")
            logger.info("="*80)
            
            # Step 1: Analyze approver patterns
            logger.info("[PolicyLearning] Step 1: Analyzing approver decision patterns...")
            approval_patterns = self.feedback_agent.learn_from_approver_decisions(db)
            
            if "error" in approval_patterns:
                logger.warning(f"[PolicyLearning] Analysis error: {approval_patterns['error']}")
                return {"status": "no_data", "error": approval_patterns['error']}
            
            # Log approval patterns summary
            logger.info(f"[PolicyLearning] Analyzed {approval_patterns['total_approvals']} approval decisions")
            logger.info(f"[PolicyLearning] Overall approval rate: {approval_patterns['approval_rate_overall']:.1%}")
            
            # Step 2: Update policy thresholds
            logger.info("[PolicyLearning] Step 2: Updating policy thresholds...")
            updates = self.approval_agent.update_policy_thresholds(approval_patterns, db)
            
            # Step 3: Generate audit log
            logger.info("[PolicyLearning] Step 3: Generating audit log...")
            audit_log = self._generate_audit_log(approval_patterns, updates)
            
            # Step 4: Check for significant changes
            logger.info("[PolicyLearning] Step 4: Checking for significant policy changes...")
            alerts = self._check_for_alerts(approval_patterns, updates)
            
            if alerts:
                logger.warning(f"[PolicyLearning] ⚠️  {len(alerts)} significant changes detected:")
                for alert in alerts:
                    logger.warning(f"[PolicyLearning]   - {alert}")
            
            # Update tracking variables
            self.last_analysis_time = datetime.utcnow()
            self.approval_count_at_last_analysis = approval_patterns['total_approvals']
            
            logger.info("="*80)
            logger.info("[PolicyLearning] ANALYSIS COMPLETE")
            logger.info("="*80)
            
            return {
                "status": "success",
                "timestamp": self.last_analysis_time.isoformat(),
                "approvals_analyzed": approval_patterns['total_approvals'],
                "approval_rate": approval_patterns['approval_rate_overall'],
                "thresholds_updated": len(updates),
                "alerts": alerts,
                "patterns": approval_patterns,
                "updates": updates,
                "audit_log": audit_log
            }
        
        except Exception as e:
            logger.error(f"[PolicyLearning] Task execution failed: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
        
        finally:
            if close_session:
                db.close()
    
    def _generate_audit_log(self, approval_patterns: dict, updates: dict) -> str:
        """Generate human-readable audit log of changes"""
        log_lines = [
            f"Policy Learning Analysis - {datetime.utcnow().isoformat()}",
            "-" * 80,
            f"Total Approvals Analyzed: {approval_patterns['total_approvals']}",
            f"Overall Approval Rate: {approval_patterns['approval_rate_overall']:.1%}",
            ""
        ]
        
        # By action type
        log_lines.append("Approval Rates by Action Type:")
        for action_type, counts in approval_patterns.get("by_action_type", {}).items():
            log_lines.append(
                f"  {action_type:20s}: {counts['rate']:6.1%} "
                f"({counts['approved']}/{counts['approved']+counts['rejected']} approved)"
            )
        
        log_lines.append("")
        
        # By risk level
        log_lines.append("Approval Rates by Risk Level:")
        for risk_level, counts in approval_patterns.get("by_risk_level", {}).items():
            log_lines.append(
                f"  {risk_level:20s}: {counts['rate']:6.1%} "
                f"({counts['approved']}/{counts['approved']+counts['rejected']} approved)"
            )
        
        log_lines.append("")
        
        # By confidence range
        log_lines.append("Approval Rates by Confidence Range:")
        for conf_range, counts in approval_patterns.get("by_confidence_range", {}).items():
            log_lines.append(
                f"  {conf_range:20s}: {counts['rate']:6.1%} "
                f"({counts['approved']}/{counts['approved']+counts['rejected']} approved)"
            )
        
        if updates:
            log_lines.append("")
            log_lines.append(f"Policy Updates ({len(updates)}):")
            for policy_name, update_info in updates.items():
                if "new_threshold" in update_info:
                    log_lines.append(
                        f"  {policy_name}: {update_info['new_threshold']} "
                        f"({update_info['reasoning']})"
                    )
                else:
                    log_lines.append(f"  {policy_name}: {update_info['new_policy']}")
        
        return "\n".join(log_lines)
    
    def _check_for_alerts(self, approval_patterns: dict, updates: dict) -> list:
        """
        Check for significant policy changes that warrant alerts.
        
        Alerts trigger when:
        - Approval rate drops below 40% for any action type
        - Approval rate exceeds 95% for any action type (very permissive)
        - High-risk actions have <20% approval rate
        - Policy thresholds shift by >0.15
        """
        alerts = []
        
        # Check approval rates by action type
        for action_type, counts in approval_patterns.get("by_action_type", {}).items():
            rate = counts['rate']
            total = counts['approved'] + counts['rejected']
            
            if total >= 5:  # Only alert if sufficient data
                if rate < 0.40:
                    alerts.append(
                        f"LOW APPROVAL RATE: {action_type} only approved {rate:.1%} "
                        f"({counts['approved']}/{total})"
                    )
                elif rate > 0.95:
                    alerts.append(
                        f"HIGH APPROVAL RATE: {action_type} approved {rate:.1%} "
                        f"({counts['approved']}/{total}) - consider auto-approval"
                    )
        
        # Check high-risk approval rates
        high_risk_rate = approval_patterns.get("by_risk_level", {}).get("high", {}).get("rate", 0.5)
        high_risk_total = (
            approval_patterns.get("by_risk_level", {}).get("high", {}).get("approved", 0) +
            approval_patterns.get("by_risk_level", {}).get("high", {}).get("rejected", 0)
        )
        
        if high_risk_total >= 5 and high_risk_rate < 0.20:
            alerts.append(
                f"STRICT HIGH-RISK POLICY: High-risk actions only approved {high_risk_rate:.1%} "
                f"({high_risk_total} decisions)"
            )
        
        # Check for threshold changes
        for policy_name, update_info in updates.items():
            if "new_threshold" in update_info and "previous" in update_info:
                diff = abs(update_info['new_threshold'] - update_info['previous'])
                if diff > 0.15:
                    alerts.append(
                        f"SIGNIFICANT THRESHOLD CHANGE: {policy_name} "
                        f"shifted by {diff:+.2f}"
                    )
        
        return alerts


# Task scheduling function for use with APScheduler or similar
async def run_policy_learning_task():
    """
    Async wrapper for running the policy learning task.
    
    Usage with APScheduler:
    ```python
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_policy_learning_task,
        trigger=IntervalTrigger(hours=1),  # Check every hour
        id='policy_learning'
    )
    scheduler.start()
    ```
    """
    task = PolicyLearningTask()
    db = SessionLocal()
    
    try:
        if task.should_run(db):
            result = task.execute(db)
            logger.info(f"[PolicyLearning] Task result: {result['status']}")
        else:
            logger.debug("[PolicyLearning] Conditions not met - skipping execution")
    except Exception as e:
        logger.error(f"[PolicyLearning] Unexpected error: {e}", exc_info=True)
    finally:
        db.close()


# Standalone execution for testing
if __name__ == "__main__":
    logger.info("[PolicyLearning] Running policy learning task (standalone mode)")
    
    task = PolicyLearningTask()
    db = SessionLocal()
    
    try:
        result = task.execute(db)
        
        print("\n" + "="*80)
        print("POLICY LEARNING TASK RESULTS")
        print("="*80)
        print(f"Status: {result['status']}")
        
        if result['status'] == 'success':
            print(f"Approvals Analyzed: {result['approvals_analyzed']}")
            print(f"Overall Approval Rate: {result['approval_rate']:.1%}")
            print(f"Thresholds Updated: {result['thresholds_updated']}")
            
            if result['alerts']:
                print(f"\n⚠️  {len(result['alerts'])} ALERTS:")
                for alert in result['alerts']:
                    print(f"   - {alert}")
            
            if result['updates']:
                print(f"\n📊 Policy Updates:")
                for policy_name, update_info in result['updates'].items():
                    if "new_threshold" in update_info:
                        print(
                            f"   {policy_name}: {update_info['new_threshold']} "
                            f"({update_info['reasoning']})"
                        )
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
        
        print("="*80)
    
    finally:
        db.close()
