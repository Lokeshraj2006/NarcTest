"""initial_schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='consumer'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('badge_number', sa.String(length=50), nullable=True),
        sa.Column('phone_number', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # 2. products
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('generic_name', sa.String(length=255), nullable=False),
        sa.Column('brand_name', sa.String(length=150), nullable=True),
        sa.Column('manufacturer_name', sa.String(length=255), nullable=True),
        sa.Column('manufacturer_address', sa.Text(), nullable=True),
        sa.Column('packer_name', sa.String(length=255), nullable=True),
        sa.Column('packer_address', sa.Text(), nullable=True),
        sa.Column('importer_name', sa.String(length=255), nullable=True),
        sa.Column('importer_address', sa.Text(), nullable=True),
        sa.Column('country_of_origin', sa.String(length=100), nullable=True),
        sa.Column('net_quantity_raw', sa.String(length=100), nullable=True),
        sa.Column('net_quantity_value', sa.Float(), nullable=True),
        sa.Column('net_quantity_unit', sa.String(length=20), nullable=True),
        sa.Column('mrp', sa.Float(), nullable=True),
        sa.Column('mrp_raw', sa.String(length=100), nullable=True),
        sa.Column('mfg_date_raw', sa.String(length=50), nullable=True),
        sa.Column('expiry_date_raw', sa.String(length=50), nullable=True),
        sa.Column('consumer_care_name', sa.String(length=150), nullable=True),
        sa.Column('consumer_care_email', sa.String(length=255), nullable=True),
        sa.Column('consumer_care_phone', sa.String(length=50), nullable=True),
        sa.Column('consumer_care_address', sa.Text(), nullable=True),
        sa.Column('lmpc_number', sa.String(length=100), nullable=True),
        sa.Column('package_type', sa.String(length=50), server_default='standard_retail', nullable=False),
        sa.Column('buyer_type', sa.String(length=50), server_default='retail_consumer', nullable=False),
        sa.Column('is_exempt', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('exemption_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_products_generic_name'), 'products', ['generic_name'], unique=False)
    op.create_index('idx_product_generic_brand', 'products', ['generic_name', 'brand_name'], unique=False)

    # 3. inspections
    op.create_table(
        'inspections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('inspection_number', sa.String(length=50), nullable=False),
        sa.Column('inspector_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='in_progress', nullable=False),
        sa.Column('compliance_status', sa.String(length=30), server_default='pending', nullable=False),
        sa.Column('location_name', sa.String(length=255), nullable=True),
        sa.Column('store_or_market', sa.String(length=255), nullable=True),
        sa.Column('gps_latitude', sa.Float(), nullable=True),
        sa.Column('gps_longitude', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['inspector_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inspections_inspection_number'), 'inspections', ['inspection_number'], unique=True)

    # 4. complaints
    op.create_table(
        'complaints',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('complaint_number', sa.String(length=50), nullable=False),
        sa.Column('consumer_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('brand_name', sa.String(length=150), nullable=True),
        sa.Column('store_name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='submitted', nullable=False),
        sa.Column('gps_latitude', sa.Float(), nullable=True),
        sa.Column('gps_longitude', sa.Float(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['consumer_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_complaints_complaint_number'), 'complaints', ['complaint_number'], unique=True)

    # 5. evidence_records
    op.create_table(
        'evidence_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=100), server_default='image/jpeg', nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('sha256_hash', sa.String(length=64), nullable=False),
        sa.Column('gps_latitude', sa.Float(), nullable=True),
        sa.Column('gps_longitude', sa.Float(), nullable=True),
        sa.Column('gps_accuracy_meters', sa.Float(), nullable=True),
        sa.Column('timestamp_device', sa.DateTime(timezone=True), nullable=False),
        sa.Column('timestamp_ntp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ntp_drift_seconds', sa.Float(), nullable=True),
        sa.Column('is_tampered', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('tamper_reason', sa.String(length=255), nullable=True),
        sa.Column('ocr_raw_payload', sa.Text(), nullable=True),
        sa.Column('detected_fields_json', sa.Text(), nullable=True),
        sa.Column('captured_by_id', sa.Integer(), nullable=True),
        sa.Column('inspection_id', sa.Integer(), nullable=True),
        sa.Column('complaint_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['captured_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['inspection_id'], ['inspections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evidence_records_sha256_hash'), 'evidence_records', ['sha256_hash'], unique=False)

    # 6. calibration_records
    op.create_table(
        'calibration_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('evidence_id', sa.Integer(), nullable=False),
        sa.Column('barcode_detected', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('barcode_type', sa.String(length=50), nullable=True),
        sa.Column('raw_barcode_data', sa.String(length=100), nullable=True),
        sa.Column('bbox_x', sa.Integer(), nullable=True),
        sa.Column('bbox_y', sa.Integer(), nullable=True),
        sa.Column('bbox_width_px', sa.Float(), nullable=True),
        sa.Column('bbox_height_px', sa.Float(), nullable=True),
        sa.Column('reference_width_mm', sa.Float(), server_default='37.29', nullable=False),
        sa.Column('scale_factor_mm_per_px', sa.Float(), nullable=True),
        sa.Column('orientation_angle_deg', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='REVIEW_NEEDED', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence_records.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_calibration_records_evidence_id'), 'calibration_records', ['evidence_id'], unique=False)

    # 7. font_size_rules
    op.create_table(
        'font_size_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('category', sa.String(length=50), server_default='weight_volume', nullable=False),
        sa.Column('unit_category', sa.String(length=30), nullable=False),
        sa.Column('min_quantity', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('max_quantity', sa.Float(), nullable=True),
        sa.Column('min_font_height_mm', sa.Float(), nullable=False),
        sa.Column('min_font_height_molded_mm', sa.Float(), nullable=False),
        sa.Column('min_width_height_ratio', sa.Float(), server_default='0.333', nullable=False),
        sa.Column('statutory_reference', sa.String(length=100), server_default='Rule 7 Table-I Legal Metrology Rules, 2011', nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 8. rule_checks
    op.create_table(
        'rule_checks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('inspection_id', sa.Integer(), nullable=True),
        sa.Column('evidence_id', sa.Integer(), nullable=True),
        sa.Column('rule_number', sa.Integer(), nullable=False),
        sa.Column('rule_name', sa.String(length=150), nullable=False),
        sa.Column('rule_code', sa.String(length=50), nullable=False),
        sa.Column('statutory_reference', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='REVIEW', nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('detected_value', sa.Text(), nullable=True),
        sa.Column('required_value', sa.Text(), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence_records.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['inspection_id'], ['inspections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rule_checks_rule_code'), 'rule_checks', ['rule_code'], unique=False)

    # 9. violation_reports
    op.create_table(
        'violation_reports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('report_number', sa.String(length=50), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('inspection_id', sa.Integer(), nullable=True),
        sa.Column('complaint_id', sa.Integer(), nullable=True),
        sa.Column('inspector_id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=40), server_default='pending_admin_confirmation', nullable=False),
        sa.Column('severity', sa.String(length=20), server_default='moderate', nullable=False),
        sa.Column('violation_summary', sa.Text(), nullable=False),
        sa.Column('violated_rules_json', sa.Text(), nullable=False),
        sa.Column('inspector_notes', sa.Text(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['inspection_id'], ['inspections.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['inspector_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_violation_reports_report_number'), 'violation_reports', ['report_number'], unique=True)

    # 10. penalties
    op.create_table(
        'penalties',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('violation_report_id', sa.Integer(), nullable=False),
        sa.Column('issued_by_id', sa.Integer(), nullable=True),
        sa.Column('legal_act', sa.String(length=100), server_default='Legal Metrology Act, 2009', nullable=False),
        sa.Column('section_code', sa.String(length=50), nullable=False),
        sa.Column('offense_tier', sa.String(length=30), server_default='first_offense', nullable=False),
        sa.Column('min_fine_inr', sa.Float(), nullable=False),
        sa.Column('max_fine_inr', sa.Float(), nullable=False),
        sa.Column('assessed_fine_inr', sa.Float(), nullable=False),
        sa.Column('imprisonment_months', sa.Integer(), server_default='0', nullable=False),
        sa.Column('compounding_allowed', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='assessed', nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('payment_reference', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['issued_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['violation_report_id'], ['violation_reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 11. legal_notices
    op.create_table(
        'legal_notices',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('notice_number', sa.String(length=60), nullable=False),
        sa.Column('violation_report_id', sa.Integer(), nullable=False),
        sa.Column('penalty_id', sa.Integer(), nullable=True),
        sa.Column('recipient_name', sa.String(length=255), nullable=False),
        sa.Column('recipient_company', sa.String(length=255), nullable=True),
        sa.Column('recipient_address', sa.Text(), nullable=False),
        sa.Column('recipient_email', sa.String(length=255), nullable=True),
        sa.Column('issuing_authority', sa.String(length=255), server_default='Office of the Field Drug Testing Dashboard', nullable=False),
        sa.Column('issuing_officer_name', sa.String(length=150), nullable=False),
        sa.Column('statutory_clauses_cited', sa.Text(), nullable=False),
        sa.Column('notice_body', sa.Text(), nullable=False),
        sa.Column('response_deadline_days', sa.Integer(), server_default='15', nullable=False),
        sa.Column('pdf_file_path', sa.String(length=500), nullable=True),
        sa.Column('pdf_sha256', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='generated', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['penalty_id'], ['penalties.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['violation_report_id'], ['violation_reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_legal_notices_notice_number'), 'legal_notices', ['notice_number'], unique=True)


def downgrade() -> None:
    op.drop_table('legal_notices')
    op.drop_table('penalties')
    op.drop_table('violation_reports')
    op.drop_table('rule_checks')
    op.drop_table('font_size_rules')
    op.drop_table('calibration_records')
    op.drop_table('evidence_records')
    op.drop_table('complaints')
    op.drop_table('inspections')
    op.drop_table('products')
    op.drop_table('users')
