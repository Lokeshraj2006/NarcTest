"""
FieldProof — Compliance Aggregator

Takes the raw results from the compliance rules, authenticity service, and
FSSAI mark service for a single EvidenceRecord and produces a persisted
ComplianceResult row (upserted — one aggregate per evidence record).

Zero FastAPI dependency — plain functions callable from any router,
worker, or unit test. Caller supplies the DB session.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.compliance_result import (
    ComplianceResult,
    ComplianceResultFailure,
    OverallStatus,
)
from app.models.rule_check import CheckStatus, RuleCheck
from app.services.authenticity_service import (
    STATUS_AUTHENTIC,
    STATUS_TAMPERED,
    STATUS_UNVERIFIED,
    AuthenticityResult,
)
from app.services.fssai_mark_service import (
    STATUS_NON_VEG,
    STATUS_VEG,
    FssaiMarkResult,
)


def _fmt_check_summary(rc: RuleCheck) -> str:
    detail = rc.failure_reason or "no additional detail"
    return f"Rule {rc.rule_number} — {rc.rule_name}: {detail}"


# Required label details. When one of these is REVIEW with nothing read (a
# heading without its value, say), the pack can't be called compliant: the
# detail may be hidden, blank or just unreadable, and a person has to look.
# Scan #41 hid the MRP and dates under a finger and was shown as compliant.
_REQUIRED_DETAILS = {
    "MANUFACTURER_DETAILS": "maker's name and address",
    "GENERIC_NAME": "product name",
    "NET_QUANTITY": "net quantity",
    "MRP_DECLARATION": "MRP",
    "MFG_DATE": "manufacture date",
    "EXPIRY_DATE": "expiry date",
    "CONSUMER_CARE": "consumer care details",
}


def unread_required_details(checks: Iterable[RuleCheck]) -> List[str]:
    """Required details whose check is REVIEW with no value read, in rule order."""
    return [
        _REQUIRED_DETAILS[rc.rule_code]
        for rc in sorted(checks, key=lambda rc: rc.rule_number)
        if rc.rule_code in _REQUIRED_DETAILS
        and rc.status == CheckStatus.REVIEW
        and not (rc.detected_value or "").strip()
    ]


def _join(items: List[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def build_compliance_result(
    db: Session,
    evidence_record_id: int,
    rule_checks: Iterable[RuleCheck],
    authenticity: Optional[AuthenticityResult] = None,
    fssai_mark: Optional[FssaiMarkResult] = None,
    gstin_status: Optional[str] = None,
    product_name_fallback: Optional[str] = None,
) -> ComplianceResult:
    """Create or update the ComplianceResult for an evidence record.

    Args:
        db: active SQLAlchemy session (caller commits).
        evidence_record_id: FK into evidence_records.
        rule_checks: persisted RuleCheck rows already flushed with valid ids.
        authenticity: authenticity_service verdict (optional).
        fssai_mark: fssai_mark_service verdict (optional).
        gstin_status: 'PASS' | 'FAIL' | 'EXEMPT' string for quick surfacing.

    Returns:
        The persisted (unflushed-by-us; caller commits) ComplianceResult.
    """
    existing = (
        db.query(ComplianceResult)
        .filter(ComplianceResult.evidence_record_id == evidence_record_id)
        .first()
    )
    if existing:
        for failure in list(existing.failures):
            db.delete(failure)
        result = existing
    else:
        result = ComplianceResult(evidence_record_id=evidence_record_id)
        db.add(result)

    checks: List[RuleCheck] = list(rule_checks)
    failed: List[RuleCheck] = [rc for rc in checks if rc.status == CheckStatus.FAIL]
    reasons: List[str] = []
    primary_law_ref: Optional[str] = None

    # ── Attach per-failure rows with their statute references ─────────
    for rc in failed:
        db.add(
            ComplianceResultFailure(
                compliance_result=result,
                rule_check_id=rc.id,
                law_reference=rc.statutory_reference,
                note=rc.failure_reason,
            )
        )
        reasons.append(_fmt_check_summary(rc))
        if primary_law_ref is None:
            primary_law_ref = rc.statutory_reference

    # ── Fold in authenticity verdict ──────────────────────────────────
    result.authenticity_status = authenticity.status if authenticity else None
    if authenticity is not None:
        if authenticity.status == STATUS_TAMPERED:
            fields = ", ".join(
                f"{m.field} (label {m.detected}, registered {m.expected})"
                for m in authenticity.mismatches
            ) or "unknown fields"
            reasons.append(
                f"Authenticity: registry cross-check flagged tampering on {fields}. "
                "An inspector checks the pack (Rule 6(3))."
            )
            if primary_law_ref is None:
                primary_law_ref = "Rule 6(3), Legal Metrology (Packaged Commodities) Rules, 2011"
        elif authenticity.status == STATUS_UNVERIFIED:
            reasons.append(
                "Authenticity: barcode not found in reference registry — "
                "product could not be verified."
            )

    result.fssai_mark_status = fssai_mark.status if fssai_mark else None

    # ── Roll up ───────────────────────────────────────────────────────
    result.gstin_status = gstin_status
    result.total_checks = len(checks)
    result.failed_checks = len(failed)

    # Product name: prefer the registry match (trusted), fall back to OCR value.
    if authenticity and authenticity.matched_product_name:
        result.product_name = authenticity.matched_product_name
    elif product_name_fallback:
        result.product_name = product_name_fallback

    # Only evidence of a problem needs action. An unregistered barcode or an
    # undetected veg mark means "not verified", which the result already says.
    is_action_needed = bool(failed) or (
        authenticity is not None and authenticity.status == STATUS_TAMPERED
    )
    # Without that evidence, a required detail nobody could read still stops
    # the pack being called compliant — REVIEW is never quietly a PASS.
    unread = unread_required_details(checks)

    if is_action_needed:
        result.overall_status = OverallStatus.ACTION_NEEDED
    elif unread:
        result.overall_status = OverallStatus.NEEDS_REVIEW
        reasons.insert(0, f"Couldn't read: {_join(unread)}. Check them on the pack.")
    else:
        result.overall_status = OverallStatus.COMPLIANT
    result.action_reason = " | ".join(reasons) if reasons else None
    result.law_reference = primary_law_ref

    return result


def serialize_compliance_result(result: ComplianceResult) -> Dict[str, Any]:
    """Small helper for API responses — one flat dict."""
    return {
        "id": result.id,
        "evidence_record_id": result.evidence_record_id,
        "overall_status": result.overall_status.value
        if hasattr(result.overall_status, "value")
        else result.overall_status,
        "action_reason": result.action_reason,
        "law_reference": result.law_reference,
        "product_name": result.product_name,
        "authenticity_status": result.authenticity_status,
        "fssai_mark_status": result.fssai_mark_status,
        "gstin_status": result.gstin_status,
        "total_checks": result.total_checks,
        "failed_checks": result.failed_checks,
        "failed_rule_check_ids": [f.rule_check_id for f in result.failures],
        "failures": [
            {
                "rule_check_id": f.rule_check_id,
                "law_reference": f.law_reference,
                "note": f.note,
            }
            for f in result.failures
        ],
    }
