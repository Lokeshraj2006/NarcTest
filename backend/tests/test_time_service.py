"""Trusted time: NTP first, then internet time over HTTPS, then the server clock."""

from datetime import datetime, timezone

from app.services import time_service


def test_ntp_is_used_when_it_works(monkeypatch):
    t = datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(time_service, "_ntp_time", lambda timeout: t)
    monkeypatch.setattr(time_service, "_https_time", lambda timeout: None)
    now, internet, source = time_service.get_trusted_time()
    assert (now, internet, source) == (t, t, "ntp")


def test_https_backup_when_ntp_is_blocked(monkeypatch):
    t = datetime(2026, 9, 28, 6, 0, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(time_service, "_ntp_time", lambda timeout: None)
    monkeypatch.setattr(time_service, "_https_time", lambda timeout: t)
    now, internet, source = time_service.get_trusted_time()
    assert (now, internet, source) == (t, t, "https")
    assert time_service.label(source) == "internet time (HTTPS)"


def test_server_clock_when_offline(monkeypatch):
    monkeypatch.setattr(time_service, "_ntp_time", lambda timeout: None)
    monkeypatch.setattr(time_service, "_https_time", lambda timeout: None)
    now, internet, source = time_service.get_trusted_time()
    assert internet is None and source == "server_clock"
    assert time_service.label(source) == "server clock"


def test_https_date_header_is_parsed(monkeypatch):
    class FakeResp:
        headers = {"date": "Mon, 28 Sep 2026 06:00:00 GMT"}

    import httpx

    monkeypatch.setattr(httpx, "head", lambda *a, **k: FakeResp())
    got = time_service._https_time(1.0)
    assert got is not None
    assert abs((got - datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)).total_seconds() - 0.5) < 0.5
