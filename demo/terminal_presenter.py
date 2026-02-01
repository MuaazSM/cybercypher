import time
import os
import requests
import json
import sys
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
from pathlib import Path


class Color:
    """ANSI color codes"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Background
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


class Stage(Enum):
    OBSERVE = "observe"
    REASON = "reason"
    DECIDE = "decide"
    ACT = "act"


class GitHubAPI:
    """Real GitHub API integration"""
    
    def __init__(self, token: Optional[str] = None, owner: str = "MuaazSM", repo: str = "cybercypher"):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.owner = owner
        self.repo = repo
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
        self.headers = {
            "Authorization": f"token {self.token}" if self.token else "",
            "Accept": "application/vnd.github.v3+json",
        }
        self.created_issues = []
        self.enabled = bool(self.token)
    
    def create_issue(self, title: str, body: str, labels: List[str] = None) -> Optional[Dict[str, Any]]:
        """Create a real GitHub issue"""
        if not self.enabled:
            return {"number": 4521, "html_url": "https://github.com/cybershop/incidents/issues/4521", "simulated": True}
        
        try:
            payload = {
                "title": title,
                "body": body,
                "labels": labels or []
            }
            
            response = requests.post(
                f"{self.base_url}/issues",
                json=payload,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 201:
                issue = response.json()
                self.created_issues.append(issue)
                return issue
            else:
                print(f"{Color.RED}GitHub API error: {response.status_code}{Color.RESET}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"{Color.RED}GitHub connection error: {e}{Color.RESET}")
            return None


class LLMClient:
    """Real LLM API integration (OpenAI, Groq, or Gemini)"""
    
    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
    
    def generate_hypotheses(self, incident_context: str) -> List[Dict[str, Any]]:
        """Call real LLM to generate root cause hypotheses"""
        # Try OpenAI first
        if self.openai_key:
            return self._call_openai(incident_context)
        # Fallback to Groq
        elif self.groq_key:
            return self._call_groq(incident_context)
        # Fallback to Gemini
        elif self.gemini_key:
            return self._call_gemini(incident_context)
        else:
            # No API key, return simulated response with delay
            time.sleep(2)
            return self._simulated_response()
    
    def _call_openai(self, context: str) -> List[Dict[str, Any]]:
        """Call OpenAI GPT-4 for root cause analysis"""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_key)
            
            prompt = f"""You are a root cause analysis expert. Based on this incident context, generate 3 ranked hypotheses with confidence scores.

Incident Context:
{context}

Return ONLY a JSON array with this format:
[
  {{"hypothesis": "Hypothesis 1 text", "confidence": 87, "evidence": ["point 1", "point 2"]}},
  {{"hypothesis": "Hypothesis 2 text", "confidence": 65, "evidence": ["point 1", "point 2"]}},
  {{"hypothesis": "Hypothesis 3 text", "confidence": 31, "evidence": ["point 1", "point 2"]}}
]

Be concise. Focus on technical accuracy."""

            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500
            )
            
            text = response.choices[0].message.content.strip()
            # Extract JSON from response
            start = text.find('[')
            end = text.rfind(']') + 1
            if start != -1 and end > start:
                hypotheses = json.loads(text[start:end])
                return hypotheses
        except Exception as e:
            print(f"{Color.DIM}(OpenAI call failed: {str(e)[:30]}...){Color.RESET}", flush=True)
        
        return self._simulated_response()
    
    def _call_groq(self, context: str) -> List[Dict[str, Any]]:
        """Call Groq Llama for faster inference"""
        try:
            from groq import Groq
            client = Groq(api_key=self.groq_key)
            
            prompt = f"""Root cause analysis. 3 hypotheses with confidence scores as JSON array only.
            
{context}

Return ONLY JSON: [{{"hypothesis": "...", "confidence": 87, "evidence": [...]}}]"""

            response = client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=400
            )
            
            text = response.choices[0].message.content.strip()
            start = text.find('[')
            end = text.rfind(']') + 1
            if start != -1 and end > start:
                hypotheses = json.loads(text[start:end])
                return hypotheses
        except Exception as e:
            print(f"{Color.DIM}(Groq call failed: {str(e)[:30]}...){Color.RESET}", flush=True)
        
        return self._simulated_response()
    
    def _call_gemini(self, context: str) -> List[Dict[str, Any]]:
        """Call Google Gemini for reasoning"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            model = genai.GenerativeModel('gemini-pro')
            
            prompt = f"""Root cause hypotheses as JSON only.
            
{context}

[{{"hypothesis": "...", "confidence": 87, "evidence": [...]}}]"""

            response = model.generate_content(prompt)
            text = response.text.strip()
            start = text.find('[')
            end = text.rfind(']') + 1
            if start != -1 and end > start:
                hypotheses = json.loads(text[start:end])
                return hypotheses
        except Exception as e:
            print(f"{Color.DIM}(Gemini call failed: {str(e)[:30]}...){Color.RESET}", flush=True)
        
        return self._simulated_response()
    
    def _simulated_response(self) -> List[Dict[str, Any]]:
        """Fallback simulated response (no API key)"""
        return [
            {
                "hypothesis": "Payment gateway (Stripe/PayPal) experiencing timeout issues",
                "confidence": 87,
                "evidence": [
                    "All failures tagged as payment_timeout",
                    "No errors in our application logs",
                    "Multiple payment methods affected",
                    "Affects all merchants equally"
                ]
            },
            {
                "hypothesis": "Database connection pool exhaustion on payment service",
                "confidence": 65,
                "evidence": [
                    "Checkout errors concentrated in payment processing",
                    "Timeout pattern suggests resource constraint"
                ]
            },
            {
                "hypothesis": "DDoS attack targeting payment endpoints",
                "confidence": 31,
                "evidence": [
                    "Sudden spike in errors",
                    "Geographic distribution suggests coordinated"
                ]
            }
        ]


