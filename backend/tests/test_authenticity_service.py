"""
Tests for app.services.authenticity_service.

Covers the three verdict paths (verified_authentic, tampered_suspected,
unverified_product) and the FSSAI mark cross-check surface.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.product_registry import ProductRegistry
from app.services.authenticity_service import (
    STATUS_AUTHENTIC,
    STATUS_TAMPERED,
    STATUS_UNVERIFIED,
    lookup_registry,
    verify_against_registry,
)


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def maggi(db_session):
    row = ProductRegistry(
        barcode="8901491101837",
        product_name="Maggi 2-Minute Masala Noodles",
        manufacturer_name="Nestle India Ltd.",
        manufacturer_address="Nestle House, Gurgaon 122002, Haryana",
        mrp=14.00,
        net_quantity="70 g",
        fssai_license_number="10012011000027",
        gst_number="06AAACN1160N1ZG",
        is_vegetarian=True,
    )
    db_session.add(row)
    db_session.commit()
    return row


@pytest.fixture
def venkys(db_session):
    row = ProductRegistry(
        barcode="8901719110018",
        product_name="Venky's Chicken Nuggets",
        manufacturer_name="Venky's (India) Limited",
        manufacturer_address="Pune 411030, Maharashtra",
        mrp=220.00,
        net_quantity="500 g",
        is_vegetarian=False,
    )
    db_session.add(row)
    db_session.commit()
    return row


# ── lookup_registry ───────────────────────────────────────────────────────
def test_lookup_registry_hit(db_session, maggi):
    hit = lookup_registry(db_session, "8901491101837")
    assert hit is not None
    assert hit.id == maggi.id


def test_lookup_registry_miss(db_session):
    assert lookup_registry(db_session, "0000000000000") is None


def test_lookup_registry_normalizes_whitespace(db_session, maggi):
    assert lookup_registry(db_session, " 89014 91101837 ") is not None


# ── verified_authentic ────────────────────────────────────────────────────
def test_verify_against_registry_exact_match(db_session, maggi):
    result = verify_against_registry(
        db_session,
        "8901491101837",
        {
            "product_name": "Maggi 2-Minute Masala Noodles",
            "manufacturer_name": "Nestle India Ltd.",
            "manufacturer_address": "Nestle House, Gurgaon 122002, Haryana",
            "mrp": 14.00,
            "net_quantity": "70 g",
            "fssai_license_number": "10012011000027",
            "gst_number": "06AAACN1160N1ZG",
        },
    )
    assert result.status == STATUS_AUTHENTIC
    assert result.mismatches == []
    assert result.matched_product_name == "Maggi 2-Minute Masala Noodles"


def test_verify_against_registry_tolerates_case_and_whitespace(db_session, maggi):
    result = verify_against_registry(
        db_session,
        "8901491101837",
        {
            "product_name": "maggi  2-minute masala noodles",
            "mrp": 14.05,  # within 0.5% tolerance
            "net_quantity": "70g",
        },
    )
    assert result.status == STATUS_AUTHENTIC


def test_verify_against_registry_quantity_unit_normalization(db_session):
    row = ProductRegistry(
        barcode="1000000000001",
        product_name="Test Kilogram",
        manufacturer_name="X",
        manufacturer_address="Y",
        mrp=100.0,
        net_quantity="1 kg",
        is_vegetarian=True,
    )
    db_session.add(row); db_session.commit()

    result = verify_against_registry(
        db_session, "1000000000001", {"net_quantity": "1000 g"}
    )
    assert result.status == STATUS_AUTHENTIC


# ── tampered_suspected ───────────────────────────────────────────────────
def test_verify_against_registry_mrp_mismatch(db_session, maggi):
    result = verify_against_registry(
        db_session, "8901491101837", {"mrp": 50.00}
    )
    assert result.status == STATUS_TAMPERED
    mismatched_fields = {m.field for m in result.mismatches}
    assert "mrp" in mismatched_fields
    (mrp_row,) = [m for m in result.mismatches if m.field == "mrp"]
    assert mrp_row.expected == "14.0"
    assert mrp_row.detected == "50.0"


def test_a_higher_mrp_is_tampering_citing_rule_6_3(db_session, maggi):
    result = verify_against_registry(db_session, "8901491101837", {"mrp": 16.00})
    assert result.status == STATUS_TAMPERED
    (mrp_row,) = result.mismatches
    assert "Rule 6(3)" in mrp_row.note


def test_a_lower_mrp_is_not_tampering(db_session, maggi):
    # Rule 6(3) allows a sticker that lowers the MRP; a covered price reads short too.
    result = verify_against_registry(
        db_session, "8901491101837", {"mrp": 10.00, "net_quantity": "70 g"}
    )
    assert result.status == STATUS_AUTHENTIC
    assert result.mismatches == []
    [divergence] = result.text_divergences
    assert divergence.field == "mrp"
    assert "Rule 6(3)" in divergence.note


def test_verify_against_registry_multiple_mismatches(db_session, maggi):
    result = verify_against_registry(
        db_session,
        "8901491101837",
        {
            "product_name": "Some Other Brand Noodles",
            "manufacturer_name": "Fake Foods Ltd.",
            "mrp": 25.00,
            "fssai_license_number": "99999999999999",
        },
    )
    assert result.status == STATUS_TAMPERED
    fields = {m.field for m in result.mismatches}
    assert {"manufacturer_name", "mrp", "fssai_license_number"}.issubset(fields)
    # Product names are misread too often to count as tampering; recorded instead.
    assert "product_name" not in fields
    assert "product_name" in {d.field for d in result.text_divergences}


def test_verify_against_registry_fssai_veg_mark_mismatch(db_session, maggi):
    # Registry says veg but detected mark is non-veg → tampering signal.
    result = verify_against_registry(
        db_session,
        "8901491101837",
        {"product_name": "Maggi 2-Minute Masala Noodles"},
        fssai_mark="non_vegetarian",
    )
    assert result.status == STATUS_TAMPERED
    assert any(m.field == "fssai_veg_mark" for m in result.mismatches)


def test_verify_against_registry_fssai_veg_mark_match(db_session, venkys):
    # Registry says non-veg, detected mark is non-veg → still authentic.
    result = verify_against_registry(
        db_session,
        "8901719110018",
        {
            "product_name": "Venky's Chicken Nuggets",
            "manufacturer_name": "Venky's (India) Limited",
            "manufacturer_address": "Pune 411030, Maharashtra",
            "mrp": 220.0,
            "net_quantity": "500 g",
        },
        fssai_mark="non_vegetarian",
    )
    assert result.status == STATUS_AUTHENTIC


def test_verify_against_registry_fssai_not_found_is_no_signal(db_session, maggi):
    result = verify_against_registry(
        db_session,
        "8901491101837",
        {"product_name": "Maggi 2-Minute Masala Noodles"},
        fssai_mark="not_found",
    )
    # not_found doesn't add a mismatch — mark simply wasn't detected.
    assert all(m.field != "fssai_veg_mark" for m in result.mismatches)


# ── unverified_product ───────────────────────────────────────────────────
def test_verify_against_registry_unknown_barcode(db_session):
    result = verify_against_registry(
        db_session, "0000000000000", {"product_name": "Anything"}
    )
    assert result.status == STATUS_UNVERIFIED
    assert result.registry_id is None
    assert result.mismatches == []
    assert "not found" in result.message.lower()


def test_verify_against_registry_empty_barcode(db_session):
    result = verify_against_registry(db_session, "", {})
    assert result.status == STATUS_UNVERIFIED


def test_to_dict_is_serializable(db_session, maggi):
    result = verify_against_registry(
        db_session, "8901491101837", {"mrp": 999.0}
    )
    payload = result.to_dict()
    assert payload["status"] == STATUS_TAMPERED
    assert isinstance(payload["mismatches"], list)
    assert payload["mismatches"][0]["field"] == "mrp"
    assert payload["text_divergences"] == []


# ── OCR misreads vs contradictions (real text from a genuine pack) ───────
@pytest.fixture
def aloo_bhujia(db_session):
    row = ProductRegistry(
        barcode="8904004400779",
        product_name="Haldiram's Aloo Bhujia",
        manufacturer_name="Haldiram Snacks Food Private Limited",
        manufacturer_address=(
            "Unit-Hariomkar, 20 Km Stone, Kh. No. 409/3, 410, 411, Village Gumthala, "
            "Tah. Kamptee, Bhandara Road, Nagpur, Maharashtra 441104"
        ),
        mrp=109.00,
        net_quantity="400 g",
        fssai_license_number="10014011001919",
        additional_fssai_license_numbers="10015022004173",
        is_vegetarian=True,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_misread_manufacturer_name_is_not_tampering(db_session, aloo_bhujia):
    result = verify_against_registry(
        db_session,
        "8904004400779",
        {
            "manufacturer_name": "HALDIRAM SNACKS FOOD PRVATE UMTE (UNIT-HARIOMKAR) 20 Krn Stone",
            "mrp": 109.0,
            "net_quantity": "400g",
            "fssai_license_number": "10014011001919",
        },
    )
    assert result.status == STATUS_AUTHENTIC
    assert result.mismatches == []


def test_misread_product_name_and_other_address_are_recorded_not_tampering(db_session, aloo_bhujia):
    result = verify_against_registry(
        db_session,
        "8904004400779",
        {
            "product_name": "FIND MOR",
            "manufacturer_address": "Delhi -Japu Highway, Gurugram -122001, Haryana",
            "mrp": 109.0,
        },
    )
    assert result.status == STATUS_AUTHENTIC
    assert {d.field for d in result.text_divergences} == {"product_name", "manufacturer_address"}
    assert "not treated as tampering" in result.message


def test_legal_form_variants_match(db_session, aloo_bhujia):
    result = verify_against_registry(
        db_session, "8904004400779",
        {"manufacturer_name": "Haldiram Snacks Food Pvt. Ltd."},
    )
    assert result.status == STATUS_AUTHENTIC
    assert result.text_divergences == []


def test_unrelated_manufacturer_name_is_tampering(db_session, aloo_bhujia):
    result = verify_against_registry(
        db_session, "8904004400779",
        {"manufacturer_name": "Bikaji International Limited"},
    )
    assert result.status == STATUS_TAMPERED
    assert [m.field for m in result.mismatches] == ["manufacturer_name"]


def test_label_text_read_as_manufacturer_is_not_tampering(db_session, aloo_bhujia):
    # Scan #17: OCR placed a nutrition footnote after "MARKETED BY:".
    result = verify_against_registry(
        db_session, "8904004400779",
        {"manufacturer_name": (
            "size is 20g; 20 Serving in this pack. ##Limit of quantification "
            "%RDA Per Servet For EPR details scan the"
        )},
    )
    assert result.status == STATUS_AUTHENTIC
    assert [d.field for d in result.text_divergences] == ["manufacturer_name"]


def test_the_units_own_licence_on_the_same_pack_is_not_tampering(db_session, aloo_bhujia):
    # Scan #19: the pack prints the registered licence and the Nagpur unit's.
    result = verify_against_registry(
        db_session, "8904004400779",
        {"fssai_license_number": "10015022004173", "mrp": 109.0},
    )
    assert result.status == STATUS_AUTHENTIC
    assert "fssai_license_number" in result.message


def test_a_licence_that_is_not_14_digits_is_an_ocr_misread(db_session, aloo_bhujia):
    # Scan #20 read the unit's licence one digit short.
    result = verify_against_registry(
        db_session, "8904004400779", {"fssai_license_number": "1001502200173"},
    )
    assert result.status == STATUS_AUTHENTIC
    assert [d.field for d in result.text_divergences] == ["fssai_license_number"]


def test_an_unlisted_14_digit_licence_is_still_tampering(db_session, aloo_bhujia):
    result = verify_against_registry(
        db_session, "8904004400779", {"fssai_license_number": "10099999000001"},
    )
    assert result.status == STATUS_TAMPERED
    assert [m.field for m in result.mismatches] == ["fssai_license_number"]


def test_a_licence_one_digit_off_is_an_ocr_misread(db_session, aloo_bhujia):
    # Scan #37 read the Ob & Gob tub's ...476 as ...478.
    result = verify_against_registry(
        db_session, "8904004400779",
        {"fssai_license_number": "10015022004178", "mrp": 109.0},
    )
    assert result.status == STATUS_AUTHENTIC
    assert result.mismatches == []
    [divergence] = result.text_divergences
    assert divergence.field == "fssai_license_number"
    assert "10015022004173" in divergence.note
    assert "not treated as tampering" in divergence.note


def test_a_licence_two_digits_off_is_still_tampering(db_session, aloo_bhujia):
    result = verify_against_registry(
        db_session, "8904004400779", {"fssai_license_number": "10015022004188"},
    )
    assert result.status == STATUS_TAMPERED
    assert [m.field for m in result.mismatches] == ["fssai_license_number"]


def test_mrp_sticker_is_tampering_despite_matching_text(db_session, aloo_bhujia):
    result = verify_against_registry(
        db_session, "8904004400779",
        {"manufacturer_name": "Haldiram Snacks Food Private Limited", "mrp": 129.0},
    )
    assert result.status == STATUS_TAMPERED
    assert [m.field for m in result.mismatches] == ["mrp"]
