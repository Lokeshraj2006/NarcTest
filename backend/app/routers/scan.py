"""
FieldProof — Consumer/Inspector Scan Router

    POST /scan
        Multipart form upload — one image + a JSON `context` blob, plus up to
        three extra photos of other faces ("Scan another part"), which are
        kept with their own fingerprints and checked for the FSSAI mark.
        Runs authenticity + FSSAI mark + GSTIN checks, persists the
        EvidenceRecord, RuleChecks, and aggregate ComplianceResult, and
        (for consumer callers) auto-creates a pending-inspector Complaint
        when the verdict is action_needed. A rescan is a new record naming
        the scan it repeats; a photo submitted before is flagged; fields the
        user changed from the OCR reading are recorded.

    GET /scan/history
        The signed-in user's own scans, newest first.

Any authenticated user may call this endpoint — role determines what
happens after the verdict lands.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.core.dependencies import require_authenticated_user
from app.database import get_db
from app.models.compliance_result import ComplianceResult
from app.models.evidence import EvidenceRecord
from app.models.rule_check import CheckStatus, RuleCheck
from app.models.user import User, UserRole
from app.models.rule import Rule
from app.schemas.inspection import InspectionLogResponse
from app.schemas.scan import RuleCheckSummary, ScanContext, ScanResponse
from app.services.authenticity_service import (
    AuthenticityResult,
    verify_against_registry,
)
from app.services.barcode_service import detect_barcode
from app.services.complaint_service import auto_notify_inspector
from app.services.compliance_aggregator import build_compliance_result
from app.services import cv_service
from app.services.fssai_mark_service import (
    FssaiMarkResult,
    STATUS_NOT_FOUND,
    combine_photo_results,
    detect_fssai_mark_from_bytes,
)
from app.services.compliance_rules import EXEMPT, evaluate_all, summarize
from app.services.scan_audit import edited_fields, enum_value, log_row, log_row_options
from app.services.scan_audit import pin_color as verdict_pin

router = APIRouter(prefix="/scan", tags=["scan"])


# ── Storage helpers ───────────────────────────────────────────────────────
def _resolve_upload_dir() -> Path:
    """Return the directory where evidence images are stored on disk.

    Prefers settings.evidence_upload_dir if present; otherwise falls back
    to <cwd>/uploads/evidence — created on demand.
    """
    configured = getattr(settings, "evidence_upload_dir", None)
    base = Path(configured) if configured else Path.cwd() / "uploads" / "evidence"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _persist_image(data: bytes, original_filename: str, sha256: str) -> Path:
    ext = os.path.splitext(original_filename)[1].lower() or ".jpg"
    out_dir = _resolve_upload_dir()
    out_path = out_dir / f"{sha256}{ext}"
    if not out_path.exists():
        with open(out_path, "wb") as fh:
            fh.write(data)
    return out_path


def _mark_on(data: bytes, region: Optional[tuple] = None) -> FssaiMarkResult:
    """The FSSAI mark on one photo; an undecodable photo simply shows none."""
    try:
        return detect_fssai_mark_from_bytes(data, region=region)
    except ValueError:
        return FssaiMarkResult(
            status=STATUS_NOT_FOUND, confidence=0.0,
            message="Image could not be decoded for FSSAI mark detection.",
        )


# "Scan another part" photos of other faces (lid, seal, back). They are kept
# as supporting evidence with their own fingerprints and checked for the veg
# mark; the evidence photo stays the first one.
MAX_EXTRA_PHOTOS = 3


def _rule_id_map(db: Session) -> dict:
    """rule_code -> rules.id, so each RuleCheck links to its seeded definition."""
    return {code: rid for code, rid in db.query(Rule.rule_code, Rule.id).all()}


SWITCHED_OFF_REASON = (
    "Switched off by the Controller on the dashboard, so it was not checked on this scan."
)


def _apply_rule_switches(db: Session, payloads: List[dict]) -> List[dict]:
    """Record each rule the Controller has switched off as EXEMPT for this scan.

    A switched-off rule can't raise a complaint or go into a report. What the
    check would have said is kept in its details, so the record stays honest.
    """
    off = {n for (n,) in db.query(Rule.rule_number).filter(Rule.is_active.is_(False)).all()}
    out: List[dict] = []
    for p in payloads:
        if p["rule_number"] in off:
            details = json.loads(p["details_json"]) if p.get("details_json") else {}
            details.update({"switched_off": True, "result_if_on": p["status"]})
            p = {
                **p,
                "status": EXEMPT,
                "score": 0.0,
                "failure_reason": SWITCHED_OFF_REASON,
                "details_json": json.dumps(details),
            }
        out.append(p)
    return out


def _persist_rule_checks(
    db: Session, evidence_id: int, payloads: List[dict]
) -> List[RuleCheck]:
    """Insert RuleCheck rows from compliance_rules-shaped dicts; return the rows."""
    id_map = _rule_id_map(db)
    rows: List[RuleCheck] = []
    for payload in payloads:
        rc = RuleCheck(
            evidence_id=evidence_id,
            rule_id=id_map.get(payload["rule_code"]),
            rule_number=payload["rule_number"],
            rule_name=payload["rule_name"],
            rule_code=payload["rule_code"],
            statutory_reference=payload["statutory_reference"],
            status=CheckStatus(payload["status"]),
            score=payload.get("score"),
            detected_value=payload.get("detected_value"),
            required_value=payload.get("required_value"),
            failure_reason=payload.get("failure_reason"),
            details_json=payload.get("details_json"),
        )
        db.add(rc)
        rows.append(rc)
    db.flush()
    return rows


# ── POST /scan ────────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=ScanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an evidence image + scan context for full compliance analysis",
)
async def submit_scan(
    image: UploadFile = File(..., description="Evidence image (JPEG/PNG)."),
    context: str = Form(
        ...,
        description="JSON-encoded ScanContext blob (barcode, GPS, OCR fields, ROI).",
    ),
    extra_images: Optional[List[UploadFile]] = File(
        None,
        description=(
            f"Up to {MAX_EXTRA_PHOTOS} photos of other faces of the pack ('Scan another "
            "part'). Stored with their own SHA-256 and checked for the FSSAI mark."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> ScanResponse:
    """Full scan pipeline — authenticity + FSSAI + GSTIN + aggregation + auto-notify."""

    # ── Parse the context blob ───────────────────────────────────────
    try:
        parsed = ScanContext.model_validate_json(context)
    except Exception as exc:  # pydantic ValidationError et al.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid scan context JSON: {exc}",
        )

    # ── Rescan: a new record naming the scan it repeats ─────────────────
    # Inspectors and the Controller may rescan any scan; a consumer only
    # their own. The original is never changed.
    if parsed.rescan_of_id is not None:
        original = db.get(EvidenceRecord, parsed.rescan_of_id)
        if original is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scan #{parsed.rescan_of_id} was not found, so it can't be rescanned.",
            )
        if (
            enum_value(current_user.role) == UserRole.CONSUMER.value
            and original.captured_by_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only rescan your own scans.",
            )

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image upload.",
        )

    extra_uploads = [u for u in (extra_images or []) if u is not None]
    if len(extra_uploads) > MAX_EXTRA_PHOTOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {MAX_EXTRA_PHOTOS} extra photos can be sent with a scan.",
        )
    extra_photos: List[Dict[str, Any]] = []
    extra_marks: List[FssaiMarkResult] = []
    for upload in extra_uploads:
        data = await upload.read()
        if not data:
            continue
        index = len(extra_photos) + 1
        digest = hashlib.sha256(data).hexdigest()
        path = _persist_image(data, upload.filename or f"extra{index}.jpg", digest)
        mark = _mark_on(data)
        extra_marks.append(mark)
        extra_photos.append({
            "index": index,
            "sha256": digest,
            "file_path": str(path),
            "mime_type": upload.content_type or "image/jpeg",
            "file_size_bytes": len(data),
            "fssai_mark": {"status": mark.status, "confidence": mark.confidence},
        })

    sha256 = hashlib.sha256(image_bytes).hexdigest()
    # A photo submitted before is flagged rather than taken as fresh evidence.
    first_submission = (
        db.query(EvidenceRecord.id)
        .filter(EvidenceRecord.sha256_hash == sha256)
        .order_by(EvidenceRecord.id)
        .first()
    )
    duplicate_of_id = first_submission[0] if first_submission else None
    stored_path = _persist_image(image_bytes, image.filename or "scan.jpg", sha256)
    decoded_image = cv2.imdecode(
        np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
    )

    # ── Barcode: the app's reading, else decoded here from the photo ─────
    # ML Kit on the phone misses some small or glossy barcodes that are
    # plainly in frame; without one there is no registry check and no scale.
    barcode = parsed.barcode
    barcode_bbox = parsed.barcode_bbox
    barcode_format = parsed.barcode_format
    barcode_source = "device" if barcode else None
    if not barcode and decoded_image is not None:
        found = detect_barcode(decoded_image)
        if found is not None:
            barcode, barcode_bbox, barcode_format = found.data, found.bbox, found.format
            barcode_source = "server"

    # ── FSSAI mark detection: the evidence photo, then any extra photos ──
    fssai_region = tuple(parsed.fssai_region) if parsed.fssai_region and len(parsed.fssai_region) == 4 else None
    fssai_result: Optional[FssaiMarkResult] = combine_photo_results(
        [_mark_on(image_bytes, fssai_region), *extra_marks]
    )

    # ── Authenticity registry cross-check ───────────────────────────
    ocr_fields_dict = parsed.ocr_fields.model_dump(exclude_none=True)
    authenticity: Optional[AuthenticityResult] = None
    if barcode:
        authenticity = verify_against_registry(
            db,
            barcode,
            ocr_fields_dict,
            fssai_mark=fssai_result.status if fssai_result else None,
        )

    # ── CV calibration for rules 9-11 ───────────────────────────────
    # The barcode doubles as a physical ruler: a GS1 symbol has a known
    # printed width, which converts pixel heights to millimetres. When the
    # app sends no barcode box or text geometry, no measurement is produced
    # and those rules stay at REVIEW rather than being guessed.
    cv_measurements: Optional[Dict[str, Any]] = None
    try:
        cv_measurements = cv_service.analyse(
            decoded_image,
            barcode_bbox=barcode_bbox,
            barcode_format=barcode_format,
            text_blocks=parsed.text_blocks,
            image_width_px=parsed.image_width_px,
            image_height_px=parsed.image_height_px,
        )
    except Exception:
        # Measurement is best-effort; a failure here must not lose the scan.
        cv_measurements = None

    # ── All 13 compliance rules, minus any the Controller switched off ──
    rule_payloads = _apply_rule_switches(db, evaluate_all(
        ocr_fields_dict,
        is_imported=parsed.is_imported,
        cv_measurements=cv_measurements,
    ))
    gstin_payload = next(
        p for p in rule_payloads if p["rule_code"] == "GSTIN_FORMAT"
    )

    # ── Chain of custody ────────────────────────────────────────────
    # Prefer the device's own capture time; server receipt time is only a
    # fallback, and is flagged as such so the record never overstates what
    # it actually knows.
    received_at = datetime.now(timezone.utc)
    device_ts = parsed.device_timestamp or received_at
    ntp_ts = parsed.ntp_timestamp

    drift = parsed.ntp_drift_seconds
    if drift is None and ntp_ts is not None:
        drift = abs((device_ts - ntp_ts).total_seconds())

    # A device clock disagreeing with atomic time by more than the configured
    # tolerance undermines the timestamp's evidential value.
    max_drift = float(getattr(settings, "ntp_max_drift_seconds", 5) or 5)
    tampered = drift is not None and drift > max_drift
    tamper_reason = (
        f"Device clock differs from NTP by {drift:.1f}s "
        f"(tolerance {max_drift:.0f}s)."
        if tampered
        else None
    )

    # ── Fields the user changed from what OCR read ──────────────────
    changed_fields = edited_fields(
        parsed.extracted_fields.model_dump(exclude_none=True)
        if parsed.extracted_fields is not None
        else None,
        ocr_fields_dict,
    )

    # ── Persist EvidenceRecord ──────────────────────────────────────
    now = device_ts
    detected_blob = {
        "ocr": ocr_fields_dict,
        "barcode": barcode,
        "barcode_source": barcode_source,
        "authenticity": authenticity.to_dict() if authenticity else None,
        "fssai_mark": fssai_result.to_dict() if fssai_result else None,
        "gstin": {
            "status": gstin_payload["status"],
            "detected_value": gstin_payload.get("detected_value"),
            "failure_reason": gstin_payload.get("failure_reason"),
        },
        "extra_photos": extra_photos,
    }
    evidence = EvidenceRecord(
        file_path=str(stored_path),
        original_filename=image.filename or "scan.jpg",
        mime_type=image.content_type or "image/jpeg",
        file_size_bytes=len(image_bytes),
        sha256_hash=sha256,
        gps_latitude=parsed.gps_latitude,
        gps_longitude=parsed.gps_longitude,
        gps_accuracy_meters=parsed.gps_accuracy_meters,
        timestamp_device=device_ts,
        timestamp_ntp=ntp_ts,
        ntp_drift_seconds=drift,
        is_tampered=tampered,
        tamper_reason=tamper_reason,
        detected_fields_json=json.dumps(detected_blob),
        seller_name=parsed.seller_name,
        seller_address=parsed.seller_address,
        captured_by_id=current_user.id,
        rescan_of_id=parsed.rescan_of_id,
        duplicate_of_id=duplicate_of_id,
        edited_fields_json=json.dumps(changed_fields) if changed_fields is not None else None,
    )
    db.add(evidence)
    db.flush()

    # ── Persist all 13 RuleCheck rows ───────────────────────────────
    rule_check_rows: List[RuleCheck] = _persist_rule_checks(
        db, evidence.id, rule_payloads
    )

    # ── Aggregate ───────────────────────────────────────────────────
    result = build_compliance_result(
        db,
        evidence_record_id=evidence.id,
        rule_checks=rule_check_rows,
        authenticity=authenticity,
        fssai_mark=fssai_result,
        gstin_status=str(gstin_payload["status"]),
        product_name_fallback=parsed.ocr_fields.product_name,
    )
    db.flush()

    # ── Consumer auto-notify ────────────────────────────────────────
    complaint, complaint_created = auto_notify_inspector(db, current_user, evidence, result)

    db.commit()
    db.refresh(result)
    if complaint is not None:
        db.refresh(complaint)

    from app.models.compliance_result import OverallStatus  # local import to avoid cycles
    status_value = (
        result.overall_status.value
        if isinstance(result.overall_status, OverallStatus)
        else str(result.overall_status)
    )
    pin_color = verdict_pin(status_value)

    return ScanResponse(
        evidence_record_id=evidence.id,
        compliance_result_id=result.id,
        overall_status=status_value,
        action_reason=result.action_reason,
        law_reference=result.law_reference,
        product_name=result.product_name,
        pin_color=pin_color,
        barcode=barcode,
        barcode_source=barcode_source,
        authenticity=authenticity.to_dict() if authenticity else None,
        fssai_mark=fssai_result.to_dict() if fssai_result else None,
        gstin={
            "status": gstin_payload["status"],
            "detected_value": gstin_payload.get("detected_value"),
            "failure_reason": gstin_payload.get("failure_reason"),
            "note": "Format/checksum only — not a live GST Council registry lookup.",
        },
        rule_checks=[
            RuleCheckSummary(
                id=rc.id,
                rule_number=rc.rule_number,
                rule_code=rc.rule_code,
                rule_name=rc.rule_name,
                statutory_reference=rc.statutory_reference,
                status=rc.status.value if hasattr(rc.status, "value") else str(rc.status),
                detected_value=rc.detected_value,
                required_value=rc.required_value,
                failure_reason=rc.failure_reason,
            )
            for rc in rule_check_rows
        ],
        checks_summary=summarize(rule_payloads),
        failed_rule_check_ids=[f.rule_check_id for f in result.failures],
        complaint_created=complaint_created,
        complaint_linked=complaint is not None and not complaint_created,
        complaint_id=complaint.id if complaint else None,
        complaint_number=complaint.complaint_number if complaint else None,
        rescan_of_id=evidence.rescan_of_id,
        duplicate_of_id=duplicate_of_id,
        edited_fields=changed_fields,
    )


# ── GET /scan/history ─────────────────────────────────────────────────────
@router.get(
    "/history",
    response_model=InspectionLogResponse,
    summary="The signed-in user's own scans, newest first",
)
def my_scan_history(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> InspectionLogResponse:
    query = (
        db.query(ComplianceResult)
        .join(ComplianceResult.evidence)
        .options(*log_row_options())
        .filter(EvidenceRecord.captured_by_id == current_user.id)
        .order_by(desc(ComplianceResult.created_at), desc(ComplianceResult.id))
    )
    total = query.count()
    rows = [log_row(r) for r in query.offset(offset).limit(limit).all()]
    return InspectionLogResponse(total=total, rows=rows)