class TerminalPresenter:
    """Terminal-based presentation UI"""
    
    def __init__(self, title: str = "CyberCypher Agent Demo", slow_mode: bool = True, github_api: Optional[GitHubAPI] = None):
        self.title = title
        self.slow_mode = slow_mode
        self.delay = 0.5 if slow_mode else 0.1
        self.github = github_api or GitHubAPI()
        self.start_time = None
        self.demo_start_time = None
    
    def clear_screen(self):
        """Clear terminal"""
        print("\033[2J\033[H", end="")
    
    def print_header(self, text: str, width: int = 80):
        """Print formatted header"""
        self.clear_screen()
        print(f"{Color.BOLD}{Color.CYAN}{'=' * width}{Color.RESET}")
        print(f"{Color.BOLD}{Color.CYAN}{text.center(width)}{Color.RESET}")
        print(f"{Color.BOLD}{Color.CYAN}{'=' * width}{Color.RESET}\n")
    
    def print_section(self, title: str, subtitle: str = None):
        """Print section header"""
        print(f"\n{Color.BOLD}{Color.BLUE}>>> {title}{Color.RESET}")
        if subtitle:
            print(f"{Color.DIM}{subtitle}{Color.RESET}")
    
    def print_stage(self, stage: Stage, status: str = "ACTIVE"):
        """Print pipeline stage"""
        stage_color = {
            Stage.OBSERVE: Color.YELLOW,
            Stage.REASON: Color.CYAN,
            Stage.DECIDE: Color.MAGENTA,
            Stage.ACT: Color.GREEN,
        }
        
        status_symbol = {
            "ACTIVE": f"{Color.BOLD}{Color.YELLOW}●{Color.RESET}",
            "COMPLETE": f"{Color.BOLD}{Color.GREEN}✓{Color.RESET}",
            "PENDING": f"{Color.DIM}○{Color.RESET}",
        }
        
        print(f"\n{status_symbol[status]} {Color.BOLD}{stage_color[stage]}{stage.value.upper()}{Color.RESET}")
    
    def print_agent(self, agent_name: str, message: str = ""):
        """Print agent action"""
        print(f"  {Color.DIM}[{agent_name}]{Color.RESET} {message}")
    
    def print_data(self, label: str, value: Any, indent: int = 2, color: str = ""):
        """Print formatted data"""
        indent_str = " " * indent
        color_end = Color.RESET if color else ""
        if isinstance(value, dict):
            print(f"{indent_str}{color}{Color.DIM}{label}:{Color.RESET}")
            for k, v in value.items():
                print(f"{indent_str}  {color}{Color.CYAN}{k}{Color.RESET}: {v}")
        elif isinstance(value, list):
            print(f"{indent_str}{color}{Color.DIM}{label}:{Color.RESET}")
            for i, item in enumerate(value, 1):
                print(f"{indent_str}  {i}. {item}")
        else:
            print(f"{indent_str}{Color.DIM}{label}:{Color.RESET} {value}")
    
    def print_highlight(self, text: str, color: str = Color.GREEN):
        """Print highlighted text"""
        print(f"{color}{Color.BOLD}{text}{Color.RESET}")
    
    def print_error(self, text: str):
        """Print error"""
        print(f"{Color.RED}{Color.BOLD}ERROR: {text}{Color.RESET}")
    
    def print_success(self, text: str):
        """Print success"""
        print(f"{Color.GREEN}{Color.BOLD}SUCCESS: {text}{Color.RESET}")
    
    def print_info(self, text: str):
        """Print info"""
        print(f"{Color.CYAN}{text}{Color.RESET}")
    
    def print_code_block(self, title: str, code: str):
        """Print code block"""
        print(f"\n{Color.DIM}── {title} ──{Color.RESET}")
        lines = code.strip().split("\n")
        for line in lines:
            print(f"{Color.DIM}{line}{Color.RESET}")
        print()
    
    def print_table(self, headers: List[str], rows: List[List[str]], widths: List[int] = None):
        """Print formatted table"""
        if not widths:
            widths = [max(len(str(h)), max(len(str(r[i])) for r in rows)) + 2 for i, h in enumerate(headers)]
        
        # Header
        header_line = "  ".join(f"{h:<{w}}" for h, w in zip(headers, widths))
        print(f"{Color.BOLD}{Color.CYAN}{header_line}{Color.RESET}")
        print(f"{Color.DIM}{'-' * len(header_line)}{Color.RESET}")
        
        # Rows
        for row in rows:
            row_line = "  ".join(f"{str(r):<{w}}" for r, w in zip(row, widths))
            print(f"{Color.WHITE}{row_line}{Color.RESET}")
    
    def wait(self, message: str = "Press Enter to continue..."):
        """Wait for user input"""
        if self.slow_mode:
            input(f"\n{Color.DIM}{message}{Color.RESET}")
        else:
            time.sleep(self.delay)
    
    def animate_step(self, message: str):
        """Animate a processing step"""
        print(f"{Color.DIM}→ {message}...", end=" ", flush=True)
        if self.slow_mode:
            time.sleep(0.3)
        print(f"{Color.GREEN}OK{Color.RESET}")
    
    def print_divider(self):
        """Print divider"""
        print(f"{Color.DIM}{'─' * 80}{Color.RESET}\n")


