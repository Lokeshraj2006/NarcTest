"""
FieldProof — Rule Definition Model

The 13 compliance rules stored as data rather than hard-coded constants, so
the admin dashboard can view them, toggle them, and adjust thresholds
without a redeploy. `RuleCheck` rows reference these definitions, which
keeps statutory citations consistent across the API, the PDFs and the UI.

Seeded by `app.scripts.seed_rules`.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.rule_check import RuleCheck


class RuleCategory(str, Enum):
    """Grouping used by the dashboard to organise the 13 checks."""
    DECLARATION = "declaration"      # what must appear on the label
    PRESENTATION = "presentation"    # how it must appear (size, contrast, placement)
    STATUTORY = "statutory"          # licences and registrations


class RuleSeverity(str, Enum):
    """Default severity applied to a violation of this rule."""
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class Rule(Base):
    """One of the 13 Legal Metrology compliance checks."""

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    rule_number: Mapped[int] = mapped_column(
        Integer, unique=True, index=True, nullable=False
    )  # 1..13
    rule_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    rule_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    statutory_reference: Mapped[str] = mapped_column(String(255), nullable=False)

    category: Mapped[RuleCategory] = mapped_column(
        String(30), default=RuleCategory.DECLARATION, nullable=False
    )
    default_severity: Mapped[RuleSeverity] = mapped_column(
        String(20), default=RuleSeverity.MODERATE, nullable=False
    )

    # True when the check depends on computer-vision measurement (font height,
    # contrast, placement). Those return REVIEW until calibration is wired up,
    # rather than reporting an unverified PASS.
    requires_cv: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Admin can disable a rule (e.g. exempt categories) without code changes.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Tunable thresholds as JSON, e.g. {"min_font_mm": 1.0}.
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    rule_checks: Mapped[List[RuleCheck]] = relationship(
        "RuleCheck", back_populates="rule"
    )
