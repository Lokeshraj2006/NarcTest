"""
FieldProof — Violation escalation service.

Drives the inspector → admin chain:

    inspector files a report  → PENDING_ADMIN_CONFIRMATION
    admin confirms / rejects  → CONFIRMED / REJECTED
    admin issues a GO notice  → NOTICE_GENERATED

Only the admin may issue a notice; the inspector's job ends at filing the
report. Enforced at the router with RBAC, and mirrored here by the state
guards so the rules hold even if called directly.

Plain functions taking a Session, so they're unit-testable without FastAPI.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.compliance_result import ComplianceResult
from app.models.evidence import EvidenceRecord
from app.models.legal_notice import LegalNotice, NoticeStatus
from app.models.rule import Rule, RuleSeverity
from app.models.rule_check import CheckStatus, RuleCheck
from app.models.user import User
from app.models.violation import (
    ViolationReport,
    ViolationSeverity,
    ViolationStatus,
)
from app.services.authenticity_service import _parse_mrp

# Ordered weakest → strongest, so the report inherits the worst failure.
_SEVERITY_ORDER = [
    ViolationSeverity.MINOR,
    ViolationSeverity.MODERATE,
    ViolationSeverity.MAJOR,
    ViolationSeverity.CRITICAL,
]


class ViolationWorkflowError(Exception):
    """Raised when a transition is not legal from the current state."""


# A declaration on the pack that contradicts the registered product (a price
# sticker raising the MRP, a changed quantity or maker) is an altered
# declaration, which Rule 6(3) forbids — except a sticker lowering the MRP,
# which the registry check already lets through. Scans stored before that
# (#43: 9.31 against 109) still carry a lower MRP as a mismatch, so it is
# skipped here too. Other registry fields (FSSAI licence, veg mark, GSTIN)
# aren't Legal Metrology declarations, so a report can't cite them.
RULE_6_3 = "Rule 6(3), Legal Metrology (Packaged Commodities) Rules, 2011"
_CITABLE_REGISTRY_FIELDS = {
    "mrp": "MRP",
    "net_quantity": "Net quantity",
    "manufacturer_name": "Manufacturer",
}


def registry_grounds(evidence: EvidenceRecord) -> List[Dict[str, Any]]:
    """Report grounds from the scan's registry mismatch, if it has a citable one."""
    try:
        blob = json.loads(evidence.detected_fields_json or "{}")
    except (ValueError, TypeError):
        return []
    authenticity = blob.get("authenticity") if isinstance(blob, dict) else None
    if not isinstance(authenticity, dict) or authenticity.get("status") != "tampered_suspected":
        return []
    grounds = []
    for m in authenticity.get("mismatches") or []:
        label = _CITABLE_REGISTRY_FIELDS.get((m or {}).get("field"))
        if not label or _is_lower_mrp(m):
            continue
        grounds.append({
            "rule_number": None,
            "rule_code": "REGISTRY_MISMATCH",
            "rule_name": f"{label} differs from the registered product",
            "statutory_reference": RULE_6_3,
            "detected_value": str(m.get("detected")),
            "required_value": f"{m.get('expected')} (registered)",
            "failure_reason": (
                f"The pack shows {label.lower() if label != 'MRP' else 'MRP'} "
                f"{m.get('detected')}; the registered product has {m.get('expected')}. "
                "The inspector checked the pack: the declaration was altered, which "
                "Rule 6(3) forbids (only a sticker lowering the MRP is allowed)."
            ),
            "source": "registry",
        })
    return grounds


def _is_lower_mrp(m: Dict[str, Any]) -> bool:
    if m.get("field") != "mrp":
        return False
    detected, expected = _parse_mrp(m.get("detected")), _parse_mrp(m.get("expected"))
    return detected is not None and expected is not None and detected < expected


def _ground_label(c: Dict[str, Any]) -> str:
    return f"Rule {c['rule_number']}" if c.get("rule_number") is not None else "Registry"


