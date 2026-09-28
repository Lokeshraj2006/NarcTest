"""A scan whose MRP and dates can't be read comes back NEEDS REVIEW, never compliant."""

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
from app.models.product_registry import ProductRegistry
from app.models.user import User
from app.routers import scan as scan_router

PHOTO = Path(__file__).parent / "fixtures" / "barcode" / "pack_a_back_barcode.png"

# Scan #41: the pack's MRP, dates and batch hidden under a finger; the
# headings and everything else still readable.
HIDDEN_VALUES = {
    "product_name": "Aloo Bhujia Sev",
    "manufacturer_name": "Haldiram Snacks Food Private Limited",
    "manufacturer_address": "20 Km Stone, Bhandara Road, Nagpur, Maharashtra 441104",
    "net_quantity": "400 g",
    "country_of_origin": "India",
    "consumer_care_phone": "0120-2400286",
    "raw_text": (
        "NET QUANTITY: 400 g\nBATCH NO.:\nMFG. DATE:\nUSE BY:\nMRP:\n"
        "HALDIRAM SNACKS FOOD PRIVATE LIMITED"
    ),
}


@pytest.fixture()
def scan_client(tmp_path, monkeypatch):
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
        db.add(ProductRegistry(
            barcode="8904004400779", product_name="Haldiram's Aloo Bhujia",
            manufacturer_name="Haldiram Snacks Food Private Limited",
            manufacturer_address="Nagpur, Maharashtra 441104",
            mrp=109.0, net_quantity="400 g", is_vegetarian=True,
        ))
        db.commit()
        token = create_access_token(subject=consumer.id, role="consumer")

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(scan_router, "_resolve_upload_dir", lambda: tmp_path)
    try:
        yield TestClient(app), token
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_hidden_mrp_and_dates_come_back_needs_review(scan_client):
    http, token = scan_client
    with PHOTO.open("rb") as photo:
        r = http.post(
            "/scan",
            headers={"Authorization": f"Bearer {token}"},
            files={"image": ("pack.png", photo, "image/png")},
            data={"context": json.dumps({"barcode": "8904004400779", "ocr_fields": HIDDEN_VALUES})},
        )
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["overall_status"] == "needs_review"
    assert body["pin_color"] == "amber"
    assert "Couldn't read: MRP, manufacture date and expiry date" in body["action_reason"]
    # Not evidence of a violation: no complaint, nothing a report could cite.
    assert body["complaint_created"] is False
    assert body["failed_rule_check_ids"] == []

    expiry = next(c for c in body["rule_checks"] if c["rule_number"] == 7)
    assert expiry["status"] == "REVIEW"
    assert "use-by or best-before heading is on the label" in expiry["failure_reason"]

    log = http.get("/scan/history", headers={"Authorization": f"Bearer {token}"}).json()
    assert log["rows"][0]["overall_status"] == "needs_review"
    assert log["rows"][0]["pin_color"] == "amber"
