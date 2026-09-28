"""FieldProof — Kit profile (the colours a test kit can show)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KitProfile(Base):
    __tablename__ = "kit_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    reagent: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    read_time_s: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    # [{"label", "category", "srgb": [r,g,b], "lab": [L,a,b]}]
    outcomes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    max_delta_e: Mapped[float] = mapped_column(Float, default=14.0, nullable=False)
    min_margin: Mapped[float] = mapped_column(Float, default=4.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