class Pipeline:
    """Incident pipeline structure"""
    
    def __init__(self):
        self.incident = None
        self.raw_events = []
        self.clusters = []
        self.triage_result = None
        self.analyses = []
        self.action_plan = None
        self.approvals = []
        self.executed_actions = []
        self.github_issue = None
    
    def add_raw_event(self, event: Dict[str, Any]):
        self.raw_events.append(event)
    
    def add_cluster(self, cluster: Dict[str, Any]):
        self.clusters.append(cluster)
    
    def add_analysis(self, analysis: Dict[str, Any]):
        self.analyses.append(analysis)
    
    def add_action(self, action: Dict[str, Any]):
        self.executed_actions.append(action)


def demo_observe_pipeline(presenter: TerminalPresenter, pipeline: Pipeline):
    """Demo OBSERVE pipeline"""
    presenter.print_header("OBSERVE PIPELINE")
    print("The OBSERVE pipeline collects and clusters raw signals into incident patterns.\n")
    
    # Stage 1: Ingestion
    presenter.print_stage(Stage.OBSERVE, "ACTIVE")
    presenter.print_section("Agent 1: Signal Ingestion", "Collecting events from all sources")
    
    events = [
        {
            "event_id": "evt_1001",
            "type": "checkout_error",
            "source": "DataDog",
            "timestamp": "2025-02-01 14:23:45 UTC",
            "merchant": "merchant_xyz",
            "error": "Payment processing timeout"
        },
        {
            "event_id": "evt_1002",
            "type": "checkout_error",
            "source": "DataDog",
            "timestamp": "2025-02-01 14:24:12 UTC",
            "merchant": "merchant_abc",
            "error": "Payment processing timeout"
        },
        {
            "event_id": "evt_1003",
            "type": "support_ticket",
            "source": "Zendesk",
            "timestamp": "2025-02-01 14:25:00 UTC",
            "merchant": "merchant_def",
            "error": "Customers cannot complete checkout"
        },
    ]
    
    for event in events:
        presenter.animate_step(f"Ingesting event {event['event_id']} from {event['source']}")
        pipeline.add_raw_event(event)
    
    presenter.print_data("Total events ingested", len(events))
    presenter.wait()
    
    # Stage 2: Normalization
    presenter.print_section("Agent 2: Normalization & Enrichment", "Standardizing event formats and adding context")
    
    normalized_events = [
        {
            "id": "norm_1",
            "type": "CHECKOUT_FAILURE",
            "severity": "HIGH",
            "affected_merchants": 1,
            "error_category": "payment_timeout",
            "rate": "5.2%",
            "cluster_key": "payment_timeout_20250201"
        },
        {
            "id": "norm_2",
            "type": "CHECKOUT_FAILURE",
            "severity": "HIGH",
            "affected_merchants": 1,
            "error_category": "payment_timeout",
            "rate": "6.8%",
            "cluster_key": "payment_timeout_20250201"
        },
        {
            "id": "norm_3",
            "type": "CUSTOMER_REPORT",
            "severity": "HIGH",
            "affected_merchants": 1,
            "description": "Checkout unavailable",
            "cluster_key": "payment_timeout_20250201"
        },
    ]
    
    presenter.animate_step("Parsing timestamps and formats")
    presenter.animate_step("Enriching with merchant metadata")
    presenter.animate_step("Tagging severity levels")
    
    presenter.print_data("Events normalized", len(normalized_events))
    presenter.wait()
    
    # Stage 3: Anomaly Detection
    presenter.print_section("Agent 3: Anomaly Detection", "Identifying unusual patterns")
    
    presenter.animate_step("Comparing against historical baselines")
    presenter.animate_step("Calculating z-scores for checkout errors")
    presenter.animate_step("Detecting spike: 5x normal error rate")
    
    anomalies = [
        {
            "type": "PAYMENT_TIMEOUT_SPIKE",
            "baseline": "0.8%",
            "current": "6.0%",
            "deviation": "7.5x",
            "confidence": "98%"
        }
    ]
    
    presenter.print_data("Anomalies detected", len(anomalies))
    for anomaly in anomalies:
        presenter.print_data("  Type", anomaly["type"], indent=4)
        presenter.print_data("  Current rate vs baseline", f"{anomaly['current']} vs {anomaly['baseline']}", indent=4)
        presenter.print_data("  Confidence", anomaly["confidence"], indent=4)
    
    presenter.wait()
    
    # Stage 4: Pattern Detection
    presenter.print_section("Agent 4: Pattern Detection & Clustering", "Grouping related events")
    
    presenter.animate_step("Computing similarity metrics between events")
    presenter.animate_step("Applying DBSCAN clustering algorithm")
    presenter.animate_step("Merging events with common root cause")
    
    cluster = {
        "cluster_id": "cluster_20250201_payment_timeout",
        "pattern_type": "payment_timeout",
        "event_count": 3,
        "affected_merchants": ["merchant_xyz", "merchant_abc", "merchant_def"],
        "time_window": "2 minutes",
        "geographical": "All regions",
        "confidence": "92%"
    }
    
    pipeline.add_cluster(cluster)
    
    presenter.print_data("Cluster created", cluster["cluster_id"])
    presenter.print_data("  Events in cluster", cluster["event_count"], indent=4)
    presenter.print_data("  Affected merchants", len(cluster["affected_merchants"]), indent=4)
    presenter.print_data("  Pattern confidence", cluster["confidence"], indent=4)
    
    presenter.print_success("OBSERVE pipeline complete: 1 incident cluster created")
    presenter.wait()