def _report_number() -> str:
    return f"VR-{datetime.now().year}-{uuid.uuid4().hex[:8].upper()}"


def _notice_number() -> str:
    return f"GO-{datetime.now().year}-{uuid.uuid4().hex[:8].upper()}"


def _worst_severity(codes: List[str], db: Session) -> ViolationSeverity:
    """Take the highest default_severity among the cited rules."""
    if not codes:
        return ViolationSeverity.MODERATE
    rows = db.query(Rule.default_severity).filter(Rule.rule_code.in_(codes)).all()
    worst = ViolationSeverity.MINOR
    for (sev,) in rows:
        value = sev.value if isinstance(sev, RuleSeverity) else str(sev)
        try:
            candidate = ViolationSeverity(value)
        except ValueError:
            continue
        if _SEVERITY_ORDER.index(candidate) > _SEVERITY_ORDER.index(worst):
            worst = candidate
    return worst


def _lock(db: Session, report: ViolationReport) -> ViolationReport:
    # Row lock: a concurrent second click waits here, then sees the first click's result.
    return (
        db.query(ViolationReport)
        .filter(ViolationReport.id == report.id)
        .with_for_update()
        .populate_existing()
        .one()
    )


def _failed_checks(
    db: Session, evidence_record_id: int, rule_check_ids: Optional[List[int]] = None
) -> List[RuleCheck]:
    """The scan's FAILed checks, narrowed to ``rule_check_ids`` when given.

    A report may only cite checks that FAILed on its own scan, so an id that
    isn't one of them is refused rather than cited or silently dropped.
    """
    failed = (
        db.query(RuleCheck)
        .filter(
            RuleCheck.evidence_id == evidence_record_id,
            RuleCheck.status == CheckStatus.FAIL,
        )
        .order_by(RuleCheck.rule_number.asc())
        .all()
    )
    if not rule_check_ids:
        return failed

    requested = set(rule_check_ids)
    refused = sorted(requested - {rc.id for rc in failed})
    if refused:
        found = {
            rc.id: rc
            for rc in db.query(RuleCheck).filter(RuleCheck.id.in_(refused))
        }
        reasons = []
        for check_id in refused:
            rc = found.get(check_id)
            if rc is None or rc.evidence_id != evidence_record_id:
                reasons.append(f"#{check_id} is not a check on this scan")
            else:
                status = getattr(rc.status, "value", rc.status)
                reasons.append(f"#{check_id} (rule {rc.rule_number}) is {status}")
        raise ViolationWorkflowError(
            "A report can only cite checks that FAILed on this scan: "
            + "; ".join(reasons)
            + "."
        )
    return [rc for rc in failed if rc.id in requested]


