"""FieldProof — Public record verification (JSON + simple HTML page)."""

from __future__ import annotations

from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.test_record import TestRecord
from app.services import record_service, signing

router = APIRouter(tags=["verify"])

CHECK_TEXT = {
    "image_hash": ("The photo is the same as when it was taken", "The photo was changed"),
    "record_hash": ("The saved details match their fingerprint (hash)", "The saved details do not match their fingerprint"),
    "signature": ("The FieldProof server's digital signature is valid", "The digital signature is not valid"),
    "chain": ("The record is correctly linked to the record before it", "The link to the record before it is broken"),
    "fields_match": ("The result, officer and kit shown are the ones that were signed", "The result, officer or kit shown was changed"),
}


def _get(db: Session, test_id: int) -> TestRecord:
    test = (
        db.query(TestRecord)
        .options(selectinload(TestRecord.officer))
        .filter(TestRecord.id == test_id)
        .first()
    )
    if test is None:
        raise HTTPException(404, "No record with this number.")
    return test


@router.get("/verify/pubkey")
def pubkey():
    return {"key_id": signing.key_id, "public_key_pem": signing.public_key_pem()}


@router.get("/verify/{test_id}")
def verify_json(test_id: int, db: Session = Depends(get_db)):
    return record_service.verify_record(db, _get(db, test_id))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FieldProof record check</title>
<style>
 body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f4f5f7;color:#1c1c1c}}
 .wrap{{max-width:560px;margin:0 auto;padding:16px}}
 .brand{{font-weight:700;color:#444;margin:4px 0 12px}}
 .banner{{border-radius:14px;padding:22px 18px;color:#fff;background:{colour}}}
 .banner h1{{margin:0 0 6px;font-size:26px;line-height:1.2}}
 .banner p{{margin:0;font-size:15px;opacity:.95}}
 .card{{background:#fff;border-radius:12px;padding:14px 16px;margin-top:14px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
 .card h2{{font-size:16px;margin:0 0 10px}}
 ul{{list-style:none;padding:0;margin:0}}
 li{{padding:7px 0;border-bottom:1px solid #eee;font-size:15px}} li:last-child{{border:0}}
 .ok{{color:#2e7d32;font-weight:700}} .bad{{color:#c62828;font-weight:700}}
 table{{width:100%;border-collapse:collapse;font-size:14px}}
 td{{padding:6px 0;vertical-align:top;border-bottom:1px solid #eee}} td:first-child{{color:#666;width:40%;padding-right:8px}}
 .mono{{font-family:ui-monospace,Consolas,monospace;font-size:12px;word-break:break-all}}
 .res{{font-weight:700;color:{res_colour}}}
 .note{{font-size:13px;color:#555;margin-top:14px;line-height:1.4}}
</style></head><body><div class="wrap">
<div class="brand">FieldProof &middot; Record check</div>
<div class="banner"><h1>{headline}</h1><p>{sub}</p></div>
<div class="card"><h2>What we checked</h2><ul>{checks}</ul></div>
<div class="card"><h2>Record details</h2><table>{rows}</table></div>
<p class="note">Presumptive field result &mdash; not a substitute for laboratory confirmatory testing.</p>
</div></body></html>"""

RESULT_COLOURS = {"POSITIVE": "#c62828", "NEGATIVE": "#2e7d32", "INCONCLUSIVE": "#6a1b9a"}


@router.get("/v/{test_id}", response_class=HTMLResponse)
def verify_page(test_id: int, db: Session = Depends(get_db)):
    test = db.query(TestRecord).filter(TestRecord.id == test_id).first()
    if test is None:
        return HTMLResponse(
            "<!doctype html><meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<body style='font-family:sans-serif;padding:24px'><h2>No record with this number</h2>"
            "<p>Please check the link or QR code.</p></body>",
            status_code=404,
        )
    v = record_service.verify_record(db, test)
    ok = v["ok"]
    checks = "".join(
        f'<li><span class="{"ok" if passed else "bad"}">{"&#10003;" if passed else "&#10007;"}</span> '
        f"{escape(CHECK_TEXT[name][0 if passed else 1])}</li>"
        for name, passed in v["checks"].items()
    )
    r = v["record"]
    result = r["result"] or "-"
    shown_result = "INCONCLUSIVE (not sure)" if result == "INCONCLUSIVE" else result
    gps = (
        "-" if r["latitude"] is None or r["longitude"] is None
        else f'{r["latitude"]:.5f}, {r["longitude"]:.5f}'
    )
    rows_data = [
        ("Test number", str(v["test_id"]), False),
        ("Result", f'<span class="res">{escape(shown_result)}</span>', True),
        ("What the kit showed", escape(r["outcome_label"] or "-"), True),
        ("How sure", "-" if r["confidence"] is None else f'{r["confidence"]}%', False),
        ("Kit", escape(f'{r["kit_name"]} (version {r["kit_version"]})'), True),
        ("Officer", escape(r["officer_name"] or "-"), True),
        ("Saved at (UTC)", escape(f'{r["created_at"]} ({"internet time" if r["time_source"] == "ntp" else "server clock"})'), True),
        ("GPS", escape(gps), True),
        ("Test ID", f'<span class="mono">{escape(r["test_uid"])}</span>', True),
        ("Photo fingerprint (SHA-256)", f'<span class="mono">{escape(r["image_sha256"])}</span>', True),
        ("Record fingerprint", f'<span class="mono">{escape(r["record_hash"])}</span>', True),
    ]
    rows = "".join(
        f"<tr><td>{escape(k)}</td><td>{val if safe else escape(val)}</td></tr>"
        for k, val, safe in rows_data
    )
    html = PAGE.format(
        colour="#2e7d32" if ok else "#c62828",
        res_colour=RESULT_COLOURS.get(result, "#333"),
        headline="&#10003; Record is genuine" if ok else "&#9888; TAMPERED - this record was changed",
        sub=(
            "The photo and details were not changed after they were saved."
            if ok else
            "Something in this record was changed after it was saved. Do not trust it."
        ),
        checks=checks,
        rows=rows,
    )
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})
