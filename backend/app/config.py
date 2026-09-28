"""
FieldProof — Application Configuration

Centralised settings loaded from environment variables / .env file.
Uses pydantic-settings for validation and type coercion.
"""

from __future__ import annotations

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings, sourced from env vars / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ───────────────────────────────────────────────
    database_url: str = "postgresql://fieldproof:fieldproof_dev@localhost:5432/fieldproof_db"

    # ── JWT / Auth ─────────────────────────────────────────────
    secret_key: str = "CHANGE_ME"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── Evidence storage ───────────────────────────────────────
    storage_backend: str = "local"  # "local" | "gcs"
    local_storage_path: str = "./uploads"
    gcs_bucket_name: str | None = None

    # ── NTP ────────────────────────────────────────────────────
    ntp_server: str = "pool.ntp.org"
    ntp_max_drift_seconds: int = 5

    # ── Application ────────────────────────────────────────────
    app_name: str = "FieldProof"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]


# Singleton instance — import this everywhere
settings = Settings()
