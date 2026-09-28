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
    logger.info(
        "Starting %s v%s (debug=%s)",
        settings.app_name,
        settings.app_version,
        settings.debug,
    )
    try:
        from app.database import Base, engine
        import app.models

        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.warning("Database auto-initialization skipped or failed: %s", e)

    yield
    logger.info("Shutting down %s", settings.app_name)


# ── App ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="FieldProof — Digital Companion for Field Drug Testing (SIH26231, Team HexTech)",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # The dashboard reads this to show whether an evidence photo still
    # matches the fingerprint recorded at capture.
    expose_headers=["X-Evidence-Sha256-Match"],
)


# ── Health check ────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health_check():
    """Simple liveness probe for Cloud Run / load balancers."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }


# ── Router registration ────────────────────────────────────────
from app.routers import auth, inspections, legal_notice, rules, scan, violations

app.include_router(auth.router)
app.include_router(inspections.router)
app.include_router(inspections.complaints_router)
app.include_router(legal_notice.router)
app.include_router(rules.router)
app.include_router(scan.router)
app.include_router(violations.router)
