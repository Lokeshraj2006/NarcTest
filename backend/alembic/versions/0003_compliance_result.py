"""compliance_result

Adds the ComplianceResult aggregate + ComplianceResultFailure association
tables introduced for item 4 of the SIH26231 extensions.

Revision ID: 0003_compliance_result
Revises: 0002_product_registry
Create Date: 2026-09-12 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_compliance_result"
down_revision: Union[str, None] = "0002_product_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "compliance_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evidence_record_id", sa.Integer(), nullable=False),
        sa.Column(
            "overall_status",
            sa.String(length=30),
            nullable=False,
            server_default="compliant",
        ),
        sa.Column("action_reason", sa.Text(), nullable=True),
        sa.Column("law_reference", sa.String(length=255), nullable=True),
        sa.Column("product_name", sa.String(length=255), nullable=True),
        sa.Column("authenticity_status", sa.String(length=50), nullable=True),
        sa.Column("fssai_mark_status", sa.String(length=30), nullable=True),
        sa.Column("gstin_status", sa.String(length=30), nullable=True),
        sa.Column("total_checks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_checks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["evidence_record_id"], ["evidence_records.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evidence_record_id", name="uq_compliance_results_evidence"
        ),
    )
    op.create_index(
        "ix_compliance_results_evidence_record_id",
        "compliance_results",
        ["evidence_record_id"],
        unique=False,
    )

    op.create_table(
        "compliance_result_failures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("compliance_result_id", sa.Integer(), nullable=False),
        sa.Column("rule_check_id", sa.Integer(), nullable=False),
        sa.Column("law_reference", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["compliance_result_id"], ["compliance_results.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["rule_check_id"], ["rule_checks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "compliance_result_id",
            "rule_check_id",
            name="uq_compliance_failure_per_check",
        ),
    )


def downgrade() -> None:
    op.drop_table("compliance_result_failures")
    op.drop_index(
        "ix_compliance_results_evidence_record_id", table_name="compliance_results"
    )
    op.drop_table("compliance_results")
