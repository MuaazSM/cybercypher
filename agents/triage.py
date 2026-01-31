from typing import Optional
from sqlalchemy.orm import Session
from models.incidents import IncidentCluster, Incident
from db.models import IncidentClusterDB, IncidentDB
from tools.llm_router import LLMRouter
from uuid import uuid4
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class IncidentTriageAgent:
    """
    Triage clusters into confirmed incidents.
    
    Responsibilities:
    - Filter false positives (false alerts, non-critical clusters)
    - Calculate severity based on impact and rate
    - Generate human-readable titles and summaries
    - Assess business impact (checkout, revenue, trust)
    - Create incident records in database
    """
    
    def __init__(self, llm_router: LLMRouter):
        """
        Initialize triage agent.
        
        Args:
            llm_router: LLMRouter instance for description generation
        """
        self.llm = llm_router
        
        # Severity rules (rule-based + LLM-enhanced)
        self.severity_rules = {
            "critical": {
                "checkout_component": True,
                "min_merchants": 20,
                "min_rate": 20.0
            },
            "high": {
                "checkout_component": True,
                "min_merchants": 10,
                "min_rate": 10.0
            },
            "medium": {
                "min_merchants": 5,
                "min_rate": 5.0
            },
            "low": {}  # default
        }
    
    def triage_cluster(self, cluster: IncidentCluster, db: Session) -> Optional[Incident]:
        """
        Evaluate cluster and create incident if warranted.
        
        Args:
            cluster: IncidentCluster from pattern detection
            db: SQLAlchemy session
        
        Returns:
            Incident if created, None if filtered out
        """
        logger.info(f"[IncidentTriageAgent] Triaging cluster {cluster.cluster_id}")
        
        # Check if incident already exists for this cluster
        existing = db.query(IncidentDB).filter(
            IncidentDB.cluster_id == cluster.cluster_id
        ).first()
        
        if existing:
            # Update existing incident
            existing.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"[IncidentTriageAgent] Cluster already has incident {existing.incident_id}")
            return self._db_to_pydantic(existing)
        
        # Determine if this cluster warrants an incident
        is_incident = self._is_incident(cluster)
        
        if not is_incident:
            logger.info(f"[IncidentTriageAgent] Cluster {cluster.cluster_id} filtered out (not incident)")
            return None
        
        # Calculate severity
        severity = self._calculate_severity(cluster)
        logger.info(f"[IncidentTriageAgent] Calculated severity: {severity}")
        
        # Generate title and summary using LLM
        title, summary = self._generate_incident_description(cluster)
        
        # Determine business impact
        impacts_checkout = self._impacts_checkout(cluster)
        impacts_revenue = self._impacts_revenue(cluster)
        customer_trust_risk = self._assess_trust_risk(cluster, severity)
        
        # Create incident
        incident = Incident(
            incident_id=uuid4(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            status="open",
            severity=severity,
            title=title,
            summary=summary,
            cluster_id=cluster.cluster_id,
            affected_merchants=cluster.affected_merchant_ids,
            blast_radius_estimate=f"{cluster.merchant_count} merchants",
            impacts_checkout=impacts_checkout,
            impacts_revenue=impacts_revenue,
            customer_trust_risk=customer_trust_risk
        )
        
        # Store in DB
        db_incident = IncidentDB(
            incident_id=incident.incident_id,
            created_at=incident.created_at,
            updated_at=incident.updated_at,
            status=incident.status,
            severity=incident.severity,
            title=incident.title,
            summary=incident.summary,
            cluster_id=incident.cluster_id,
            affected_merchants=json.dumps(incident.affected_merchants),
            blast_radius_estimate=incident.blast_radius_estimate,
            impacts_checkout=incident.impacts_checkout,
            impacts_revenue=incident.impacts_revenue,
            customer_trust_risk=incident.customer_trust_risk
        )
        db.add(db_incident)
        db.commit()
        
        logger.info(f"[IncidentTriageAgent] Created {severity} incident: {title}")
        return incident
    
    def _is_incident(self, cluster: IncidentCluster) -> bool:
        """
        Determine if cluster is a real incident.
        
        Filters:
        - Must be spiking (not stable/declining)
        - Must have minimum event count (5+)
        - Must affect multiple merchants OR be critical component
        
        Args:
            cluster: IncidentCluster to evaluate
        
        Returns:
            True if incident, False if false positive
        """
        # Must be spiking
        if cluster.trend != "spiking":
            logger.debug(f"[IncidentTriageAgent] Filtered: trend is {cluster.trend}, not spiking")
            return False
        
        # Must have minimum events
        if cluster.event_count < 5:
            logger.debug(f"[IncidentTriageAgent] Filtered: only {cluster.event_count} events")
            return False
        
        # Must affect multiple merchants (or be critical component)
        if cluster.merchant_count < 3 and "CHECKOUT" not in cluster.primary_signature:
            logger.debug(f"[IncidentTriageAgent] Filtered: only {cluster.merchant_count} merchants")
            return False
        
        return True
    
    def _calculate_severity(self, cluster: IncidentCluster) -> str:
        """
        Rule-based severity calculation.
        
        Hierarchy:
        - Critical: checkout + many merchants + high rate
        - High: checkout/auth + many merchants OR very high rate
        - Medium: moderate merchants + rate
        - Low: everything else
        
        Args:
            cluster: IncidentCluster with metrics
        
        Returns:
            Severity: "critical", "high", "medium", or "low"
        """
        # Critical: checkout + many merchants + high rate
        if ("CHECKOUT" in cluster.primary_signature and 
            cluster.merchant_count >= 20 and 
            cluster.rate_per_hour >= 20):
            logger.debug("[IncidentTriageAgent] Severity: CRITICAL (checkout + scale + rate)")
            return "critical"
        
        # High: checkout OR auth + many merchants
        if (("CHECKOUT" in cluster.primary_signature or "AUTH" in cluster.primary_signature) and
            cluster.merchant_count >= 10):
            logger.debug("[IncidentTriageAgent] Severity: HIGH (checkout/auth + scale)")
            return "high"
        
        # High: very high rate regardless of component
        if cluster.rate_per_hour >= 30:
            logger.debug("[IncidentTriageAgent] Severity: HIGH (extreme rate)")
            return "high"
        
        # Medium: moderate merchants + rate
        if cluster.merchant_count >= 5 and cluster.rate_per_hour >= 5:
            logger.debug("[IncidentTriageAgent] Severity: MEDIUM (moderate scale + rate)")
            return "medium"
        
        # Low: everything else
        logger.debug("[IncidentTriageAgent] Severity: LOW (default)")
        return "low"
    
    def _generate_incident_description(self, cluster: IncidentCluster) -> tuple[str, str]:
        """
        Use LLM to generate human-readable title and summary.
        
        Args:
            cluster: IncidentCluster with data
        
        Returns:
            Tuple of (title, summary)
        """
        prompt = f"""
                Given this incident cluster, generate a clear, actionable title and summary.

                Cluster Details:
                - Signature: {cluster.primary_signature}
                - Affected Merchants: {cluster.merchant_count}
                - Event Count: {cluster.event_count}
                - Rate: {cluster.rate_per_hour:.1f} events/hour (baseline: {cluster.baseline_rate:.1f})
                - Stage Distribution: {cluster.stage_distribution}
                - Component Distribution: {cluster.component_distribution}
                - Trend: {cluster.trend}

                Generate:
                1. A concise title (max 100 chars, actionable)
                2. A 2-3 sentence summary (what is happening, why it matters)

                Response format:
                TITLE: <title here>
                SUMMARY: <summary here>
                """
        
        try:
            response = self.llm.invoke(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            # Parse response
            lines = response.strip().split('\n')
            title = "Unknown incident"
            summary = "Incident detected in system"
            
            for line in lines:
                if line.startswith("TITLE:"):
                    title = line.replace("TITLE:", "").strip()
                elif line.startswith("SUMMARY:"):
                    summary = line.replace("SUMMARY:", "").strip()
            
            logger.debug(f"[IncidentTriageAgent] Generated title: {title}")
            return title, summary
        
        except Exception as e:
            logger.warning(f"[IncidentTriageAgent] LLM generation failed: {e}, using fallback")
            # Fallback to template
            title = f"{cluster.primary_signature} affecting {cluster.merchant_count} merchants"
            summary = f"Spike detected: {cluster.event_count} events ({cluster.rate_per_hour:.1f}/hr) vs baseline {cluster.baseline_rate:.1f}/hr"
            return title, summary
    
    def _impacts_checkout(self, cluster: IncidentCluster) -> bool:
        """
        Check if incident affects checkout flow.
        
        Args:
            cluster: IncidentCluster
        
        Returns:
            True if checkout component affected
        """
        return "CHECKOUT" in cluster.primary_signature
    
    def _impacts_revenue(self, cluster: IncidentCluster) -> bool:
        """
        Check if incident affects revenue-critical flows.
        
        Args:
            cluster: IncidentCluster
        
        Returns:
            True if checkout/orders/payment affected
        """
        revenue_components = ["CHECKOUT", "ORDERS", "PAYMENT"]
        return any(comp in cluster.primary_signature for comp in revenue_components)
    
    def _assess_trust_risk(self, cluster: IncidentCluster, severity: str) -> str:
        """
        Assess customer trust and reputation risk.
        
        Args:
            cluster: IncidentCluster
            severity: Incident severity level
        
        Returns:
            Risk level: "low", "medium", or "high"
        """
        if severity == "critical":
            return "high"
        if severity == "high":
            return "medium"
        if cluster.merchant_count > 10:
            return "medium"
        return "low"
    
    def _db_to_pydantic(self, db_incident: IncidentDB) -> Incident:
        """
        Convert database model to Pydantic model.
        
        Args:
            db_incident: IncidentDB instance
        
        Returns:
            Incident Pydantic model
        """
        return Incident(
            incident_id=db_incident.incident_id,
            created_at=db_incident.created_at,
            updated_at=db_incident.updated_at,
            status=db_incident.status,
            severity=db_incident.severity,
            title=db_incident.title,
            summary=db_incident.summary,
            cluster_id=db_incident.cluster_id,
            affected_merchants=json.loads(db_incident.affected_merchants),
            blast_radius_estimate=db_incident.blast_radius_estimate,
            impacts_checkout=db_incident.impacts_checkout,
            impacts_revenue=db_incident.impacts_revenue,
            customer_trust_risk=db_incident.customer_trust_risk
        )
    
    def get_triage_stats(self, db: Session) -> dict:
        """
        Get triage statistics.
        
        Args:
            db: SQLAlchemy session
        
        Returns:
            Dictionary with incident counts by severity and status
        """
        total_clusters = db.query(IncidentClusterDB).filter(
            IncidentClusterDB.trend == "spiking"
        ).count()
        
        total_incidents = db.query(IncidentDB).count()
        
        by_severity = {}
        for severity in ["critical", "high", "medium", "low"]:
            count = db.query(IncidentDB).filter(
                IncidentDB.severity == severity
            ).count()
            by_severity[severity] = count
        
        by_status = {}
        for status in ["open", "investigating", "resolved", "wontfix"]:
            count = db.query(IncidentDB).filter(
                IncidentDB.status == status
            ).count()
            by_status[status] = count
        
        return {
            "total_clusters": total_clusters,
            "total_incidents": total_incidents,
            "by_severity": by_severity,
            "by_status": by_status,
            "triage_rate": f"{(total_incidents / total_clusters * 100):.1f}%" if total_clusters > 0 else "0%"
        }
