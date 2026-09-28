"""
FieldProof — Scan audit helpers

A submitted scan is evidence and is never edited. These helpers add context
around it: which label fields the user changed from what OCR read, and the
rows the history views list (who scanned, rescans, re-used photos).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload

from app.models.compliance_result import ComplianceResult, OverallStatus
from app.models.evidence import EvidenceRecord
from app.schemas.inspection import InspectionLogRow
from app.schemas.scan import OcrFields


def enum_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def pin_color(status_value: Optional[str]) -> str:
    """Map pin for a verdict: red = action needed, amber = needs review, green = compliant."""
    if status_value == OverallStatus.ACTION_NEEDED.value:
        return "red"
    if status_value == OverallStatus.NEEDS_REVIEW.value:
        return "amber"
    return "green"


def _comparable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = " ".join(str(value).split())
    return text or None


def edited_fields(
    extracted: Optional[Dict[str, Any]], submitted: Dict[str, Any]
) -> Optional[List[Dict[str, Any]]]:
    """Fields whose submitted value differs from the OCR reading.

    None when the app sent no reading, so "not recorded" is never confused
    with "nothing changed". Whitespace-only differences don't count.
    """
    if extracted is None:
        return None
    changes: List[Dict[str, Any]] = []
    for name in OcrFields.model_fields:
        if name == "raw_text":
            continue
        before, after = extracted.get(name), submitted.get(name)
        if _comparable(before) != _comparable(after):
            changes.append({"field": name, "extracted": before, "submitted": after})
    return changes


def load_edited_fields(evidence: Optional[EvidenceRecord]) -> Optional[List[Dict[str, Any]]]:
    if evidence is None or evidence.edited_fields_json is None:
        return None
    try:
        value = json.loads(evidence.edited_fields_json)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, list) else None


def log_row_options():
    """Eager loads log_row needs, so a long list doesn't query per row."""
    return (
        joinedload(ComplianceResult.evidence).joinedload(EvidenceRecord.captured_by),
        joinedload(ComplianceResult.evidence).joinedload(EvidenceRecord.complaint),
    )


def log_row(result: ComplianceResult) -> InspectionLogRow:
    ev = result.evidence
    scanned_by = ev.captured_by if ev else None
    complaint = ev.complaint if ev else None
    edited = load_edited_fields(ev)
    status_value = enum_value(result.overall_status)
    try:
        barcode = json.loads(ev.detected_fields_json or "{}").get("barcode") if ev else None
    except (ValueError, TypeError, AttributeError):
        barcode = None
    return InspectionLogRow(
        evidence_record_id=result.evidence_record_id,
        compliance_result_id=result.id,
        product_name=result.product_name,
        barcode=barcode,
        timestamp=(ev.timestamp_ntp or ev.timestamp_device) if ev else result.created_at,
        gps_latitude=ev.gps_latitude if ev else None,
        gps_longitude=ev.gps_longitude if ev else None,
        overall_status=status_value,
        action_reason=result.action_reason,
        pin_color=pin_color(status_value),
        captured_by_id=ev.captured_by_id if ev else None,
        captured_by_username=scanned_by.username if scanned_by else None,
        captured_by_role=enum_value(scanned_by.role) if scanned_by else None,
        complaint_number=complaint.complaint_number if complaint else None,
        complaint_status=enum_value(complaint.status) if complaint else None,
        rescan_of_id=ev.rescan_of_id if ev else None,
        duplicate_of_id=ev.duplicate_of_id if ev else None,
        edited_fields=[e.get("field") for e in edited] if edited is not None else None,
    )
