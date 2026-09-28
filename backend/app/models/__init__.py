"""
FieldProof — SQLAlchemy Models Registry

Central imports for all models so Alembic and SQLAlchemy can discover them.
"""

from __future__ import annotations

from app.models.calibration import CalibrationRecord, CalibrationStatus
from app.models.complaint import Complaint, ComplaintStatus
from app.models.compliance_result import (
    ComplianceResult,
    ComplianceResultFailure,
    OverallStatus,
)
from app.models.evidence import EvidenceRecord
from app.models.font_size_rule import FontSizeRule
from app.models.inspection import ComplianceOutcome, Inspection, InspectionStatus
from app.models.legal_notice import LegalNotice, NoticeStatus
from app.models.penalty import OffenseTier, Penalty, PenaltyStatus
from app.models.product import Product
from app.models.product_registry import ProductRegistry
from app.models.rule import Rule, RuleCategory, RuleSeverity
from app.models.rule_check import CheckStatus, RuleCheck
from app.models.user import User, UserRole
from app.models.violation import ViolationReport, ViolationSeverity, ViolationStatus

__all__ = [
    "User",
    "UserRole",
    "Product",
    "ProductRegistry",
    "EvidenceRecord",
    "Inspection",
    "InspectionStatus",
    "ComplianceOutcome",
    "Complaint",
    "ComplaintStatus",
    "RuleCheck",
    "CheckStatus",
    "Rule",
    "RuleCategory",
    "RuleSeverity",
    "ViolationReport",
    "ViolationStatus",
    "ViolationSeverity",
    "Penalty",
    "PenaltyStatus",
    "OffenseTier",
    "LegalNotice",
    "NoticeStatus",
    "CalibrationRecord",
    "CalibrationStatus",
    "FontSizeRule",
    "ComplianceResult",
    "ComplianceResultFailure",
    "OverallStatus",
]
