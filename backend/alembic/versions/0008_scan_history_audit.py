"""scan_history_audit

A submitted scan is never edited. These columns add context around it: a
rescan points at the scan it repeats, a photo submitted before points at its
first submission, and the label fields the user changed from what OCR read
are listed.

Revision ID: 0008_scan_history_audit
Revises: 0007_additional_fssai_licences
Create Date: 2026-09-14 10:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0008_scan_history_audit"
down_revision: Union[str, None] = "0007_additional_fssai_licences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("evidence_records") as batch_op:
        batch_op.add_column(sa.Column("rescan_of_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("duplicate_of_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("edited_fields_json", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_evidence_records_rescan_of_id", "evidence_records",
            ["rescan_of_id"], ["id"], ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_evidence_records_duplicate_of_id", "evidence_records",
            ["duplicate_of_id"], ["id"], ondelete="SET NULL",
        )
        batch_op.create_index("ix_evidence_records_rescan_of_id", ["rescan_of_id"])
        batch_op.create_index("ix_evidence_records_duplicate_of_id", ["duplicate_of_id"])


def downgrade() -> None:
    with op.batch_alter_table("evidence_records") as batch_op:
        batch_op.drop_index("ix_evidence_records_duplicate_of_id")
        batch_op.drop_index("ix_evidence_records_rescan_of_id")
        batch_op.drop_constraint("fk_evidence_records_duplicate_of_id", type_="foreignkey")
        batch_op.drop_constraint("fk_evidence_records_rescan_of_id", type_="foreignkey")
        batch_op.drop_column("edited_fields_json")
        batch_op.drop_column("duplicate_of_id")
        batch_op.drop_column("rescan_of_id")
