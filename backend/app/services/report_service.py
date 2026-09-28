"""
FieldProof — Per-test PDF report (ReportLab).

build_test_pdf(record, image_bytes) -> PDF bytes. `record` is the TestRecord
JSON dict from record_service.to_dict (verify_url included).
"""

from __future__ import annotations

import io
from typing import Any, Dict, Optional
from xml.sax.saxutils import escape

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services import time_service

TITLE = "FieldProof - Field Test Record"
DISCLAIMER = (
    "Presumptive field result — not a substitute for laboratory confirmatory testing."
)
HASH_LINE = "Hash details (SHA-256) for a BSA 2023 Sec 63 certificate"

RESULT_COLOURS = {
    "POSITIVE": colors.HexColor("#c62828"),
    "NEGATIVE": colors.HexColor("#2e7d32"),
    "INCONCLUSIVE": colors.HexColor("#6a1b9a"),
}

_ss = getSampleStyleSheet()
_H1 = ParagraphStyle("fpH1", parent=_ss["Heading1"], fontSize=17, spaceAfter=4)
_NORMAL = ParagraphStyle("fpN", parent=_ss["Normal"], fontSize=9.5, leading=12)
_SMALL = ParagraphStyle("fpS", parent=_ss["Normal"], fontSize=8, leading=10)
_MONO = ParagraphStyle("fpM", parent=_ss["Normal"], fontName="Courier", fontSize=7.5, leading=9.5)
_WARN = ParagraphStyle(
    "fpW", parent=_ss["Normal"], fontSize=9.5, leading=12,
    textColor=colors.HexColor("#8a4b00"), backColor=colors.HexColor("#fff4e0"),
    borderPadding=4, spaceAfter=6,
)


def _p(text: Any, style: ParagraphStyle = _NORMAL) -> Paragraph:
    return Paragraph(escape("" if text is None else str(text)), style)


def _qr(url: str, size_mm: float = 32) -> Drawing:
    widget = QrCodeWidget(url)
    x1, y1, x2, y2 = widget.getBounds()
    w, h = x2 - x1, y2 - y1
    size = size_mm * mm
    d = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
    d.add(widget)
    return d


def _photo(image_bytes: Optional[bytes]) -> Optional[Image]:
    if not image_bytes:
        return None
    try:
        reader = ImageReader(io.BytesIO(image_bytes))
        iw, ih = reader.getSize()
        max_w, max_h = 110 * mm, 75 * mm
        scale = min(max_w / iw, max_h / ih)
        return Image(io.BytesIO(image_bytes), width=iw * scale, height=ih * scale)
    except Exception:
        return None


def _short(sig: Optional[str], n: int = 24) -> str:
    if not sig:
        return "-"
    return sig if len(sig) <= 2 * n else f"{sig[:n]}...{sig[-n:]}"


def build_test_pdf(record: Dict[str, Any], image_bytes: Optional[bytes]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=TITLE, author="FieldProof",
    )
    story: list = [_p(TITLE, _H1), Paragraph(escape(DISCLAIMER), _WARN)]

    # Result banner
    result = record.get("result") or "INCONCLUSIVE"
    banner_text = {"INCONCLUSIVE": "INCONCLUSIVE (NOT SURE)"}.get(result, result)
    conf = record.get("confidence")
    banner = Table(
        [[Paragraph(
            f'<font color="white" size="15"><b>{escape(banner_text)}</b></font>'
            f'<br/><font color="white" size="10">{escape(record.get("outcome_label") or "-")}'
            f'{"" if conf is None else f" | {conf}% sure"}</font>',
            _NORMAL,
        )]],
        colWidths=[180 * mm],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), RESULT_COLOURS.get(result, colors.grey)),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [banner, Spacer(1, 4)]
    if record.get("reason"):
        story.append(_p(f"Reason: {record['reason']}"))
    story.append(Spacer(1, 4))

    # Photo + QR side by side
    photo = _photo(image_bytes) or _p("(Photo could not be shown)")
    url = record.get("verify_url") or ""
    # The QR is scanned by OTHER phones, so it must use the laptop's network address, not 127.0.0.1.
    from pathlib import Path
    from app.config import settings
    tunnel_file = Path(__file__).resolve().parents[2] / "qr_base_url.txt"  # written by scripts/public_link.py
    qr_base = tunnel_file.read_text(encoding="utf-8").strip() if tunnel_file.exists() else settings.qr_base_url
    if qr_base and record.get("id") is not None:
        url = f"{qr_base.rstrip('/')}/v/{record['id']}"
    qr_cell = [_qr(url), _p("Scan to check this record", _SMALL), _p(url, _SMALL)]
    top = Table([[photo, qr_cell]], colWidths=[125 * mm, 55 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [top, Spacer(1, 6)]

    # Record fields
    lat, lon = record.get("latitude"), record.get("longitude")
    gps = "-" if lat is None or lon is None else f"{lat:.6f}, {lon:.6f}"
    if record.get("gps_accuracy_m") is not None:
        gps += f"  (±{record['gps_accuracy_m']} m)"
    if record.get("gps_is_mock"):
        gps += "  WARNING: phone said this may be a fake location"
    rows = [
        ("Test number", record.get("id")),
        ("Test ID", record.get("test_uid")),
        ("Saved at (UTC)", f"{record.get('created_at')}  (time from: {time_service.label(record.get('time_source'))})"),
        ("Phone time", f"{record.get('device_time') or '-'}  (difference: {record.get('clock_drift_s')} s)"),
        ("GPS location", gps),
        ("Officer", f"{record.get('officer_name') or '-'} (user id {record.get('officer_id')})"),
        ("Device ID", record.get("device_id") or "-"),
        ("Kit", f"{record.get('kit_name')} [{record.get('kit_code')}], profile version {record.get('kit_version')}"),
        ("Lab sample ID", record.get("lab_sample_id") or "-"),
        ("Review status", record.get("review_status")),
    ]
    t = Table([[_p(k, _SMALL), _p(v)] for k, v in rows], colWidths=[38 * mm, 142 * mm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f2f2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story += [t, Spacer(1, 8)]

    # Hash block
    story.append(_p(HASH_LINE, ParagraphStyle("fpH3", parent=_ss["Heading4"], spaceAfter=2)))
    hrows = [
        ("Photo SHA-256", record.get("image_sha256")),
        ("Record hash (SHA-256)", record.get("record_hash")),
        ("Previous record hash", record.get("prev_record_hash")),
        ("Signature (Ed25519, shortened)", _short(record.get("signature"))),
        ("Key ID", record.get("key_id")),
    ]
    ht = Table([[_p(k, _SMALL), _p(v, _MONO)] for k, v in hrows], colWidths=[45 * mm, 135 * mm])
    ht.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story += [ht, Spacer(1, 6)]
    story.append(_p(
        "The photo was hashed with SHA-256 the moment it reached the server. The record was "
        "then hashed, chained to the previous record and signed. Anyone can re-check it using "
        "the QR code above.", _SMALL,
    ))
    story.append(Spacer(1, 4))
    story.append(_p(DISCLAIMER, _SMALL))

    doc.build(story)
    return buf.getvalue()
