"""
FieldProof — Inspection dashboard response schemas.

Shapes the /inspections/log and /inspections/{id} payloads consumed by
the React admin dashboard and Leaflet map.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class InspectionLogRow(BaseModel):
    """One row on the inspector dashboard table / map pin."""

    model_config = ConfigDict(from_attributes=True)

    evidence_record_id: int
    compliance_result_id: int
    product_name: Optional[str] = Field(
        None, description="From registry match, else OCR fallback, else None."
    )
    barcode: Optional[str] = None
    timestamp: datetime = Field(
        ..., description="Device timestamp (NTP-verified when available) of capture."
    )
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    overall_status: str = Field(
        ..., description='"compliant", "needs_review" (a required detail unread) or "action_needed".'
    )
    action_reason: Optional[str] = None
    pin_color: str = Field(
        ...,
        description='Precomputed marker colour for Leaflet — "green" or "red".',
    )
    # Who scanned it, and its audit flags.
    captured_by_id: Optional[int] = None
    captured_by_username: Optional[str] = None
    captured_by_role: Optional[str] = None
    complaint_number: Optional[str] = None
    complaint_status: Optional[str] = None
    rescan_of_id: Optional[int] = None
    duplicate_of_id: Optional[int] = None
    edited_fields: Optional[List[str]] = Field(
        None,
        description="Fields the user changed from the OCR reading; None = not recorded.",
    )


class InspectionLogResponse(BaseModel):
    total: int
    rows: List[InspectionLogRow]


class RuleCheckDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_number: int
    rule_name: str
    rule_code: str
    statutory_reference: str
    status: str
    score: Optional[float] = None
    detected_value: Optional[str] = None
    required_value: Optional[str] = None
    failure_reason: Optional[str] = None
    # Rule 9 only: the scale the barcode gave and the barcode type, so the
    # dashboard can show how the letter height was measured. None when no
    # measurement was made.
    scale_mm_per_px: Optional[float] = None
    scale_reference: Optional[str] = None


class AuthenticityMismatchDetail(BaseModel):
    field: str
    expected: Optional[str] = None
    detected: Optional[str] = None
    note: Optional[str] = None


class AuthenticityDetail(BaseModel):
    status: str
    matched_product_name: Optional[str] = None
    registry_id: Optional[int] = None
    message: str = ""
    mismatches: List[AuthenticityMismatchDetail] = []


class FssaiMarkDetail(BaseModel):
    status: str
    confidence: float = 0.0
    green_pixel_ratio: float = 0.0
    red_pixel_ratio: float = 0.0
    detected_region: Optional[List[int]] = None
    message: str = ""
    photo: Optional[int] = Field(
        None,
        description="Photo the mark was found on: 0 = the evidence photo, 1.. = extra photos.",
    )
    photos_checked: int = 1


class ExtraPhotoDetail(BaseModel):
    """A photo of another face of the pack sent with the scan ("Scan another part")."""

    index: int
    sha256_hash: str
    file_size_bytes: Optional[int] = None
    fssai_mark_status: Optional[str] = None


class GstinDetail(BaseModel):
    status: str = Field(
        ..., description='"PASS", "FAIL", "EXEMPT", or "NOT_RUN".'
    )
    detected_value: Optional[str] = None
    failure_reason: Optional[str] = None
    note: str = (
        "Format/checksum only — not a live GST Council registry lookup."
    )


class EvidenceMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sha256_hash: str
    file_path: str
    original_filename: str
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    timestamp_device: datetime
    timestamp_ntp: Optional[datetime] = None
    ntp_drift_seconds: Optional[float] = None
    is_tampered: bool = False
    gps_accuracy_meters: Optional[float] = None


class EditedField(BaseModel):
    """A label field the user changed from what OCR read, before submitting."""

    field: str
    extracted: Optional[Any] = None
    submitted: Optional[Any] = None


class InspectionDetailResponse(BaseModel):
    """Full detail payload for one inspected evidence record."""

    evidence_record_id: int
    compliance_result_id: int
    overall_status: str
    action_reason: Optional[str] = None
    law_reference: Optional[str] = None
    product_name: Optional[str] = None
    total_checks: int
    failed_checks: int
    rule_checks: List[RuleCheckDetail]
    barcode: Optional[str] = None
    barcode_source: Optional[str] = Field(
        None,
        description=(
            '"device" (phone) or "server" (read from the photo); None when no '
            "barcode was found, or on scans from before this was recorded."
        ),
    )
    authenticity: Optional[AuthenticityDetail] = None
    fssai_mark: Optional[FssaiMarkDetail] = None
    gstin: GstinDetail
    evidence: EvidenceMeta
    failed_rule_check_ids: List[int]
    # Lets the mobile app hide the "File report" action when this scan has
    # already been escalated, instead of letting the inspector submit and
    # then get rejected.
    has_violation_report: bool = False
    violation_report_id: Optional[int] = None
    violation_report_number: Optional[str] = None
    violation_report_status: Optional[str] = None

    # Who scanned it, and how it relates to other scans.
    captured_by_username: Optional[str] = None
    captured_by_role: Optional[str] = None
    complaint_id: Optional[int] = None
    complaint_number: Optional[str] = None
    complaint_status: Optional[str] = None
    rescan_of_id: Optional[int] = None
    rescan_ids: List[int] = Field(
        default_factory=list, description="Later scans that repeat this one."
    )
    duplicate_of_id: Optional[int] = None
    same_photo_ids: List[int] = Field(
        default_factory=list, description="Other scans submitted with this exact photo."
    )
    edited_fields: Optional[List[EditedField]] = Field(
        None, description="Fields changed from the OCR reading; None = not recorded."
    )
    extra_photos: List[ExtraPhotoDetail] = Field(
        default_factory=list,
        description="Photos of other faces sent with the scan; served by /extra-image/{index}.",
    )


class PendingComplaintRow(BaseModel):
    """One row for the /complaints/pending inspector queue (item 7 preview)."""

    model_config = ConfigDict(from_attributes=True)

    complaint_id: int
    evidence_record_id: Optional[int] = None
    product_name: Optional[str] = None
    overall_status: Optional[str] = None
    action_reason: Optional[str] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    filed_at: datetime
    status: str


class PendingComplaintsResponse(BaseModel):
    total: int
    rows: List[PendingComplaintRow]
