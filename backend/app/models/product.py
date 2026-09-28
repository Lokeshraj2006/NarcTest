"""
FieldProof — Product Model

Stores packaged commodity products and their declared label parameters.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.complaint import Complaint
    from app.models.inspection import Inspection
    from app.models.rule_check import RuleCheck
    from app.models.violation import ViolationReport


class Product(Base):
    """Packaged commodity product entity under Legal Metrology Rules."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    generic_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    brand_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    # Declarations per Rule 6
    manufacturer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manufacturer_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    packer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    packer_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    importer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    importer_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country_of_origin: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Net quantity & pricing
    net_quantity_raw: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "500 g", "1 L"
    net_quantity_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_quantity_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # g, kg, ml, l, m, number
    mrp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # in INR (inclusive of all taxes)
    mrp_raw: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Dates
    mfg_date_raw: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Month & Year of packing
    expiry_date_raw: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Best before / use by

    # Consumer care
    consumer_care_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    consumer_care_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    consumer_care_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    consumer_care_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Statutory details & applicability parameters
    lmpc_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Importer registration
    package_type: Mapped[str] = mapped_column(
        String(50), default="standard_retail", nullable=False
    )  # standard_retail, wholesale, industrial_consumer, institutional_consumer, agricultural_50kg
    buyer_type: Mapped[str] = mapped_column(
        String(50), default="retail_consumer", nullable=False
    )  # retail_consumer, institutional, industrial
    is_exempt: Mapped[bool] = mapped_column(default=False, nullable=False)
    exemption_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    inspections: Mapped[List[Inspection]] = relationship("Inspection", back_populates="product")
    complaints: Mapped[List[Complaint]] = relationship("Complaint", back_populates="product")
    rule_checks: Mapped[List[RuleCheck]] = relationship("RuleCheck", back_populates="product")
    violation_reports: Mapped[List[ViolationReport]] = relationship(
        "ViolationReport", back_populates="product"
    )

    __table_args__ = (
        Index("idx_product_generic_brand", "generic_name", "brand_name"),
    )
