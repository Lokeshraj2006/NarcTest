"""
FieldProof — Rule Check Model

Stores the outcome of each individual rule check (13 independent points)
under the Legal Metrology (Packaged Commodities) Rules, 2011.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.evidence import EvidenceRecord
    from app.models.inspection import Inspection
    from app.models.product import Product
    from app.models.rule import Rule


class CheckStatus(str, Enum):
    """Result of an individual rule check."""
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    EXEMPT = "EXEMPT"


class RuleCheck(Base):
    """Result of one rule check against a product/evidence."""

    __tablename__ = "rule_checks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=True
    )
    inspection_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), nullable=True
    )
    evidence_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("evidence_records.id", ondelete="SET NULL"), nullable=True
    )

    # FK to the seeded Rule definition. Nullable so historical checks survive
    # a rule being removed; the denormalised columns below keep the citation
    # as it stood when the check ran, even if the definition later changes.
    rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("rules.id", ondelete="SET NULL"), nullable=True
    )

    rule_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 to 13
    rule_name: Mapped[str] = mapped_column(String(150), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    statutory_reference: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[CheckStatus] = mapped_column(String(20), default=CheckStatus.REVIEW, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 0.0 to 1.0 confidence/compliance

    detected_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    required_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    product: Mapped[Optional[Product]] = relationship("Product", back_populates="rule_checks")
    inspection: Mapped[Optional[Inspection]] = relationship("Inspection", back_populates="rule_checks")
    evidence: Mapped[Optional[EvidenceRecord]] = relationship("EvidenceRecord", back_populates="rule_checks")
    rule: Mapped[Optional[Rule]] = relationship("Rule", back_populates="rule_checks")
