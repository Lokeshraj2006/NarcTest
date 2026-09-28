"""
FieldProof — Product Registry Model

Reference registry of authentic packaged products, keyed by barcode/GTIN.
Used by the authenticity service to detect forged / tampered labels by
comparing OCR-detected fields against the trusted registry values.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductRegistry(Base):
    """Authoritative reference record for a manufactured product (by GTIN/barcode)."""

    __tablename__ = "product_registry"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Primary lookup key — GTIN-8 / EAN-13 / UPC-A / GTIN-14
    barcode: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)

    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer_address: Mapped[str] = mapped_column(Text, nullable=False)

    mrp: Mapped[float] = mapped_column(Float, nullable=False)  # INR, inclusive of taxes
    net_quantity: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "500 g", "1 L"

    fssai_license_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Other licences printed on the same genuine pack, comma-separated — e.g. a
    # manufacturing unit's own licence beside the brand owner's.
    additional_fssai_license_numbers: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gst_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # True → vegetarian (green FSSAI dot expected); False → non-veg (brown/red dot expected)
    is_vegetarian: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