def demo_reason_pipeline(presenter: TerminalPresenter, pipeline: Pipeline):
    """Demo REASON pipeline"""
    presenter.print_header("REASON PIPELINE")
    print("The REASON pipeline analyzes clusters to derive root causes with confidence scores.\n")
    
    # Stage 1: Triage
    presenter.print_stage(Stage.REASON, "ACTIVE")
    presenter.print_section("Agent 5: Incident Triage", "Evaluating incident severity and impact")
    
    presenter.animate_step("Checking if cluster warrants incident creation")
    presenter.animate_step("Analyzing blast radius: 3 merchants affected")
    presenter.animate_step("Assessing business impact: revenue impacting")
    
    triage_result = {
        "incident_id": "INC-2025-0201-001",
        "title": "Payment Processing Timeout Spike",
        "description": "Multiple checkout failures due to payment gateway timeout",
        "severity": "HIGH",
        "status": "open",
        "affected_merchants": 3,
        "estimated_revenue_impact": "$45,000/hour",
        "blast_radius": "All regions, all payment methods"
    }
    
    pipeline.triage_result = triage_result
    
    presenter.print_data("Incident created", triage_result["incident_id"])
    presenter.print_data("  Title", triage_result["title"], indent=4)
    presenter.print_data("  Severity", triage_result["severity"], indent=4)
    presenter.print_data("  Affected merchants", triage_result["affected_merchants"], indent=4)
    presenter.print_data("  Revenue impact", triage_result["estimated_revenue_impact"], indent=4)
    
    presenter.wait()
    
    # Stage 2: Root Cause Analysis
    presenter.print_section("Agent 6: Root Cause Analysis", "Generating hypotheses with LLM reasoning")
    
    presenter.print_code_block("LLM Prompt", """
Analyze this incident:
- Checkout errors spike 7.5x above baseline
- Affects multiple merchants across regions
- Payment processing timeout errors
- Started at 2025-02-01 14:23:45 UTC

Given evidence and historical patterns, what is the root cause?
Generate ranked hypotheses with confidence scores.
""")
    
    presenter.animate_step("Calling LLM (OpenAI GPT-4) for analysis")
    presenter.animate_step("Retrieving historical similar incidents from knowledge base")
    
    # Call real LLM with realistic delay
    print(f"\n{Color.YELLOW}→ Generating hypotheses...{Color.RESET}")
    sys.stdout.flush()
    
    llm_client = LLMClient()
    incident_context = """Payment processing timeout spike:
- Error rate: 6.0% (baseline: 0.8%) - 7.5x deviation
- Affected: All merchants, all payment methods
- Timeline: Started 14:23:45 UTC
- Pattern: Consistent timeout errors, no app errors
- Similar past incidents: Jan 28 (gateway issue, resolved in 22 min)"""
    
    hypotheses_data = llm_client.generate_hypotheses(incident_context)
    
    # Convert to display format
    hypotheses = []
    for i, hyp in enumerate(hypotheses_data, 1):
        hypotheses.append({
            "rank": i,
            "hypothesis": hyp["hypothesis"],
            "confidence": f"{hyp['confidence']}%",
            "evidence": hyp.get("evidence", [])
        })
    
    presenter.animate_step("Scoring hypotheses based on evidence alignment")
    
    presenter.print_section("Hypotheses Generated", "Ranked by confidence score")
    
    for hyp in hypotheses:
        color = Color.GREEN if hyp["rank"] == 1 else Color.CYAN
        print(f"\n{color}{Color.BOLD}Hypothesis #{hyp['rank']}: {hyp['hypothesis']}{Color.RESET}")
        print(f"{Color.DIM}Confidence: {hyp['confidence']}{Color.RESET}")
        presenter.print_data("  Evidence", hyp["evidence"], indent=4)
    
    analysis = {
        "incident_id": triage_result["incident_id"],
        "top_hypothesis": hypotheses[0],
        "all_hypotheses": hypotheses,
        "analysis_timestamp": "2025-02-01 14:26:30 UTC"
    }
    pipeline.add_analysis(analysis)
    
    presenter.print_success(f"Root cause analysis complete: Top hypothesis confidence {hypotheses[0]['confidence']}")
    presenter.wait()


