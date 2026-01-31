import httpx
from typing import Dict, Any, Optional
from pydantic import BaseModel

class SlackMessage(BaseModel):
    """Slack message structure"""
    text: str
    blocks: Optional[list] = None

class SlackClient:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send_incident_alert(
        self,
        incident_title: str,
        severity: str,
        affected_merchants: int,
        hypothesis_summary: str,
        action_summary: str,
        incident_url: Optional[str] = None
    ) -> bool:
        """Send formatted incident alert"""
        
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢"
        }
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity_emoji.get(severity, '⚪')} New Incident Detected"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Title:*\n{incident_title}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Severity:*\n{severity.upper()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Affected Merchants:*\n{affected_merchants}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Root Cause Hypothesis:*\n{hypothesis_summary}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Recommended Actions:*\n{action_summary}"
                }
            }
        ]
        
        if incident_url:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{incident_url}|View Full Incident Details>"
                }
            })
        
        message = SlackMessage(
            text=f"New {severity} incident: {incident_title}",
            blocks=blocks
        )
        
        return self._send(message)
    
    def send_simple_message(self, text: str) -> bool:
        """Send simple text message"""
        message = SlackMessage(text=text)
        return self._send(message)
    
    def _send(self, message: SlackMessage) -> bool:
        """Internal method to POST to webhook"""
        try:
            response = httpx.post(
                self.webhook_url,
                json=message.model_dump(exclude_none=True),
                timeout=10.0
            )
            response.raise_for_status()
            print(f"[Slack] Message sent successfully")
            return True
        except Exception as e:
            print(f"[Slack] Failed to send message: {e}")
            return False

# Usage Example:
# slack = SlackClient(webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL")
# slack.send_incident_alert(
#     incident_title="Webhook failures for Stage 2 merchants",
#     severity="high",
#     affected_merchants=17,
#     hypothesis_summary="Migration step missing webhook registration",
#     action_summary="1. Create GitHub issue\n2. Draft merchant communication",
#     incident_url="http://localhost:8000/incidents/123"
# )
