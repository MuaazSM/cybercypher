from db.database import SessionLocal
from db.models import (
    RawEventDB, MerchantProfileDB, CleanEventDB, IncidentClusterDB,
    IncidentDB, IncidentHypothesisDB, ActionPlanDB, ActionDB, ApprovalDB,
    ExecutedActionDB, ActionOutcomeDB, KnownPatternDB
)
from simulator.event_generator import EventSimulator
from datetime import datetime, timedelta
from uuid import uuid4
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_merchant_profiles():
    """Create 100 realistic merchant profiles."""
    merchants = []
    
    industries = ["fashion", "electronics", "food", "beauty", "home", "sports"]
    frameworks = ["shopify", "custom", "react", "vue", "nextjs"]
    regions = ["US-WEST", "US-EAST", "EU-CENTRAL", "APAC"]
    
    for i in range(1, 101):
        merchant = MerchantProfileDB(
            merchant_id=f"m_{i:04d}",
            migration_stage=random.choice([1, 2, 3, 4]),
            migrated_at=datetime.utcnow() - timedelta(days=random.randint(1, 90)),
            industry=random.choice(industries),
            storefront_framework=random.choice(frameworks),
            region=random.choice(regions),
            monthly_volume=random.randint(100, 10000),
            high_value=random.choice([True, False])
        )
        merchants.append(merchant)
    
    return merchants


def create_historical_events(days_back: int = 7, events_per_day: int = 100) -> list:
    """
    Create historical events over past N days (background noise).
    
    Args:
        days_back: How many days of history to create
        events_per_day: Average events per day
    
    Returns:
        List of RawEventDB objects
    """
    simulator = EventSimulator()
    events = []
    
    base_time = datetime.utcnow() - timedelta(days=days_back)
    
    for day in range(days_back):
        # Generate random events for this day
        day_events = simulator.generate_random_events(count=events_per_day)
        
        for event in day_events:
            # Adjust timestamp to be in this day
            adjusted_time = base_time + timedelta(
                days=day,
                minutes=random.randint(0, 1439)
            )
            
            # Convert Pydantic to DB model
            db_event = RawEventDB(
                event_id=event.event_id,
                event_type=event.event_type,
                merchant_id=event.merchant_id,
                timestamp=adjusted_time,
                payload=event.payload,
                source=event.source,
                idempotency_key=event.idempotency_key
            )
            events.append(db_event)
    
    return events


def create_spike_events() -> list:
    """
    Create concentrated spike scenario (50 webhook failures from 17 merchants).
    
    Returns:
        List of RawEventDB objects
    """
    simulator = EventSimulator()
    spike_events = simulator.generate_spike_scenario(
        event_type="webhook_fail",
        error_pattern={"webhook": "orders/create", "error": "DELIVERY_FAIL"},
        merchant_count=17,
        event_count=50,
        migration_stage=2,
        time_window_minutes=30
    )
    
    # Convert to DB models
    db_events = []
    for event in spike_events:
        db_event = RawEventDB(
            event_id=event.event_id,
            event_type=event.event_type,
            merchant_id=event.merchant_id,
            timestamp=event.timestamp,
            payload=event.payload,
            source=event.source,
            idempotency_key=event.idempotency_key
        )
        db_events.append(db_event)
    
    return db_events


def seed_database():
    """Main seeding function."""
    print("\n" + "=" * 70)
    print("SEEDING DATABASE WITH MOCK DATA")
    print("=" * 70)
    
    db = SessionLocal()
    
    try:
        # 0. Clear existing data for clean seed (respecting foreign keys)
        print("\n[0/3] Clearing existing data...")
        # Delete in reverse dependency order
        db.query(ActionOutcomeDB).delete()
        db.query(ExecutedActionDB).delete()
        db.query(ApprovalDB).delete()
        db.query(ActionDB).delete()
        db.query(ActionPlanDB).delete()
        db.query(IncidentHypothesisDB).delete()
        db.query(IncidentDB).delete()
        db.query(IncidentClusterDB).delete()
        db.query(CleanEventDB).delete()
        db.query(RawEventDB).delete()
        db.query(KnownPatternDB).delete()
        db.query(MerchantProfileDB).delete()
        db.commit()
        logger.info("✓ Cleared all existing data")
        
        # 1. Create merchant profiles
        print("\n[1/3] Creating 100 merchant profiles...")
        merchants = create_merchant_profiles()
        db.bulk_save_objects(merchants)
        db.commit()
        logger.info(f"✓ Created {len(merchants)} merchant profiles")
        
        # 2. Create historical events
        print("\n[2/3] Creating 700 historical events (7 days × 100/day)...")
        historical_events = create_historical_events(days_back=7, events_per_day=100)
        db.bulk_save_objects(historical_events)
        db.commit()
        logger.info(f"✓ Created {len(historical_events)} historical events")
        
        # 3. Create spike scenario
        print("\n[3/3] Creating spike scenario (50 webhook failures)...")
        spike_events = create_spike_events()
        db.bulk_save_objects(spike_events)
        db.commit()
        logger.info(f"✓ Created {len(spike_events)} spike events")
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ DATABASE SEEDED SUCCESSFULLY")
        print("=" * 70)
        print(f"\nData Summary:")
        print(f"  • Merchant profiles: {len(merchants)}")
        print(f"  • Historical events: {len(historical_events)}")
        print(f"  • Spike events: {len(spike_events)}")
        print(f"  • Total events: {len(historical_events) + len(spike_events)}")
        
        print(f"\nNext Steps:")
        print(f"  1. Run Agent 2 to normalize: python -m agents.normalization")
        print(f"  2. Run Agent 3 to detect patterns: python -m agents.pattern_detection")
        print(f"  3. Or run demo: python scripts/demo_data_flow.py")
        print("\n")
        
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
