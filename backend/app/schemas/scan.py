"""
FieldProof — Consumer Scan Request/Response Schemas.

The scan pipeline is the entry point for both consumer app scans and
inspector captures. Request shape is intentionally structured JSON so
this endpoint can be exercised without a real OCR pipeline sitting
in front of it; the image itself is still uploaded as multipart form data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OcrFields(BaseModel):
    product_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    manufacturer_address: Optional[str] = None
    mrp: Optional[float] = None
    net_quantity: Optional[str] = None
    fssai_license_number: Optional[str] = None
    gst_number: Optional[str] = None
    mfg_date: Optional[str] = None
    expiry_date: Optional[str] = None
    country_of_origin: Optional[str] = None
    # Rule 8 — consumer care contact details
    consumer_care_phone: Optional[str] = None
    consumer_care_email: Optional[str] = None
    # Rule 12 — LMPC registration number
    lmpc_number: Optional[str] = None
    batch_number: Optional[str] = None
    # Full OCR text. Rule 5 scans this for the mandatory "inclusive of all
    # taxes" wording, which is easily missed by field-level extraction.
    raw_text: Optional[str] = None


class ScanContext(BaseModel):
    barcode: Optional[str] = Field(
        None, description="GTIN/EAN/UPC read from the package."
    )
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_accuracy_meters: Optional[float] = None
    ocr_fields: OcrFields = Field(default_factory=OcrFields)
    seller_name: Optional[str] = None
    seller_address: Optional[str] = None
    fssai_region: Optional[List[int]] = Field(
        None,
        description="Optional (x, y, w, h) ROI around the FSSAI mark.",
    )
    is_imported: Optional[bool] = Field(
        None,
        description=(
            "Whether the commodity is imported. Drives rules 2 and 12 — when "
            "omitted those return REVIEW rather than guessing."
        ),
    )

    # ── Chain of custody ────────────────────────────────────────────────
    device_timestamp: Optional[datetime] = Field(
        None,
        description=(
            "When the device says the photo was captured. Falls back to "
            "server receipt time when absent."
        ),
    )
    ntp_timestamp: Optional[datetime] = Field(
        None,
        description=(
            "Atomic time from an NTP server at capture. Its agreement with "
            "device_timestamp is what makes the timestamp evidentially useful."
        ),
    )
    ntp_drift_seconds: Optional[float] = Field(
        None,
        description="Absolute |device - NTP| in seconds, as measured on device.",
    )

    # ── Calibration inputs for rules 9-11 ───────────────────────────────
    barcode_bbox: Optional[List[float]] = Field(
        None,
        description=(
            "(x, y, w, h) of the detected barcode in image pixels. An EAN-13 "
            "symbol is a known 37.29 mm wide, giving the mm-per-pixel scale "
            "needed to measure font height under Rule 9."
        ),
    )
    barcode_format: Optional[str] = Field(
        None, description='e.g. "ean13", "upca" — sets the physical reference width.'
    )
    text_blocks: Optional[List[Dict[str, Any]]] = Field(
        None,
        description=(
            'OCR blocks as [{"text": str, "x": n, "y": n, "width": n, '
            '"height": n}]. Heights are measured against the barcode scale.'
        ),
    )
    image_width_px: Optional[int] = None
    image_height_px: Optional[int] = None

    # ── Audit context ───────────────────────────────────────────────────
    rescan_of_id: Optional[int] = Field(
        None,
        description="Evidence record this scan repeats. The original is never changed.",
    )
    extracted_fields: Optional[OcrFields] = Field(
        None,
        description=(
            "What the app's OCR read before the user reviewed it. Fields that "
            "differ in ocr_fields are recorded as changed by the user."
        ),
    )


class RuleCheckSummary(BaseModel):
    """One of the 13 rule outcomes, as returned to the scanning client."""

    id: int
    rule_number: int
    rule_code: str
    rule_name: str
    statutory_reference: str
    status: str = Field(..., description='"PASS", "FAIL", "REVIEW" or "EXEMPT".')
    detected_value: Optional[str] = None
    required_value: Optional[str] = None
    failure_reason: Optional[str] = None


class ScanResponse(BaseModel):
    evidence_record_id: int
    compliance_result_id: int
    overall_status: str
    action_reason: Optional[str] = None
    law_reference: Optional[str] = None
    product_name: Optional[str] = None
    pin_color: str
    barcode: Optional[str] = None
    barcode_source: Optional[str] = Field(
        None,
        description=(
            '"device" when the phone read the barcode, "server" when it was read '
            "from the photo here; None when neither found one."
        ),
    )
    authenticity: Optional[Dict[str, Any]] = None
    fssai_mark: Optional[Dict[str, Any]] = None
    gstin: Dict[str, Any]
    rule_checks: List[RuleCheckSummary] = Field(
        default_factory=list,
        description="All 13 rule outcomes, ordered by rule number.",
    )
    checks_summary: Dict[str, int] = Field(
        default_factory=dict,
        description='Counts by status, e.g. {"PASS": 9, "FAIL": 2, "REVIEW": 2}.',
    )
    failed_rule_check_ids: List[int]
    complaint_created: bool = Field(
        False, description="True when a pending-inspector Complaint was auto-created."
    )
    complaint_linked: bool = Field(
        False,
        description=(
            "True when this scan joined the open complaint of the scan it repeats "
            "or of the same photo, instead of opening another."
        ),
    )
    complaint_id: Optional[int] = None
    complaint_number: Optional[str] = None
    rescan_of_id: Optional[int] = None
    duplicate_of_id: Optional[int] = Field(
        None, description="Earlier scan submitted with this exact photo."
    )
    edited_fields: Optional[List[Dict[str, Any]]] = Field(
        None,
        description=(
            'Fields changed from the OCR reading, as {"field", "extracted", '
            '"submitted"}. None when the app sent no reading to compare.'
        ),
    )
