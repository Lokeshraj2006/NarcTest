"""rules_catalogue_and_escalation

Brings the migration chain up to the current models:

  * `rules` — the 13 compliance rules stored as data so the dashboard can
    list them and the admin can toggle/tune them without a redeploy.
  * `rule_checks.rule_id` — FK to that catalogue. Nullable, and the
    citation columns stay denormalised, so a check keeps the wording that
    applied when it ran even if the definition later changes.
  * `violation_reports` — anchored on evidence rather than product (a scan
    creates an EvidenceRecord, never a Product), plus denormalised
    shop/manufacturer columns so the admin queue renders without joins,
    and `rejected_at` to mirror `confirmed_at`.

Revision ID: 0005_rules_catalogue_and_escalation
Revises: 0004_evidence_seller_fields
Create Date: 2026-09-13 16:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Kept under 32 chars: alembic_version.version_num is VARCHAR(32).
revision: str = "0005_rules_and_escalation"
down_revision: Union[str, None] = "0004_evidence_seller_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Rule catalogue ───────────────────────────────────────────────
    op.create_table(
        "rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rule_number", sa.Integer(), nullable=False),
        sa.Column("rule_code", sa.String(length=50), nullable=False),
        sa.Column("rule_name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("statutory_reference", sa.String(length=255), nullable=False),
        sa.Column(
            "category", sa.String(length=30), nullable=False, server_default="declaration"
        ),
        sa.Column(
            "default_severity",
            sa.String(length=20),
            nullable=False,
            server_default="moderate",
        ),
        sa.Column(
            "requires_cv", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("config_json", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_number", name="uq_rules_rule_number"),
        sa.UniqueConstraint("rule_code", name="uq_rules_rule_code"),
    )
    op.create_index("ix_rules_rule_number", "rules", ["rule_number"])
    op.create_index("ix_rules_rule_code", "rules", ["rule_code"])

    # ── RuleCheck → Rule ─────────────────────────────────────────────
    # batch_alter_table so this also runs on SQLite, which cannot ALTER
    # constraints in place (the .env documents a SQLite fallback).
    with op.batch_alter_table("rule_checks") as batch_op:
        batch_op.add_column(sa.Column("rule_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_rule_checks_rule_id", "rules", ["rule_id"], ["id"], ondelete="SET NULL"
        )
        # Citations outgrew 100 chars once full Act names were cited.
        batch_op.alter_column(
            "statutory_reference",
            existing_type=sa.String(length=100),
            type_=sa.String(length=255),
            existing_nullable=False,
        )

    # ── Violation reports: evidence-anchored + dashboard columns ─────
    with op.batch_alter_table("violation_reports") as batch_op:
        batch_op.add_column(sa.Column("evidence_record_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("shop_name", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("shop_address", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("manufacturer_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(sa.Column("manufacturer_address", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("product_name", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_violation_reports_evidence",
            "evidence_records",
            ["evidence_record_id"],
            ["id"],
            ondelete="SET NULL",
        )
        # A scan yields evidence, not a Product row, so a report must be able
        # to exist without one.
        batch_op.alter_column(
            "product_id", existing_type=sa.Integer(), nullable=True
        )

    op.create_index(
        "ix_violation_reports_evidence_record_id",
        "violation_reports",
        ["evidence_record_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_violation_reports_evidence_record_id", table_name="violation_reports"
    )
    with op.batch_alter_table("violation_reports") as batch_op:
        batch_op.alter_column(
            "product_id", existing_type=sa.Integer(), nullable=False
        )
        batch_op.drop_constraint("fk_violation_reports_evidence", type_="foreignkey")
        for column in (
            "rejected_at",
            "product_name",
            "manufacturer_address",
            "manufacturer_name",
            "shop_address",
            "shop_name",
            "evidence_record_id",
        ):
            batch_op.drop_column(column)

    with op.batch_alter_table("rule_checks") as batch_op:
        batch_op.alter_column(
            "statutory_reference",
            existing_type=sa.String(length=255),
            type_=sa.String(length=100),
            existing_nullable=False,
        )
        batch_op.drop_constraint("fk_rule_checks_rule_id", type_="foreignkey")
        batch_op.drop_column("rule_id")

    op.drop_index("ix_rules_rule_code", table_name="rules")
    op.drop_index("ix_rules_rule_number", table_name="rules")
    op.drop_table("rules")
