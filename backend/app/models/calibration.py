"""
FieldProof — Calibration Record Model

Stores optical calibration metrics derived from barcode detection.
Barcode is used PURELY as a physical reference anchor (GS1 EAN-13 nominal width: 37.29 mm)
to compute the scale factor S (mm/px) for font-size compliance checks.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.evidence import EvidenceRecord


class CalibrationStatus(str, Enum):
    """Status of optical calibration."""
    CALIBRATED = "CALIBRATED"
    NO_BARCODE = "NO_BARCODE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    REVIEW_NEEDED = "REVIEW_NEEDED"


class CalibrationRecord(Base):
    """Optical calibration entry calculated from reference barcode geometry."""

    __tablename__ = "calibration_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_records.id", ondelete="CASCADE"), index=True, nullable=False
    )

    barcode_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    barcode_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "EAN13"
    raw_barcode_data: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Preserved for reference, not product metadata lookup

    # Pixel measurements
    bbox_x: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_y: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_width_px: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bbox_height_px: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Physical reference & scale factor
    # Nominal EAN-13 width = 37.29 mm (GS1 standard at 100% magnification)
    reference_width_mm: Mapped[float] = mapped_column(Float, default=37.29, nullable=False)
    scale_factor_mm_per_px: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Orientation & image quality
    orientation_angle_deg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    status: Mapped[CalibrationStatus] = mapped_column(
        String(30), default=CalibrationStatus.REVIEW_NEEDED, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    evidence: Mapped[EvidenceRecord] = relationship("EvidenceRecord", back_populates="calibration_records")