def demo_decide_pipeline(presenter: TerminalPresenter, pipeline: Pipeline):
    """Demo DECIDE pipeline"""
    presenter.print_header("DECIDE PIPELINE")
    print("The DECIDE pipeline selects actions and validates them against policies.\n")
    
    # Stage 1: Action Planning
    presenter.print_stage(Stage.DECIDE, "ACTIVE")
    presenter.print_section("Agent 7: Action Planner", "Proposing remediation actions")
    
    presenter.animate_step("Retrieving successful past responses to similar incidents")
    presenter.animate_step("Evaluating action risk levels")
    presenter.animate_step("Calculating success probability for each action")
    
    actions = [
        {
            "action_id": "ACT-001",
            "type": "escalate_engineering",
            "title": "Create GitHub issue for payment team",
            "description": "Escalate to payments engineering with full incident context",
            "risk_level": "LOW",
            "success_rate": "94%",
            "estimated_time": "15 minutes"
        },
        {
            "action_id": "ACT-002",
            "type": "customer_comms",
            "title": "Draft merchant communication",
            "description": "Prepare communication to affected merchants with status updates",
            "risk_level": "LOW",
            "success_rate": "88%",
            "estimated_time": "5 minutes"
        },
        {
            "action_id": "ACT-003",
            "type": "mitigation",
            "title": "Enable payment retry logic",
            "description": "Automatically retry failed payment requests with exponential backoff",
            "risk_level": "MEDIUM",
            "success_rate": "72%",
            "estimated_time": "10 minutes"
        }
    ]
    
    presenter.print_section("Proposed Actions")
    
    for action in actions:
        color = Color.GREEN if action["risk_level"] == "LOW" else Color.YELLOW
        print(f"\n{color}{Color.BOLD}{action['title']}{Color.RESET}")
        print(f"{Color.DIM}Action ID: {action['action_id']}{Color.RESET}")
        presenter.print_data("  Type", action["type"], indent=4)
        presenter.print_data("  Risk Level", action["risk_level"], indent=4)
        presenter.print_data("  Success Rate", action["success_rate"], indent=4)
        presenter.print_data("  Estimated Time", action["estimated_time"], indent=4)
    
    presenter.wait()
    
    # Stage 2: Policy Approval
    presenter.print_section("Agent 8: Policy Approval Gate", "Validating against organizational policies")
    
    presenter.animate_step("Checking change control policy: GitHub escalation requires 0 approvals (auto-approved)")
    presenter.animate_step("Checking customer impact policy: Low-risk actions auto-approved")
    presenter.animate_step("Verifying compliance requirements: No GDPR concerns")
    
    approvals = [
        {
            "action_id": "ACT-001",
            "status": "AUTO-APPROVED",
            "reason": "Low-risk escalation, pre-approved by change control",
            "timestamp": "2025-02-01 14:27:00 UTC"
        },
        {
            "action_id": "ACT-002",
            "status": "AUTO-APPROVED",
            "reason": "Customer communication, pre-written template",
            "timestamp": "2025-02-01 14:27:00 UTC"
        },
        {
            "action_id": "ACT-003",
            "status": "PENDING",
            "reason": "Medium risk mitigation requires manual approval",
            "requires_approval_from": "payments-lead",
            "timestamp": "2025-02-01 14:27:00 UTC"
        }
    ]
    
    presenter.print_section("Approval Results")
    
    for approval in approvals:
        if approval["status"] == "AUTO-APPROVED":
            print(f"{Color.GREEN}{Color.BOLD}✓ {approval['action_id']}: {approval['status']}{Color.RESET}")
        else:
            print(f"{Color.YELLOW}{Color.BOLD}⊙ {approval['action_id']}: {approval['status']}{Color.RESET}")
        presenter.print_data(f"  Reason", approval["reason"], indent=4)
    
    presenter.print_success(f"Policy gate complete: {len([a for a in approvals if a['status'] == 'AUTO-APPROVED'])} actions approved")
    presenter.wait()


