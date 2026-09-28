"""
FieldProof — User Model

Stores system users (Admin, Inspector, Consumer) with role-based access control.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.evidence import EvidenceRecord
    from app.models.inspection import Inspection
    from app.models.violation import ViolationReport


class UserRole(str, Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    INSPECTOR = "inspector"
    CONSUMER = "consumer"


class User(Base):
    """User account entity."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(20), default=UserRole.CONSUMER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    badge_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # For inspectors
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    inspections: Mapped[List[Inspection]] = relationship("Inspection", back_populates="inspector")
    complaints: Mapped[List[Complaint]] = relationship("Complaint", back_populates="consumer")
    uploaded_evidence: Mapped[List[EvidenceRecord]] = relationship(
        "EvidenceRecord", back_populates="captured_by"
    )
    assigned_violations: Mapped[List[ViolationReport]] = relationship(
        "ViolationReport", foreign_keys="ViolationReport.inspector_id", back_populates="inspector"
    )
    confirmed_violations: Mapped[List[ViolationReport]] = relationship(
        "ViolationReport", foreign_keys="ViolationReport.admin_id", back_populates="admin"
    )
