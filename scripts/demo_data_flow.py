"""
Demo Data Flow - Complete end-to-end demonstration.

Shows:
1. Generating spike scenario
2. Agent 1: Ingesting raw events
3. Agent 2: Normalizing to clean events
4. Agent 3: Detecting incident patterns
"""

from simulator.event_generator import EventSimulator
from agents.ingestion import SignalIngestionAgent
from agents.normalization import NormalizationAgent
from db.database import SessionLocal
from db.models import RawEventDB, CleanEventDB, IncidentClusterDB
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demonstrate_data_flow():
    """Complete walkthrough of data flowing through Observe pipeline."""
    
    print("\n" + "=" * 80)
    print("OBSERVING DATA FLOW: RAW → CLEAN → CLUSTERS")
    print("=" * 80)
    
    # Initialize agents and simulator
    simulator = EventSimulator()
    ingestion = SignalIngestionAgent()
    normalization = NormalizationAgent()
    
    # STEP 1: Generate spike scenario
    print("\n[STEP 1] GENERATING SPIKE SCENARIO")
    print("-" * 80)
    print("Simulating: 50 webhook failures across 17 Stage 2 merchants")
    
    events = simulator.generate_spike_scenario(
        event_type="webhook_fail",
        error_pattern={"webhook": "orders/create", "error": "DELIVERY_FAIL"},
        merchant_count=17,
        event_count=50,
        migration_stage=2
    )
    
    affected_merchants = set(e.merchant_id for e in events)
    print(f"✓ Generated {len(events)} events")
    print(f"✓ Affected merchants: {len(affected_merchants)}")
    print(f"✓ Time range: {min(e.timestamp for e in events).strftime('%Y-%m-%d %H:%M:%S')} → "
          f"{max(e.timestamp for e in events).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"✓ Sample event: {events[0].event_type} from {events[0].merchant_id}")
    print(f"  Payload: {events[0].payload}")
    
    # STEP 2: Ingest events (Agent 1)
    print("\n[STEP 2] AGENT 1: SIGNAL INGESTION")
    print("-" * 80)
    print("Action: Writing raw events to events_raw table")
    
    db = SessionLocal()
    try:
        count = ingestion.ingest_batch(events, db)
        
        print(f"✓ Ingested {count} new events to events_raw")
        
        # Show database state
        raw_count = db.query(RawEventDB).count()
        print(f"✓ Total events in events_raw: {raw_count}")
        
        # Show sample
        sample_raw = db.query(RawEventDB).limit(1).first()
        if sample_raw:
            print(f"✓ Sample record:")
            print(f"  - ID: {sample_raw.event_id}")
            print(f"  - Type: {sample_raw.event_type}")
            print(f"  - Source: {sample_raw.source}")
            print(f"  - Idempotency Key: {sample_raw.idempotency_key}")
        
        # STEP 3: Normalize events (Agent 2)
        print("\n[STEP 3] AGENT 2: NORMALIZATION & ENRICHMENT")
        print("-" * 80)
        print("Action: Reading events_raw, writing to events_clean")
        print("        Extracting components, error codes, signatures")
        print("        Enriching with merchant context")
        
        normalized = normalization.process_raw_events(db, limit=100)
        
        print(f"✓ Normalized {normalized} events to events_clean")
        
        # Show database state
        clean_count = db.query(CleanEventDB).count()
        print(f"✓ Total events in events_clean: {clean_count}")
        
        # Show signature examples
        signatures = db.query(CleanEventDB.signature).distinct().limit(3).all()
        print(f"✓ Signatures generated:")
        for sig_row in signatures:
            sig = sig_row[0]
            count = db.query(CleanEventDB).filter(CleanEventDB.signature == sig).count()
            print(f"  - {sig} ({count} events)")
        
        # Show enrichment example
        sample_clean = db.query(CleanEventDB).limit(1).first()
        if sample_clean:
            print(f"✓ Sample enriched event:")
            print(f"  - Component: {sample_clean.component}")
            print(f"  - Error Code: {sample_clean.error_code}")
            print(f"  - Severity: {sample_clean.severity_hint}")
            print(f"  - Migration Stage: {sample_clean.migration_stage}")
            print(f"  - Industry: {sample_clean.merchant_industry}")
            print(f"  - Framework: {sample_clean.merchant_framework}")
        
        # STEP 4: Pattern detection (Agent 3)
        print("\n[STEP 4] AGENT 3: PATTERN DETECTION")
        print("-" * 80)
        print("Action: Reading events_clean, creating incident_clusters")
        print("        Detecting spikes, grouping by signature")
        print("        Calculating trend and rate metrics")
        
        # Note: Agent 3 (PatternDetectionAgent) requires tools/knowledge_base.py
        # For now, we'll show what the clean events look like
        
        cluster_count = db.query(IncidentClusterDB).count()
        print(f"✓ Total clusters: {cluster_count}")
        
        # Show aggregate statistics
        print(f"\n✓ Data Flow Summary:")
        print(f"  - Raw Events: {raw_count}")
        print(f"  - Clean Events: {clean_count}")
        print(f"  - Incident Clusters: {cluster_count}")
        
        # Show component distribution
        components = db.query(
            CleanEventDB.component
        ).distinct().all()
        print(f"\n✓ Components affected:")
        for comp_row in components:
            comp = comp_row[0]
            count = db.query(CleanEventDB).filter(CleanEventDB.component == comp).count()
            print(f"  - {comp}: {count} events")
        
        # Show migration stage distribution
        print(f"\n✓ Migration stage distribution:")
        for stage in range(1, 5):
            count = db.query(CleanEventDB).filter(CleanEventDB.migration_stage == stage).count()
            if count > 0:
                print(f"  - Stage {stage}: {count} events")
        
    finally:
        db.close()
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ DATA FLOW COMPLETE")
    print("=" * 80)
    print("\nKey Insights:")
    print("  • Events flow through database tables (not in-memory)")
    print("  • Each agent reads output of previous agent")
    print("  • Signatures enable pattern grouping")
    print("  • Merchant enrichment provides context for decision-making")
    print("\nNext: Implement Agent 3 (PatternDetectionAgent) for clustering")
    print("      Then Agents 4-5 (Reason Pipeline) for root cause analysis")
    print("\n")


if __name__ == "__main__":
    demonstrate_data_flow()