def create_report(
    db: Session,
    inspector: User,
    evidence_record_id: int,
    *,
    complaint_id: Optional[int] = None,
    violation_summary: Optional[str] = None,
    inspector_notes: Optional[str] = None,
    severity: Optional[str] = None,
    rule_check_ids: Optional[List[int]] = None,
    shop_name: Optional[str] = None,
    shop_address: Optional[str] = None,
    cite_registry: bool = False,
    pack_checked: bool = False,
) -> ViolationReport:
    """File a violation report against a scan. Caller commits.

    A report cites the scan's FAILed checks and, with ``cite_registry``, its
    registry mismatch under Rule 6(3) — only once the inspector confirms
    (``pack_checked``) that the physical pack contradicts the registered
    details, since a misread photo alone can look like tampering.

    Raises ViolationWorkflowError when the evidence doesn't exist, already
    has an open report, has nothing to cite, ``rule_check_ids`` names a check
    that didn't FAIL on this scan, or a registry citation isn't confirmed.
    """
    evidence = (
        db.query(EvidenceRecord)
        .filter(EvidenceRecord.id == evidence_record_id)
        .first()
    )
    if evidence is None:
        raise ViolationWorkflowError(
            f"Evidence record #{evidence_record_id} not found."
        )

    existing = (
        db.query(ViolationReport)
        .filter(
            ViolationReport.evidence_record_id == evidence_record_id,
            ViolationReport.status.notin_(
                [ViolationStatus.REJECTED, ViolationStatus.CLOSED]
            ),
        )
        .first()
    )
    if existing is not None:
        raise ViolationWorkflowError(
            f"Report {existing.report_number} is already open for this scan."
        )

    checks = _failed_checks(db, evidence_record_id, rule_check_ids)
    grounds: List[Dict[str, Any]] = []
    if cite_registry:
        if not pack_checked:
            raise ViolationWorkflowError(
                "Confirm that you checked the pack yourself before citing the registry "
                "mismatch: a misread photo alone can look like tampering."
            )
        grounds = registry_grounds(evidence)
        if not grounds:
            raise ViolationWorkflowError(
                "This scan has no registry mismatch that can be cited. Only an MRP higher "
                "than registered, a different net quantity or a different maker can be."
            )
    if not checks and not grounds:
        raise ViolationWorkflowError(
            "No failed rule checks on this scan — nothing to report. A report "
            "can only cite checks that FAILed, or a registry mismatch the "
            "inspector has checked on the pack."
        )

    cited = [
        {
            "rule_number": rc.rule_number,
            "rule_code": rc.rule_code,
            "rule_name": rc.rule_name,
            "statutory_reference": rc.statutory_reference,
            "detected_value": rc.detected_value,
            "required_value": rc.required_value,
            "failure_reason": rc.failure_reason,
            "source": "rule",
        }
        for rc in checks
    ] + grounds

    aggregate = (
        db.query(ComplianceResult)
        .filter(ComplianceResult.evidence_record_id == evidence_record_id)
        .first()
    )

    if not violation_summary:
        lines = [
            f"{_ground_label(c)} ({c['rule_name']}): "
            f"{c['failure_reason'] or 'non-compliant'}"
            for c in cited
        ]
        violation_summary = (
            f"{len(cited)} violation(s) found on inspection. " + " | ".join(lines)
        )

    if severity:
        resolved_severity = ViolationSeverity(severity)
    else:
        rule_codes = [c["rule_code"] for c in cited if c.get("source") != "registry"]
        resolved_severity = (
            _worst_severity(rule_codes, db) if rule_codes else ViolationSeverity.MAJOR
        )
        # An altered declaration is at least a major matter.
        if grounds and _SEVERITY_ORDER.index(resolved_severity) < _SEVERITY_ORDER.index(
            ViolationSeverity.MAJOR
        ):
            resolved_severity = ViolationSeverity.MAJOR

    extras = _evidence_extras(evidence)
    manufacturer = extras.get("manufacturer_name")
    manufacturer_address = extras.get("manufacturer_address")

    report = ViolationReport(
        report_number=_report_number(),
        product_id=None,
        evidence_record_id=evidence_record_id,
        complaint_id=complaint_id or evidence.complaint_id,
        inspector_id=inspector.id,
        status=ViolationStatus.PENDING_ADMIN_CONFIRMATION,
        severity=resolved_severity,
        violation_summary=violation_summary,
        violated_rules_json=json.dumps(cited),
        inspector_notes=inspector_notes,
        shop_name=shop_name or evidence.seller_name,
        shop_address=shop_address or evidence.seller_address,
        manufacturer_name=manufacturer,
        manufacturer_address=manufacturer_address,
        product_name=aggregate.product_name if aggregate else None,
    )
    db.add(report)
    db.flush()
    return report


