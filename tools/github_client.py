import httpx
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class GitHubIssue(BaseModel):
    """GitHub issue structure"""
    title: str
    body: str
    labels: List[str] = []
    assignees: List[str] = []


class GitHubClient:
    def __init__(self, token: str, repo_owner: str, repo_name: str):
        self.token = token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.base_url = "https://api.github.com"
    
    def create_engineering_escalation(
        self,
        incident_title: str,
        severity: str,
        hypothesis: str,
        evidence: List[str],
        affected_merchants: int,
        blast_radius: str,
        incident_id: str
    ) -> Optional[Dict[str, Any]]:
        """Create formatted engineering escalation issue"""
        
        # Map severity to priority label
        priority_labels = {
            "critical": "p0",
            "high": "p1",
            "medium": "p2",
            "low": "p3"
        }
        
        body = f"""## Incident Summary
**Incident ID:** `{incident_id}`
**Severity:** {severity.upper()}
**Affected Merchants:** {affected_merchants}
**Blast Radius:** {blast_radius}

## Root Cause Hypothesis
{hypothesis}

## Supporting Evidence
{self._format_list(evidence)}

## Next Steps
- [ ] Verify hypothesis with internal logs
- [ ] Implement fix or mitigation
- [ ] Test with affected merchants
- [ ] Update documentation if needed

---
*This issue was automatically created by the Agentic Support System*
"""
        
        labels = [
            "bug",
            "automated-escalation",
            priority_labels.get(severity, "p2")
        ]
        
        # Add component-specific labels based on title
        if "webhook" in incident_title.lower():
            labels.append("webhooks")
        if "api" in incident_title.lower():
            labels.append("api")
        if "checkout" in incident_title.lower():
            labels.append("checkout")
        
        issue = GitHubIssue(
            title=f"[{severity.upper()}] {incident_title}",
            body=body,
            labels=labels
        )
        
        return self.create_issue(issue)
    
    def create_issue(self, issue: GitHubIssue) -> Optional[Dict[str, Any]]:
        """Create GitHub issue via API"""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/issues"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        try:
            response = httpx.post(
                url,
                headers=headers,
                json=issue.model_dump(),
                timeout=15.0
            )
            response.raise_for_status()
            
            issue_data = response.json()
            print(f"[GitHub] Created issue #{issue_data['number']}: {issue_data['html_url']}")
            
            return {
                "issue_number": issue_data['number'],
                "issue_url": issue_data['html_url'],
                "issue_id": issue_data['id']
            }
        
        except Exception as e:
            print(f"[GitHub] Failed to create issue: {e}")
            return None
    
    def _format_list(self, items: List[str]) -> str:
        """Format list as markdown"""
        return "\n".join([f"- {item}" for item in items])


# Usage Example:
# github = GitHubClient(
#     token="ghp_YOUR_TOKEN",
#     repo_owner="your-org",
#     repo_name="support-escalations"
# )
# 
# result = github.create_engineering_escalation(
#     incident_title="Webhook delivery failures for Stage 2 merchants",
#     severity="high",
#     hypothesis="Missing webhook registration step in Stage 2 migration guide",
#     evidence=[
#         "12/17 affected merchants are in Stage 2",
#         "All failures on orders/create webhook",
#         "Similar to past incident INC_031"
#     ],
#     affected_merchants=17,
#     blast_radius="Stage 2 merchants, orders/create webhook only",
#     incident_id="inc_44"
# )
