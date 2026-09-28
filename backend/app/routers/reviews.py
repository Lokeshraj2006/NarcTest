"""FieldProof — Supervisor review of INCONCLUSIVE tests (append-only)."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.core.dependencies import require_supervisor_or_admin
from app.database import get_db
from app.models.review import Review
from app.models.test_record import TestRecord
from app.models.user import User
from app.services import record_service

router = APIRouter(tags=["reviews"])


class ReviewIn(BaseModel):
    decision: Literal["CONFIRMED", "RETEST"]
    note: Optional[str] = Field(None, max_length=2000)


@router.post("/tests/{test_id}/review", status_code=201)
def add_review(
    test_id: int,
    body: ReviewIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_supervisor_or_admin),
):
    test = db.get(TestRecord, test_id)
    if test is None:
        raise HTTPException(404, "Test not found.")
    review = Review(test_id=test.id, reviewer_id=user.id, decision=body.decision, note=body.note)
    db.add(review)
    db.commit()
    db.refresh(review)
    db.refresh(test)
    return {
        "id": review.id,
        "test_id": test.id,
        "reviewer_id": user.id,
        "reviewer_name": user.full_name,
        "decision": review.decision,
        "note": review.note,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "review_status": record_service.review_status(test),
    }


@router.get("/reviews/pending")
def pending(
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor_or_admin),
):
    rows = (
        db.query(TestRecord)
        .options(selectinload(TestRecord.reviews), selectinload(TestRecord.officer))
        .filter(TestRecord.result == "INCONCLUSIVE", ~TestRecord.reviews.any())
        .order_by(TestRecord.id.desc())
        .all()
    )
    return [record_service.to_dict(t, request) for t in rows]
