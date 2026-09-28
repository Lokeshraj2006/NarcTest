"""
FieldProof — Application Configuration

Centralised settings loaded from environment variables / backend/.env.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application-wide settings, sourced from env vars / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ───────────────────────────────────────────────
    # SQLite for the quick demo, PostgreSQL later (both work).
    database_url: str = "sqlite:///./fieldproof.db"

    # ── JWT / Auth ─────────────────────────────────────────────
    secret_key: str = "CHANGE_ME"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # ── NTP ────────────────────────────────────────────────────
    ntp_server: str = "pool.ntp.org"
    ntp_max_drift_seconds: int = 5

    # ── Application ────────────────────────────────────────────
    app_name: str = "FieldProof"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── FieldProof ─────────────────────────────────────────────
    # Base URL printed into QR codes / verify links. Empty = use the request URL.
    public_base_url: Optional[str] = None
    qr_base_url: Optional[str] = None  # address other phones use to open the PDF's QR link (laptop Wi-Fi IP)
    # Password for the demo users (officer1 / supervisor1 / admin1).
    demo_password: Optional[str] = None
    # Where the Ed25519 signing key lives (gitignored).
    keys_dir: str = str(BACKEND_DIR / "keys")
    # Where uploaded test photos are stored (gitignored).
    uploads_dir: str = str(BACKEND_DIR / "uploads")


# Singleton instance — import this everywhere
settings = Settings()
