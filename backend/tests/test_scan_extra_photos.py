"""Extra photos sent with a scan ("Scan another part") are kept and checked for the veg mark."""

from __future__ import annotations

import hashlib
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
from app.services.fssai_mark_service import (
    STATUS_NON_VEG,
    STATUS_NOT_FOUND,
    STATUS_VEG,
    FssaiMarkResult,
    combine_photo_results,
)

FIXTURES = Path(__file__).parent / "fixtures"
# Pack A's back: barcode readable, veg mark not detected (glossy, see decision 9).
MAIN_PHOTO = FIXTURES / "barcode" / "pack_a_back_barcode.png"
# The Ob & Gob tub's veg mark, which the detector finds.
VEG_MARK_PHOTO = FIXTURES / "fssai" / "obgob_blurred_veg_mark.png"
NO_MARK_PHOTO = FIXTURES / "fssai" / "pack_a_fabric_top.png"


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
        owner = User(
            email="consumer@lm.test", username="consumer_one", hashed_password="unused",
            full_name="Consumer One", role="consumer",
        )
        other = User(
            email="other@lm.test", username="consumer_two", hashed_password="unused",
            full_name="Consumer Two", role="consumer",
        )
        db.add_all([owner, other])
        db.add(ProductRegistry(
            barcode="8904004400779", product_name="Haldiram's Aloo Bhujia",
            manufacturer_name="Haldiram Snacks Food Private Limited",
            manufacturer_address="Nagpur, Maharashtra 441104",
            mrp=109.0, net_quantity="400 g", is_vegetarian=True,
        ))
        db.commit()
        tokens = {
            "owner": create_access_token(subject=owner.id, role="consumer"),
            "other": create_access_token(subject=other.id, role="consumer"),
        }

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
        yield TestClient(app), tokens
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        Base.metadata.drop_all(engine)
        engine.dispose()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _post(http, token, extras=()):
    files = [("image", ("pack.png", MAIN_PHOTO.read_bytes(), "image/png"))]
    files += [
        ("extra_images", (f"extra{i}.png", p.read_bytes(), "image/png"))
        for i, p in enumerate(extras, start=1)
    ]
    context = {"ocr_fields": {"mrp": 109.0, "net_quantity": "400 g"}}
    return http.post("/scan", headers=_auth(token), files=files, data={"context": json.dumps(context)})


def test_veg_mark_on_an_extra_photo_is_found(scan_client):
    http, tokens = scan_client
    r = _post(http, tokens["owner"], extras=[VEG_MARK_PHOTO])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["fssai_mark"]["status"] == STATUS_VEG
    assert body["fssai_mark"]["photo"] == 1
    assert body["fssai_mark"]["photos_checked"] == 2
    # The registry says vegetarian, so the mark agrees rather than contradicts.
    assert body["authenticity"]["status"] == "verified_authentic"

    detail = http.get(f"/inspections/{body['evidence_record_id']}", headers=_auth(tokens["owner"])).json()
    assert detail["fssai_mark"]["photo"] == 1
    assert detail["fssai_mark"]["photos_checked"] == 2
    # The evidence photo stays the first one; the extra photo has its own fingerprint.
    assert detail["evidence"]["sha256_hash"] == hashlib.sha256(MAIN_PHOTO.read_bytes()).hexdigest()
    assert detail["extra_photos"] == [{
        "index": 1,
        "sha256_hash": hashlib.sha256(VEG_MARK_PHOTO.read_bytes()).hexdigest(),
        "file_size_bytes": len(VEG_MARK_PHOTO.read_bytes()),
        "fssai_mark_status": STATUS_VEG,
    }]


def test_extra_photo_is_served_with_its_fingerprint_check(scan_client):
    http, tokens = scan_client
    evidence_id = _post(http, tokens["owner"], extras=[NO_MARK_PHOTO, VEG_MARK_PHOTO]).json()["evidence_record_id"]

    r = http.get(f"/inspections/{evidence_id}/extra-image/2", headers=_auth(tokens["owner"]))
    assert r.status_code == 200
    assert r.content == VEG_MARK_PHOTO.read_bytes()
    assert r.headers["X-Evidence-Sha256-Match"] == "true"

    assert http.get(f"/inspections/{evidence_id}/extra-image/3", headers=_auth(tokens["owner"])).status_code == 404
    # Same access rule as the evidence photo: a consumer sees only their own scans.
    assert http.get(f"/inspections/{evidence_id}/extra-image/1", headers=_auth(tokens["other"])).status_code == 403


def test_scan_without_extra_photos_is_unchanged(scan_client):
    http, tokens = scan_client
    body = _post(http, tokens["owner"]).json()
    assert body["fssai_mark"]["status"] == STATUS_NOT_FOUND
    assert body["fssai_mark"]["photo"] is None
    assert body["fssai_mark"]["photos_checked"] == 1
    detail = http.get(f"/inspections/{body['evidence_record_id']}", headers=_auth(tokens["owner"])).json()
    assert detail["extra_photos"] == []


def test_more_than_three_extra_photos_are_refused(scan_client):
    http, tokens = scan_client
    r = _post(http, tokens["owner"], extras=[NO_MARK_PHOTO] * 4)
    assert r.status_code == 400
    assert "At most 3 extra photos" in r.json()["detail"]


def _mark(status, confidence=0.9):
    return FssaiMarkResult(status=status, confidence=confidence, message=f"classified as {status}")


def test_combine_keeps_a_single_photo_as_it_was():
    single = combine_photo_results([_mark(STATUS_VEG)])
    assert (single.status, single.photo, single.photos_checked) == (STATUS_VEG, 0, 1)
    assert single.message == "classified as vegetarian"
    none = combine_photo_results([_mark(STATUS_NOT_FOUND, 0.0)])
    assert (none.status, none.photo, none.photos_checked) == (STATUS_NOT_FOUND, None, 1)


def test_combine_takes_the_mark_from_whichever_photo_shows_it():
    result = combine_photo_results([_mark(STATUS_NOT_FOUND, 0.0), _mark(STATUS_NOT_FOUND, 0.0), _mark(STATUS_VEG)])
    assert (result.status, result.photo, result.photos_checked) == (STATUS_VEG, 2, 3)
    assert "extra photo 2" in result.message


def test_photos_that_disagree_decide_nothing():
    result = combine_photo_results([_mark(STATUS_VEG), _mark(STATUS_NON_VEG)])
    assert result.status == STATUS_NOT_FOUND
    assert result.photo is None
    assert result.photos_checked == 2
    assert "disagree" in result.message
    assert "the main photo: vegetarian" in result.message
    assert "extra photo 1: non-vegetarian" in result.message


def test_no_mark_on_any_photo_says_how_many_were_checked():
    result = combine_photo_results([_mark(STATUS_NOT_FOUND, 0.0)] * 3)
    assert result.status == STATUS_NOT_FOUND
    assert result.photos_checked == 3
    assert "any of the 3 photos" in result.message
