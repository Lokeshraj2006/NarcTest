"""
FieldProof — Font Size Rules Model

Stores statutory minimum font dimensions according to Rule 7 (Table-I)
of the Legal Metrology (Packaged Commodities) Rules, 2011.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FontSizeRule(Base):
    """Statutory minimum font dimensions categorized by net quantity range."""

    __tablename__ = "font_size_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    category: Mapped[str] = mapped_column(
        String(50), default="weight_volume", nullable=False
    )  # weight_volume, length_area, count
    unit_category: Mapped[str] = mapped_column(String(30), nullable=False)  # g_ml, kg_l, units

    # Quantity range bounds (e.g. 0 to 50 g/ml)
    min_quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # None = unbounded

    # Statutory dimensions in millimeters
    min_font_height_mm: Mapped[float] = mapped_column(Float, nullable=False)
    min_font_height_molded_mm: Mapped[float] = mapped_column(Float, nullable=False)  # molded, blown, perforated
    min_width_height_ratio: Mapped[float] = mapped_column(Float, default=0.333, nullable=False)  # Width >= 1/3 Height

    statutory_reference: Mapped[str] = mapped_column(
        String(100), default="Rule 7 Table-I Legal Metrology Rules, 2011", nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
