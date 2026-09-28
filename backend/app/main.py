"""
FieldProof — FastAPI Application Entry Point

Initialises the FastAPI app, CORS middleware, and mounts all routers.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Lifespan ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    logger.info("Starting %s v%s (debug=%s)", settings.app_name, settings.app_version, settings.debug)
    try:
        import app.models  # noqa: F401  (registers all tables)
        from app.database import Base, SessionLocal, engine
        from app.services.kit_service import seed_demo_kits

        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            seed_demo_kits(db)
        finally:
            db.close()
        logger.info("Database tables ready.")
    except Exception as e:
        logger.warning("Database auto-initialization skipped or failed: %s", e)

    try:
        from app.services import signing

        signing.get_private_key()
    except Exception as e:
        logger.warning("Signing key could not be loaded/created: %s", e)

    yield
    logger.info("Shutting down %s", settings.app_name)


# ── App ─────────────────────────────────────────────────────────
app = FastAPI(
    title="FieldProof",
    version=settings.app_version,
    description=(
        "FieldProof — tamper-evident field drug-test records (SIH26231, Team HexTech). "
        "Results are presumptive field results only."
    ),
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # The dashboard reads this to show whether a test photo still
    # matches the fingerprint recorded when it was uploaded.
    expose_headers=["X-Evidence-Sha256-Match", "Content-Disposition"],
)


# ── Health check ────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health_check():
    """Simple liveness probe."""
    return {"status": "healthy", "app": "FieldProof", "version": settings.app_version}


# ── Router registration ────────────────────────────────────────
from app.routers import auth, kits, reviews, tests, verify  # noqa: E402

app.include_router(auth.router)
app.include_router(kits.router)
app.include_router(reviews.router)
app.include_router(tests.router)
app.include_router(verify.router)
