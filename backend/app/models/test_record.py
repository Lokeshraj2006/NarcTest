"""FieldProof — Test record (append-only, signed, hash-chained)."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.review import Review
    from app.models.user import User


class TestRecord(Base):
    __tablename__ = "test_records"
    __test__ = False  # stop pytest trying to collect this class

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_uid: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    # ISO strings, stored exactly as they were signed
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    ntp_time: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    time_source: Mapped[str] = mapped_column(String(20), nullable=False)
    device_time: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    clock_drift_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_accuracy_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    officer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    device_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    kit_id: Mapped[int] = mapped_column(ForeignKey("kit_profiles.id"), index=True, nullable=False)
    kit_code: Mapped[str] = mapped_column(String(64), nullable=False)
    kit_name: Mapped[str] = mapped_column(String(200), nullable=False)
    kit_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kit_outcomes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    client_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    client_hash_match: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    result: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    outcome_label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    confidence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    measured_lab: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    measured_rgb: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    delta_e_by_outcome: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    quality: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    lab_sample_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    signed_payload: Mapped[str] = mapped_column(Text, nullable=False)
    prev_record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    signature: Mapped[str] = mapped_column(String(200), nullable=False)
    key_id: Mapped[str] = mapped_column(String(40), nullable=False)

    officer: Mapped["User"] = relationship("User", back_populates="tests")
    reviews: Mapped[List["Review"]] = relationship(
        "Review", back_populates="test", order_by="Review.id"
    )
