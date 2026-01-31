from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os

# Get database URL from environment or use default for development
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cybercypher"
)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL logging in development
    pool_size=10,
    max_overflow=20,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to inject database sessions.
    
    Usage:
        @app.get("/incidents")
        def list_incidents(db: Session = Depends(get_db)):
            incidents = db.query(IncidentDB).all()
            return incidents
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_sync_db() -> Session:
    """
    Get a database session for synchronous code.
    
    Usage:
        db = get_sync_db()
        events = db.query(RawEventDB).filter(...).all()
        db.close()
    """
    return SessionLocal()
