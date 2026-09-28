"""
FieldProof — Aggregate Compliance Result Model

Per-EvidenceRecord roll-up that condenses the 13 individual RuleCheck
outcomes (plus authenticity + FSSAI mark + GSTIN cross-checks) into a
single verdict the inspector/consumer/dashboard can act on.

Design:
    ComplianceResult
        ├── evidence_record_id   (unique — one aggregate per evidence)
        ├── overall_status       enum: compliant | needs_review | action_needed
        ├── action_reason        text (concatenated human summary)
        ├── law_reference        text (primary statutory reference)
        ├── authenticity_status  from authenticity_service verdict
        ├── fssai_mark_status    from fssai_mark_service verdict
        └── failed_rule_checks   M2M → RuleCheck rows that FAILed,
                                 each row carrying its own per-failure
                                 law_reference on the association row.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.evidence import EvidenceRecord
    from app.models.rule_check import RuleCheck


class OverallStatus(str, Enum):
    """Two-state consumer/inspector-facing verdict."""
    COMPLIANT = "compliant"
    ACTION_NEEDED = "action_needed"
    # No evidence of a violation, but a required detail couldn't be read, so
    # it isn't shown as compliant. Raises no complaint on its own.
    NEEDS_REVIEW = "needs_review"


class ComplianceResultFailure(Base):
    """Association row: one failed RuleCheck attached to one ComplianceResult.

    Carries its own law_reference so different failures under the same
    aggregate can cite different statutes (e.g. Rule 6 for missing MRP,
    Rule 46 CGST for a bad GSTIN).
    """

    __tablename__ = "compliance_result_failures"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    compliance_result_id: Mapped[int] = mapped_column(
        ForeignKey("compliance_results.id", ondelete="CASCADE"), nullable=False
    )
    rule_check_id: Mapped[int] = mapped_column(
        ForeignKey("rule_checks.id", ondelete="CASCADE"), nullable=False
    )
    law_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    compliance_result: Mapped[ComplianceResult] = relationship(
        "ComplianceResult", back_populates="failures"
    )
    rule_check: Mapped[RuleCheck] = relationship("RuleCheck")

    __table_args__ = (
        UniqueConstraint(
            "compliance_result_id",
            "rule_check_id",
            name="uq_compliance_failure_per_check",
        ),
    )


class ComplianceResult(Base):
    """Aggregate outcome for one EvidenceRecord (one per scan/inspection)."""

    __tablename__ = "compliance_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    evidence_record_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_records.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    overall_status: Mapped[OverallStatus] = mapped_column(
        String(30), default=OverallStatus.COMPLIANT, nullable=False
    )
    action_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    law_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Cached product name for dashboard rendering — set from the authenticity
    # registry match if available, otherwise from the OCR payload as a fallback.
    product_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Extra top-level signals for quick dashboard rendering / API responses
    authenticity_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fssai_mark_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    gstin_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    total_checks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_checks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    evidence: Mapped[EvidenceRecord] = relationship("EvidenceRecord")
    failures: Mapped[List[ComplianceResultFailure]] = relationship(
        "ComplianceResultFailure",
        back_populates="compliance_result",
        cascade="all, delete-orphan",
    )
