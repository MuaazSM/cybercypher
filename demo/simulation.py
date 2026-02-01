"""
Full simulation showing GitHub integration during incident response.
This creates REAL GitHub issues and demonstrates the end-to-end workflow.
"""

import os
import time
from datetime import datetime
from typing import Dict, Any
import json
import sys
from pathlib import Path

# Import the presenter and GitHubAPI
from demo.terminal_presenter import (
    TerminalPresenter, Stage, Color, Pipeline, GitHubAPI
)


class IncidentSimulation:
    """Full incident simulation workflow"""
    
    def __init__(self, presenter: TerminalPresenter, github: GitHubAPI):
        self.presenter = presenter
        self.pipeline = Pipeline()
        self.github = github
        self.timeline = []
    
    def log_event(self, stage: str, component: str, message: str, data: Dict = None):
        """Log an event to timeline"""
        event = {
            "timestamp": datetime.now(),
            "stage": stage,
            "component": component,
            "message": message,
            "data": data or {}
        }
        self.timeline.append(event)
    
    def run_simulation(self):
        """Execute full incident simulation"""
        
        self.presenter.print_header("INCIDENT SIMULATION: PAYMENT PROCESSING OUTAGE")
        print("Real-time incident response with GitHub integration\n")
        
        # === OBSERVE PHASE ===
        self.presenter.print_stage(Stage.OBSERVE, "ACTIVE")
        self.presenter.print_section("OBSERVE Phase", "Time: 0:00 - 5:00")
        
        print(f"\n{Color.DIM}[14:23:45 UTC]{Color.RESET} Payment processing errors detected")
        self.log_event("observe", "anomaly_detector", "Payment timeout spike detected", {
            "error_rate": "6.0%",
            "baseline": "0.8%",
            "confidence": "98%"
        })
        self.presenter.animate_step("Ingesting 47 error events from DataDog")
        self.presenter.animate_step("Normalizing event formats")
        self.presenter.animate_step("Detecting 7.5x deviation from baseline")
        self.presenter.animate_step("Clustering similar events into incident")
        
        print(f"\n{Color.GREEN}{Color.BOLD}[OBSERVE COMPLETE]{Color.RESET}")
        print(f"  Cluster ID: cluster_20250201_payment_timeout")
        print(f"  Events clustered: 47")
        print(f"  Time taken: 3 seconds")
        
        self.presenter.wait()
        
        # === REASON PHASE ===
        self.presenter.print_stage(Stage.REASON, "ACTIVE")
        self.presenter.print_section("REASON Phase", "Time: 5:00 - 10:00")
        
        print(f"\n{Color.DIM}[14:23:50 UTC]{Color.RESET} Analyzing root cause...")
        
        self.presenter.animate_step("Creating incident: INC-2025-0201-001")
        self.presenter.animate_step("Scoring severity: HIGH (revenue impacting)")
        self.presenter.animate_step("Calling LLM (GPT-4) for analysis")
        
        print(f"\n{Color.CYAN}LLM Analysis:{Color.RESET}")
        print(f"  Hypothesis 1: Payment gateway timeout (87% confidence)")
        print(f"  Hypothesis 2: Database pool exhaustion (65% confidence)")
        print(f"  Hypothesis 3: DDoS attack (31% confidence)")
        
        self.pipeline.triage_result = {
            "incident_id": "INC-2025-0201-001",
            "title": "Payment Processing Timeout Spike",
            "severity": "HIGH",
            "affected_merchants": 3
        }
        
        self.pipeline.add_analysis({
            "top_hypothesis": "Payment gateway timeout",
            "confidence": "87%"
        })
        
        self.log_event("reason", "root_cause_agent", "Root cause identified: Payment gateway timeout", {
            "confidence": "87%",
            "hypothesis": "Payment gateway experiencing timeout issues"
        })
        
        print(f"\n{Color.GREEN}{Color.BOLD}[REASON COMPLETE]{Color.RESET}")
        print(f"  Incident ID: INC-2025-0201-001")
        print(f"  Top hypothesis: Payment gateway timeout")
        print(f"  Time taken: 4 seconds")
        
        self.presenter.wait()
        
        # === DECIDE PHASE ===
        self.presenter.print_stage(Stage.DECIDE, "ACTIVE")
        self.presenter.print_section("DECIDE Phase", "Time: 10:00 - 15:00")
        
        print(f"\n{Color.DIM}[14:24:00 UTC]{Color.RESET} Planning remediation actions...")
        
        self.presenter.animate_step("Generating action recommendations")
        self.presenter.animate_step("Scoring risk levels")
        
        print(f"\n{Color.CYAN}Proposed Actions:{Color.RESET}")
        print(f"  Action 1: Escalate to payments engineering (LOW risk)")
        print(f"  Action 2: Draft customer notification (LOW risk)")
        print(f"  Action 3: Enable retry logic (MEDIUM risk)")
        
        self.presenter.animate_step("Running policy approval gate")
        self.presenter.animate_step("Action 1: AUTO-APPROVED (low-risk escalation)")
        self.presenter.animate_step("Action 2: AUTO-APPROVED (pre-approved template)")
        self.presenter.animate_step("Action 3: PENDING (requires manual approval)")
        
        self.log_event("decide", "action_planner", "Actions planned and approved", {
            "approved_actions": 2,
            "pending_actions": 1
        })
        
        print(f"\n{Color.GREEN}{Color.BOLD}[DECIDE COMPLETE]{Color.RESET}")
        print(f"  Actions approved: 2")
        print(f"  Actions pending: 1")
        print(f"  Time taken: 3 seconds")
        
        self.presenter.wait()
        
        # === ACT PHASE ===
        self.presenter.print_stage(Stage.ACT, "ACTIVE")
        self.presenter.print_section("ACT Phase", "Time: 15:00 - 25:00")
        
        print(f"\n{Color.DIM}[14:24:05 UTC]{Color.RESET} Executing approved actions...")
        
        # Action 1: Create GitHub Issue
        print(f"\n{Color.BOLD}→ Action 1: Create GitHub Escalation Issue{Color.RESET}")
        self.presenter.animate_step("Authenticating with GitHub API")
        
        issue_body = """
## Payment Processing Timeout Spike

**Incident:** INC-2025-0201-001
**Severity:** HIGH
**Start Time:** 2025-02-01 14:23:45 UTC

### Root Cause (Confidence: 87%)
Payment gateway (Stripe/PayPal) experiencing timeout issues.

### Evidence
- All failures tagged as payment_timeout
- No errors in our application logs
- Multiple payment methods affected
- Affects all merchants equally

### Impact
- Merchants affected: 3
- Error rate: 6.0% (baseline: 0.8%)
- Estimated revenue impact: $45,000/hour

### Immediate Next Steps
1. Contact payment gateway support
2. Monitor recovery metrics
3. Prepare merchant notification

**Automated by:** CyberCypher Incident Response System
"""
        
        github_issue = self.github.create_issue(
            title="Payment Processing Timeout Spike - INC-2025-0201-001",
            body=issue_body,
            labels=["critical", "payment", "auto-escalated"]
        )
        
        if github_issue:
            self.pipeline.github_issue = github_issue
            issue_num = github_issue.get("number")
            issue_url = github_issue.get("html_url") or github_issue.get("url")
            is_real = "simulated" not in github_issue
            
            self.log_event("act", "execution_agent", "GitHub issue created", {
                "issue_number": issue_num,
                "url": issue_url,
                "real": is_real
            })
            
            print(f"\n{Color.GREEN}✓ GitHub Issue Created{Color.RESET}")
            print(f"  Issue #: {issue_num}")
            print(f"  URL: {issue_url}")
            if is_real:
                print(f"  Status: {Color.GREEN}REAL GitHub issue created{Color.RESET}")
            else:
                print(f"  Status: {Color.DIM}(Simulated - set GITHUB_TOKEN for real issues){Color.RESET}")
            print(f"  Labels: critical, payment, auto-escalated")
        else:
            print(f"\n{Color.RED}✗ GitHub Issue creation failed{Color.RESET}")
            github_issue = {"number": 4521, "url": "https://github.com/cybershop/payments/issues/4521"}
        
        self.presenter.wait()
        
        # Action 2: Send notifications
        print(f"\n{Color.BOLD}→ Action 2: Send Notifications{Color.RESET}")
        self.presenter.animate_step("Posting to #incidents Slack channel")
        
        issue_url = github_issue.get("html_url") or github_issue.get("url")
        slack_msg = f"INCIDENT ALERT: Payment timeout spike. GitHub issue: {issue_url}"
        print(f"\n{Color.CYAN}Slack Message:{Color.RESET}")
        print(f"  {slack_msg}")
        
        self.log_event("act", "execution_agent", "Slack notification sent", {
            "channel": "#incidents"
        })
        
        print(f"{Color.GREEN}✓ Slack notification sent{Color.RESET}")
        
        self.presenter.wait()
        
        # Action 3: Create monitoring dashboard
        print(f"\n{Color.BOLD}→ Action 3: Setup Monitoring{Color.RESET}")
        self.presenter.animate_step("Creating DataDog dashboard")
        self.presenter.animate_step("Setting up real-time alerts")
        
        dashboard_url = "https://datadog.com/dashboard/incident-4521"
        print(f"\n{Color.GREEN}✓ Monitoring dashboard created{Color.RESET}")
        print(f"  URL: {dashboard_url}")
        
        self.log_event("act", "execution_agent", "Monitoring setup complete", {
            "dashboard_url": dashboard_url
        })
        
        print(f"\n{Color.GREEN}{Color.BOLD}[ACT COMPLETE]{Color.RESET}")
        print(f"  Actions executed: 3")
        print(f"  External references created: 1 GitHub issue, 1 Slack message, 1 dashboard")
        print(f"  Time taken: 8 seconds")
        
        self.presenter.wait()
        
        # === RECOVERY ===
        self.presenter.print_stage(Stage.OBSERVE, "PENDING")
        print(f"\n{Color.DIM}[14:24:27 UTC]{Color.RESET} Monitoring recovery...")
        
        print(f"\n{Color.BOLD}Recovery Timeline:{Color.RESET}")
        self.presenter.animate_step("Error rate: 6.0% → 4.2%")
        self.presenter.animate_step("Error rate: 4.2% → 1.8%")
        self.presenter.animate_step("Error rate: 1.8% → 0.9%")
        
        print(f"\n{Color.GREEN}{Color.BOLD}[INCIDENT RESOLVED]{Color.RESET}")
        print(f"  Resolution time: 22 minutes")
        print(f"  Root cause: Payment gateway provider recovery")
        print(f"  Status: CLOSED")
        
        self.log_event("resolve", "feedback_agent", "Incident resolved", {
            "resolution_time": "22 minutes",
            "recovery_successful": True
        })
        
        self.presenter.wait()
        
        # === SUMMARY ===
        self.presenter.print_header("SIMULATION COMPLETE")
        
        print(f"{Color.BOLD}{Color.GREEN}Incident INC-2025-0201-001 Successfully Handled{Color.RESET}\n")
        
        print(f"{Color.BOLD}Timeline:{Color.RESET}")
        print(f"  Detection → Action: 5 seconds (automated)")
        print(f"  Total resolution: 22 minutes (infrastructure)")
        print(f"  GitHub issue created: #{github_issue['number']}")
        print(f"  GitHub URL: {github_issue['url']}\n")
        
        print(f"{Color.BOLD}System Activity:{Color.RESET}")
        print(f"  Events processed: 47")
        print(f"  Agents involved: 9")
        print(f"  LLM calls: 2")
        print(f"  External integrations used: 3 (GitHub, Slack, DataDog)")
        print(f"  API calls: {len(self.github.api_calls)}\n")
        
        print(f"{Color.BOLD}Agent Contributions:{Color.RESET}")
        print(f"  OBSERVE: Signal ingestion, normalization, anomaly detection")
        print(f"  REASON: Triage, root cause analysis")
        print(f"  DECIDE: Action planning, policy approval")
        print(f"  ACT: GitHub escalation, notifications, monitoring")
        print(f"  LEARN: Outcome recording, pattern updates\n")
        
        # Print full timeline
        self.presenter.print_section("Full Event Timeline", "")
        
        for event in self.timeline:
            timestamp = event["timestamp"].strftime("%H:%M:%S")
            print(f"{Color.DIM}[{timestamp}]{Color.RESET} {event['component']}: {event['message']}")
        
        print(f"\n{Color.CYAN}{Color.BOLD}Demo Simulation Complete!{Color.RESET}")
        print(f"GitHub Issue Reference: {github_issue['url']}")
        
        self.presenter.wait("Press Enter to exit...")
        
        return 0


def load_env_file():
    """Load environment variables from .env file"""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    os.environ.setdefault(key.strip(), value)


def main():
    """Main simulation entry point"""
    # Load .env file first
    load_env_file()
    
    # Check for GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    github_api = GitHubAPI(token=github_token)
    
    presenter = TerminalPresenter(slow_mode=True, github_api=github_api)
    
    try:
        simulation = IncidentSimulation(presenter, github_api)
        return simulation.run_simulation()
    except KeyboardInterrupt:
        print(f"\n\n{Color.RED}Simulation interrupted by user{Color.RESET}")
        return 1
    except Exception as e:
        print(f"\n\n{Color.RED}Error: {str(e)}{Color.RESET}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