def _evidence_extras(evidence: EvidenceRecord) -> Dict[str, Any]:
    """Pull manufacturer details out of the stored OCR/authenticity payload."""
    if not evidence.detected_fields_json:
        return {}
    try:
        blob = json.loads(evidence.detected_fields_json)
    except (ValueError, TypeError):
        return {}
    if not isinstance(blob, dict):
        return {}

    ocr = blob.get("ocr") if isinstance(blob.get("ocr"), dict) else {}
    return {
        "manufacturer_name": ocr.get("manufacturer_name"),
        "manufacturer_address": ocr.get("manufacturer_address"),
    }


def confirm_report(
    db: Session, admin: User, report: ViolationReport, admin_notes: Optional[str] = None
) -> ViolationReport:
    """Admin confirms a filed report. Caller commits."""
    report = _lock(db, report)
    if report.status != ViolationStatus.PENDING_ADMIN_CONFIRMATION:
        raise ViolationWorkflowError(
            f"Report {report.report_number} is '{_status(report)}' — only "
            "reports pending confirmation can be confirmed."
        )
    report.status = ViolationStatus.CONFIRMED
    report.admin_id = admin.id
    report.admin_notes = admin_notes
    report.confirmed_at = datetime.now(timezone.utc)
    db.add(report)
    return report


def reject_report(
    db: Session, admin: User, report: ViolationReport, admin_notes: Optional[str] = None
) -> ViolationReport:
    """Admin rejects a filed report. Caller commits."""
    report = _lock(db, report)
    if report.status != ViolationStatus.PENDING_ADMIN_CONFIRMATION:
        raise ViolationWorkflowError(
            f"Report {report.report_number} is '{_status(report)}' — only "
            "reports pending confirmation can be rejected."
        )
    report.status = ViolationStatus.REJECTED
    report.admin_id = admin.id
    report.admin_notes = admin_notes
    report.rejected_at = datetime.now(timezone.utc)
    db.add(report)
    return report


def issue_notice(
    db: Session,
    admin: User,
    report: ViolationReport,
    *,
    response_deadline_days: int = 15,
) -> LegalNotice:
    """Admin issues the GO notice for a confirmed report. Caller commits.

    A notice may only follow confirmation — that ordering is the whole point
    of the escalation chain, so it is enforced rather than assumed.
    """
    report = _lock(db, report)
    if report.status == ViolationStatus.PENDING_ADMIN_CONFIRMATION:
        raise ViolationWorkflowError(
            f"Report {report.report_number} has not been confirmed yet. "
            "Confirm it before issuing a notice."
        )
    if report.status == ViolationStatus.REJECTED:
        raise ViolationWorkflowError(
            f"Report {report.report_number} was rejected — no notice can be issued."
        )

    existing = (
        db.query(LegalNotice)
        .filter(LegalNotice.violation_report_id == report.id)
        .first()
    )
    if existing is not None:
        return existing

    cited = json.loads(report.violated_rules_json or "[]")
    clauses = sorted({c.get("statutory_reference", "") for c in cited if c.get("statutory_reference")})

    recipient_name = report.manufacturer_name or report.shop_name or "The Manufacturer / Seller"
    recipient_address = (
        report.manufacturer_address or report.shop_address or "Address not on record"
    )

    body_lines = [
        f"Whereas an inspection conducted under the Legal Metrology Act, 2009 "
        f"has disclosed {len(cited)} contravention(s) in respect of the "
        f"packaged commodity '{report.product_name or 'under inspection'}'",
        f"offered for sale at {report.shop_name or 'the premises inspected'}"
        f"{', ' + report.shop_address if report.shop_address else ''};",
        "",
        "And whereas the said contraventions are particularised below:",
        "",
    ]
    for c in cited:
        mark = c.get("rule_number") if c.get("rule_number") is not None else "Registry"
        body_lines.append(
            f"  ({mark}) {c.get('rule_name')} — "
            f"{c.get('failure_reason') or 'non-compliant'} "
            f"[{c.get('statutory_reference')}]"
        )
    body_lines += [
        "",
        f"Now therefore you are hereby called upon to show cause within "
        f"{response_deadline_days} days of receipt of this notice as to why "
        "proceedings should not be initiated against you under the Legal "
        "Metrology Act, 2009 and the Rules made thereunder.",
    ]

    notice = LegalNotice(
        notice_number=_notice_number(),
        violation_report_id=report.id,
        recipient_name=recipient_name,
        recipient_company=report.manufacturer_name,
        recipient_address=recipient_address,
        issuing_officer_name=admin.full_name,
        statutory_clauses_cited="; ".join(clauses) or "Legal Metrology Act, 2009",
        notice_body="\n".join(body_lines),
        response_deadline_days=response_deadline_days,
        status=NoticeStatus.GENERATED,
    )
    db.add(notice)

    report.status = ViolationStatus.NOTICE_GENERATED
    db.add(report)
    db.flush()
    return notice


