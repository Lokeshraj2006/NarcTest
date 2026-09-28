"""
FieldProof — Inspector / Admin Dashboard Router

Feeds the React admin dashboard table and Leaflet map.

    GET /inspections/log
        Lists every ComplianceResult with the fields the dashboard table
        renders and a precomputed `pin_color` for the map (green =
        compliant, red = action_needed). Inspector + admin only.

    GET /inspections/{evidence_record_id}
        Full detail view for a single evidence record — all persisted
        RuleCheck rows, the authenticity verdict, FSSAI mark result,
        GSTIN validation summary, and evidence chain-of-custody metadata.

    GET /inspections/{evidence_record_id}/image
        The evidence photo itself, with a live SHA-256 check against the
        fingerprint recorded at capture (X-Evidence-Sha256-Match header).

    GET /inspections/{evidence_record_id}/extra-image/{index}
        An extra photo of another face sent with the scan, same checks.

The GET /complaints/pending endpoint added for item 7's consumer→inspector
handoff is co-located here since it draws from the same dashboard data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import require_authenticated_user, require_inspector_or_admin
from app.database import get_db
from app.models.complaint import Complaint, ComplaintStatus
from app.models.compliance_result import ComplianceResult, OverallStatus
from app.models.evidence import EvidenceRecord
from app.models.rule_check import RuleCheck
from app.models.user import User, UserRole
from app.models.violation import ViolationReport, ViolationStatus
from app.schemas.inspection import (
    AuthenticityDetail,
    AuthenticityMismatchDetail,
    EditedField,
    EvidenceMeta,
    ExtraPhotoDetail,
    FssaiMarkDetail,
    GstinDetail,
    InspectionDetailResponse,
    InspectionLogResponse,
    InspectionLogRow,
    PendingComplaintRow,
    PendingComplaintsResponse,
    RuleCheckDetail,
)
from app.services.scan_audit import enum_value, load_edited_fields, log_row, log_row_options

router = APIRouter(prefix="/inspections", tags=["inspections"])
complaints_router = APIRouter(prefix="/complaints", tags=["complaints"])


def _require_view_access(user: User, evidence: Optional[EvidenceRecord]) -> None:
    """Inspectors and the Controller see every scan; anyone else only their own."""
    owner_id = evidence.captured_by_id if evidence else None
    if (
        enum_value(user.role) not in (UserRole.INSPECTOR.value, UserRole.ADMIN.value)
        and owner_id != user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own scans.",
        )

def _load_evidence_extras(db: Session, evidence_id: int) -> Dict[str, Any]:
    """Return the OCR / authenticity / fssai / gstin blobs stashed on evidence.

    We keep those large payloads in EvidenceRecord.detected_fields_json as
    JSON so the aggregate row stays small; the detail endpoint deserializes
    them on demand.
    """
    ev = (
        db.query(EvidenceRecord)
        .filter(EvidenceRecord.id == evidence_id)
        .first()
    )
    if not ev or not ev.detected_fields_json:
        return {}
    try:
        return json.loads(ev.detected_fields_json)
    except (ValueError, TypeError):
        return {}


# ── GET /inspections/log ──────────────────────────────────────────────────
@router.get(
    "/log",
    response_model=InspectionLogResponse,
    summary="List inspected products for the dashboard table + map",
)
def list_inspections(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    only_action_needed: bool = Query(
        False,
        description="If true, return only rows whose overall_status is action_needed.",
    ),
    mine: bool = Query(False, description="Only scans taken by the signed-in user."),
    captured_by_id: Optional[int] = Query(None, description="Only scans taken by this user."),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_inspector_or_admin),
) -> InspectionLogResponse:
    """List all inspected evidence records with dashboard-friendly fields."""
    query = (
        db.query(ComplianceResult)
        .join(ComplianceResult.evidence)
        .options(*log_row_options())
        .order_by(desc(ComplianceResult.created_at), desc(ComplianceResult.id))
    )
    if only_action_needed:
        query = query.filter(
            ComplianceResult.overall_status == OverallStatus.ACTION_NEEDED
        )
    if mine:
        query = query.filter(EvidenceRecord.captured_by_id == current_user.id)
    if captured_by_id is not None:
        query = query.filter(EvidenceRecord.captured_by_id == captured_by_id)

    total = query.count()
    rows: List[InspectionLogRow] = [log_row(r) for r in query.offset(offset).limit(limit).all()]
    return InspectionLogResponse(total=total, rows=rows)


def _rule_check_detail(rc: RuleCheck) -> RuleCheckDetail:
    """One check for the detail view; Rule 9 also carries the barcode's scale."""
    detail = RuleCheckDetail.model_validate(rc)
    if rc.rule_code == "FONT_SIZE" and rc.details_json:
        try:
            measured = json.loads(rc.details_json)
        except ValueError:
            measured = {}
        if isinstance(measured, dict) and measured.get("mm_per_px"):
            detail.scale_mm_per_px = float(measured["mm_per_px"])
            detail.scale_reference = measured.get("reference")
    return detail


