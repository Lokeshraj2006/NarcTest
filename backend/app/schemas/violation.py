"""
FieldProof — Violation report request/response schemas.

Shapes the inspector → admin escalation chain:
    inspector files a report  → PENDING_ADMIN_CONFIRMATION
    admin confirms / rejects  → CONFIRMED / REJECTED
    admin issues GO notice    → NOTICE_GENERATED
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ViolatedRuleItem(BaseModel):
    """One ground the inspector is citing: a failed check, or a registry mismatch."""

    rule_number: Optional[int] = Field(
        None, description="The check's number; None for a registry mismatch."
    )
    rule_code: str
    rule_name: str
    statutory_reference: str
    detected_value: Optional[str] = None
    required_value: Optional[str] = None
    failure_reason: Optional[str] = None
    source: str = Field(
        "rule", description='"rule" (a failed check) or "registry" (checked on the pack).'
    )


class ViolationReportCreate(BaseModel):
    """Inspector files a report against a scan they performed."""

    evidence_record_id: int = Field(
        ..., description="The scan this report is raised from."
    )
    complaint_id: Optional[int] = Field(
        None,
        description="Consumer complaint that triggered the inspection, if any.",
    )
    violation_summary: Optional[str] = Field(
        None,
        description=(
            "Inspector's summary. Auto-generated from the failed rule checks "
            "when omitted."
        ),
    )
    inspector_notes: Optional[str] = None
    severity: Optional[str] = Field(
        None,
        description=(
            'One of "minor", "moderate", "major", "critical". Derived from '
            "the failed rules' severities when omitted."
        ),
    )
    rule_check_ids: Optional[List[int]] = Field(
        None,
        description=(
            "Narrow the citation to these FAILed checks on the evidence "
            "record. Defaults to every FAIL; an id that didn't FAIL on this "
            "scan is refused (400)."
        ),
    )
    shop_name: Optional[str] = None
    shop_address: Optional[str] = None
    cite_registry: bool = Field(
        False,
        description=(
            "Also cite the scan's registry mismatch (an MRP higher than registered, "
            "a different net quantity or maker) under Rule 6(3). Needs pack_checked."
        ),
    )
    pack_checked: bool = Field(
        False,
        description=(
            "The inspector checked the physical pack and it contradicts the "
            "registered details — a misread photo alone can look like tampering."
        ),
    )


class AdminDecision(BaseModel):
    """Admin confirms or rejects a filed report."""

    admin_notes: Optional[str] = Field(
        None, description="Reasoning shown on the report and in the audit trail."
    )


class ViolationReportRow(BaseModel):
    """Row in the admin queue / inspector's filed list."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    report_number: str
    status: str
    severity: str
    product_name: Optional[str] = None
    shop_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    violation_summary: str
    violated_rule_count: int = 0
    evidence_record_id: Optional[int] = None
    complaint_id: Optional[int] = None
    inspector_id: int
    inspector_name: Optional[str] = None
    inspector_badge: Optional[str] = None
    admin_id: Optional[int] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    pin_color: str = Field(
        "red", description='Precomputed Leaflet marker colour for the dashboard.'
    )
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None


class ViolationReportListResponse(BaseModel):
    total: int
    rows: List[ViolationReportRow]


class ViolationReportDetail(ViolationReportRow):
    """Full report as shown on the admin review screen."""

    inspector_notes: Optional[str] = None
    admin_notes: Optional[str] = None
    shop_address: Optional[str] = None
    manufacturer_address: Optional[str] = None
    violated_rules: List[ViolatedRuleItem] = []
    evidence_sha256: Optional[str] = None
    evidence_captured_at: Optional[datetime] = None
    notice_generated: bool = False
    notice_id: Optional[int] = None


class LegalNoticeResponse(BaseModel):
    """Result of the admin issuing a GO notice."""

    notice_id: int
    notice_number: str
    violation_report_id: int
    status: str
    issued_by: str
    issued_at: datetime
    download_url: str
