"""
FieldProof — Complaint Model

Stores citizen / consumer complaints against packaged commodities.
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
    from app.models.user import User
    from app.models.violation import ViolationReport


class ComplaintStatus(str, Enum):
    """Lifecycle status of a consumer complaint."""
    SUBMITTED = "submitted"
    PENDING_INSPECTOR_REVIEW = "pending_inspector_review"
    UNDER_REVIEW = "under_review"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class Complaint(Base):
    """Consumer complaint entity."""

    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    complaint_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    consumer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)

    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    store_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[ComplaintStatus] = mapped_column(
        String(30), default=ComplaintStatus.SUBMITTED, nullable=False
    )

    gps_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    consumer: Mapped[User] = relationship("User", back_populates="complaints")
    product: Mapped[Optional[Product]] = relationship("Product", back_populates="complaints")
    evidence_records: Mapped[List[EvidenceRecord]] = relationship(
        "EvidenceRecord", back_populates="complaint", cascade="all, delete-orphan"
    )
    violation_reports: Mapped[List[ViolationReport]] = relationship(
        "ViolationReport", back_populates="complaint"
    )
