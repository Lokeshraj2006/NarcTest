"""Scan history, linked rescans, edited-field records and re-used photo flags."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.complaint import Complaint
from app.models.evidence import EvidenceRecord
from app.models.user import User
from app.routers import scan as scan_router

PHOTO = Path(__file__).parent / "fixtures" / "barcode" / "pack_a_back_barcode.png"
# No net quantity and no label text: Rule 4 fails, so a consumer scan opens a complaint.
FAILING = {"ocr_fields": {"mrp": 109.0}}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)
    tokens = {}
    with Session() as db:
        for username, role in (
            ("consumer_one", "consumer"),
            ("consumer_two", "consumer"),
            ("inspector_one", "inspector"),
            ("controller", "admin"),
        ):
            user = User(
                email=f"{username}@lm.test", username=username,
                hashed_password="unused", full_name=username, role=role,
            )
            db.add(user)
            db.flush()
            tokens[username] = create_access_token(subject=user.id, role=role)
            tokens[f"{username}_id"] = user.id
        db.commit()

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
        yield TestClient(app), Session, tokens, tmp_path
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        Base.metadata.drop_all(engine)
        engine.dispose()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _variant(folder: Path, n: int) -> Path:
    """The same label with one pixel changed: a different photo to the hash."""
    image = cv2.imread(str(PHOTO))
    image[0, n] = (image[0, n].astype(int) + 1) % 256
    out = folder / f"variant_{n}.png"
    cv2.imwrite(str(out), image)
    return out


def _scan(http, token, context=FAILING, photo=PHOTO):
    with photo.open("rb") as f:
        return http.post(
            "/scan",
            headers=_auth(token),
            files={"image": ("pack.png", f, "image/png")},
            data={"context": json.dumps(context)},
        )


# ── History ──────────────────────────────────────────────────────────────
def test_history_lists_only_the_signed_in_users_scans(env):
    http, _, t, folder = env
    assert _scan(http, t["consumer_one"]).status_code == 201
    assert _scan(http, t["consumer_two"], photo=_variant(folder, 1)).status_code == 201
    rows = http.get("/scan/history", headers=_auth(t["consumer_one"])).json()["rows"]
    assert [r["captured_by_username"] for r in rows] == ["consumer_one"]
    assert rows[0]["complaint_number"]
    assert rows[0]["complaint_status"] == "pending_inspector_review"


def test_log_shows_who_scanned_and_filters_by_person(env):
    http, _, t, folder = env
    _scan(http, t["consumer_one"])
    _scan(http, t["inspector_one"], photo=_variant(folder, 1))
    admin = _auth(t["controller"])
    rows = http.get("/inspections/log", headers=admin).json()["rows"]
    assert {r["captured_by_username"] for r in rows} == {"consumer_one", "inspector_one"}
    only = http.get(
        "/inspections/log", headers=admin, params={"captured_by_id": t["inspector_one_id"]}
    ).json()["rows"]
    assert [r["captured_by_role"] for r in only] == ["inspector"]
    mine = http.get(
        "/inspections/log", headers=_auth(t["inspector_one"]), params={"mine": True}
    ).json()["rows"]
    assert [r["captured_by_username"] for r in mine] == ["inspector_one"]


def test_a_consumer_opens_their_own_scan_detail_but_not_anyone_elses(env):
    http, _, t, folder = env
    own = _scan(http, t["consumer_one"]).json()["evidence_record_id"]
    other = _scan(http, t["consumer_two"], photo=_variant(folder, 1)).json()["evidence_record_id"]
    consumer = _auth(t["consumer_one"])
    assert http.get(f"/inspections/{own}", headers=consumer).status_code == 200
    assert http.get(f"/inspections/{other}", headers=consumer).status_code == 403
    assert http.get("/inspections/log", headers=consumer).status_code == 403


# ── Rescans ──────────────────────────────────────────────────────────────
def test_a_rescan_is_a_new_record_that_joins_the_open_complaint(env):
    http, Session, t, folder = env
    first = _scan(http, t["consumer_one"]).json()
    again = _scan(
        http, t["consumer_one"],
        {**FAILING, "rescan_of_id": first["evidence_record_id"]},
        photo=_variant(folder, 1),
    ).json()
    assert again["evidence_record_id"] != first["evidence_record_id"]
    assert again["rescan_of_id"] == first["evidence_record_id"]
    assert again["complaint_created"] is False
    assert again["complaint_linked"] is True
    assert again["complaint_number"] == first["complaint_number"]
    with Session() as db:
        assert db.query(Complaint).count() == 1
        assert db.get(EvidenceRecord, first["evidence_record_id"]).rescan_of_id is None
    detail = http.get(
        f"/inspections/{first['evidence_record_id']}", headers=_auth(t["controller"])
    ).json()
    assert detail["rescan_ids"] == [again["evidence_record_id"]]


def test_a_consumer_cannot_rescan_someone_elses_scan_but_an_inspector_can(env):
    http, _, t, folder = env
    theirs = _scan(http, t["consumer_two"]).json()["evidence_record_id"]
    rescan = {**FAILING, "rescan_of_id": theirs}
    assert _scan(http, t["consumer_one"], rescan, photo=_variant(folder, 1)).status_code == 403
    assert _scan(http, t["inspector_one"], rescan, photo=_variant(folder, 2)).status_code == 201


def test_rescanning_a_missing_scan_is_404(env):
    http, _, t, _ = env
    assert _scan(http, t["consumer_one"], {**FAILING, "rescan_of_id": 999}).status_code == 404


# ── Fields changed before submitting ─────────────────────────────────────
def test_fields_changed_from_the_ocr_reading_are_recorded(env):
    http, Session, t, _ = env
    r = _scan(http, t["consumer_one"], {
        "ocr_fields": {"mrp": 109.0, "net_quantity": "400 g", "manufacturer_name": "HALDIRAMS"},
        "extracted_fields": {"mrp": 109.0, "net_quantity": "400  g"},
    }).json()
    assert r["edited_fields"] == [
        {"field": "manufacturer_name", "extracted": None, "submitted": "HALDIRAMS"}
    ]
    row = http.get("/scan/history", headers=_auth(t["consumer_one"])).json()["rows"][0]
    assert row["edited_fields"] == ["manufacturer_name"]
    with Session() as db:
        complaint = db.get(Complaint, r["complaint_id"])
        assert "Changed by the consumer before submitting: manufacturer_name." in complaint.description


def test_without_an_ocr_reading_edits_are_not_recorded(env):
    http, _, t, _ = env
    assert _scan(http, t["consumer_one"]).json()["edited_fields"] is None


# ── Re-used photos ───────────────────────────────────────────────────────
def test_the_same_photo_again_is_flagged_and_opens_no_second_complaint(env):
    http, Session, t, _ = env
    first = _scan(http, t["consumer_one"]).json()
    again = _scan(http, t["consumer_one"]).json()
    assert again["duplicate_of_id"] == first["evidence_record_id"]
    assert again["complaint_linked"] is True
    with Session() as db:
        assert db.query(Complaint).count() == 1
    detail = http.get(
        f"/inspections/{first['evidence_record_id']}", headers=_auth(t["controller"])
    ).json()
    assert detail["same_photo_ids"] == [again["evidence_record_id"]]


def test_another_users_copy_of_a_photo_is_noted_in_their_complaint(env):
    http, Session, t, _ = env
    first = _scan(http, t["consumer_one"]).json()
    copy = _scan(http, t["consumer_two"]).json()
    assert copy["duplicate_of_id"] == first["evidence_record_id"]
    assert copy["complaint_created"] is True
    with Session() as db:
        complaint = db.get(Complaint, copy["complaint_id"])
        assert f"Same photo as scan #{first['evidence_record_id']}." in complaint.description


# ── Evidence photo ───────────────────────────────────────────────────────
def test_the_controller_gets_the_evidence_photo_with_its_fingerprint_checked(env):
    http, _, t, _ = env
    evidence_id = _scan(http, t["consumer_one"]).json()["evidence_record_id"]
    r = http.get(f"/inspections/{evidence_id}/image", headers=_auth(t["controller"]))
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == PHOTO.read_bytes()
    assert r.headers["x-evidence-sha256-match"] == "true"


def test_a_photo_changed_on_disk_fails_its_fingerprint_check(env):
    http, Session, t, _ = env
    evidence_id = _scan(http, t["consumer_one"]).json()["evidence_record_id"]
    with Session() as db:
        stored = Path(db.get(EvidenceRecord, evidence_id).file_path)
    stored.write_bytes(stored.read_bytes() + b"altered")
    r = http.get(f"/inspections/{evidence_id}/image", headers=_auth(t["controller"]))
    assert r.status_code == 200
    assert r.headers["x-evidence-sha256-match"] == "false"


def test_a_consumer_gets_only_their_own_evidence_photo(env):
    http, _, t, folder = env
    own = _scan(http, t["consumer_one"]).json()["evidence_record_id"]
    other = _scan(http, t["consumer_two"], photo=_variant(folder, 1)).json()["evidence_record_id"]
    consumer = _auth(t["consumer_one"])
    assert http.get(f"/inspections/{own}/image", headers=consumer).status_code == 200
    assert http.get(f"/inspections/{other}/image", headers=consumer).status_code == 403
    assert http.get("/inspections/999/image", headers=_auth(t["controller"])).status_code == 404
