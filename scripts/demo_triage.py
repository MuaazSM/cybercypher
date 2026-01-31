import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from db.database import SessionLocal
from db.models import IncidentClusterDB, IncidentDB
from models.incidents import IncidentCluster
from agents.triage import IncidentTriageAgent
from tools.llm_router import LLMRouter, LLMConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_triage():
    """Demo incident triage with synthetic cluster."""
    print("\n" + "=" * 80)
    print("INCIDENT TRIAGE AGENT DEMO (Agent 4)")
    print("=" * 80)
    
    # Initialize LLM router
    print("\n[1] Initializing LLM Router...")
    llm_config = LLMConfig()  # Reads from env vars
    
    if not any([llm_config.openai_api_key, llm_config.groq_api_key, llm_config.gemini_api_key]):
        print("⚠️  WARNING: No LLM API keys found in environment")
        print("   Set OPENAI_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY")
        print("   Using fallback (non-LLM) descriptions\n")
    
    try:
        llm = LLMRouter(llm_config)
        print("✓ LLM Router initialized")
    except Exception as e:
        print(f"✗ LLM Router initialization warning: {e}")
        llm = LLMRouter(llm_config)  # Will use fallbacks
    
    # Create triage agent
    triage_agent = IncidentTriageAgent(llm)
    print("✓ IncidentTriageAgent initialized")
    
    db = SessionLocal()
    
    try:
        print("\n[2] Checking for spiking clusters...")
        spiking_clusters = db.query(IncidentClusterDB).filter(
            IncidentClusterDB.trend == "spiking"
        ).all()
        
        print(f"✓ Found {len(spiking_clusters)} spiking clusters")
        
        if not spiking_clusters:
            print("   Creating synthetic cluster for demo...")
            
            # Create synthetic spike for demo
            now = datetime.utcnow()
            synthetic_cluster = IncidentClusterDB(
                cluster_id=uuid4(),
                created_at=now,
                updated_at=now,
                primary_signature="WEBHOOK::DELIVERY_FAIL::orders/create::STAGE2",
                top_signatures=json.dumps([
                    "WEBHOOK::DELIVERY_FAIL::orders/create::STAGE2",
                    "WEBHOOK::DELIVERY_FAIL::orders/update::STAGE2"
                ]),
                affected_merchant_ids=json.dumps([f"m_{i:04d}" for i in range(1001, 1018)]),
                merchant_count=17,
                event_count=53,
                trend="spiking",
                first_seen=now - timedelta(minutes=30),
                last_seen=now,
                rate_per_hour=15.3,
                baseline_rate=2.1,
                sample_event_ids=json.dumps([str(uuid4()) for _ in range(5)]),
                stage_distribution=json.dumps({1: 2, 2: 48, 3: 3}),
                component_distribution=json.dumps({"webhook": 53})
            )
            db.add(synthetic_cluster)
            db.commit()
            
            spiking_clusters = [synthetic_cluster]
            print("   ✓ Created synthetic cluster")
        
        # Triage each cluster
        print(f"\n[3] Triaging {len(spiking_clusters)} clusters...")
        triaged_count = 0
        filtered_count = 0
        
        for db_cluster in spiking_clusters:
            # Convert to Pydantic
            cluster = IncidentCluster(
                cluster_id=db_cluster.cluster_id,
                created_at=db_cluster.created_at,
                updated_at=db_cluster.updated_at,
                top_signatures=json.loads(db_cluster.top_signatures),
                primary_signature=db_cluster.primary_signature,
                affected_merchant_ids=json.loads(db_cluster.affected_merchant_ids),
                merchant_count=db_cluster.merchant_count,
                event_count=db_cluster.event_count,
                trend=db_cluster.trend,
                first_seen=db_cluster.first_seen,
                last_seen=db_cluster.last_seen,
                rate_per_hour=db_cluster.rate_per_hour,
                baseline_rate=db_cluster.baseline_rate,
                sample_event_ids=json.loads(db_cluster.sample_event_ids),
                stage_distribution=json.loads(db_cluster.stage_distribution),
                component_distribution=json.loads(db_cluster.component_distribution)
            )
            
            # Triage
            incident = triage_agent.triage_cluster(cluster, db)
            
            if incident:
                triaged_count += 1
                print(f"\n   ✓ Incident created: {incident.title}")
                print(f"     - Severity: {incident.severity}")
                print(f"     - Status: {incident.status}")
                print(f"     - Merchants: {len(incident.affected_merchants)} affected")
                print(f"     - Checkout Impact: {incident.impacts_checkout}")
                print(f"     - Revenue Impact: {incident.impacts_revenue}")
                print(f"     - Trust Risk: {incident.customer_trust_risk}")
                print(f"     - Summary: {incident.summary[:80]}...")
            else:
                filtered_count += 1
                print(f"   ✗ Cluster filtered out (not incident)")
        
        # Statistics
        print(f"\n[4] Triage Statistics")
        print(f"   - Clusters: {len(spiking_clusters)}")
        print(f"   - Created Incidents: {triaged_count}")
        print(f"   - Filtered Out: {filtered_count}")
        
        stats = triage_agent.get_triage_stats(db)
        print(f"\n   Overall Statistics:")
        print(f"   - Total Clusters (Spiking): {stats['total_clusters']}")
        print(f"   - Total Incidents: {stats['total_incidents']}")
        print(f"   - Triage Rate: {stats['triage_rate']}")
        print(f"   - By Severity: {stats['by_severity']}")
        print(f"   - By Status: {stats['by_status']}")
        
        # Show sample incident details
        if triaged_count > 0:
            print(f"\n[5] Sample Incident Details")
            latest_incident = db.query(IncidentDB).order_by(
                IncidentDB.created_at.desc()
            ).first()
            
            if latest_incident:
                print(f"   - ID: {latest_incident.incident_id}")
                print(f"   - Title: {latest_incident.title}")
                print(f"   - Created: {latest_incident.created_at}")
                print(f"   - Cluster ID: {latest_incident.cluster_id}")
                merchants = json.loads(latest_incident.affected_merchants)
                print(f"   - Affected Merchants: {merchants[:3]}... ({len(merchants)} total)")
        
        print("\n" + "=" * 80)
        print("✅ INCIDENT TRIAGE DEMO COMPLETE")
        print("=" * 80)
        
    finally:
        db.close()


if __name__ == "__main__":
    demo_triage()