# ── GET /inspections/{evidence_record_id} ─────────────────────────────────
@router.get(
    "/{evidence_record_id}",
    response_model=InspectionDetailResponse,
    summary="Full detail for one inspected evidence record",
)
def get_inspection_detail(
    evidence_record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> InspectionDetailResponse:
    """Return the full inspection detail for one evidence record."""
    result = (
        db.query(ComplianceResult)
        .options(
            joinedload(ComplianceResult.evidence),
            joinedload(ComplianceResult.failures),
        )
        .filter(ComplianceResult.evidence_record_id == evidence_record_id)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No compliance result recorded for evidence #{evidence_record_id}.",
        )

    _require_view_access(current_user, result.evidence)

    rule_check_rows = (
        db.query(RuleCheck)
        .filter(RuleCheck.evidence_id == evidence_record_id)
        .order_by(RuleCheck.rule_number.asc())
        .all()
    )

    extras = _load_evidence_extras(db, evidence_record_id)

    # Authenticity blob (may not exist if the scan skipped registry lookup)
    authenticity_payload = extras.get("authenticity")
    authenticity: Optional[AuthenticityDetail] = None
    if isinstance(authenticity_payload, dict):
        authenticity = AuthenticityDetail(
            status=authenticity_payload.get("status", result.authenticity_status or "unknown"),
            matched_product_name=authenticity_payload.get("matched_product_name"),
            registry_id=authenticity_payload.get("registry_id"),
            message=authenticity_payload.get("message", ""),
            mismatches=[
                AuthenticityMismatchDetail(**m)
                for m in authenticity_payload.get("mismatches", [])
                if isinstance(m, dict)
            ],
        )
    elif result.authenticity_status:
        authenticity = AuthenticityDetail(status=result.authenticity_status)

    # FSSAI mark blob
    fssai_payload = extras.get("fssai_mark")
    fssai_mark: Optional[FssaiMarkDetail] = None
    if isinstance(fssai_payload, dict):
        region = fssai_payload.get("detected_region")
        fssai_mark = FssaiMarkDetail(
            status=fssai_payload.get("status", result.fssai_mark_status or "not_found"),
            confidence=float(fssai_payload.get("confidence", 0.0) or 0.0),
            green_pixel_ratio=float(fssai_payload.get("green_pixel_ratio", 0.0) or 0.0),
            red_pixel_ratio=float(fssai_payload.get("red_pixel_ratio", 0.0) or 0.0),
            detected_region=list(region) if isinstance(region, (list, tuple)) else None,
            message=fssai_payload.get("message", ""),
            photo=fssai_payload.get("photo"),
            photos_checked=int(fssai_payload.get("photos_checked") or 1),
        )
    elif result.fssai_mark_status:
        fssai_mark = FssaiMarkDetail(status=result.fssai_mark_status)

    extra_photos = [
        ExtraPhotoDetail(
            index=int(p["index"]),
            sha256_hash=str(p.get("sha256", "")),
            file_size_bytes=p.get("file_size_bytes"),
            fssai_mark_status=(p.get("fssai_mark") or {}).get("status"),
        )
        for p in extras.get("extra_photos") or []
        if isinstance(p, dict) and "index" in p
    ]

    # GSTIN summary — walk the rule check for the canonical row, then fall
    # back to whatever the aggregate cached.
    gstin_row = next(
        (rc for rc in rule_check_rows if rc.rule_code == "GSTIN_FORMAT"), None
    )
    if gstin_row is not None:
        gstin = GstinDetail(
            status=str(gstin_row.status.value) if hasattr(gstin_row.status, "value") else str(gstin_row.status),
            detected_value=gstin_row.detected_value,
            failure_reason=gstin_row.failure_reason,
        )
    else:
        gstin = GstinDetail(status=result.gstin_status or "NOT_RUN")

    # An open report means this scan has already been escalated — surface it
    # so the app can show status rather than offering a duplicate filing.
    open_report = (
        db.query(ViolationReport)
        .filter(
            ViolationReport.evidence_record_id == evidence_record_id,
            ViolationReport.status.notin_(
                [ViolationStatus.REJECTED, ViolationStatus.CLOSED]
            ),
        )
        .order_by(desc(ViolationReport.created_at))
        .first()
    )

    evidence_meta = EvidenceMeta.model_validate(result.evidence) if result.evidence else None
    if evidence_meta is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Compliance result is missing its evidence record.",
        )

    ev = result.evidence
    scanned_by = ev.captured_by
    complaint = ev.complaint
    rescan_ids = [
        rid for (rid,) in db.query(EvidenceRecord.id)
        .filter(EvidenceRecord.rescan_of_id == ev.id)
        .order_by(EvidenceRecord.id)
    ]
    same_photo_ids = [
        pid for (pid,) in db.query(EvidenceRecord.id)
        .filter(EvidenceRecord.sha256_hash == ev.sha256_hash, EvidenceRecord.id != ev.id)
        .order_by(EvidenceRecord.id)
    ]
    edited = load_edited_fields(ev)

    return InspectionDetailResponse(
        evidence_record_id=result.evidence_record_id,
        compliance_result_id=result.id,
        overall_status=(
            result.overall_status.value
            if isinstance(result.overall_status, OverallStatus)
            else str(result.overall_status)
        ),
        action_reason=result.action_reason,
        law_reference=result.law_reference,
        product_name=result.product_name,
        total_checks=result.total_checks,
        failed_checks=result.failed_checks,
        rule_checks=[_rule_check_detail(rc) for rc in rule_check_rows],
        barcode=extras.get("barcode"),
        barcode_source=extras.get("barcode_source"),
        authenticity=authenticity,
        fssai_mark=fssai_mark,
        gstin=gstin,
        evidence=evidence_meta,
        failed_rule_check_ids=[f.rule_check_id for f in result.failures],
        has_violation_report=open_report is not None,
        violation_report_id=open_report.id if open_report else None,
        violation_report_number=open_report.report_number if open_report else None,
        violation_report_status=(
            open_report.status.value
            if open_report and isinstance(open_report.status, ViolationStatus)
            else (str(open_report.status) if open_report else None)
        ),
        captured_by_username=scanned_by.username if scanned_by else None,
        captured_by_role=enum_value(scanned_by.role) if scanned_by else None,
        complaint_id=ev.complaint_id,
        complaint_number=complaint.complaint_number if complaint else None,
        complaint_status=enum_value(complaint.status) if complaint else None,
        rescan_of_id=ev.rescan_of_id,
        rescan_ids=rescan_ids,
        duplicate_of_id=ev.duplicate_of_id,
        same_photo_ids=same_photo_ids,
        edited_fields=[EditedField(**e) for e in edited] if edited is not None else None,
        extra_photos=extra_photos,
    )


