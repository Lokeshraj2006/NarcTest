"""evidence_seller_fields

Adds seller_name / seller_address to evidence_records so the legal-notice
PDF (item 6) can name the shop/seller being notified.

Revision ID: 0004_evidence_seller_fields
Revises: 0003_compliance_result
Create Date: 2026-09-12 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_evidence_seller_fields"
down_revision: Union[str, None] = "0003_compliance_result"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evidence_records",
        sa.Column("seller_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "evidence_records",
        sa.Column("seller_address", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evidence_records", "seller_address")
    op.drop_column("evidence_records", "seller_name")
