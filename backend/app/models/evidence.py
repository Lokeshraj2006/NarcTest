"""
FieldProof — Evidence Record Model

Stores uploaded evidence images with cryptographic SHA-256 hash,
GPS coordinates, and NTP atomic timestamp sync verification.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.calibration import CalibrationRecord
    from app.models.complaint import Complaint
    from app.models.inspection import Inspection
    from app.models.rule_check import RuleCheck
    from app.models.user import User


class EvidenceRecord(Base):
    """Cryptographically verifiable evidence record."""

    __tablename__ = "evidence_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Storage information
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), default="image/jpeg", nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Evidence Integrity & Security
    sha256_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # 64-char hex

    # Geolocation
    gps_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_accuracy_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # NTP Atomic Sync Verification
    timestamp_device: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timestamp_ntp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ntp_drift_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_tampered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tamper_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Structured OCR & Vision Data
    ocr_raw_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON dump from ML Kit V2
    detected_fields_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Point-of-sale metadata (filled in by inspector during inspection; used
    # by legal notice PDF generation to name the shop/seller being notified).
    seller_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    seller_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Context link
    captured_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    inspection_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), nullable=True
    )
    complaint_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), nullable=True
    )

    # Audit context. A submitted scan is never edited: a rescan is a new record
    # pointing at the scan it repeats, a photo submitted before points at its
    # first submission, and the fields the user changed from what OCR read are
    # listed as JSON (NULL = the app sent no OCR reading to compare).
    rescan_of_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("evidence_records.id", ondelete="SET NULL"), index=True, nullable=True
    )
    duplicate_of_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("evidence_records.id", ondelete="SET NULL"), index=True, nullable=True
    )
    edited_fields_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    captured_by: Mapped[Optional[User]] = relationship("User", back_populates="uploaded_evidence")
    inspection: Mapped[Optional[Inspection]] = relationship("Inspection", back_populates="evidence_records")
    complaint: Mapped[Optional[Complaint]] = relationship("Complaint", back_populates="evidence_records")
    calibration_records: Mapped[List[CalibrationRecord]] = relationship(
        "CalibrationRecord", back_populates="evidence", cascade="all, delete-orphan"
    )
    rule_checks: Mapped[List[RuleCheck]] = relationship("RuleCheck", back_populates="evidence")
