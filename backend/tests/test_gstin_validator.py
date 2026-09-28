"""
Tests for app.utils.gstin_validator and the compliance_rules wrapper.
"""

from __future__ import annotations

import pytest

from app.services.compliance_rules import check_gstin_format
from app.utils.gstin_validator import (
    gstin_checksum,
    validate_gstin,
    validate_gstin_verbose,
)


# ── Known-valid GSTINs (well-formed, correct checksum) ────────────────────
# These are constructed by computing the checksum for the 14-char prefix,
# so the tests are self-consistent regardless of whether any external list
# ever changes.
def _make_valid(prefix14: str) -> str:
    return prefix14 + gstin_checksum(prefix14)


# ── checksum algorithm ───────────────────────────────────────────────────
def test_checksum_wrong_length_raises():
    with pytest.raises(ValueError):
        gstin_checksum("123")


def test_checksum_non_alphanumeric_raises():
    # gstin_checksum operates on the raw 14 chars — a punctuation char is a hard fail.
    with pytest.raises(ValueError):
        gstin_checksum("06AAACN-160N1Z")


def test_checksum_output_is_single_base36_char():
    ck = gstin_checksum("06AAACN1160N1Z")
    assert len(ck) == 1
    assert ck in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# ── validate_gstin (happy path) ──────────────────────────────────────────
def test_valid_gstin_karnataka_pattern():
    prefix = "29AAACN1160N1Z"
    gstin = _make_valid(prefix)
    assert validate_gstin(gstin) is True


def test_valid_gstin_delhi_pattern():
    prefix = "07AAACN1160N1Z"
    gstin = _make_valid(prefix)
    assert validate_gstin(gstin) is True


def test_valid_gstin_normalizes_case_and_whitespace():
    prefix = "27AABCB2984B1Z"
    gstin = _make_valid(prefix).lower()
    assert validate_gstin(f"  {gstin}  ") is True


# ── validate_gstin (invalid cases) ───────────────────────────────────────
def test_invalid_gstin_wrong_length():
    v = validate_gstin_verbose("06AAACN1160N1Z")  # 14 chars
    assert v["valid"] is False
    assert "15 characters" in v["reason"]


def test_invalid_gstin_bad_structure_letters_where_digits():
    v = validate_gstin_verbose("XXAAACN1160N1ZG")
    assert v["valid"] is False
    assert "structure invalid" in v["reason"].lower()


def test_invalid_gstin_bad_state_code():
    # 45 isn't a valid state code, but structure is otherwise correct.
    prefix = "45AAACN1160N1Z"
    gstin = _make_valid(prefix)
    v = validate_gstin_verbose(gstin)
    assert v["valid"] is False
    assert "state code" in v["reason"].lower()


def test_invalid_gstin_wrong_checksum():
    prefix = "27AABCB2984B1Z"
    right = _make_valid(prefix)
    wrong_char = "0" if right[-1] != "0" else "1"
    tampered = prefix + wrong_char
    v = validate_gstin_verbose(tampered)
    assert v["valid"] is False
    assert "checksum" in v["reason"].lower()
    assert v["checksum_expected"] == right[-1]


def test_invalid_gstin_missing_z_marker():
    # Position 14 must be literal 'Z'
    prefix = "27AABCB2984B1A"  # 'A' instead of 'Z'
    gstin = prefix + "0"
    v = validate_gstin_verbose(gstin)
    assert v["valid"] is False


def test_invalid_gstin_none_or_empty():
    assert validate_gstin("") is False
    assert validate_gstin(None) is False  # type: ignore[arg-type]


# ── compliance_rules wrapper─────────────────────────────────────────────
def test_check_gstin_format_pass():
    prefix = "29AAACN1160N1Z"
    gstin = _make_valid(prefix)
    result = check_gstin_format(gstin)
    assert result["status"] == "PASS"
    assert result["rule_number"] == 13
    assert result["rule_code"] == "GSTIN_FORMAT"
    assert result["failure_reason"] is None


def test_check_gstin_format_fail():
    result = check_gstin_format("29AAACN1160N1Z0")  # wrong checksum
    assert result["status"] == "FAIL"
    assert result["failure_reason"]
    assert "live_registry_verified" in (result["details_json"] or "")


def test_check_gstin_format_exempt_when_missing():
    result = check_gstin_format(None)
    assert result["status"] == "EXEMPT"
    assert result["failure_reason"] is None


def test_check_gstin_format_carries_cgst_reference():
    result = check_gstin_format("06AAACN1160N1ZG")
    assert "Central Goods and Services Tax" in result["statutory_reference"]
