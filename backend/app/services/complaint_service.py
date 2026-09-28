"""
FieldProof — Complaint Service

Business-logic helpers around consumer complaints. Currently exposes the
auto-notification path: when a consumer scan produces a ComplianceResult
with overall_status == action_needed, open a Complaint on the consumer's
behalf and route it to the inspector queue.

A rescan, or the same photo submitted again, joins the consumer's open
complaint from the earlier scan instead of opening another, so one pack
can't stack complaints against a shop.

Zero FastAPI dependency — pure functions the routers (item 7) and unit
tests can call.
"""

from __future__ import annotations

import uuid
from typing import NamedTuple, Optional

from sqlalchemy.orm import Session

from app.models.complaint import Complaint, ComplaintStatus
from app.models.compliance_result import ComplianceResult, OverallStatus
from app.models.evidence import EvidenceRecord
from app.models.user import User, UserRole
from app.services.scan_audit import load_edited_fields


class ComplaintOutcome(NamedTuple):
    complaint: Optional[Complaint]
    created: bool


def _next_complaint_number() -> str:
    """Short, human-readable, collision-resistant complaint id."""
    return f"CMP-{uuid.uuid4().hex[:10].upper()}"


def _open_complaint_of_earlier_scan(
    db: Session, consumer: User, evidence: EvidenceRecord
) -> Optional[Complaint]:
    earlier_ids = [i for i in (evidence.rescan_of_id, evidence.duplicate_of_id) if i]
    if not earlier_ids:
        return None
    return (
        db.query(Complaint)
        .join(EvidenceRecord, EvidenceRecord.complaint_id == Complaint.id)
        .filter(
            EvidenceRecord.id.in_(earlier_ids),
            Complaint.consumer_id == consumer.id,
            Complaint.status == ComplaintStatus.PENDING_INSPECTOR_REVIEW,
        )
        .first()
    )


def auto_notify_inspector(
    db: Session,
    consumer: User,
    evidence: EvidenceRecord,
    result: ComplianceResult,
) -> ComplaintOutcome:
    """Open (or join) a pending-inspector-review Complaint for a consumer's action_needed scan.

    Returns the complaint and whether it was newly created. No complaint when:

        • the user is not a consumer, or
        • the compliance verdict is compliant.

    The evidence joins an existing pending complaint when one already covers
    this evidence, or covers the scan it repeats or the same photo.
    """
    role_value = consumer.role.value if isinstance(consumer.role, UserRole) else str(consumer.role)
    if role_value != UserRole.CONSUMER.value:
        return ComplaintOutcome(None, False)

    status_value = (
        result.overall_status.value
        if isinstance(result.overall_status, OverallStatus)
        else str(result.overall_status)
    )
    if status_value != OverallStatus.ACTION_NEEDED.value:
        return ComplaintOutcome(None, False)

    # Idempotency — avoid stacking duplicates for the same evidence.
    existing = (
        db.query(Complaint)
        .join(EvidenceRecord, EvidenceRecord.complaint_id == Complaint.id)
        .filter(
            EvidenceRecord.id == evidence.id,
            Complaint.status == ComplaintStatus.PENDING_INSPECTOR_REVIEW,
        )
        .first()
    )
    if existing is not None:
        return ComplaintOutcome(existing, False)

    earlier = _open_complaint_of_earlier_scan(db, consumer, evidence)
    if earlier is not None:
        evidence.complaint_id = earlier.id
        db.add(evidence)
        return ComplaintOutcome(earlier, False)

    description_bits = [
        f"Consumer scan flagged as {OverallStatus.ACTION_NEEDED.value}.",
    ]
    if result.action_reason:
        description_bits.append(result.action_reason)
    # What an inspector should weigh before acting on the scan.
    if evidence.rescan_of_id:
        description_bits.append(f"Rescan of scan #{evidence.rescan_of_id}.")
    if evidence.duplicate_of_id:
        description_bits.append(f"Same photo as scan #{evidence.duplicate_of_id}.")
    changed = load_edited_fields(evidence)
    if changed:
        description_bits.append(
            "Changed by the consumer before submitting: "
            + ", ".join(c["field"] for c in changed) + "."
        )
    if result.law_reference:
        description_bits.append(f"Primary reference: {result.law_reference}")

    complaint = Complaint(
        complaint_number=_next_complaint_number(),
        consumer_id=consumer.id,
        product_id=None,
        product_name=result.product_name or "Unknown product",
        brand_name=None,
        store_name=evidence.seller_name,
        description=" | ".join(description_bits),
        status=ComplaintStatus.PENDING_INSPECTOR_REVIEW,
        gps_latitude=evidence.gps_latitude,
        gps_longitude=evidence.gps_longitude,
    )
    db.add(complaint)
    db.flush()  # populate complaint.id so we can link the evidence back

    evidence.complaint_id = complaint.id
    db.add(evidence)

    return ComplaintOutcome(complaint, True)
