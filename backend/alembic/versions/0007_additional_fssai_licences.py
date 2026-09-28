"""additional_fssai_licences

A genuine pack can print more than one FSSAI licence: the brand owner's and
the manufacturing unit's. Reading either one must agree with the registry.

Revision ID: 0007_additional_fssai_licences
Revises: 0006_one_notice_per_report
Create Date: 2026-09-14 04:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0007_additional_fssai_licences"
down_revision: Union[str, None] = "0006_one_notice_per_report"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("product_registry") as batch_op:
        batch_op.add_column(
            sa.Column("additional_fssai_license_numbers", sa.String(length=255), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("product_registry") as batch_op:
        batch_op.drop_column("additional_fssai_license_numbers")
