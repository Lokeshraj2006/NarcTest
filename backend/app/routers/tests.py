"""FieldProof — Test submission and test log endpoints."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.core.dependencies import get_current_active_user, require_supervisor_or_admin, role_of
from app.database import get_db
from app.models.kit_profile import KitProfile
from app.models.review import Review
from app.models.test_record import TestRecord
from app.models.user import User
from app.services import record_service, signing, time_service
from app.services.record_service import GENESIS, SIGNED_FIELDS
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/tests", tags=["tests"])

MAX_IMAGE_BYTES = 20 * 1024 * 1024
ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "heic", "bmp"}
RESULTS = {"POSITIVE", "NEGATIVE", "INCONCLUSIVE"}
# One writer at a time, so two records never point at the same previous hash.
_chain_lock = threading.Lock()


# ── helpers ─────────────────────────────────────────────────────
def _is_staff(user: User) -> bool:
    return role_of(user) in ("supervisor", "admin")


def _load(db: Session, test_id: int, user: User) -> TestRecord:
    test = (
        db.query(TestRecord)
        .options(selectinload(TestRecord.reviews).selectinload(Review.reviewer),
                 selectinload(TestRecord.officer))
        .filter(TestRecord.id == test_id)
        .first()
    )
    if test is None:
        raise HTTPException(404, "Test not found.")
    if not _is_staff(user) and test.officer_id != user.id:
        raise HTTPException(403, "You can only see your own tests.")
    return test


def _ext(upload: UploadFile) -> str:
    name = (upload.filename or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ALLOWED_EXT:
        ctype = (upload.content_type or "").lower()
        ext = {"image/png": "png", "image/webp": "webp", "image/heic": "heic"}.get(ctype, "jpg")
    return "jpg" if ext == "jpeg" else ext


def _num(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        raise HTTPException(422, "GPS values must be numbers.")


def _str(v: Any, limit: int = 200) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s[:limit] if s else None


def _safe_classify(image_bytes: bytes, profile: Dict[str, Any]) -> Dict[str, Any]:
    """Run the colour engine. Any crash becomes INCONCLUSIVE (never guess)."""
    try:
        from app.services import colour_engine

        out = colour_engine.classify(image_bytes, profile) or {}
    except Exception as exc:  # engine missing or crashed
        logger.warning("colour engine failed: %s", exc)
        out = {"result": "INCONCLUSIVE", "reason": "Could not read the photo — please retake it."}
    result = str(out.get("result") or "INCONCLUSIVE").upper()
    if result not in RESULTS:
        result = "INCONCLUSIVE"
    conf = out.get("confidence")
    try:
        conf = None if conf is None else int(round(float(conf)))
    except (TypeError, ValueError):
        conf = None

    def floats(v):
        try:
            return None if v is None else [round(float(x), 3) for x in v]
        except (TypeError, ValueError):
            return None

    return {
        "result": result,
        "outcome_label": out.get("outcome_label"),
        "confidence": conf,
        "reason": out.get("reason"),
        "measured_lab": floats(out.get("measured_lab")),
        "measured_rgb": [int(round(x)) for x in out["measured_rgb"]] if out.get("measured_rgb") else None,
        "delta_e_by_outcome": out.get("delta_e_by_outcome"),
        "quality": out.get("quality"),
    }


def _filtered(db: Session, user: User, date_from=None, date_to=None, officer_id=None,
              kit_id=None, result=None, q=None, mine=False):
    query = db.query(TestRecord).options(
        selectinload(TestRecord.reviews).selectinload(Review.reviewer),
        selectinload(TestRecord.officer),
    )
    if not _is_staff(user) or mine:
        query = query.filter(TestRecord.officer_id == user.id)
    if officer_id:
        query = query.filter(TestRecord.officer_id == officer_id)
    if kit_id:
        query = query.filter(TestRecord.kit_id == kit_id)
    if result:
        query = query.filter(TestRecord.result == result.upper())
    if date_from:
        query = query.filter(TestRecord.created_at >= date_from)
    if date_to:
        end = date_to + "T23:59:59.999Z" if len(date_to) == 10 else date_to
        query = query.filter(TestRecord.created_at <= end)
    if q:
        like = f"%{q.strip()}%"
        query = query.outerjoin(User, User.id == TestRecord.officer_id).filter(or_(
            TestRecord.test_uid.ilike(like),
            TestRecord.outcome_label.ilike(like),
            TestRecord.kit_name.ilike(like),
            TestRecord.kit_code.ilike(like),
            TestRecord.lab_sample_id.ilike(like),
            TestRecord.device_id.ilike(like),
            TestRecord.result.ilike(like),
            User.full_name.ilike(like),
            User.username.ilike(like),
        ))
    return query.order_by(TestRecord.id.desc())


# ── POST /tests ─────────────────────────────────────────────────
@router.post("", status_code=201)
async def submit_test(
    request: Request,
    image: UploadFile = File(...),
    context: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    try:
        ctx = json.loads(context)
        if not isinstance(ctx, dict):
            raise ValueError
    except ValueError:
        raise HTTPException(422, "context must be a JSON object.")

    try:
        kit_id = int(ctx.get("kit_id"))
    except (TypeError, ValueError):
        raise HTTPException(422, "Please pick a kit first (kit_id missing).")
    kit = db.get(KitProfile, kit_id)
    if kit is None or not kit.is_active:
        raise HTTPException(404, "This kit is not available.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(400, "The photo is empty. Please take it again.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "The photo is too big (max 20 MB).")

    image_sha256 = hashlib.sha256(image_bytes).hexdigest()
    client_sha = _str(ctx.get("client_sha256"), 64)
    client_sha = client_sha.lower() if client_sha else None
    client_match = None if client_sha is None else (client_sha == image_sha256)

    # Save the exact bytes first
    test_uid = str(uuid.uuid4())
    ext = _ext(image)
    rel_path = f"tests/{test_uid}.{ext}"
    abs_path = Path(settings.uploads_dir) / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(image_bytes)

    profile = {
        "id": kit.id, "code": kit.code, "name": kit.name, "reagent": kit.reagent,
        "read_time_s": kit.read_time_s, "outcomes": kit.outcomes or [],
        "max_delta_e": kit.max_delta_e, "min_margin": kit.min_margin,
        "is_active": kit.is_active, "version": kit.version,
    }
    cls = _safe_classify(image_bytes, profile)

    now, ntp_dt, time_source = time_service.get_trusted_time()
    created_at = time_service.iso(now)
    device_time = _str(ctx.get("device_time"), 40)
    dev_dt = time_service.parse_iso(device_time)
    drift = round((dev_dt - now).total_seconds(), 1) if dev_dt else None

    lat, lon, acc = _num(ctx.get("latitude")), _num(ctx.get("longitude")), _num(ctx.get("gps_accuracy_m"))

    with _chain_lock:
        prev = db.query(TestRecord).order_by(TestRecord.id.desc()).first()
        prev_hash = prev.record_hash if prev else GENESIS
        payload = {
            "test_uid": test_uid,
            "created_at": created_at,
            "ntp_time": time_service.iso(ntp_dt),
            "time_source": time_source,
            "device_time": device_time,
            "latitude": lat,
            "longitude": lon,
            "gps_accuracy_m": acc,
            "gps_is_mock": bool(ctx.get("gps_is_mock", False)),
            "officer_id": user.id,
            "device_id": _str(ctx.get("device_id"), 128),
            "kit_id": kit.id,
            "kit_code": kit.code,
            "kit_version": kit.version,
            "image_sha256": image_sha256,
            "result": cls["result"],
            "outcome_label": cls["outcome_label"],
            "confidence": cls["confidence"],
            "reason": cls["reason"],
            "measured_lab": cls["measured_lab"],
            "lab_sample_id": _str(ctx.get("lab_sample_id"), 100),
            "prev_record_hash": prev_hash,
        }
        assert set(payload) == set(SIGNED_FIELDS)
        signed_payload = signing.canonical_json(payload)
        test = TestRecord(
            **payload,
            clock_drift_s=drift,
            kit_name=kit.name,
            kit_outcomes=kit.outcomes or [],
            image_path=rel_path,
            client_sha256=client_sha,
            client_hash_match=client_match,
            measured_rgb=cls["measured_rgb"],
            delta_e_by_outcome=cls["delta_e_by_outcome"],
            quality=cls["quality"],
            notes=_str(ctx.get("notes"), 2000),
            signed_payload=signed_payload,
            record_hash=signing.sha256_hex(signed_payload),
            signature=signing.sign(signed_payload),
            key_id=signing.key_id,
        )
        db.add(test)
        db.commit()
    return record_service.to_dict(_load(db, test.id, user), request)


# ── GET /tests ──────────────────────────────────────────────────
@router.get("")
def list_tests(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    officer_id: Optional[int] = None,
    kit_id: Optional[int] = None,
    result: Optional[str] = None,
    q: Optional[str] = None,
    mine: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    rows = _filtered(db, user, date_from, date_to, officer_id, kit_id, result, q, mine).limit(1000).all()
    return [record_service.to_dict(t, request) for t in rows]


CSV_COLUMNS = [
    "id", "test_uid", "created_at", "time_source", "device_time", "clock_drift_s",
    "latitude", "longitude", "gps_accuracy_m", "gps_is_mock", "officer_id", "officer_name",
    "device_id", "kit_id", "kit_code", "kit_name", "kit_version", "result", "outcome_label",
    "confidence", "reason", "lab_sample_id", "review_status", "image_sha256",
    "client_hash_match", "prev_record_hash", "record_hash", "key_id", "verify_url",
]


@router.get("/export.csv")
def export_csv(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    officer_id: Optional[int] = None,
    kit_id: Optional[int] = None,
    result: Optional[str] = None,
    q: Optional[str] = None,
    mine: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_supervisor_or_admin),
):
    rows = _filtered(db, user, date_from, date_to, officer_id, kit_id, result, q, mine).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    for t in rows:
        d = record_service.to_dict(t, request)
        w.writerow(["" if d.get(c) is None else d.get(c) for c in CSV_COLUMNS])
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="fieldproof_tests.csv"'},
    )


# ── GET /tests/{id} ─────────────────────────────────────────────
@router.get("/{test_id}")
def get_test(
    test_id: int, request: Request,
    db: Session = Depends(get_db), user: User = Depends(get_current_active_user),
):
    return record_service.to_dict(_load(db, test_id, user), request)


MEDIA = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp",
         "heic": "image/heic", "bmp": "image/bmp"}


@router.get("/{test_id}/image")
def get_image(
    test_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_active_user),
):
    test = _load(db, test_id, user)
    data = record_service.read_image(test)
    if data is None:
        raise HTTPException(404, "Photo file is missing.")
    match = hashlib.sha256(data).hexdigest() == test.image_sha256
    ext = test.image_path.rsplit(".", 1)[-1].lower()
    return Response(
        content=data,
        media_type=MEDIA.get(ext, "application/octet-stream"),
        headers={"X-Evidence-Sha256-Match": "true" if match else "false",
                 "Cache-Control": "no-store"},
    )


@router.get("/{test_id}/pdf")
def get_pdf(
    test_id: int, request: Request,
    db: Session = Depends(get_db), user: User = Depends(get_current_active_user),
):
    from app.services.report_service import build_test_pdf

    test = _load(db, test_id, user)
    pdf = build_test_pdf(record_service.to_dict(test, request), record_service.read_image(test))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="fieldproof_test_{test.id}.pdf"'},
    )
