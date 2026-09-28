"""
FieldProof — Test record helpers: JSON form, review status, verification.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import settings
from app.models.test_record import TestRecord
from app.services import signing

# Fields that go into signed_payload (CONTRACT section 4), in no special order
SIGNED_FIELDS = [
    "test_uid", "created_at", "ntp_time", "time_source", "device_time",
    "latitude", "longitude", "gps_accuracy_m", "gps_is_mock",
    "officer_id", "device_id", "kit_id", "kit_code", "kit_version",
    "image_sha256", "result", "outcome_label", "confidence", "reason",
    "measured_lab", "lab_sample_id", "prev_record_hash",
]

GENESIS = "GENESIS"


def base_url(request: Optional[Request]) -> str:
    if settings.public_base_url:
        return settings.public_base_url.rstrip("/")
    if request is None:
        return "http://localhost:8000"
    return str(request.base_url).rstrip("/")


def verify_url(request: Optional[Request], test_id: int) -> str:
    return f"{base_url(request)}/v/{test_id}"


def image_file(test: TestRecord) -> Path:
    p = Path(test.image_path)
    return p if p.is_absolute() else Path(settings.uploads_dir) / p


def read_image(test: TestRecord) -> Optional[bytes]:
    try:
        return image_file(test).read_bytes()
    except OSError:
        return None


def review_status(test: TestRecord) -> str:
    if test.result != "INCONCLUSIVE":
        return "NOT_NEEDED"
    if not test.reviews:
        return "PENDING"
    return test.reviews[-1].decision


def _payload(test: TestRecord) -> Dict[str, Any]:
    try:
        data = json.loads(test.signed_payload)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def to_dict(test: TestRecord, request: Optional[Request] = None) -> Dict[str, Any]:
    officer = test.officer
    return {
        "id": test.id,
        "test_uid": test.test_uid,
        "created_at": test.created_at,
        "ntp_time": test.ntp_time,
        "time_source": test.time_source,
        "device_time": test.device_time,
        "clock_drift_s": test.clock_drift_s,
        "latitude": test.latitude,
        "longitude": test.longitude,
        "gps_accuracy_m": test.gps_accuracy_m,
        "gps_is_mock": test.gps_is_mock,
        "officer_id": test.officer_id,
        "officer_name": officer.full_name if officer else None,
        "device_id": test.device_id,
        "kit_id": test.kit_id,
        "kit_code": test.kit_code,
        "kit_name": test.kit_name,
        "kit_version": test.kit_version,
        "kit_outcomes": [
            {"label": o.get("label"), "category": o.get("category"), "srgb": o.get("srgb")}
            for o in (test.kit_outcomes or [])
        ],
        "image_sha256": test.image_sha256,
        "client_sha256": test.client_sha256,
        "client_hash_match": test.client_hash_match,
        "result": test.result,
        "outcome_label": test.outcome_label,
        "confidence": test.confidence,
        "reason": test.reason,
        "measured_lab": test.measured_lab,
        "measured_rgb": test.measured_rgb,
        "delta_e_by_outcome": test.delta_e_by_outcome,
        "quality": test.quality,
        "lab_sample_id": test.lab_sample_id,
        "notes": test.notes,
        "prev_record_hash": test.prev_record_hash,
        "record_hash": test.record_hash,
        "signature": test.signature,
        "key_id": test.key_id,
        "review_status": review_status(test),
        "reviews": [
            {
                "id": r.id,
                "decision": r.decision,
                "note": r.note,
                "reviewer_id": r.reviewer_id,
                "reviewer_name": r.reviewer.full_name if r.reviewer else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in (test.reviews or [])
        ],
        "verify_url": verify_url(request, test.id),
    }


def image_hash_ok(test: TestRecord) -> bool:
    data = read_image(test)
    if data is None:
        return False
    expected = _payload(test).get("image_sha256") or ""
    return hashlib.sha256(data).hexdigest() == expected


def verify_record(db: Session, test: TestRecord) -> Dict[str, Any]:
    payload = _payload(test)
    has_payload = bool(payload)

    checks = {
        "image_hash": has_payload and image_hash_ok(test),
        "record_hash": has_payload and signing.sha256_hex(test.signed_payload) == test.record_hash,
        "signature": has_payload and signing.verify(test.signed_payload, test.signature),
        "chain": False,
        "fields_match": False,
    }

    prev = (
        db.query(TestRecord)
        .filter(TestRecord.id < test.id)
        .order_by(TestRecord.id.desc())
        .first()
    )
    expected_prev = prev.record_hash if prev else GENESIS
    checks["chain"] = has_payload and payload.get("prev_record_hash") == expected_prev

    if has_payload:
        checks["fields_match"] = all(
            [
                payload.get("result") == test.result,
                payload.get("image_sha256") == test.image_sha256,
                payload.get("officer_id") == test.officer_id,
                payload.get("kit_id") == test.kit_id,
                payload.get("test_uid") == test.test_uid,
                payload.get("prev_record_hash") == test.prev_record_hash,
            ]
        )

    ok = all(checks.values())
    officer = test.officer
    return {
        "test_id": test.id,
        "ok": ok,
        "checks": checks,
        "message": (
            "Record is genuine — photo and details were not changed."
            if ok
            else "TAMPERED — this record was changed after it was saved. Do not trust it."
        ),
        "record": {
            "test_uid": test.test_uid,
            "created_at": test.created_at,
            "time_source": test.time_source,
            "latitude": test.latitude,
            "longitude": test.longitude,
            "officer_name": officer.full_name if officer else None,
            "kit_name": test.kit_name,
            "kit_version": test.kit_version,
            "result": test.result,
            "outcome_label": test.outcome_label,
            "confidence": test.confidence,
            "image_sha256": test.image_sha256,
            "record_hash": test.record_hash,
        },
    }
