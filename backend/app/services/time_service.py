"""
FieldProof — Trusted time.

Asks an NTP server (2 s timeout). If that fails, falls back to the server clock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from app.config import settings


def get_trusted_time(timeout: float = 2.0) -> Tuple[datetime, Optional[datetime], str]:
    """Return (now_utc, ntp_time_or_None, time_source)."""
    try:
        import ntplib

        resp = ntplib.NTPClient().request(settings.ntp_server, version=3, timeout=timeout)
        ntp_dt = datetime.fromtimestamp(resp.tx_time, tz=timezone.utc)
        return ntp_dt, ntp_dt, "ntp"
    except Exception:
        now = datetime.now(timezone.utc)
        return now, None, "server_clock"


def iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None