def _photo_response(path: Path, recorded_sha256: str, mime_type: Optional[str]) -> Response:
    """The stored photo, with whether it still hashes to its capture fingerprint."""
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The photo for this scan is no longer on the server.",
        )
    data = path.read_bytes()
    matches = hashlib.sha256(data).hexdigest() == recorded_sha256
    return Response(
        content=data,
        media_type=mime_type or "image/jpeg",
        headers={
            "X-Evidence-Sha256-Match": "true" if matches else "false",
            "Cache-Control": "private, no-store",
        },
    )


# ── GET /inspections/{evidence_record_id}/image ───────────────────────────
@router.get(
    "/{evidence_record_id}/image",
    summary="The evidence photo for one scan, checked against its capture fingerprint",
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}},
)
def get_evidence_image(
    evidence_record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> Response:
    """Return the stored photo and whether it still matches its SHA-256.

    ``X-Evidence-Sha256-Match`` is "true" only when the file on disk hashes to
    the value recorded at capture, so a reviewer can tell a replaced or
    altered photo from the original.
    """
    evidence = db.get(EvidenceRecord, evidence_record_id)
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evidence record #{evidence_record_id}.",
        )
    _require_view_access(current_user, evidence)
    return _photo_response(Path(evidence.file_path), evidence.sha256_hash, evidence.mime_type)


