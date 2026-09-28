"""
FieldProof — Database Engine & Session Factory

Provides:
  • SQLAlchemy async-compatible engine (sync for Alembic, async for app)
  • SessionLocal factory
  • Base declarative class for ORM models
  • get_db() dependency for FastAPI route injection
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# ── Engine ──────────────────────────────────────────────────────
is_sqlite = settings.database_url.startswith("sqlite")
engine_kwargs = {"echo": settings.debug}

if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(settings.database_url, **engine_kwargs)

# ── Session factory ─────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Declarative base ───────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# ── FastAPI dependency ──────────────────────────────────────────
def get_db():
    """Yield a database session, ensuring cleanup on completion."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
