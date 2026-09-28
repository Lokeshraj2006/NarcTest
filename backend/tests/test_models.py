"""
Tests for SQLAlchemy Models — Deliverable 2

Tests database table creation, model relationships, and default values
using an in-memory SQLite database.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    CalibrationRecord,
    CalibrationStatus,
    CheckStatus,
    Complaint,
    ComplaintStatus,
    ComplianceOutcome,
    EvidenceRecord,
    FontSizeRule,
    Inspection,
    InspectionStatus,
    LegalNotice,
    NoticeStatus,
    OffenseTier,
    Penalty,
    PenaltyStatus,
    Product,
    RuleCheck,
    User,
    UserRole,
    ViolationReport,
    ViolationSeverity,
    ViolationStatus,
)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_create_all_tables(db_session):
    """Verify all 11 tables are mapped and registered on Base.metadata."""
    table_names = set(Base.metadata.tables.keys())
    expected_tables = {
        "users",
        "products",
        "inspections",
        "complaints",
        "evidence_records",
        "calibration_records",
        "font_size_rules",
        "rule_checks",
        "violation_reports",
        "penalties",
        "legal_notices",
    }
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"


def test_user_creation_and_roles(db_session):
    """Test user creation with different roles."""
    inspector = User(
        email="inspector@legalmetrology.gov.in",
        username="inspector_sharma",
        hashed_password="hashed_pw_secret",
        full_name="Rajesh Sharma",
        role=UserRole.INSPECTOR,
        badge_number="LM-DEL-4021",
    )
    admin = User(
        email="admin@legalmetrology.gov.in",
        username="admin_verma",
        hashed_password="hashed_pw_secret",
        full_name="Anita Verma",
        role=UserRole.ADMIN,
    )
    consumer = User(
        email="consumer@example.com",
        username="citizen_rahul",
        hashed_password="hashed_pw_secret",
        full_name="Rahul Kumar",
        role=UserRole.CONSUMER,
    )
    db_session.add_all([inspector, admin, consumer])
    db_session.commit()

    saved_inspector = db_session.query(User).filter_by(username="inspector_sharma").first()
    assert saved_inspector is not None
    assert saved_inspector.role == UserRole.INSPECTOR
    assert saved_inspector.badge_number == "LM-DEL-4021"
    assert saved_inspector.is_active is True


def test_product_and_rule_checks(db_session):
    """Test product creation and its associated 13-point rule checks."""
    product = Product(
        generic_name="Atta (Wheat Flour)",
        brand_name="Peshawari Gold",
        manufacturer_name="Peshawari Agro Ltd",
        manufacturer_address="12 Industrial Estate, Karnal, Haryana",
        country_of_origin="India",
        net_quantity_raw="5 kg",
        net_quantity_value=5.0,
        net_quantity_unit="kg",
        mrp=240.0,
        mrp_raw="Rs. 240.00 (incl. of all taxes)",
        mfg_date_raw="09/2026",
        consumer_care_email="support@peshawariagro.com",
        consumer_care_phone="1800-11-2233",
        package_type="standard_retail",
        buyer_type="retail_consumer",
    )
    db_session.add(product)
    db_session.commit()

    check1 = RuleCheck(
        product_id=product.id,
        rule_number=1,
        rule_name="Manufacturer/Packer/Importer Details",
        rule_code="RULE_1_MFG_DETAILS",
        statutory_reference="Rule 6(1)(a)",
        status=CheckStatus.PASS,
        score=1.0,
        detected_value="Peshawari Agro Ltd, 12 Industrial Estate, Karnal",
    )
    check9 = RuleCheck(
        product_id=product.id,
        rule_number=9,
        rule_name="Font Size Compliance",
        rule_code="RULE_9_FONT_SIZE",
        statutory_reference="Rule 7 Table-I",
        status=CheckStatus.FAIL,
        score=0.0,
        detected_value="2.8 mm",
        required_value=">= 4.0 mm for > 200g up to 1kg (or 6.0 mm for > 1kg)",
        failure_reason="Measured numeral height 2.8 mm is below statutory minimum 6.0 mm",
    )
    db_session.add_all([check1, check9])
    db_session.commit()

    assert len(product.rule_checks) == 2
    assert product.rule_checks[0].rule_code == "RULE_1_MFG_DETAILS"
    assert product.rule_checks[1].status == CheckStatus.FAIL


def test_evidence_and_calibration_records(db_session):
    """Test evidence recording with SHA-256 hash, NTP sync, and calibration record."""
    now = datetime.now(timezone.utc)
    evidence = EvidenceRecord(
        file_path="/uploads/evidence/20260912_batch12_label.jpg",
        original_filename="label_wheat_flour.jpg",
        mime_type="image/jpeg",
        file_size_bytes=245800,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        gps_latitude=28.6139,
        gps_longitude=77.2090,
        timestamp_device=now,
        timestamp_ntp=now,
        ntp_drift_seconds=0.42,
        is_tampered=False,
    )
    db_session.add(evidence)
    db_session.commit()

    # Barcode-based calibration record (GS1 EAN-13 nominal 37.29 mm)
    calib = CalibrationRecord(
        evidence_id=evidence.id,
        barcode_detected=True,
        barcode_type="EAN13",
        raw_barcode_data="8901030999999",
        bbox_x=120,
        bbox_y=450,
        bbox_width_px=372.9,
        bbox_height_px=180.0,
        reference_width_mm=37.29,
        scale_factor_mm_per_px=37.29 / 372.9,  # 0.1 mm/px
        orientation_angle_deg=0.0,
        confidence=0.98,
        status=CalibrationStatus.CALIBRATED,
    )
    db_session.add(calib)
    db_session.commit()

    saved_evidence = db_session.query(EvidenceRecord).first()
    assert len(saved_evidence.calibration_records) == 1
    cal = saved_evidence.calibration_records[0]
    assert cal.scale_factor_mm_per_px == pytest.approx(0.1, rel=1e-3)
    assert cal.status == CalibrationStatus.CALIBRATED


def test_violation_penalty_legal_notice_workflow(db_session):
    """Test complete enforcement lifecycle: violation -> penalty -> legal notice."""
    inspector = User(
        email="insp@lm.gov.in",
        username="insp1",
        hashed_password="pw",
        full_name="Officer Insp",
        role=UserRole.INSPECTOR,
    )
    admin = User(
        email="admin@lm.gov.in",
        username="adm1",
        hashed_password="pw",
        full_name="Admin Director",
        role=UserRole.ADMIN,
    )
    product = Product(
        generic_name="Biscuits",
        brand_name="SweetBite",
        package_type="standard_retail",
    )
    db_session.add_all([inspector, admin, product])
    db_session.commit()

    # Violation report
    violation = ViolationReport(
        report_number="VR-2026-0001",
        product_id=product.id,
        inspector_id=inspector.id,
        admin_id=admin.id,
        status=ViolationStatus.CONFIRMED,
        severity=ViolationSeverity.MAJOR,
        violation_summary="Font size below statutory minimum (Rule 7) and missing MRP declaration",
        violated_rules_json='["RULE_5_MRP", "RULE_9_FONT_SIZE"]',
        confirmed_at=datetime.now(timezone.utc),
    )
    db_session.add(violation)
    db_session.commit()

    # Statutory Penalty under Section 36(1)
    penalty = Penalty(
        violation_report_id=violation.id,
        issued_by_id=admin.id,
        legal_act="Legal Metrology Act, 2009",
        section_code="Section 36(1)",
        offense_tier=OffenseTier.FIRST_OFFENSE,
        min_fine_inr=25000.0,
        max_fine_inr=50000.0,
        assessed_fine_inr=25000.0,
        status=PenaltyStatus.ISSUED,
    )
    db_session.add(penalty)
    db_session.commit()

    # Legal notice
    notice = LegalNotice(
        notice_number="LM/NOTICE/2026/0001",
        violation_report_id=violation.id,
        penalty_id=penalty.id,
        recipient_name="Managing Director",
        recipient_company="SweetBite Foods Pvt Ltd",
        recipient_address="Plot 44, Food Park, Noida, UP",
        issuing_authority="Office of Field Drug Testing Dashboard",
        issuing_officer_name="Anita Verma, Joint Controller",
        statutory_clauses_cited="Section 36(1) read with Rule 6 and Rule 7",
        notice_body="Show cause notice regarding non-compliance of packaged commodity...",
        status=NoticeStatus.GENERATED,
    )
    db_session.add(notice)
    db_session.commit()

    # Assert relations
    assert len(violation.penalties) == 1
    assert violation.penalties[0].assessed_fine_inr == 25000.0
    assert len(violation.legal_notices) == 1
    assert violation.legal_notices[0].notice_number == "LM/NOTICE/2026/0001"


def test_font_size_rules_reference_data(db_session):
    """Test the statutory font size table (Rule 7 Table 1)."""
    r1 = FontSizeRule(
        category="weight_volume",
        unit_category="g_ml",
        min_quantity=0.0,
        max_quantity=50.0,
        min_font_height_mm=1.0,
        min_font_height_molded_mm=2.0,
        statutory_reference="Rule 7 Table-I Item 1",
    )
    r2 = FontSizeRule(
        category="weight_volume",
        unit_category="g_ml",
        min_quantity=50.0,
        max_quantity=200.0,
        min_font_height_mm=2.0,
        min_font_height_molded_mm=4.0,
        statutory_reference="Rule 7 Table-I Item 2",
    )
    r3 = FontSizeRule(
        category="weight_volume",
        unit_category="kg_l",
        min_quantity=1.0,
        max_quantity=None,  # Unbounded
        min_font_height_mm=6.0,
        min_font_height_molded_mm=6.0,
        statutory_reference="Rule 7 Table-I Item 4",
    )
    db_session.add_all([r1, r2, r3])
    db_session.commit()

    rules = db_session.query(FontSizeRule).all()
    assert len(rules) == 3
    large_pack_rule = db_session.query(FontSizeRule).filter(FontSizeRule.max_quantity.is_(None)).first()
    assert large_pack_rule.min_font_height_mm == 6.0
