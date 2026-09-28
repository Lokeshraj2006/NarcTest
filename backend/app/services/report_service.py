"""
FieldProof — Report Service (ReportLab)

Generates a formatted legal notice PDF for one EvidenceRecord, ready
for the inspector or admin to print, sign, and dispatch. Contents:

    • Shop / seller name & address              (from EvidenceRecord)
    • Manufacturer name & address               (from ProductRegistry, else OCR)
    • Anomalies found + per-anomaly statute     (from ComplianceResult failures)
    • Evidence image thumbnail                  (from EvidenceRecord.file_path)
    • GPS coordinates                           (from EvidenceRecord)
    • Timestamp (device + NTP-verified)         (from EvidenceRecord)
    • SHA-256 hash (chain of custody)           (from EvidenceRecord)
    • Inspector name + badge number             (from User)

Zero FastAPI dependency — plain functions callable from routers, workers,
or unit tests. Caller supplies the DB session.
"""

from __future__ import annotations

import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session, joinedload

from app.models.compliance_result import ComplianceResult, OverallStatus
from app.models.evidence import EvidenceRecord
from app.models.legal_notice import LegalNotice
from app.models.product_registry import ProductRegistry
from app.models.rule_check import RuleCheck
from app.models.user import User

# ── Styles ────────────────────────────────────────────────────────────────
_STYLES = getSampleStyleSheet()
_H1 = ParagraphStyle(
    "LegalH1", parent=_STYLES["Heading1"],
    alignment=TA_CENTER, fontSize=16, spaceAfter=6, textColor=colors.HexColor("#1a1a1a"),
)
_SUB = ParagraphStyle(
    "LegalSub", parent=_STYLES["Normal"],
    alignment=TA_CENTER, fontSize=10, textColor=colors.HexColor("#555555"), spaceAfter=14,
)
_H2 = ParagraphStyle(
    "LegalH2", parent=_STYLES["Heading2"],
    fontSize=12, textColor=colors.HexColor("#1a1a1a"), spaceBefore=10, spaceAfter=4,
)
_BODY = ParagraphStyle(
    "LegalBody", parent=_STYLES["Normal"], fontSize=10, leading=13, alignment=TA_LEFT,
)
_META = ParagraphStyle(
    "LegalMeta", parent=_STYLES["Normal"], fontSize=9, leading=11,
    textColor=colors.HexColor("#333333"),
)
_HASH = ParagraphStyle(
    "LegalHash", parent=_STYLES["Code"], fontSize=7.5, leading=9,
    textColor=colors.HexColor("#222222"),
)


class ReportGenerationError(Exception):
    """Raised when the PDF cannot be assembled (missing evidence, etc.)."""


# ── Small helpers ─────────────────────────────────────────────────────────
def _fmt_dt(dt: Optional[datetime]) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%d %b %Y, %H:%M:%S %Z").strip()


