"""
FieldProof — Trusted time.

Order of trust:
  1. NTP (pool.ntp.org, 2 s timeout)                      -> time_source "ntp"
  2. Internet time over HTTPS: the signed-TLS "Date" header -> time_source "https"
     of well-known sites (used when a network blocks NTP,
     e.g. college / office Wi-Fi). Accurate to about 1 s.
  3. This server's own clock                               -> time_source "server_clock"
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Tuple

from app.config import settings

# Sites whose HTTPS "Date" header we trust as an internet time source.
HTTPS_TIME_URLS = (
    "https://www.google.com",
    "https://www.cloudflare.com",
    "https://www.microsoft.com",
)

TIME_SOURCE_LABELS = {
    "ntp": "internet time (NTP)",
    "https": "internet time (HTTPS)",
    "server_clock": "server clock",
}


def label(time_source: Optional[str]) -> str:
    return TIME_SOURCE_LABELS.get(time_source or "", time_source or "unknown")


def _ntp_time(timeout: float) -> Optional[datetime]:
    try:
        import ntplib

        resp = ntplib.NTPClient().request(settings.ntp_server, version=3, timeout=timeout)
        return datetime.fromtimestamp(resp.tx_time, tz=timezone.utc)
    except Exception:
        return None


def _https_time(timeout: float) -> Optional[datetime]:
    """Internet time from the HTTPS Date header (1 s resolution), corrected for half the round trip."""
    try:
        import httpx
    except Exception:
        return None
    for url in HTTPS_TIME_URLS:
        try:
            t0 = time.monotonic()
            resp = httpx.head(url, timeout=timeout, follow_redirects=False)
            rtt = time.monotonic() - t0
            header = resp.headers.get("date")
            if not header:
                continue
            server_dt = parsedate_to_datetime(header).astimezone(timezone.utc)
            # The header is truncated to whole seconds: add 0.5 s, plus half the round trip.
            return server_dt + timedelta(seconds=0.5 + rtt / 2)
        except Exception:
            continue
    return None


def get_trusted_time(timeout: float = 2.0) -> Tuple[datetime, Optional[datetime], str]:
    """Return (now_utc, internet_time_or_None, time_source)."""
    ntp_dt = _ntp_time(timeout)
    if ntp_dt is not None:
        return ntp_dt, ntp_dt, "ntp"
    https_dt = _https_time(timeout)
    if https_dt is not None:
        return https_dt, https_dt, "https"
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
