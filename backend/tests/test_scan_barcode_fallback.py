"""POST /scan reads the barcode from the photo when the app sent none."""

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


def _post_scan(http, token, context):
    with PHOTO.open("rb") as photo:
        return http.post(
            "/scan",
            headers={"Authorization": f"Bearer {token}"},
            files={"image": ("pack.png", photo, "image/png")},
            data={"context": json.dumps(context)},
        )


def _detail(http, token, evidence_id):
    r = http.get(f"/inspections/{evidence_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return r.json()


def test_barcode_missing_from_the_app_is_read_from_the_photo(scan_client):
    http, token = scan_client
    r = _post_scan(http, token, {"ocr_fields": {"mrp": 109.0, "net_quantity": "400 g"}})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["authenticity"]["barcode"] == "8904004400779"
    assert body["authenticity"]["status"] == "verified_authentic"
    assert body["barcode"] == "8904004400779"
    assert body["barcode_source"] == "server"

    detail = _detail(http, token, body["evidence_record_id"])
    assert detail["barcode"] == "8904004400779"
    assert detail["barcode_source"] == "server"


def test_a_barcode_sent_by_the_app_is_never_replaced(scan_client):
    http, token = scan_client
    r = _post_scan(http, token, {"barcode": "0000000000000", "ocr_fields": {"mrp": 109.0}})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["authenticity"]["barcode"] == "0000000000000"
    assert body["authenticity"]["status"] == "unverified_product"
    assert body["barcode"] == "0000000000000"
    assert body["barcode_source"] == "device"

    detail = _detail(http, token, body["evidence_record_id"])
    assert detail["barcode"] == "0000000000000"
    assert detail["barcode_source"] == "device"