def _status(report: ViolationReport) -> str:
    return (
        report.status.value
        if isinstance(report.status, ViolationStatus)
        else str(report.status)
    )


def serialize_row(
    db: Session, report: ViolationReport
) -> Dict[str, Any]:
    """Flat dict for the admin queue and the inspector's filed list."""
    cited = json.loads(report.violated_rules_json or "[]")
    evidence = report.evidence
    inspector = report.inspector
    status = _status(report)

    return {
        "id": report.id,
        "report_number": report.report_number,
        "status": status,
        "severity": (
            report.severity.value
            if isinstance(report.severity, ViolationSeverity)
            else str(report.severity)
        ),
        "product_name": report.product_name,
        "shop_name": report.shop_name,
        "manufacturer_name": report.manufacturer_name,
        "violation_summary": report.violation_summary,
        "violated_rule_count": len(cited),
        "evidence_record_id": report.evidence_record_id,
        "complaint_id": report.complaint_id,
        "inspector_id": report.inspector_id,
        "inspector_name": inspector.full_name if inspector else None,
        "inspector_badge": inspector.badge_number if inspector else None,
        "admin_id": report.admin_id,
        "gps_latitude": evidence.gps_latitude if evidence else None,
        "gps_longitude": evidence.gps_longitude if evidence else None,
        "pin_color": _pin_for(status, report.severity),
        "created_at": report.created_at,
        "confirmed_at": report.confirmed_at,
        "rejected_at": report.rejected_at,
    }


def _pin_for(status: str, severity: Any) -> str:
    """Map colour: grey once resolved, else severity-weighted."""
    if status in (
        ViolationStatus.REJECTED.value,
        ViolationStatus.CLOSED.value,
    ):
        return "grey"
    sev = severity.value if isinstance(severity, ViolationSeverity) else str(severity)
    if sev == ViolationSeverity.CRITICAL.value:
        return "darkred"
    if sev == ViolationSeverity.MAJOR.value:
        return "red"
    if sev == ViolationSeverity.MODERATE.value:
        return "orange"
    return "yellow"


def serialize_detail(db: Session, report: ViolationReport) -> Dict[str, Any]:
    """Row plus the full citation list and chain-of-custody metadata."""
    data = serialize_row(db, report)
    evidence = report.evidence
    notice = (
        db.query(LegalNotice)
        .filter(LegalNotice.violation_report_id == report.id)
        .first()
    )
    data.update(
        {
            "inspector_notes": report.inspector_notes,
            "admin_notes": report.admin_notes,
            "shop_address": report.shop_address,
            "manufacturer_address": report.manufacturer_address,
            "violated_rules": json.loads(report.violated_rules_json or "[]"),
            "evidence_sha256": evidence.sha256_hash if evidence else None,
            "evidence_captured_at": (
                evidence.timestamp_ntp or evidence.timestamp_device
            )
            if evidence
            else None,
            "notice_generated": notice is not None,
            "notice_id": notice.id if notice else None,
        }
    )
    return data