# ── GET /inspections/{evidence_record_id}/extra-image/{index} ─────────────
@router.get(
    "/{evidence_record_id}/extra-image/{index}",
    summary="An extra photo of the pack sent with a scan, checked against its fingerprint",
    responses={200: {"content": {"image/jpeg": {}, "image/png": {}}}},
)
def get_extra_image(
    evidence_record_id: int,
    index: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
) -> Response:
    """Same access rule and fingerprint check as the evidence photo."""
    evidence = db.get(EvidenceRecord, evidence_record_id)
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evidence record #{evidence_record_id}.",
        )
    _require_view_access(current_user, evidence)
    extras = _load_evidence_extras(db, evidence_record_id)
    photo = next(
        (
            p for p in extras.get("extra_photos") or []
            if isinstance(p, dict) and p.get("index") == index
        ),
        None,
    )
    if photo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan #{evidence_record_id} has no extra photo {index}.",
        )
    return _photo_response(Path(photo["file_path"]), str(photo.get("sha256", "")), photo.get("mime_type"))


# ── GET /complaints/pending (item 7 handoff surface) ──────────────────────
@complaints_router.get(
    "/pending",
    response_model=PendingComplaintsResponse,
    summary="List complaints awaiting inspector review (consumer-filed)",
)
def list_pending_complaints(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_inspector_or_admin),
) -> PendingComplaintsResponse:
    """List complaints in PENDING_INSPECTOR_REVIEW (or equivalent) status."""
    pending_states = {
        ComplaintStatus.PENDING_INSPECTOR_REVIEW.value
        if hasattr(ComplaintStatus, "PENDING_INSPECTOR_REVIEW")
        else "pending_inspector_review",
        "pending",
        "pending_inspector_review",
    }

    query = db.query(Complaint).order_by(desc(Complaint.created_at))
    total = query.count()
    complaints = query.offset(offset).limit(limit).all()

    rows: List[PendingComplaintRow] = []
    for c in complaints:
        status_value = c.status.value if hasattr(c.status, "value") else str(c.status)
        if status_value not in pending_states:
            continue

        evidence_id = None
        product_name = getattr(c, "product_name", None)
        overall_status_val = None
        action_reason = None
        gps_lat = c.gps_latitude
        gps_lng = c.gps_longitude

        ev = getattr(c, "evidence_records", None)
        ev_row = ev[0] if ev else None
        if ev_row is not None:
            evidence_id = ev_row.id
            gps_lat = ev_row.gps_latitude
            gps_lng = ev_row.gps_longitude
            aggregate = (
                db.query(ComplianceResult)
                .filter(ComplianceResult.evidence_record_id == ev_row.id)
                .first()
            )
            if aggregate is not None:
                product_name = aggregate.product_name or product_name
                overall_status_val = (
                    aggregate.overall_status.value
                    if isinstance(aggregate.overall_status, OverallStatus)
                    else str(aggregate.overall_status)
                )
                action_reason = aggregate.action_reason

        rows.append(
            PendingComplaintRow(
                complaint_id=c.id,
                evidence_record_id=evidence_id,
                product_name=product_name,
                overall_status=overall_status_val,
                action_reason=action_reason,
                gps_latitude=gps_lat,
                gps_longitude=gps_lng,
                filed_at=c.created_at,
                status=status_value,
            )
        )

    return PendingComplaintsResponse(total=len(rows), rows=rows)
