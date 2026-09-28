"""
FieldProof — Penalty Model

Stores statutory penalties looked up and assessed under the Legal Metrology Act, 2009.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.legal_notice import LegalNotice
    from app.models.user import User
    from app.models.violation import ViolationReport


class PenaltyStatus(str, Enum):
    """Lifecycle of an assessed penalty."""
    ASSESSED = "assessed"
    ISSUED = "issued"
    PAID = "paid"
    APPEALED = "appealed"
    WAIVED = "waived"


class OffenseTier(str, Enum):
    """Offense tier per Section 36/49."""
    FIRST_OFFENSE = "first_offense"
    SECOND_OFFENSE = "second_offense"
    SUBSEQUENT_OFFENSE = "subsequent_offense"


class Penalty(Base):
    """Statutory penalty assessed against a confirmed violation."""

    __tablename__ = "penalties"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    violation_report_id: Mapped[int] = mapped_column(
        ForeignKey("violation_reports.id", ondelete="CASCADE"), nullable=False
    )
    issued_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    legal_act: Mapped[str] = mapped_column(
        String(100), default="Legal Metrology Act, 2009", nullable=False
    )
    section_code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "Section 36(1)"
    offense_tier: Mapped[OffenseTier] = mapped_column(
        String(30), default=OffenseTier.FIRST_OFFENSE, nullable=False
    )

    min_fine_inr: Mapped[float] = mapped_column(Float, nullable=False)
    max_fine_inr: Mapped[float] = mapped_column(Float, nullable=False)
    assessed_fine_inr: Mapped[float] = mapped_column(Float, nullable=False)

    imprisonment_months: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    compounding_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    status: Mapped[PenaltyStatus] = mapped_column(
        String(20), default=PenaltyStatus.ASSESSED, nullable=False
    )
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    violation_report: Mapped[ViolationReport] = relationship("ViolationReport", back_populates="penalties")
    issued_by: Mapped[Optional[User]] = relationship("User")
    legal_notices: Mapped[List[LegalNotice]] = relationship("LegalNotice", back_populates="penalty")