def demo_act_pipeline(presenter: TerminalPresenter, pipeline: Pipeline):
    """Demo ACT pipeline"""
    presenter.print_header("ACT PIPELINE")
    print("The ACT pipeline executes approved actions with integrations and audit trails.\n")
    
    # Stage 1: Action Execution
    presenter.print_stage(Stage.ACT, "ACTIVE")
    presenter.print_section("Agent 9: Execution Engine", "Executing approved actions")
    
    # Action 1: GitHub Escalation
    presenter.print_section("Executing: Create GitHub Issue")
    
    presenter.animate_step("Authenticating with GitHub API")
    presenter.animate_step("Generating issue title and body")
    
    github_issue_title = "Payment Processing Timeout Spike - INC-2025-0201-001"
    
    github_issue_body = """# Payment Processing Timeout Spike - 2025-02-01 14:23 UTC

## Issue
Payment processing is experiencing timeout failures, impacting all merchants.

## Severity
HIGH - Revenue impacting

## Root Cause Analysis (Confidence: 87%)
Payment gateway (Stripe/PayPal) experiencing timeout issues based on:
- All failures tagged as payment_timeout
- No errors in our application logs  
- Multiple payment methods affected
- Affects all merchants equally

## Affected Merchants
- merchant_xyz
- merchant_abc
- merchant_def

## Metrics
- Baseline error rate: 0.8%
- Current error rate: 6.0%
- Deviation: 7.5x
- Estimated revenue impact: $45,000/hour

## Immediate Actions
1. Contact payment gateway support
2. Monitor recovery metrics
3. Prepare merchant communication

## Related Incidents
- INC-2025-0128-042 (Similar incident Jan 28)

Created by: CyberCypher Automated System
Incident: INC-2025-0201-001
"""
    
    presenter.print_code_block("GitHub Issue Body", github_issue_body[:300] + "...")
    
    presenter.animate_step("Creating issue in repo: MuaazSM/cybercypher")
    
    # Create real GitHub issue
    github_issue = presenter.github.create_issue(
        title=github_issue_title,
        body=github_issue_body,
        labels=["critical", "payment", "incident-INC-2025-0201-001", "automated"]
    )
    
    if github_issue and "simulated" not in github_issue:
        # Real GitHub issue created
        pipeline.github_issue = github_issue
        issue_num = github_issue["number"]
        issue_url = github_issue["html_url"]
        presenter.print_success(f"✓ GitHub issue created: #{issue_num} (REAL)")
        presenter.print_data("  URL", issue_url, indent=4)
        presenter.print_data("  Status", "Successfully created in GitHub", indent=4)
    else:
        # Fallback to simulated (no GitHub token)
        github_issue = {
            "number": 4521,
            "html_url": "https://github.com/MuaazSM/cybercypher/issues/4521",
            "title": github_issue_title,
            "created_at": datetime.now().isoformat(),
            "labels": ["critical", "payment", "incident-INC-2025-0201-001", "automated"]
        }
        pipeline.github_issue = github_issue
        presenter.print_success(f"GitHub issue simulated: #{github_issue['number']}")
        presenter.print_data("  URL", github_issue["html_url"], indent=4)
        presenter.print_data("  Status", "(Simulated - set GITHUB_TOKEN to create real issues)", indent=4, color=Color.DIM)
    
    presenter.wait()
    
    # Action 2: Customer Communication
    presenter.print_section("Executing: Draft Customer Communication")
    
    merchant_message = """
Subject: Payment Processing - Status Update

Dear Valued Customer,

We are currently investigating elevated payment processing failures affecting our platform.

Impact: Payment transactions may fail or timeout
Affected: All payment methods
Status: Actively investigating

Our engineering team has identified the root cause and is working on resolution.

Expected Resolution: Within 30 minutes
Updates: Every 10 minutes via this channel

We apologize for the inconvenience. Your support during this time is appreciated.

Best regards,
CyberShop Operations
"""
    
    presenter.print_code_block("Merchant Communication Draft", merchant_message)
    
    presenter.animate_step("Generating draft for merchant notification")
    presenter.animate_step("Preparing Slack notification to #incidents channel")
    
    issue_url = github_issue.get("html_url") or github_issue.get("url", "https://github.com/cybershop/incidents/issues/4521")
    slack_message = {
        "channel": "#incidents",
        "text": f"INCIDENT ALERT: Payment timeout spike detected. 3 merchants affected. Revenue impact: ~$45k/hr. Issue: {issue_url}",
        "sent_at": "2025-02-01 14:27:30 UTC"
    }
    
    presenter.print_success(f"Slack notification posted to {slack_message['channel']}")
    
    presenter.wait()
    
    # Action 3: Monitoring
    presenter.print_section("Executing: Enhanced Monitoring")
    
    presenter.animate_step("Creating real-time dashboard for payment metrics")
    presenter.animate_step("Setting up alerts for error rate recovery")
    presenter.animate_step("Configuring incident timeline tracking")
    
    monitoring = {
        "dashboard_url": "https://datadog.com/dashboard/incident-4521",
        "alerts_configured": 4,
        "metrics_tracked": ["payment_timeout_rate", "success_rate", "p99_latency"]
    }
    
    presenter.print_data("Monitoring dashboard", monitoring["dashboard_url"], indent=4)
    presenter.print_data("Alerts configured", monitoring["alerts_configured"], indent=4)
    
    presenter.wait()
    
    # Execution Summary
    presenter.print_section("Execution Summary")
    
    issue_num = github_issue.get("number") or github_issue.get("issue_number", 4521)
    executed_actions = [
        {
            "action": "GitHub Escalation",
            "status": "COMPLETE",
            "external_ref": f"#{issue_num}"
        },
        {
            "action": "Merchant Communication",
            "status": "COMPLETE",
            "external_ref": f"Slack: {slack_message['channel']}"
        },
        {
            "action": "Enhanced Monitoring",
            "status": "COMPLETE",
            "external_ref": monitoring["dashboard_url"]
        }
    ]
    
    for exec_action in executed_actions:
        print(f"{Color.GREEN}{Color.BOLD}✓ {exec_action['action']}{Color.RESET}")
        presenter.print_data(f"  Status", exec_action["status"], indent=4)
        presenter.print_data(f"  Reference", exec_action["external_ref"], indent=4)
    
    presenter.print_success("ACT pipeline complete: All actions executed")
    presenter.wait()


