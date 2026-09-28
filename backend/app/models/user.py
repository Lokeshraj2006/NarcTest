"""
FieldProof — User Model

Roles: field_officer, supervisor, admin (lowercase strings).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.test_record import TestRecord


class UserRole(str, Enum):
    """User roles for RBAC."""
    FIELD_OFFICER = "field_officer"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class User(Base):
    """User account entity."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.FIELD_OFFICER.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    badge_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tests: Mapped[List["TestRecord"]] = relationship("TestRecord", back_populates="officer")
