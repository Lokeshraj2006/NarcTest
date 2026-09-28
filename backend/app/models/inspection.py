"""
FieldProof — Inspection Model

Stores field inspections conducted by legal metrology inspectors.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.evidence import EvidenceRecord
    from app.models.product import Product
    from app.models.rule_check import RuleCheck
    from app.models.user import User
    from app.models.violation import ViolationReport


class InspectionStatus(str, Enum):
    """Lifecycle status of an inspection."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FLAGGED = "flagged"


class ComplianceOutcome(str, Enum):
    """Aggregate compliance status."""
    PENDING = "pending"
    COMPLIANT = "compliant"
    VIOLATION = "violation"
    REVIEW_NEEDED = "review_needed"
    EXEMPT = "exempt"


class Inspection(Base):
    """Inspection session performed by an inspector."""

    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    inspection_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    inspector_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[InspectionStatus] = mapped_column(
        String(30), default=InspectionStatus.IN_PROGRESS, nullable=False
    )
    compliance_status: Mapped[ComplianceOutcome] = mapped_column(
        String(30), default=ComplianceOutcome.PENDING, nullable=False
    )

    location_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    store_or_market: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gps_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    inspector: Mapped[User] = relationship("User", back_populates="inspections")
    product: Mapped[Optional[Product]] = relationship("Product", back_populates="inspections")
    evidence_records: Mapped[List[EvidenceRecord]] = relationship(
        "EvidenceRecord", back_populates="inspection", cascade="all, delete-orphan"
    )
    rule_checks: Mapped[List[RuleCheck]] = relationship(
        "RuleCheck", back_populates="inspection", cascade="all, delete-orphan"
    )
    violation_reports: Mapped[List[ViolationReport]] = relationship(
        "ViolationReport", back_populates="inspection"
    )
