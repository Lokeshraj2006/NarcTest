"""
FieldProof — Legal Notice Router

    GET /legal-notice/{evidence_record_id}/generate
        Streams a freshly generated PDF legal notice built from the
        EvidenceRecord + ComplianceResult for that id. Inspector/admin only.
        Add ?inline=true to render in-browser instead of forcing download.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.database import get_db
from app.models.user import User
from app.services.report_service import (
    ReportGenerationError,
    generate_legal_notice_pdf,
)

router = APIRouter(prefix="/legal-notice", tags=["legal-notice"])


@router.get(
    "/{evidence_record_id}/generate",
    summary="Generate and download the compliance report PDF for a scan",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF stream — Content-Disposition attachment by default.",
        },
        404: {"description": "No evidence record or compliance result for that id."},
    },
)
def download_legal_notice(
    evidence_record_id: int,
    inline: bool = Query(
        False,
        description="If true, use Content-Disposition: inline so browsers render the PDF.",
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response:
    """Return the generated legal-notice PDF as an application/pdf response.

    Admin-only: issuing a notice is the Controller's authority. Inspectors
    file violation reports (POST /violations) and the admin decides whether
    a notice follows.
    """
    try:
        pdf_bytes, filename = generate_legal_notice_pdf(db, evidence_record_id)
    except ReportGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "X-Legal-Notice-Filename": filename,
        },
    )
