from db.models import Base
from db.database import engine, SessionLocal
import logging

logger = logging.getLogger(__name__)


def init_db():
    """
    Create all tables in the database.
    
    Safe to call multiple times - only creates tables that don't exist.
    
    Usage:
        from db.init_db import init_db
        init_db()
    """
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("✓ Database initialized successfully")


def reset_db():
    """
    Drop all tables and recreate them.
    
    WARNING: This deletes all data! Use only in development.
    
    Usage:
        from db.init_db import reset_db
        reset_db()
    """
    logger.warning("⚠️  Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("Dropped all tables")
    
    logger.info("Creating tables fresh...")
    Base.metadata.create_all(bind=engine)
    logger.info("✓ Database reset successfully")


def seed_merchant_profiles():
    """
    Seed merchant profiles for testing.
    
    Creates sample merchants in different migration stages.
    """
    from db.models import MerchantProfileDB
    
    db = SessionLocal()
    
    merchants = [
        MerchantProfileDB(
            merchant_id="m_1001",
            migration_stage=1,
            industry="fashion",
            storefront_framework="shopify",
            region="US-WEST",
            monthly_volume=5000,
            high_value=True,
        ),
        MerchantProfileDB(
            merchant_id="m_1021",
            migration_stage=2,
            industry="electronics",
            storefront_framework="custom",
            region="US-EAST",
            monthly_volume=15000,
            high_value=True,
        ),
        MerchantProfileDB(
            merchant_id="m_1045",
            migration_stage=2,
            industry="food",
            storefront_framework="react",
            region="EU-CENTRAL",
            monthly_volume=8000,
            high_value=False,
        ),
        MerchantProfileDB(
            merchant_id="m_2001",
            migration_stage=3,
            industry="home",
            storefront_framework="custom",
            region="APAC",
            monthly_volume=12000,
            high_value=False,
        ),
        MerchantProfileDB(
            merchant_id="m_3001",
            migration_stage=4,
            industry="fashion",
            storefront_framework="react",
            region="US-WEST",
            monthly_volume=20000,
            high_value=True,
        ),
    ]
    
    for merchant in merchants:
        # Check if already exists
        existing = db.query(MerchantProfileDB).filter_by(
            merchant_id=merchant.merchant_id
        ).first()
        if not existing:
            db.add(merchant)
    
    db.commit()
    logger.info(f"✓ Seeded {len(merchants)} merchant profiles")
    db.close()


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "init":
            init_db()
        elif command == "reset":
            response = input(
                "⚠️  This will delete all data. Are you sure? (yes/no): "
            )
            if response.lower() == "yes":
                reset_db()
                seed_merchant_profiles()
            else:
                logger.info("Aborted")
        elif command == "seed":
            seed_merchant_profiles()
        else:
            print("Usage: python db/init_db.py [init|reset|seed]")
    else:
        print("Usage: python db/init_db.py [init|reset|seed]")
