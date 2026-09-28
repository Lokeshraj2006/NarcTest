"""
Verdict roll-up: only a failed rule or a registry contradiction needs action.

"Could not verify" (unregistered barcode, undetected veg mark, REVIEW checks)
is reported on the result but must not raise a complaint on its own.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main  # noqa: F401  registers every model on Base.metadata
from app.database import Base
from app.models.compliance_result import OverallStatus
from app.models.evidence import EvidenceRecord
from app.models.rule_check import CheckStatus, RuleCheck
from app.services.authenticity_service import (
    STATUS_AUTHENTIC,
    STATUS_TAMPERED,
    STATUS_UNVERIFIED,
    AuthenticityResult,
    FieldMismatch,
)
from app.services.compliance_aggregator import build_compliance_result
from app.services.fssai_mark_service import STATUS_NOT_FOUND, FssaiMarkResult


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _verdict(db, statuses, authenticity=None, fssai_mark=None):
    evidence = EvidenceRecord(
        file_path="label.jpg",
        original_filename="label.jpg",
        file_size_bytes=1,
        sha256_hash="0" * 64,
        timestamp_device=datetime.now(timezone.utc),
    )
    db.add(evidence)
    db.flush()

    checks = []
    for number, status in enumerate(statuses, start=1):
        check = RuleCheck(
            evidence_id=evidence.id,
            rule_number=number,
            rule_name=f"Rule {number}",
            rule_code=f"RULE_{number}",
            statutory_reference=f"Rule {number}",
            status=status.value,
            failure_reason="Not declared." if status is CheckStatus.FAIL else None,
        )
        db.add(check)
        checks.append(check)
    db.flush()

    return build_compliance_result(
        db, evidence.id, checks, authenticity=authenticity, fssai_mark=fssai_mark
    )


_UNDETECTED_MARK = FssaiMarkResult(status=STATUS_NOT_FOUND, confidence=0.0)


def test_unregistered_barcode_alone_is_compliant(db):
    result = _verdict(
        db,
        [CheckStatus.PASS, CheckStatus.REVIEW],
        authenticity=AuthenticityResult(status=STATUS_UNVERIFIED, barcode="8904004400779"),
    )
    assert result.overall_status == OverallStatus.COMPLIANT


def test_undetected_veg_mark_alone_is_compliant(db):
    result = _verdict(db, [CheckStatus.PASS], fssai_mark=_UNDETECTED_MARK)
    assert result.overall_status == OverallStatus.COMPLIANT
    assert result.fssai_mark_status == STATUS_NOT_FOUND


def test_review_checks_alone_are_compliant(db):
    result = _verdict(db, [CheckStatus.REVIEW, CheckStatus.REVIEW, CheckStatus.EXEMPT])
    assert result.overall_status == OverallStatus.COMPLIANT


def test_authentic_registry_match_is_compliant(db):
    result = _verdict(
        db,
        [CheckStatus.PASS],
        authenticity=AuthenticityResult(status=STATUS_AUTHENTIC, barcode="8904004400779"),
        fssai_mark=_UNDETECTED_MARK,
    )
    assert result.overall_status == OverallStatus.COMPLIANT


def test_failed_rule_needs_action(db):
    result = _verdict(db, [CheckStatus.PASS, CheckStatus.FAIL])
    assert result.overall_status == OverallStatus.ACTION_NEEDED
    assert result.failed_checks == 1


def test_registry_contradiction_needs_action(db):
    tampered = AuthenticityResult(
        status=STATUS_TAMPERED,
        barcode="8904004400779",
        mismatches=[FieldMismatch(field="mrp", expected="109.0", detected="129.0")],
    )
    result = _verdict(db, [CheckStatus.PASS], authenticity=tampered)
    assert result.overall_status == OverallStatus.ACTION_NEEDED
    assert "tampering" in result.action_reason


# ── A required detail nobody could read is never "compliant" ─────────────
def _verdict_of(db, rows, authenticity=None):
    """rows: (rule_code, status, detected value), numbered in order."""
    evidence = EvidenceRecord(
        file_path="label.jpg", original_filename="label.jpg", file_size_bytes=1,
        sha256_hash="0" * 64, timestamp_device=datetime.now(timezone.utc),
    )
    db.add(evidence)
    db.flush()
    checks = []
    for number, (code, status, detected) in enumerate(rows, start=1):
        check = RuleCheck(
            evidence_id=evidence.id, rule_number=number, rule_name=code, rule_code=code,
            statutory_reference=f"Rule {number}", status=status.value, detected_value=detected,
        )
        db.add(check)
        checks.append(check)
    db.flush()
    return build_compliance_result(db, evidence.id, checks, authenticity=authenticity)


def test_hidden_mrp_and_dates_need_review_not_compliant(db):
    # Scan #41: MRP and dates under a finger, their headings still visible.
    result = _verdict_of(db, [
        ("NET_QUANTITY", CheckStatus.PASS, "400 g"),
        ("MRP_DECLARATION", CheckStatus.REVIEW, None),
        ("MFG_DATE", CheckStatus.REVIEW, None),
        ("EXPIRY_DATE", CheckStatus.REVIEW, None),
    ], authenticity=AuthenticityResult(status=STATUS_AUTHENTIC, barcode="8904004400779"))
    assert result.overall_status == OverallStatus.NEEDS_REVIEW
    assert result.action_reason.startswith(
        "Couldn't read: MRP, manufacture date and expiry date. Check them on the pack."
    )
    assert result.failed_checks == 0


def test_a_detail_read_but_uncertain_stays_compliant(db):
    # MRP read, only the "inclusive of all taxes" wording unconfirmed.
    result = _verdict_of(db, [("MRP_DECLARATION", CheckStatus.REVIEW, "Rs. 109.0")])
    assert result.overall_status == OverallStatus.COMPLIANT


def test_unread_measurements_and_registration_stay_compliant(db):
    result = _verdict_of(db, [
        ("FONT_SIZE", CheckStatus.REVIEW, None),
        ("LMPC_REGISTRATION", CheckStatus.REVIEW, None),
    ])
    assert result.overall_status == OverallStatus.COMPLIANT


def test_a_failed_rule_outranks_an_unread_detail(db):
    result = _verdict_of(db, [
        ("MRP_DECLARATION", CheckStatus.REVIEW, None),
        ("NET_QUANTITY", CheckStatus.FAIL, None),
    ])
    assert result.overall_status == OverallStatus.ACTION_NEEDED
