"""product_registry

Adds the ProductRegistry table used by authenticity_service to verify
scanned packages against a trusted reference catalog.

Revision ID: 0002_product_registry
Revises: 0001_initial_schema
Create Date: 2026-09-12 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_product_registry"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_registry",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("barcode", sa.String(length=32), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("manufacturer_name", sa.String(length=255), nullable=False),
        sa.Column("manufacturer_address", sa.Text(), nullable=False),
        sa.Column("mrp", sa.Float(), nullable=False),
        sa.Column("net_quantity", sa.String(length=100), nullable=False),
        sa.Column("fssai_license_number", sa.String(length=50), nullable=True),
        sa.Column("gst_number", sa.String(length=20), nullable=True),
        sa.Column("is_vegetarian", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("barcode", name="uq_product_registry_barcode"),
    )
    op.create_index(
        "ix_product_registry_barcode", "product_registry", ["barcode"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_product_registry_barcode", table_name="product_registry")
    op.drop_table("product_registry")
