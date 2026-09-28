"""The Controller's rule switches are honoured by scans, and Rule 9's scale reaches the dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.rule import Rule
from app.models.user import User
from app.routers import scan as scan_router

PHOTO = Path(__file__).parent / "fixtures" / "barcode" / "pack_a_back_barcode.png"

# Every check passes or is REVIEW, except Rule 4: the net quantity is missing.
LABEL_WITHOUT_NET_QUANTITY = {
    "product_name": "Masala Noodles",
    "manufacturer_name": "Nestle India Ltd.",
    "manufacturer_address": "Nestle House, Gurgaon 122002, Haryana",
    "country_of_origin": "India",
    "mrp": 14.0,
    "mfg_date": "12/05/2026",
    "expiry_date": "12/05/2027",
    "consumer_care_phone": "1800103194",
    "consumer_care_email": "care@nestle.in",
    "raw_text": "MRP Rs 14.00 inclusive of all taxes",
}
# Not in the registry, so the registry check can't decide the verdict.
UNREGISTERED = "0000000000000"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    with Session() as db:
        consumer = User(
            email="consumer@lm.test", username="consumer_one", hashed_password="unused",
            full_name="Consumer One", role="consumer",
        )
        db.add(consumer)
        db.add(Rule(
            rule_number=4, rule_code="NET_QUANTITY", rule_name="Net quantity",
            description="Net quantity must be declared.", statutory_reference="Rule 6(1)(c)",
            is_active=True,
        ))
        db.commit()
        token = create_access_token(subject=consumer.id, role="consumer")

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def switch(rule_number: int, active: bool) -> None:
        with Session() as db:
            db.query(Rule).filter(Rule.rule_number == rule_number).update({"is_active": active})
            db.commit()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(scan_router, "_resolve_upload_dir", lambda: tmp_path)
    try:
        yield TestClient(app), token, switch
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        Base.metadata.drop_all(engine)
        engine.dispose()


def _scan(http, token, **context):
    with PHOTO.open("rb") as photo:
        r = http.post(
            "/scan",
            headers={"Authorization": f"Bearer {token}"},
            files={"image": ("pack.png", photo, "image/png")},
            data={"context": json.dumps(context)},
        )
    assert r.status_code == 201, r.text
    return r.json()


def _check(checks, number):
    return next(c for c in checks if c["rule_number"] == number)


# ── Rule switches ─────────────────────────────────────────────────────────
def test_with_the_rule_on_a_missing_net_quantity_fails(client):
    http, token, _ = client
    body = _scan(http, token, barcode=UNREGISTERED, ocr_fields=LABEL_WITHOUT_NET_QUANTITY)
    assert _check(body["rule_checks"], 4)["status"] == "FAIL"
    assert body["overall_status"] == "action_needed"


def test_a_switched_off_rule_is_exempt_and_raises_nothing(client):
    http, token, switch = client
    switch(4, False)
    body = _scan(http, token, barcode=UNREGISTERED, ocr_fields=LABEL_WITHOUT_NET_QUANTITY)

    net = _check(body["rule_checks"], 4)
    assert net["status"] == "EXEMPT"
    assert "Switched off by the Controller" in net["failure_reason"]
    assert net["id"] not in body["failed_rule_check_ids"]
    assert body["overall_status"] == "compliant"
    assert body["complaint_created"] is False


def test_switching_the_rule_back_on_restores_the_check(client):
    http, token, switch = client
    switch(4, False)
    _scan(http, token, barcode=UNREGISTERED, ocr_fields=LABEL_WITHOUT_NET_QUANTITY)
    switch(4, True)
    body = _scan(http, token, barcode=UNREGISTERED, ocr_fields=LABEL_WITHOUT_NET_QUANTITY)
    assert _check(body["rule_checks"], 4)["status"] == "FAIL"


# ── Rule 9's scale in the scan detail ─────────────────────────────────────
def test_scan_detail_shows_the_barcode_scale_behind_rule_9(client):
    http, token, _ = client
    body = _scan(
        http, token,
        barcode=UNREGISTERED,
        barcode_bbox=[0, 0, 373, 100],   # 373 px wide EAN-13 -> ~0.1 mm per pixel
        barcode_format="ean13",
        text_blocks=[{"text": "MRP Rs 14.00", "x": 10, "y": 10, "width": 220, "height": 50}],
        ocr_fields=LABEL_WITHOUT_NET_QUANTITY,
    )
    r = http.get(
        f"/inspections/{body['evidence_record_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    checks = r.json()["rule_checks"]

    font = _check(checks, 9)
    assert font["status"] == "PASS"
    assert font["scale_mm_per_px"] == pytest.approx(37.29 / 373, abs=1e-4)
    assert font["scale_reference"] == "ean13"
    assert _check(checks, 4)["scale_mm_per_px"] is None


def test_without_a_barcode_box_rule_9_says_there_was_no_ruler(client):
    http, token, _ = client
    body = _scan(http, token, barcode=UNREGISTERED, ocr_fields=LABEL_WITHOUT_NET_QUANTITY)
    font = _check(body["rule_checks"], 9)
    assert font["status"] == "REVIEW"
    assert "no barcode was found to use as a ruler" in font["failure_reason"]
