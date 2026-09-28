"""one_notice_per_report

A violation report gets exactly one GO notice. The service serialises
transitions with a row lock; this constraint is the database-level backstop
for any path that bypasses the service.

Revision ID: 0006_one_notice_per_report
Revises: 0005_rules_and_escalation
Create Date: 2026-09-13 22:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0006_one_notice_per_report"
down_revision: Union[str, None] = "0005_rules_and_escalation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("legal_notices") as batch_op:
        batch_op.create_unique_constraint(
            "uq_legal_notices_violation_report_id", ["violation_report_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("legal_notices") as batch_op:
        batch_op.drop_constraint(
            "uq_legal_notices_violation_report_id", type_="unique"
        )
