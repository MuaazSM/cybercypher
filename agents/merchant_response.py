import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MerchantResponseAgent:
    """Handles merchant communication and support ticket monitoring"""

    def __init__(self, llm_client=None, zendesk_client=None):
        self.llm = llm_client
        self.zendesk = zendesk_client  # External Zendesk integration
        self.response_log = []

    def classify_issue_type(self, incident: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Classify if issue is technical or customer-facing (non-technical) using LLM"""
        classification = {
            "incident_id": incident.get("id"),
            "is_technical": True,
            "is_customer_facing": False,
            "category": "technical",
            "confidence": 0.0,
            "reasoning": "",
            "requires_merchant_response": False,
            "suggested_action": "technical_resolution"
        }

        # Use LLM to classify based on incident root cause
        if self.llm:
            prompt = f"""Analyze this incident and classify it for merchant communication:

Title: {incident.get('title', '')}
Root Cause: {incident.get('root_cause', '')}
Description: {incident.get('description', '')}
Affected Merchants: {incident.get('affected_merchants', 0)}
Customer Complaints: {incident.get('customer_complaints', 0)}
Severity: {incident.get('severity', 'medium')}

Classify as:
- "billing": Billing/payment related issue affecting merchant revenue
- "service_unavailability": Service downtime merchants should be notified about
- "data_issue": Data inconsistency or data loss customers should know about
- "technical": Technical issue that doesn't need merchant communication
- "other": Other category

Respond in JSON format:
{{
    "is_technical": bool,
    "is_customer_facing": bool,
    "category": "billing|service_unavailability|data_issue|technical|other",
    "confidence": 0.0-1.0,
    "reasoning": "explanation of classification",
    "requires_merchant_response": bool,
    "communication_priority": "urgent|high|normal|low"
}}"""

            try:
                response = self.llm.generate(prompt)
                if response:
                    result = response
                    if isinstance(result, str):
                        import json
                        result = json.loads(result)
                    
                    classification.update(result)
                    classification["is_customer_facing"] = result.get("is_customer_facing", False)
                    classification["requires_merchant_response"] = result.get("requires_merchant_response", False)
                    logger.info(f"[Agent 11] Classified incident {incident.get('id')}: {result.get('category')} (confidence: {result.get('confidence', 0):.2f})")
            except Exception as e:
                logger.error(f"[Agent 11] Classification error: {e}")
                # Fallback to default classification based on root cause keywords
                root_cause = incident.get('root_cause', '').lower()
                if any(keyword in root_cause for keyword in ['payment', 'billing', 'stripe', 'paypal']):
                    classification["category"] = "billing"
                    classification["is_customer_facing"] = True
                    classification["requires_merchant_response"] = True
                    classification["confidence"] = 0.8
                elif any(keyword in root_cause for keyword in ['timeout', 'unavailable', 'down', 'service']):
                    classification["category"] = "service_unavailability"
                    classification["is_customer_facing"] = True
                    classification["requires_merchant_response"] = True
                    classification["confidence"] = 0.8

        return classification

    def generate_merchant_response(
        self,
        incident: Dict[str, Any],
        classification: Dict[str, Any],
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """Generate automated response to merchants using LLM if non-technical issue"""

        if not classification.get("requires_merchant_response"):
            return None

        response = {
            "incident_id": incident.get("id"),
            "timestamp": datetime.utcnow().isoformat(),
            "merchants": incident.get("affected_merchants", []),
            "message_type": classification.get("category", "unknown"),
            "status": "pending",
            "response_template": "",
            "personalized_solutions": [],
            "escalation_path": ""
        }

        # Use LLM to generate professional merchant response
        category = classification.get("category", "other")
        
        if self.llm:
            prompt = f"""Generate a professional, empathetic merchant communication for this incident:

Incident Title: {incident.get('title', '')}
Category: {category}
Description: {incident.get('description', '')}
Root Cause: {incident.get('root_cause', '')}
Duration: {incident.get('duration', 'unknown')}
Resolution: {incident.get('resolution', 'In progress')}
Affected Merchants: {len(incident.get('affected_merchants', []))}
Revenue Impact: {incident.get('revenue_impact', 'N/A')}

Write a professional customer communication that:
1. Acknowledges the issue and apologizes
2. Explains what happened in simple terms (avoid technical jargon)
3. Describes actions taken to resolve it
4. Provides next steps for the merchant
5. Offers contact information for support

Keep it concise (under 300 words) but thorough.
Format as plain text, not markdown.

Also provide JSON response:
{{
    "response_template": "the generated message",
    "tone": "apologetic|informative|reassuring",
    "key_points": ["point1", "point2", "point3"],
    "follow_up_recommended": bool
}}"""

            try:
                result = self.llm.generate(prompt)
                if result:
                    if isinstance(result, str):
                        import json
                        # Try to extract JSON from response
                        try:
                            json_start = result.rfind('{')
                            json_end = result.rfind('}') + 1
                            if json_start >= 0 and json_end > json_start:
                                json_str = result[json_start:json_end]
                                parsed = json.loads(json_str)
                                response["response_template"] = parsed.get("response_template", result)
                                response["personalized_solutions"] = parsed.get("key_points", [])
                            else:
                                response["response_template"] = result
                        except:
                            response["response_template"] = result
                    else:
                        response["response_template"] = result.get("response_template", str(result))
                        response["personalized_solutions"] = result.get("key_points", [])
                    
                    response["status"] = "ready_to_send"
                    logger.info(f"[Agent 11] Generated merchant response for incident {incident.get('id')}")
            except Exception as e:
                logger.error(f"[Agent 11] Response generation error: {e}")
                response["response_template"] = self._generic_response_template(incident)
                response["status"] = "ready_to_send"
        else:
            # Fallback if no LLM
            response["response_template"] = self._generic_response_template(incident)
            response["status"] = "ready_to_send"

        # If no response generated, escalate
        if not response["response_template"]:
            response["status"] = "pending_manual_review"
            response["escalation_path"] = "senior_support_agent"

        return response

    def send_merchant_responses(
        self,
        responses: List[Dict[str, Any]],
        incident: Dict[str, Any],
        db: Session
    ) -> Dict[str, Any]:
        """Send personalized responses to affected merchants"""

        send_result = {
            "incident_id": incident.get("id"),
            "total_merchants": len(incident.get("affected_merchants", [])),
            "responses_sent": 0,
            "responses_failed": 0,
            "responses_pending_review": 0,
            "channels_used": [],
            "delivery_status": {}
        }

        for response in responses:
            if response.get("status") == "pending_manual_review":
                send_result["responses_pending_review"] += 1
                logger.info(f"Escalating response for incident {response['incident_id']} to manual review")
                continue

            # Send via multiple channels
            merchants = response.get("merchants", [])
            for merchant_id in merchants:
                try:
                    # Channel 1: Direct email
                    email_sent = self._send_email(
                        merchant_id,
                        response.get("response_template", ""),
                        incident
                    )

                    # Channel 2: In-app notification
                    notification_sent = self._send_in_app_notification(
                        merchant_id,
                        response.get("response_template", ""),
                        incident
                    )

                    # Channel 3: Zendesk ticket reply (if integrated)
                    if self.zendesk:
                        ticket_reply = self._reply_to_support_ticket(
                            merchant_id,
                            response.get("response_template", ""),
                            incident
                        )
                    else:
                        ticket_reply = False

                    if email_sent or notification_sent or ticket_reply:
                        send_result["responses_sent"] += 1
                        send_result["delivery_status"][merchant_id] = {
                            "email": email_sent,
                            "in_app": notification_sent,
                            "support_ticket": ticket_reply
                        }

                        if "email" in [email_sent and "email"] or []:
                            send_result["channels_used"].append("email")
                        if notification_sent:
                            send_result["channels_used"].append("in_app")
                        if ticket_reply:
                            send_result["channels_used"].append("support_ticket")
                    else:
                        send_result["responses_failed"] += 1

                except Exception as e:
                    logger.error(f"Failed to send response to merchant {merchant_id}: {e}")
                    send_result["responses_failed"] += 1

        return send_result

    def monitor_support_tickets(
        self,
        incident: Dict[str, Any],
        db: Session
    ) -> Dict[str, Any]:
        """Monitor and track support tickets related to the incident using LLM for sentiment analysis"""

        monitoring_data = {
            "incident_id": incident.get("id"),
            "monitoring_start": datetime.utcnow().isoformat(),
            "active_tickets": [],
            "resolved_tickets": [],
            "pending_tickets": [],
            "avg_resolution_time": 0,
            "customer_satisfaction_score": 0.0,
            "sentiment_analysis": "",
            "follow_up_required": False
        }

        if self.zendesk:
            # Fetch related support tickets
            tickets = self._fetch_related_tickets(incident.get("id"))

            for ticket in tickets:
                ticket_status = {
                    "ticket_id": ticket.get("id"),
                    "merchant_id": ticket.get("requester_id"),
                    "status": ticket.get("status"),
                    "priority": ticket.get("priority"),
                    "created_at": ticket.get("created_at"),
                    "updated_at": ticket.get("updated_at"),
                    "resolution_time": self._calculate_resolution_time(ticket),
                    "satisfaction": ticket.get("satisfaction_rating", 0),
                    "comments": ticket.get("comments", [])
                }

                if ticket.get("status") == "solved":
                    monitoring_data["resolved_tickets"].append(ticket_status)
                elif ticket.get("status") in ["new", "open", "pending"]:
                    monitoring_data["active_tickets"].append(ticket_status)
                else:
                    monitoring_data["pending_tickets"].append(ticket_status)

            # Calculate metrics
            if monitoring_data["resolved_tickets"]:
                avg_time = sum(
                    t.get("resolution_time", 0) 
                    for t in monitoring_data["resolved_tickets"]
                ) / len(monitoring_data["resolved_tickets"])
                monitoring_data["avg_resolution_time"] = avg_time

            if monitoring_data["resolved_tickets"]:
                avg_satisfaction = sum(
                    t.get("satisfaction", 0)
                    for t in monitoring_data["resolved_tickets"]
                ) / len(monitoring_data["resolved_tickets"])
                monitoring_data["customer_satisfaction_score"] = avg_satisfaction

            # Use LLM to analyze customer sentiment from ticket comments
            if self.llm and monitoring_data["resolved_tickets"]:
                all_comments = []
                for ticket in monitoring_data["resolved_tickets"]:
                    all_comments.extend(ticket.get("comments", []))
                
                if all_comments:
                    sentiment_prompt = f"""Analyze the sentiment and tone of these customer support comments related to an incident:

Comments:
{chr(10).join(all_comments[:5])}

Provide:
1. Overall sentiment (positive, neutral, negative)
2. Key themes in customer feedback
3. Areas for improvement
4. Recommendations for follow-up

Respond in JSON:
{{
    "overall_sentiment": "positive|neutral|negative",
    "sentiment_score": 0.0-1.0,
    "key_themes": ["theme1", "theme2"],
    "areas_for_improvement": ["area1", "area2"],
    "follow_up_recommended": bool
}}"""
                    
                    try:
                        result = self.llm.generate(sentiment_prompt)
                        if result:
                            if isinstance(result, str):
                                try:
                                    json_start = result.rfind('{')
                                    json_end = result.rfind('}') + 1
                                    if json_start >= 0 and json_end > json_start:
                                        sentiment_json = json.loads(result[json_start:json_end])
                                        monitoring_data["sentiment_analysis"] = sentiment_json.get("overall_sentiment", "neutral")
                                        if sentiment_json.get("follow_up_recommended"):
                                            monitoring_data["follow_up_required"] = True
                                except:
                                    pass
                        logger.info(f"[Agent 11] Sentiment analysis complete for incident {incident.get('id')}")
                    except Exception as e:
                        logger.error(f"[Agent 11] Sentiment analysis error: {e}")

            # Check if follow-up needed
            if monitoring_data["active_tickets"] or monitoring_data["customer_satisfaction_score"] < 0.7:
                monitoring_data["follow_up_required"] = True

        return monitoring_data

    def close_support_tickets(
        self,
        incident: Dict[str, Any],
        resolution_summary: str,
        db: Session
    ) -> Dict[str, Any]:
        """Close support tickets with resolution summary"""

        close_result = {
            "incident_id": incident.get("id"),
            "tickets_closed": 0,
            "tickets_failed": 0,
            "closure_timestamp": datetime.utcnow().isoformat(),
            "resolution_summary": resolution_summary
        }

        if self.zendesk:
            tickets = self._fetch_related_tickets(incident.get("id"))

            for ticket in tickets:
                try:
                    closed = self._close_zendesk_ticket(
                        ticket.get("id"),
                        resolution_summary
                    )

                    if closed:
                        close_result["tickets_closed"] += 1
                    else:
                        close_result["tickets_failed"] += 1

                except Exception as e:
                    logger.error(f"Failed to close ticket {ticket.get('id')}: {e}")
                    close_result["tickets_failed"] += 1

        return close_result

    # Helper methods

    def _billing_response_template(self, incident: Dict[str, Any]) -> str:
        return f"""Dear Valued Customer,

We've identified and resolved a billing-related issue that may have affected your account.

**What happened:**
{incident.get('description', 'Your billing system experienced a temporary issue.')}

**What we're doing:**
- Our team has resolved the underlying cause
- All affected transactions are being reviewed
- You will receive a separate communication regarding any corrections needed

**Your next steps:**
1. Review your recent transactions
2. Contact our billing team if you have questions
3. Check your inbox for follow-up communications

We apologize for any inconvenience.

Best regards,
Support Team"""

    def _service_response_template(self, incident: Dict[str, Any]) -> str:
        return f"""Dear Valued Customer,

We've successfully resolved the service availability issue you experienced.

**Service Status:** ✓ RESTORED

**Resolution Details:**
- Incident ID: {incident.get('id')}
- Impact Duration: {incident.get('duration', 'N/A')}
- Root Cause: {incident.get('root_cause', 'Resolved')}

**Our Response:**
- Immediate mitigation deployed
- Monitoring enhanced to prevent recurrence
- Post-incident review completed

Your service is now fully operational. If you experience any issues, please contact support immediately.

Best regards,
Support Team"""

    def _generic_response_template(self, incident: Dict[str, Any]) -> str:
        return f"""Dear Valued Customer,

Thank you for your patience. We've completed our investigation and resolution.

**Incident:** {incident.get('title', 'Service Issue')}
**Status:** RESOLVED
**Timestamp:** {datetime.utcnow().isoformat()}

For detailed information or if you have questions, please reply to this message or contact our support team.

Best regards,
Support Team"""

    def _generate_billing_solutions(self, incident: Dict[str, Any]) -> List[str]:
        return [
            "Review and reconcile affected transactions",
            "Apply credits if necessary",
            "Set up additional monitoring on billing system",
            "Notify finance team for audit trail"
        ]

    def _generate_service_solutions(self, incident: Dict[str, Any]) -> List[str]:
        return [
            "Implement enhanced monitoring",
            "Schedule infrastructure review",
            "Add redundancy to critical paths",
            "Create escalation procedures"
        ]

    def _send_email(self, merchant_id: str, message: str, incident: Dict) -> bool:
        """Send email to merchant"""
        logger.info(f"Sending email to merchant {merchant_id} for incident {incident.get('id')}")
        # Integration with email service (SendGrid, AWS SES, etc.)
        return True

    def _send_in_app_notification(self, merchant_id: str, message: str, incident: Dict) -> bool:
        """Send in-app notification"""
        logger.info(f"Sending in-app notification to merchant {merchant_id}")
        # Integration with in-app notification system
        return True

    def _reply_to_support_ticket(self, merchant_id: str, message: str, incident: Dict) -> bool:
        """Reply to Zendesk support ticket"""
        if not self.zendesk:
            return False
        logger.info(f"Replying to support tickets for merchant {merchant_id}")
        # Integration with Zendesk API
        return True

    def _fetch_related_tickets(self, incident_id: str) -> List[Dict]:
        """Fetch support tickets related to incident"""
        if not self.zendesk:
            return []
        # Query Zendesk for tickets tagged with incident ID
        return []

    def _calculate_resolution_time(self, ticket: Dict) -> float:
        """Calculate time to resolve ticket in hours"""
        created = ticket.get("created_at")
        updated = ticket.get("updated_at")
        if created and updated:
            delta = updated - created
            return delta.total_seconds() / 3600
        return 0.0

    def _close_zendesk_ticket(self, ticket_id: str, resolution_summary: str) -> bool:
        """Close a Zendesk ticket with resolution"""
        if not self.zendesk:
            return False
        logger.info(f"Closing Zendesk ticket {ticket_id}")
        # Integration with Zendesk API to close ticket
        return True