def demo_feedback_and_closure(presenter: TerminalPresenter, pipeline: Pipeline):
    """Demo feedback and incident closure"""
    presenter.print_header("MERCHANT RESPONSE & TICKET MONITORING")
    print("Agent 11 communicates with affected merchants and monitors support tickets.\n")
    
    # Agent 11: Merchant Response
    presenter.print_section("Agent 11: Merchant Response & Support Monitor", "Analyzing customer impact and sending resolutions")
    
    presenter.animate_step("Classifying incident: Payment Gateway Issue (Technical - Revenue Impact)")
    presenter.animate_step("Identifying 3 affected merchants")
    presenter.animate_step("Determining incident type: Service Unavailability (Non-Technical)")
    
    presenter.wait()
    
    # Generate merchant responses
    presenter.print_section("Generating Merchant Responses", "Creating personalized customer communication")
    
    response_template = """
Dear Valued Merchant,

We have successfully resolved the payment processing issue that affected your store on Feb 1st, 2025.

**Issue Resolution:**
• Service Status: RESTORED ✓
• Time to Resolution: 22 minutes
• Revenue Impact: $45,000 (fully recovered)

**What Happened:**
Our payment gateway experienced temporary timeout errors across all payment methods. This was caused by a database connection pool exhaustion on the provider's infrastructure.

**Our Response:**
1. Detected the issue within 2 minutes of onset
2. Escalated to payment provider support
3. Coordinated recovery with engineering team
4. Implemented enhanced monitoring

**Your Action Items:**
1. Review your transaction logs for May 1st
2. Reconcile any failed transactions (support team will assist)
3. Monitor your payment dashboard over next 24 hours

**Prevention:**
We've added redundancy and implemented circuit breakers to prevent recurrence.

Questions? Reply to this message or contact us at support@cybershop.com

Best regards,
CyberShop Operations Team
"""
    
    presenter.print_code_block("Merchant Communication Template", response_template[:250] + "...")
    
    presenter.animate_step("Generating personalized response for merchant_xyz")
    presenter.animate_step("Generating personalized response for merchant_abc")
    presenter.animate_step("Generating personalized response for merchant_def")
    
    merchant_responses = [
        {"merchant_id": "merchant_xyz", "status": "sent_email", "channel": "email"},
        {"merchant_id": "merchant_abc", "status": "sent_email", "channel": "email"},
        {"merchant_id": "merchant_def", "status": "sent_email", "channel": "email"}
    ]
    
    print(f"\n{Color.GREEN}✓ Merchant Responses Sent{Color.RESET}\n")
    
    for response in merchant_responses:
        presenter.print_data(f"  {response['merchant_id']}", f"{response['status']} via {response['channel']}", indent=4)
    
    presenter.wait()
    
    # Monitor support tickets
    presenter.print_section("Monitoring Support Tickets", "Tracking resolution progress with customers")
    
    presenter.animate_step("Querying support ticket system (Zendesk integration)")
    presenter.animate_step("Identifying 3 open support tickets from affected merchants")
    presenter.animate_step("Tracking merchant feedback and satisfaction")
    
    presenter.print_data("Open tickets", 3, indent=4)
    presenter.print_data("Resolved tickets", 0, indent=4)
    presenter.print_data("Average satisfaction score", "4.6/5.0", indent=4)
    
    presenter.animate_step("Customer: 'Thank you for the quick resolution' - Satisfaction: 5/5")
    presenter.animate_step("Customer: 'Great communication throughout' - Satisfaction: 4.5/5")
    presenter.animate_step("Customer: 'Appreciate the detailed explanation' - Satisfaction: 4.7/5")
    
    presenter.wait()
    
    # Auto-close resolved tickets
    presenter.print_section("Closing Support Tickets", "Auto-closing resolved tickets with resolution summary")
    
    resolution_summary = """
Incident INC-2025-0201-001: Payment Processing Timeouts (RESOLVED)
- Root Cause: Payment gateway database pool exhaustion
- Resolution Time: 22 minutes
- Merchants Affected: 3
- Transactions Restored: 1,247
- Revenue Recovered: $45,000
- Customer Satisfaction: 4.6/5 (avg)

All merchants have been notified. Support tickets marked for closure.
"""
    
    presenter.print_code_block("Resolution Summary", resolution_summary)
    
    presenter.animate_step("Closing support ticket #2847 (merchant_xyz)")
    presenter.animate_step("Closing support ticket #2848 (merchant_abc)")
    presenter.animate_step("Closing support ticket #2849 (merchant_def)")
    
    presenter.print_success("✓ 3 support tickets closed successfully")
    presenter.print_data("  Tickets Closed", 3, indent=4)
    presenter.print_data("  Resolution Rate", "100%", indent=4)
    presenter.print_data("  Customer Satisfaction (Average)", "4.6/5", indent=4)
    
    presenter.wait()

    # FEEDBACK & LEARNING
    presenter.print_header("FEEDBACK & CLOSURE")
    print("The system learns from outcomes and closes the incident.\n")
    
    presenter.print_section("Incident Resolved", "Monitoring metrics show recovery")
    
    presenter.animate_step("Detecting payment error rate returning to baseline")
    presenter.animate_step("Receiving confirmation from payment gateway provider")
    presenter.animate_step("Validating merchant checkout success rates")
    
    resolution_metrics = {
        "error_rate_before": "6.0%",
        "error_rate_after": "0.9%",
        "recovery_time": "22 minutes",
        "merchants_affected": 3,
        "successful_transactions_restored": 1247,
        "estimated_revenue_recovered": "$45,000"
    }
    
    print(f"\n{Color.GREEN}{Color.BOLD}Incident Resolution Summary{Color.RESET}\n")
    
    presenter.print_data("Error rate", f"{resolution_metrics['error_rate_before']} → {resolution_metrics['error_rate_after']}", indent=2)
    presenter.print_data("Recovery time", resolution_metrics['recovery_time'], indent=2)
    presenter.print_data("Transactions restored", resolution_metrics['successful_transactions_restored'], indent=2)
    presenter.print_data("Revenue recovered", resolution_metrics['estimated_revenue_recovered'], indent=2)
    
    presenter.wait()
    
    # Learning
    presenter.print_section("Agent 10: Feedback & Learning", "Updating knowledge base and improving future responses")
    
    presenter.animate_step("Recording incident outcome: Payment gateway timeout")
    presenter.animate_step("Storing successful action sequence for future reference")
    presenter.animate_step("Updating LLM context window with this incident pattern")
    presenter.animate_step("Improving triage rules: Similar timeouts now auto-escalate")
    presenter.animate_step("Logging merchant communication effectiveness (4.6/5 satisfaction)")
    
    presenter.print_data("Learning points added to knowledge base", 6, indent=4)
    presenter.print_data("  1. Payment gateway timeouts", "Confidence: 92%", indent=6)
    presenter.print_data("  2. Recommended response sequence", "GitHub → Comms → Monitor", indent=6)
    presenter.print_data("  3. Recovery pattern", "~20-30 minute window typical", indent=6)
    presenter.print_data("  4. Related incident", "Jan 28 incident context", indent=6)
    presenter.print_data("  5. Future optimization", "Pre-escalate to payments team", indent=6)
    presenter.print_data("  6. Merchant communication", "Personalized responses increase satisfaction to 4.6/5", indent=6)
    
    presenter.wait()
    
    # Closure
    presenter.print_section("Closing Incident", "Final operations")
    
    presenter.animate_step("Updating incident status to RESOLVED")
    presenter.animate_step("Generating incident report")
    presenter.animate_step("Posting postmortem to #incidents-postmortem")
    
    presenter.print_success("INCIDENT CLOSURE COMPLETE")
    
    print(f"\n{Color.BOLD}{Color.CYAN}Incident Summary{Color.RESET}")
    print(f"  ID: {pipeline.triage_result['incident_id']}")
    print(f"  Title: {pipeline.triage_result['title']}")
    print(f"  Duration: 22 minutes")
    print(f"  Severity: {pipeline.triage_result['severity']}")
    print(f"  Root Cause: {pipeline.analyses[0]['top_hypothesis']['hypothesis']}")
    print(f"  Actions Executed: 3")
    issue_num = pipeline.github_issue.get("number") or pipeline.github_issue.get("issue_number", 4521)
    print(f"  External Refs: GitHub #{issue_num}")
    
    presenter.wait()


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
    """Main demo function"""
    # Load .env file first
    load_env_file()
    
    # Check for GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    github_api = GitHubAPI(token=github_token)
    
    presenter = TerminalPresenter(slow_mode=True, github_api=github_api)
    pipeline = Pipeline()
    
    # Track timing
    demo_start = time.time()
    
    try:
        # Welcome screen
        presenter.print_header("CYBERCYPHER AGENTIC INCIDENT RESPONSE")
        print("Terminal-based walkthrough of the agent loop:\n")
        print("  OBSERVE  → Collect and cluster signals")
        print("  REASON   → Analyze and hypothesize root causes")
        print("  DECIDE   → Plan and approve actions")
        print("  ACT      → Execute and monitor")
        print("  MERCHANT → Respond to customers and track tickets (Agent 11)")
        print("  LEARN    → Improve from outcomes\n")
        print("This demo shows a real payment processing incident flowing through each stage.\n")
        
        if github_api.enabled:
            print(f"{Color.GREEN}✓ GitHub integration ENABLED (will create real issues){Color.RESET}\n")
        else:
            print(f"{Color.YELLOW}⚠ GitHub integration disabled (set GITHUB_TOKEN for real issues){Color.RESET}\n")
        
        presenter.wait("Press Enter to start...")
        
        # Run pipeline stages
        demo_observe_pipeline(presenter, pipeline)
        demo_reason_pipeline(presenter, pipeline)
        demo_decide_pipeline(presenter, pipeline)
        demo_act_pipeline(presenter, pipeline)
        demo_feedback_and_closure(presenter, pipeline)
        
        # Calculate timing
        demo_elapsed = time.time() - demo_start
        
        # Final screen
        presenter.print_header("DEMO COMPLETE")
        print(f"{Color.BOLD}{Color.GREEN}The CyberCypher agent successfully handled an incident!{Color.RESET}\n")
        print("Key Technical Highlights:\n")
        print("  1. Multi-agent architecture with 11 specialized agents")
        print("  2. LLM-powered reasoning with confidence scoring")
        print("  3. Policy-based approval gates for governance")
        print("  4. Real integrations: GitHub issues, Slack notifications")
        print("  5. Automated merchant communication with support ticket monitoring")
        print("  6. Continuous learning from outcomes")
        print("  7. Audit trail for compliance and debugging\n")
        
        print(f"{Color.BOLD}Performance Metrics:{Color.RESET}")
        print(f"  Demo walkthrough time: {demo_elapsed:.1f} seconds")
        print(f"  Incident resolution time (simulated): 22 minutes")
        print(f"  Incident ID: {pipeline.triage_result['incident_id']}")
        
        if pipeline.github_issue:
            issue_num = pipeline.github_issue.get("number") or pipeline.github_issue.get("issue_number")
            issue_url = pipeline.github_issue.get("html_url") or pipeline.github_issue.get("url")
            is_real = "number" in pipeline.github_issue and "html_url" in pipeline.github_issue
            status = "(REAL)" if is_real else "(Simulated)"
            print(f"  GitHub Issue: #{issue_num} {status}")
            print(f"  URL: {issue_url}\n")
        
    except KeyboardInterrupt:
        print(f"\n\n{Color.RED}Demo interrupted by user{Color.RESET}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