def _load_extras(evidence: EvidenceRecord) -> Dict[str, Any]:
    """Parse EvidenceRecord.detected_fields_json into a dict (best-effort)."""
    if not evidence.detected_fields_json:
        return {}
    try:
        payload = json.loads(evidence.detected_fields_json)
    except (ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_manufacturer(
    db: Session, extras: Dict[str, Any]
) -> Tuple[str, str, Optional[str]]:
    """Return (name, address, source_label). Prefer trusted registry match."""
    auth = extras.get("authenticity") if isinstance(extras, dict) else None
    if isinstance(auth, dict) and auth.get("registry_id"):
        reg = (
            db.query(ProductRegistry)
            .filter(ProductRegistry.id == int(auth["registry_id"]))
            .first()
        )
        if reg is not None:
            return reg.manufacturer_name, reg.manufacturer_address, "reference registry"

    ocr = extras.get("ocr") if isinstance(extras, dict) else None
    if isinstance(ocr, dict):
        name = str(ocr.get("manufacturer_name") or "").strip()
        addr = str(ocr.get("manufacturer_address") or "").strip()
        if name or addr:
            return (name or "—"), (addr or "—"), "OCR-extracted label text"

    return "—", "—", None


def _anomaly_rows(
    result: ComplianceResult, rule_checks: List[RuleCheck]
) -> List[List[str]]:
    """Table body: [rule#, description, statute] for each failing check."""
    rc_by_id = {rc.id: rc for rc in rule_checks}
    rows: List[List[str]] = [["Rule", "Anomaly / Non-Compliance", "Statutory Reference"]]

    if not result.failures and not any(rc.status.value == "FAIL" if hasattr(rc.status, "value") else rc.status == "FAIL" for rc in rule_checks):
        rows.append(["—", "No individual rule failures recorded.", "—"])
        return rows

    for failure in result.failures:
        rc = rc_by_id.get(failure.rule_check_id)
        if rc is None:
            continue
        desc = failure.note or rc.failure_reason or f"{rc.rule_name} check failed."
        rows.append([str(rc.rule_number), desc, failure.law_reference])
    return rows


def _authenticity_rows(extras: Dict[str, Any]) -> Optional[List[List[str]]]:
    auth = extras.get("authenticity") if isinstance(extras, dict) else None
    if not isinstance(auth, dict):
        return None
    mismatches = auth.get("mismatches") or []
    if not mismatches:
        return None
    rows = [["Field", "Registry (expected)", "Detected on label", "Note"]]
    for m in mismatches:
        if not isinstance(m, dict):
            continue
        rows.append([
            str(m.get("field", "—")),
            str(m.get("expected") or "—"),
            str(m.get("detected") or "—"),
            str(m.get("note") or ""),
        ])
    return rows if len(rows) > 1 else None


def _make_image_flowable(path: Optional[str], max_w_mm: float = 60) -> Optional[Image]:
    if not path:
        return None
    if not os.path.isfile(path):
        return None
    try:
        img = Image(path)
    except Exception:
        return None
    max_w = max_w_mm * mm
    if img.imageWidth and img.drawWidth > max_w:
        ratio = max_w / float(img.drawWidth)
        img.drawWidth = max_w
        img.drawHeight = img.drawHeight * ratio
    return img


# ── Public API ────────────────────────────────────────────────────────────
def generate_legal_notice_pdf(
    db: Session,
    evidence_record_id: int,
    output_dir: Optional[str] = None,
    filename: Optional[str] = None,
) -> Tuple[bytes, str]:
    """Generate the legal notice PDF for one EvidenceRecord.

    Args:
        db: active SQLAlchemy session.
        evidence_record_id: FK into evidence_records.
        output_dir: if provided, the PDF is also written to this directory
            and its absolute path is returned; otherwise a suggested filename
            is returned alongside the raw bytes.
        filename: explicit filename to use; defaults to
            `legal_notice_ev<id>_<utcstamp>.pdf`.

    Returns:
        Tuple of (pdf_bytes, filename_or_absolute_path).

    Raises:
        ReportGenerationError if the evidence or compliance result is missing.
    """
    evidence = (
        db.query(EvidenceRecord)
        .options(joinedload(EvidenceRecord.captured_by))
        .filter(EvidenceRecord.id == evidence_record_id)
        .first()
    )
    if evidence is None:
        raise ReportGenerationError(
            f"Evidence record #{evidence_record_id} not found."
        )

    result = (
        db.query(ComplianceResult)
        .options(joinedload(ComplianceResult.failures))
        .filter(ComplianceResult.evidence_record_id == evidence_record_id)
        .first()
    )
    if result is None:
        raise ReportGenerationError(
            f"No compliance result exists for evidence #{evidence_record_id} — "
            "cannot generate a legal notice."
        )

    rule_checks = (
        db.query(RuleCheck)
        .filter(RuleCheck.evidence_id == evidence_record_id)
        .order_by(RuleCheck.rule_number.asc())
        .all()
    )

    extras = _load_extras(evidence)
    manu_name, manu_addr, manu_source = _resolve_manufacturer(db, extras)

    inspector: Optional[User] = evidence.captured_by
    inspector_line = "—"
    if inspector is not None:
        badge = f" (Badge {inspector.badge_number})" if inspector.badge_number else ""
        inspector_line = f"{inspector.full_name}{badge}"

    filename = filename or (
        f"compliance_report_scan{evidence_record_id}_"
        f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    )
    status_value = (
        result.overall_status.value
        if isinstance(result.overall_status, OverallStatus)
        else str(result.overall_status)
    )
    # The report of a scan, whatever its verdict. The GO show-cause notice,
    # the enforcement instrument, is a separate document.
    heading = {
        OverallStatus.COMPLIANT.value: "LEGAL METROLOGY — INSPECTION REPORT: COMPLIANT",
        OverallStatus.NEEDS_REVIEW.value: "LEGAL METROLOGY — INSPECTION REPORT: NOT FULLY VERIFIED",
    }.get(status_value, "LEGAL METROLOGY — INSPECTION REPORT: NON-COMPLIANCE FOUND")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Compliance Report — Scan #{evidence_record_id}",
        author="FieldProof",
    )

    story: List[Any] = []
    story.append(Paragraph(heading, _H1))
    story.append(Paragraph(
        f"Reference: FieldProof/SCAN-{evidence_record_id}/{datetime.utcnow().strftime('%Y%m%d')}",
        _SUB,
    ))

    # ── Seller / Shop block ──────────────────────────────────────────
    story.append(Paragraph("Shop / Seller", _H2))
    story.append(Paragraph(
        f"<b>Name:</b> {evidence.seller_name or '— (not captured)'}<br/>"
        f"<b>Address:</b> {evidence.seller_address or '— (not captured)'}",
        _BODY,
    ))

    # ── Manufacturer block ───────────────────────────────────────────
    story.append(Paragraph("Manufacturer (as printed / as registered)", _H2))
    src_note = f" &nbsp;<font size=8 color='#666666'>[source: {manu_source}]</font>" if manu_source else ""
    story.append(Paragraph(
        f"<b>Name:</b> {manu_name}{src_note}<br/><b>Address:</b> {manu_addr}",
        _BODY,
    ))

    # ── Overall verdict banner ───────────────────────────────────────
    verdict_color = colors.HexColor({
        OverallStatus.COMPLIANT.value: "#0B6A0B",
        OverallStatus.NEEDS_REVIEW.value: "#B45309",
    }.get(status_value, "#B00020"))
    verdict_tbl = Table(
        [[Paragraph(
            f"<b>Overall Status:</b> {status_value.upper()}"
            + (f" &nbsp;|&nbsp; <b>Primary Reference:</b> {result.law_reference}" if result.law_reference else ""),
            _BODY,
        )]],
        colWidths=[doc.width],
    )
    verdict_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f2f2")),
        ("BOX", (0, 0), (-1, -1), 0.8, verdict_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Spacer(1, 6))
    story.append(verdict_tbl)

    # ── Anomalies table ──────────────────────────────────────────────
    story.append(Paragraph("Anomalies Found", _H2))
    rows = _anomaly_rows(result, rule_checks)
    anomalies_tbl = Table(
        [[Paragraph(cell, _META) for cell in row] for row in rows],
        colWidths=[15 * mm, doc.width * 0.55, doc.width * 0.35],
        repeatRows=1,
    )
    anomalies_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6ecf5")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#888888")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(anomalies_tbl)

    # ── Authenticity mismatches (if any) ─────────────────────────────
    auth_rows = _authenticity_rows(extras)
    if auth_rows is not None:
        story.append(Paragraph("Authenticity Cross-Check (Registry vs Label)", _H2))
        auth_tbl = Table(
            [[Paragraph(cell, _META) for cell in row] for row in auth_rows],
            colWidths=[doc.width * 0.18, doc.width * 0.2, doc.width * 0.2, doc.width * 0.42],
            repeatRows=1,
        )
        auth_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6ecf5")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#888888")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(auth_tbl)
        story.append(Paragraph(
            "A declaration on the pack that differs from the registered product may have been "
            "altered, which Rule 6(3), Legal Metrology (Packaged Commodities) Rules, 2011 forbids "
            "(only a sticker lowering the MRP is allowed). This must be confirmed on the physical "
            "pack before it is cited in a report.",
            _META,
        ))

    # ── Evidence chain-of-custody block (image + hash + geo) ─────────
    story.append(Paragraph("Evidence — Chain of Custody", _H2))

    thumb = _make_image_flowable(evidence.file_path, max_w_mm=60)
    hash_paragraph = Paragraph(
        f"<b>SHA-256:</b><br/>{evidence.sha256_hash}", _HASH,
    )
    meta_lines: List[str] = []
    lat, lng = evidence.gps_latitude, evidence.gps_longitude
    if lat is not None and lng is not None:
        meta_lines.append(f"<b>GPS:</b> {lat:.6f}, {lng:.6f}")
        if evidence.gps_accuracy_meters:
            meta_lines[-1] += f" (±{evidence.gps_accuracy_meters:.0f} m)"
    else:
        meta_lines.append("<b>GPS:</b> —")
    meta_lines.append(f"<b>Captured (device):</b> {_fmt_dt(evidence.timestamp_device)}")
    if evidence.timestamp_ntp:
        meta_lines.append(f"<b>NTP-verified:</b> {_fmt_dt(evidence.timestamp_ntp)}")
    if evidence.ntp_drift_seconds is not None:
        meta_lines.append(f"<b>NTP drift:</b> {evidence.ntp_drift_seconds:.3f} s")
    if evidence.is_tampered:
        meta_lines.append(
            f"<b><font color='#B00020'>Tamper flag:</font></b> "
            f"{evidence.tamper_reason or 'set'}"
        )
    meta_paragraph = Paragraph("<br/>".join(meta_lines), _META)

    coc_cells: List[List[Any]] = []
    if thumb is not None:
        coc_cells.append([thumb, meta_paragraph])
    else:
        coc_cells.append([
            Paragraph("<i>Evidence image not accessible on disk.</i>", _META),
            meta_paragraph,
        ])
    coc_cells.append(["", hash_paragraph])

    coc_tbl = Table(
        coc_cells,
        colWidths=[doc.width * 0.35, doc.width * 0.65],
    )
    coc_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.3, colors.HexColor("#888888")),
        ("INNERGRID", (0, 0), (-1, -1), 0.15, colors.HexColor("#cccccc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("SPAN", (0, 0), (0, 1)),
    ]))
    story.append(KeepTogether(coc_tbl))

    # ── Inspector footer ─────────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(Paragraph("Filed by", _H2))
    story.append(Paragraph(
        f"{inspector_line}<br/>"
        f"<font size=8 color='#666666'>Generated by FieldProof on "
        f"{datetime.utcnow().strftime('%d %b %Y, %H:%M:%S UTC')}. "
        f"This notice is drawn from AI-assisted checks and requires the filing "
        f"inspector's verification and signature.</font>",
        _BODY,
    ))
    story.append(Spacer(1, 30))
    story.append(Paragraph(
        "____________________________<br/>Signature of Inspecting Officer",
        _BODY,
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()

    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        out_path = os.path.join(output_dir, filename)
        with open(out_path, "wb") as fh:
            fh.write(pdf_bytes)
        return pdf_bytes, out_path

    return pdf_bytes, filename


# ── GO notice (issued by the admin, not the inspector) ───────────────────
def generate_go_notice_pdf(
    db: Session,
    notice_id: int,
    output_dir: Optional[str] = None,
) -> Tuple[bytes, str]:
    """Render the show-cause (GO) notice the admin issues to manufacturer/shop.

    Deliberately a different document from the inspector's field report:
    this is a statutory demand addressed to a respondent, citing the
    contraventions and giving a deadline to show cause. The field report is
    evidence; this is the enforcement instrument built on top of it.
    """
    notice = db.query(LegalNotice).filter(LegalNotice.id == notice_id).first()
    if notice is None:
        raise ReportGenerationError(f"Legal notice #{notice_id} not found.")

    report = notice.violation_report
    if report is None:
        raise ReportGenerationError(
            f"Notice {notice.notice_number} has no violation report attached."
        )

    cited: List[Dict[str, Any]] = []
    try:
        cited = json.loads(report.violated_rules_json or "[]")
    except (ValueError, TypeError):
        cited = []

    filename = f"GO_notice_{notice.notice_number}.pdf"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Show Cause Notice {notice.notice_number}",
        author=notice.issuing_authority,
    )

    story: List[Any] = []

    # ── Letterhead ───────────────────────────────────────────────────
    story.append(Paragraph(notice.issuing_authority.upper(), _H1))
    story.append(Paragraph(
        "Government of India &nbsp;|&nbsp; Department of Consumer Affairs",
        _SUB,
    ))
    story.append(Paragraph("SHOW CAUSE NOTICE", _H1))
    story.append(Paragraph(
        f"Notice No. {notice.notice_number} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Report Ref. {report.report_number} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Dated {notice.created_at.strftime('%d %B %Y') if notice.created_at else ''}",
        _SUB,
    ))

    # ── Respondent ───────────────────────────────────────────────────
    story.append(Paragraph("To,", _BODY))
    story.append(Paragraph(
        f"<b>{notice.recipient_name}</b><br/>"
        + (f"{notice.recipient_company}<br/>" if notice.recipient_company else "")
        + f"{notice.recipient_address}",
        _BODY,
    ))
    story.append(Spacer(1, 6))
    if report.shop_name:
        story.append(Paragraph(
            f"<b>Premises inspected:</b> {report.shop_name}"
            + (f", {report.shop_address}" if report.shop_address else ""),
            _META,
        ))
    story.append(Spacer(1, 10))

    # ── Subject ──────────────────────────────────────────────────────
    story.append(Paragraph(
        f"<b>Subject:</b> Contravention of the Legal Metrology Act, 2009 and "
        f"the Rules made thereunder in respect of the packaged commodity "
        f"'{report.product_name or 'under inspection'}'.",
        _BODY,
    ))
    story.append(Spacer(1, 10))

    # ── Body ─────────────────────────────────────────────────────────
    for para in (notice.notice_body or "").split("\n"):
        if para.strip():
            story.append(Paragraph(para.replace("  ", "&nbsp;&nbsp;"), _BODY))
        else:
            story.append(Spacer(1, 5))

    # ── Contraventions table ─────────────────────────────────────────
    if cited:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Particulars of Contravention", _H2))
        rows = [["Rule", "Contravention", "Statutory Provision"]]
        for c in cited:
            rows.append([
                str(c["rule_number"]) if c.get("rule_number") is not None else "Reg.",
                f"{c.get('rule_name', '')}: {c.get('failure_reason') or 'non-compliant'}",
                c.get("statutory_reference", "-"),
            ])
        tbl = Table(
            [[Paragraph(cell, _META) for cell in row] for row in rows],
            colWidths=[14 * mm, doc.width * 0.55, doc.width * 0.35],
            repeatRows=1,
        )
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6ecf5")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#888888")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)

    # ── Evidence provenance ──────────────────────────────────────────
    evidence = report.evidence
    if evidence is not None:
        story.append(Paragraph("Evidence Relied Upon", _H2))
        meta = [
            f"<b>Evidence ref:</b> EV-{evidence.id}",
            f"<b>Captured:</b> {_fmt_dt(evidence.timestamp_ntp or evidence.timestamp_device)}",
        ]
        if evidence.gps_latitude is not None and evidence.gps_longitude is not None:
            meta.append(
                f"<b>Location:</b> {evidence.gps_latitude:.6f}, "
                f"{evidence.gps_longitude:.6f}"
            )
        story.append(Paragraph("<br/>".join(meta), _META))
        story.append(Paragraph(
            f"<b>SHA-256:</b> {evidence.sha256_hash}", _HASH,
        ))
        thumb = _make_image_flowable(evidence.file_path, max_w_mm=55)
        if thumb is not None:
            story.append(Spacer(1, 6))
            story.append(thumb)

    # ── Signature block ──────────────────────────────────────────────
    story.append(Spacer(1, 18))
    story.append(Paragraph(
        f"Inspected and reported by: {report.inspector.full_name}"
        + (f" (Badge {report.inspector.badge_number})"
           if report.inspector and report.inspector.badge_number else "")
        if report.inspector else "",
        _META,
    ))
    story.append(Spacer(1, 24))
    story.append(Paragraph(
        "____________________________<br/>"
        f"<b>{notice.issuing_officer_name}</b><br/>"
        f"{notice.issuing_authority}",
        _BODY,
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<font size=8 color='#666666'>Generated by FieldProof. This notice "
        "is drawn from AI-assisted inspection findings reviewed and confirmed "
        "by the issuing officer, whose signature above authenticates it."
        "</font>",
        _BODY,
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()

    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        out_path = os.path.join(output_dir, filename)
        with open(out_path, "wb") as fh:
            fh.write(pdf_bytes)
        return pdf_bytes, out_path

    return pdf_bytes, filename
