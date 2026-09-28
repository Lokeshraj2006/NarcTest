"""
FieldProof — Violation escalation router.

    POST /violations                    inspector files a report from a scan
    GET  /violations                    list (admin: all; inspector: own)
    GET  /violations/{id}               full detail for review
    POST /violations/{id}/confirm       ADMIN confirms
    POST /violations/{id}/reject        ADMIN rejects
    POST /violations/{id}/notice        ADMIN issues the GO notice
    GET  /violations/{id}/notice.pdf    download the issued notice

Authority split is deliberate: an inspector's job ends at filing the
report; only the admin (Field Drug Testing Dashboard) may issue a notice.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import (
    require_admin,
    require_inspector_or_admin,
)
from app.database import get_db
from app.models.legal_notice import LegalNotice
from app.models.user import User, UserRole
from app.models.violation import ViolationReport, ViolationStatus
from app.schemas.violation import (
    AdminDecision,
    LegalNoticeResponse,
    ViolationReportCreate,
    ViolationReportDetail,
    ViolationReportListResponse,
    ViolationReportRow,
)
from app.services import violation_service as svc
from app.services.report_service import ReportGenerationError

router = APIRouter(prefix="/violations", tags=["violations"])


def _get_report(db: Session, report_id: int) -> ViolationReport:
    report = (
        db.query(ViolationReport)
        .options(
            joinedload(ViolationReport.evidence),
            joinedload(ViolationReport.inspector),
        )
        .filter(ViolationReport.id == report_id)
        .first()
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Violation report #{report_id} not found.",
        )
    return report


def _is_admin(user: User) -> bool:
    role = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    return role == UserRole.ADMIN.value


# ── POST /violations — inspector files ───────────────────────────────────
@router.post(
    "",
    response_model=ViolationReportDetail,
    status_code=status.HTTP_201_CREATED,
    summary="File a violation report from a scan (inspector)",
)
def file_report(
    payload: ViolationReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_inspector_or_admin),
) -> ViolationReportDetail:
    """Raise a formal report against a scan, routed to the admin queue."""
    try:
        report = svc.create_report(
            db,
            current_user,
            payload.evidence_record_id,
            complaint_id=payload.complaint_id,
            violation_summary=payload.violation_summary,
            inspector_notes=payload.inspector_notes,
            severity=payload.severity,
            rule_check_ids=payload.rule_check_ids,
            shop_name=payload.shop_name,
            shop_address=payload.shop_address,
            cite_registry=payload.cite_registry,
            pack_checked=payload.pack_checked,
        )
    except svc.ViolationWorkflowError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    except ValueError as exc:  # bad severity string
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    db.commit()
    db.refresh(report)
    return ViolationReportDetail(**svc.serialize_detail(db, report))


# ── GET /violations — queue ──────────────────────────────────────────────
@router.get(
    "",
    response_model=ViolationReportListResponse,
    summary="List violation reports (admin sees all, inspector sees own)",
)
def list_reports(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description='Filter by workflow state, e.g. "pending_admin_confirmation".',
    ),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_inspector_or_admin),
) -> ViolationReportListResponse:
    query = (
        db.query(ViolationReport)
        .options(
            joinedload(ViolationReport.evidence),
            joinedload(ViolationReport.inspector),
        )
        .order_by(desc(ViolationReport.created_at))
    )

    # Inspectors only see what they filed; admins see the whole queue.
    if not _is_admin(current_user):
        query = query.filter(ViolationReport.inspector_id == current_user.id)

    if status_filter:
        try:
            query = query.filter(ViolationStatus(status_filter) == ViolationReport.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unknown status '{status_filter}'. Valid: "
                    f"{[s.value for s in ViolationStatus]}"
                ),
            )

    total = query.count()
    rows = query.offset(offset).limit(limit).all()
    return ViolationReportListResponse(
        total=total,
        rows=[ViolationReportRow(**svc.serialize_row(db, r)) for r in rows],
    )


# ── GET /violations/{id} ─────────────────────────────────────────────────
@router.get(
    "/{report_id}",
    response_model=ViolationReportDetail,
    summary="Full violation report detail",
)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_inspector_or_admin),
) -> ViolationReportDetail:
    report = _get_report(db, report_id)
    if not _is_admin(current_user) and report.inspector_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view reports you filed.",
        )
    return ViolationReportDetail(**svc.serialize_detail(db, report))


# ── POST /violations/{id}/confirm — ADMIN ────────────────────────────────
@router.post(
    "/{report_id}/confirm",
    response_model=ViolationReportDetail,
    summary="Confirm a violation report (admin only)",
)
def confirm_report(
    report_id: int,
    payload: AdminDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ViolationReportDetail:
    report = _get_report(db, report_id)
    try:
        svc.confirm_report(db, current_user, report, payload.admin_notes)
    except svc.ViolationWorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    db.commit()
    db.refresh(report)
    return ViolationReportDetail(**svc.serialize_detail(db, report))


# ── POST /violations/{id}/reject — ADMIN ─────────────────────────────────
@router.post(
    "/{report_id}/reject",
    response_model=ViolationReportDetail,
    summary="Reject a violation report (admin only)",
)
def reject_report(
    report_id: int,
    payload: AdminDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ViolationReportDetail:
    report = _get_report(db, report_id)
    try:
        svc.reject_report(db, current_user, report, payload.admin_notes)
    except svc.ViolationWorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    db.commit()
    db.refresh(report)
    return ViolationReportDetail(**svc.serialize_detail(db, report))


# ── POST /violations/{id}/notice — ADMIN issues GO notice ────────────────
@router.post(
    "/{report_id}/notice",
    response_model=LegalNoticeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue the GO notice for a confirmed report (admin only)",
)
def issue_notice(
    report_id: int,
    response_deadline_days: int = Query(15, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> LegalNoticeResponse:
    """Issue the show-cause notice to the manufacturer and shop.

    Only available after the report has been CONFIRMED — the escalation
    chain is the point, so the ordering is enforced.
    """
    report = _get_report(db, report_id)
    try:
        notice = svc.issue_notice(
            db, current_user, report, response_deadline_days=response_deadline_days
        )
    except svc.ViolationWorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    db.commit()
    db.refresh(notice)

    return LegalNoticeResponse(
        notice_id=notice.id,
        notice_number=notice.notice_number,
        violation_report_id=report.id,
        status=notice.status.value
        if hasattr(notice.status, "value")
        else str(notice.status),
        issued_by=notice.issuing_officer_name,
        issued_at=notice.created_at,
        download_url=f"/violations/{report.id}/notice.pdf",
    )


# ── GET /violations/{id}/notice.pdf ──────────────────────────────────────
@router.get(
    "/{report_id}/notice.pdf",
    summary="Download the issued GO notice PDF",
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"description": "No notice has been issued for this report."},
    },
)
def download_notice(
    report_id: int,
    inline: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_inspector_or_admin),
) -> Response:
    report = _get_report(db, report_id)
    notice = (
        db.query(LegalNotice)
        .filter(LegalNotice.violation_report_id == report.id)
        .first()
    )
    if notice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No notice issued for report {report.report_number}. The "
                "admin must confirm the report and issue a notice first."
            ),
        )

    from app.services.report_service import generate_go_notice_pdf

    try:
        pdf_bytes, filename = generate_go_notice_pdf(db, notice.id)
    except ReportGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )

    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "X-Notice-Number": notice.notice_number,
        },
    )
