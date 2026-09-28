"""
FieldProof — Compliance Rules (the 13 checks)

Independent checks for each of the 13 Legal Metrology rules:
  1. Manufacturer/packer/importer name + address   Rule 6(1)(a)
  2. Country of origin                             Rule 6(1)(aa)
  3. Generic/common name                           Rule 6(1)(b)
  4. Net quantity                                  Rule 6(1)(c)
  5. MRP                                           Rule 6(1)(e)
  6. Month/year of packing                         Rule 6(1)(d)
  7. Best-before / expiry                          Rule 6(1)(da)
  8. Consumer care details                         Rule 6(2)
  9. Font size                    [CV]             Rule 7(2) + Table I
 10. Readability / contrast       [CV]             Rule 9(1)
 11. Placement on display panel   [CV]             Rule 8(1)
 12. LMPC registration number                      Rule 27
 13. GSTIN format & checksum                       CGST Rule 46

Checks marked [CV] depend on calibrated computer-vision measurement, which
is not implemented yet. Those deliberately return REVIEW ("needs human
verification") rather than an unverified PASS — reporting fabricated
compliance would be worse than admitting the limit.

Plain Python, zero FastAPI dependency, so the whole module is pytest-able
without a database. Statutory citations come from the seeded `rules` table
when a catalogue is supplied, and fall back to the constants here otherwise.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.utils.gstin_validator import validate_gstin_verbose

# ── Statutory reference constants ─────────────────────────────────────────
LMPC = "Legal Metrology (Packaged Commodities) Rules, 2011"
CGST_RULE_46 = "Rule 46, Central Goods and Services Tax Rules, 2017"

LMPC_RULE_6 = f"Rule 6, {LMPC}"
LMPC_RULE_7 = f"Rule 7, {LMPC}"

# Status values mirror models.rule_check.CheckStatus
PASS = "PASS"
FAIL = "FAIL"
REVIEW = "REVIEW"
EXEMPT = "EXEMPT"

# Units accepted for net-quantity declarations (Rule 6(1)(c)).
_VALID_UNITS = {
    "g", "gm", "gms", "gram", "grams", "kg", "mg",
    "ml", "mls", "l", "ltr", "litre", "litres", "liter", "liters",
    "cm", "mm", "m", "n", "no", "nos", "pcs", "piece", "pieces",
}

# Rules 9-11 without a measurement say what couldn't be measured and why, and
# send it to a person rather than reporting it compliant.
def _unmeasured_font_size(calibration: Optional[Dict[str, Any]]) -> str:
    """Why letter size couldn't be measured, from the barcode calibration."""
    if calibration is None:
        why = ""
    elif calibration.get("usable"):
        why = "no label text could be located in it"
    elif calibration.get("mm_per_px"):
        why = "the barcode's scale looked wrong, so the photo may be too angled"
    elif calibration.get("reference") and calibration.get("barcode_width_px"):
        why = "this barcode type has no standard width, so it can't be used as a ruler"
    else:
        why = "no barcode was found to use as a ruler"
    reason = f": {why}." if why else "."
    return f"Letter size couldn't be measured from this photo{reason} Check the letter size on the pack."


_UNMEASURED_CONTRAST = (
    "Print contrast couldn't be measured from this photo: no declaration text could be "
    "located in it. Check that the declarations are easy to read on the pack."
)
_UNMEASURED_PLACEMENT = (
    "Placement couldn't be measured from this photo: fewer than two declarations could be "
    "located in it. Check that the declarations are grouped on the front of the pack."
)


def _result(
    rule_number: int,
    rule_code: str,
    rule_name: str,
    statutory_reference: str,
    status: str,
    *,
    detected_value: Optional[str] = None,
    required_value: Optional[str] = None,
    failure_reason: Optional[str] = None,
    score: Optional[float] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a RuleCheck-shaped dict ready for persistence."""
    return {
        "rule_number": rule_number,
        "rule_code": rule_code,
        "rule_name": rule_name,
        "statutory_reference": statutory_reference,
        "status": status,
        "score": score if score is not None else (1.0 if status == PASS else 0.0),
        "detected_value": detected_value,
        "required_value": required_value,
        "failure_reason": failure_reason,
        "details_json": json.dumps(details) if details else None,
    }


def _text(fields: Dict[str, Any], *keys: str) -> Optional[str]:
    """First non-empty string among the given keys."""
    for k in keys:
        v = fields.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


# ── Rule 1 — Manufacturer / packer / importer ────────────────────────────
# As with rules 4–6, OCR can read the heading while the name or address beside
# it goes unread; only a label showing no such heading is evidence of absence.
_MANUFACTURER_HEADING = re.compile(
    r"\b(?:manufactured|mfd\.?|packed|marketed|imported)\s*(?:(?:and|&)\s*\w+\s*)?by\b",
    re.IGNORECASE,
)


def check_manufacturer_details(fields: Dict[str, Any]) -> Dict[str, Any]:
    name = _text(fields, "manufacturer_name", "manufacturer", "packer_name")
    address = _text(fields, "manufacturer_address", "packer_address")
    required = "Name and complete address of manufacturer, packer, or importer"

    missing = [part for part, value in (("name", name), ("address", address)) if not value]
    if missing and _heading_on_label(fields, _MANUFACTURER_HEADING):
        return _result(
            1, "MANUFACTURER_DETAILS", "Manufacturer / packer / importer details",
            f"Rule 6(1)(a), {LMPC}", REVIEW,
            detected_value=name or address, required_value=required,
            failure_reason=(
                "A manufacturer or packer heading is on the label, but the "
                f"{' and '.join(missing)} couldn't be read from this photo. "
                "Confirm on the pack."
            ),
        )

    if not name and not address:
        return _result(
            1, "MANUFACTURER_DETAILS", "Manufacturer / packer / importer details",
            f"Rule 6(1)(a), {LMPC}", FAIL,
            required_value=required,
            failure_reason="Neither manufacturer name nor address is declared.",
        )
    if not name:
        return _result(
            1, "MANUFACTURER_DETAILS", "Manufacturer / packer / importer details",
            f"Rule 6(1)(a), {LMPC}", FAIL,
            detected_value=address, required_value=required,
            failure_reason="Address present but manufacturer name is missing.",
        )
    if not address:
        return _result(
            1, "MANUFACTURER_DETAILS", "Manufacturer / packer / importer details",
            f"Rule 6(1)(a), {LMPC}", FAIL,
            detected_value=name, required_value=required,
            failure_reason="Manufacturer named but no address declared.",
        )
    if len(address) < 10:
        return _result(
            1, "MANUFACTURER_DETAILS", "Manufacturer / packer / importer details",
            f"Rule 6(1)(a), {LMPC}", REVIEW,
            detected_value=f"{name} — {address}", required_value=required,
            failure_reason=(
                "Address looks too short to be complete; verify manually."
            ),
        )
    return _result(
        1, "MANUFACTURER_DETAILS", "Manufacturer / packer / importer details",
        f"Rule 6(1)(a), {LMPC}", PASS,
        detected_value=f"{name} — {address}", required_value=required,
    )


# ── Rule 2 — Country of origin ───────────────────────────────────────────
def check_country_of_origin(
    fields: Dict[str, Any], is_imported: Optional[bool] = None
) -> Dict[str, Any]:
    country = _text(fields, "country_of_origin")
    ref = f"Rule 6(1)(aa), {LMPC}"
    required = "Country of origin (mandatory for imported packages)"

    if country:
        return _result(
            2, "COUNTRY_OF_ORIGIN", "Country of origin", ref, PASS,
            detected_value=country, required_value=required,
        )
    if is_imported is False:
        return _result(
            2, "COUNTRY_OF_ORIGIN", "Country of origin", ref, EXEMPT,
            required_value=required,
            failure_reason=None,
            details={"note": "Domestically produced — declaration not required."},
        )
    # Import status unknown: absence is a finding, but not conclusively a
    # violation, so surface it for human judgement.
    return _result(
        2, "COUNTRY_OF_ORIGIN", "Country of origin", ref, REVIEW,
        required_value=required,
        failure_reason=(
            "No country of origin declared. Mandatory only for imported "
            "packages — confirm whether this commodity is imported."
        ),
    )


# ── Rule 3 — Generic / common name ───────────────────────────────────────
# Label boilerplate that OCR sometimes hands over as the product name —
# storage instructions, feedback addresses, cross-sell headings.
_NOT_A_NAME = re.compile(
    r"\b(?:store|storage|keep|container|place|opened|packaged|packed|atmosphere|"
    r"material|feedback|quer(?:y|ies)|write|consumer|customer|manufactured|marketed|"
    r"ingredients?|nutrition(?:al)?|allergen|contains|best\s+before|use\s+by|batch|"
    r"mrp|net\s+(?:qty|quantity|wt|weight)|favourites?|find\s+mor|rda|approx|calculated)",
    re.IGNORECASE,
)
_MAX_NAME_WORDS = 6


def check_generic_name(fields: Dict[str, Any]) -> Dict[str, Any]:
    name = _text(fields, "product_name", "generic_name")
    ref = f"Rule 6(1)(b), {LMPC}"
    required = "Common or generic name of the commodity"

    if not name:
        # One photo shows one panel, and the name is often only on the front.
        if str(fields.get("raw_text") or "").strip():
            return _result(
                3, "GENERIC_NAME", "Common or generic name", ref, REVIEW,
                required_value=required,
                failure_reason=(
                    "No commodity name was identified in the label text read. It may "
                    "be on another panel. Confirm on the pack."
                ),
            )
        return _result(
            3, "GENERIC_NAME", "Common or generic name", ref, FAIL,
            required_value=required,
            failure_reason="No commodity name detected on the label.",
        )
    if len(name) < 3:
        return _result(
            3, "GENERIC_NAME", "Common or generic name", ref, REVIEW,
            detected_value=name, required_value=required,
            failure_reason="Detected name is implausibly short; verify manually.",
        )
    if (
        _NOT_A_NAME.search(name)
        or name.rstrip().endswith(".")
        or len(name.split()) > _MAX_NAME_WORDS
    ):
        return _result(
            3, "GENERIC_NAME", "Common or generic name", ref, REVIEW,
            detected_value=name, required_value=required,
            failure_reason=(
                f"'{name}' reads like other label text, not a commodity name. "
                "Confirm the common or generic name on the pack."
            ),
        )
    return _result(
        3, "GENERIC_NAME", "Common or generic name", ref, PASS,
        detected_value=name, required_value=required,
    )


# ── Rule 4 — Net quantity ────────────────────────────────────────────────
# OCR often returns a label's headings and values as separate columns, so a
# value can go unread while its heading is plainly there. Only a label showing
# neither is evidence that the declaration is missing.
# OCR-tolerant: an accented E ("NĚT"), a letter misread inside QUANTITY
# ("QUAWTITY") and a cut-off end ("QUANTIT") all still count.
_NET_QUANTITY_HEADING = re.compile(
    r"\bn[eéèêëěēėę]t\s*(?:[qo0]u[a-z]{3,6}y?|qty|wt|weight|vol(?:ume)?|contents?)\b",
    re.IGNORECASE,
)
_MRP_HEADING = re.compile(r"\bm\.?\s?r\.?\s?p\b|maximum\s+retail\s+price", re.IGNORECASE)
_MFG_DATE_HEADING = re.compile(
    r"\b(?:m[fg]{1,2}|mfd|pkd|packed)[.,]?\s*(?:date|dt|on)\b"
    r"|date\s+of\s+(?:mfg|manufacture|packing|pkg)|month\s+(?:and|&)\s+year",
    re.IGNORECASE,
)
# "USE BU": the Y of a dot-matrix print misread.
_EXPIRY_HEADING = re.compile(
    r"\buse\s*b[yuv]\b|\bbest\s*before\b|\bexpiry\b|\bexp[.,]?\s*(?:date|dt)\b|\bexpires?\s+on\b",
    re.IGNORECASE,
)


def _heading_on_label(fields: Dict[str, Any], heading: "re.Pattern[str]") -> bool:
    return bool(heading.search(str(fields.get("raw_text") or "")))


# Scan #34 (Amul) showed only "We apprec…" at the wrapper's fold.
_CONSUMER_CARE_HEADING = re.compile(
    r"customer\s*care|consumer\s*(?:care|service)|we\s+apprec|feedback|toll\s*free"
    r"|call\s+(?:us|at)|write\s+to",
    re.IGNORECASE,
)


# Many packs print dates or the price on another surface and say so on the
# label: "BATCH NO., MFD., USE BY: SEE SEAL". One photo can't show both, so
# a missing value is not evidence it was never declared.
_ELSEWHERE_PLACE = (
    r"[\s\S]{0,40}?\bsee\s+(?:the\s+)?"
    r"(seal|lid|top|cap|crimp|bottom|base|back|side|neck|shoulder|carton|pack|pouch)\b"
)
_DATES_ELSEWHERE = re.compile(
    r"(?:mf[dg]|manufactur|pkd|packed|use\s*by|best\s*before|expiry|\bexp\b|batch|\bb\.?\s*no)"
    + _ELSEWHERE_PLACE,
    re.IGNORECASE,
)
_PRICE_ELSEWHERE = re.compile(
    r"(?:\bm\.?\s?r\.?\s?p\b|retail\s+(?:sale\s+)?price)" + _ELSEWHERE_PLACE,
    re.IGNORECASE,
)


def _printed_elsewhere(fields: Dict[str, Any], pattern: "re.Pattern[str]") -> Optional[str]:
    """Where the label says a declaration is printed instead ("seal"), if it does."""
    match = pattern.search(str(fields.get("raw_text") or ""))
    return match.group(1).lower() if match else None


def _elsewhere_reason(what: str, where: str) -> str:
    return (
        f"The label says the {what} is printed on the {where} (\"see {where}\"), which "
        "isn't in this photo. Check it on the pack, or scan that part too."
    )


def check_net_quantity(fields: Dict[str, Any]) -> Dict[str, Any]:
    raw = _text(fields, "net_quantity", "net_quantity_raw")
    ref = f"Rule 6(1)(c), {LMPC}"
    required = "Net quantity in standard units (e.g. 500 g, 1 L, 10 N)"

    if not raw:
        if _heading_on_label(fields, _NET_QUANTITY_HEADING):
            return _result(
                4, "NET_QUANTITY", "Net quantity declaration", ref, REVIEW,
                required_value=required,
                failure_reason=(
                    "A net quantity heading is on the label, but its value couldn't "
                    "be read. Confirm the declared quantity on the pack."
                ),
            )
        return _result(
            4, "NET_QUANTITY", "Net quantity declaration", ref, FAIL,
            required_value=required,
            failure_reason="No net quantity declared.",
        )

    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([A-Za-z]+)\s*$", raw)
    if not m:
        return _result(
            4, "NET_QUANTITY", "Net quantity declaration", ref, FAIL,
            detected_value=raw, required_value=required,
            failure_reason=(
                "Net quantity is not in the form '<number> <unit>'."
            ),
        )

    value, unit = m.group(1), m.group(2).lower()
    if unit not in _VALID_UNITS:
        return _result(
            4, "NET_QUANTITY", "Net quantity declaration", ref, FAIL,
            detected_value=raw, required_value=required,
            failure_reason=(
                f"'{m.group(2)}' is not a permitted unit symbol under Rule 6(1)(c)."
            ),
            details={"parsed_value": value, "parsed_unit": unit},
        )
    if float(value) <= 0:
        return _result(
            4, "NET_QUANTITY", "Net quantity declaration", ref, FAIL,
            detected_value=raw, required_value=required,
            failure_reason="Declared net quantity is zero or negative.",
        )
    return _result(
        4, "NET_QUANTITY", "Net quantity declaration", ref, PASS,
        detected_value=raw, required_value=required,
        details={"parsed_value": value, "parsed_unit": unit},
    )


# ── Rule 5 — MRP ─────────────────────────────────────────────────────────
# Labels print "Inclusive of all taxes" or "Incl. of all taxes", and OCR often
# drops the first letters ("(ncl. of all taxes)"), so anchor on "of all taxes"
# and reject the one wording that means the opposite.
_OF_ALL_TAXES = re.compile(r"of\s+all\s+ta\s?xes", re.IGNORECASE)


def _declares_inclusive_of_taxes(raw_text: str) -> bool:
    for match in _OF_ALL_TAXES.finditer(raw_text):
        lead = raw_text[max(0, match.start() - 15) : match.start()].lower()
        if "excl" not in lead:
            return True
    return False


# Unit sale price, declared beside the MRP: "USP ₹1.29/g", "Unit Sale Price:
# ₹1.25 Per ml", "Rs.0.31 Per g". OCR reads "/g" as "/9". Checked inside Rule 5
# and only to REVIEW: the team has yet to confirm the provision, and OCR
# misreads small print, so a missing or mismatched USP is never a FAIL.
_USP_HEADING = re.compile(r"\busp\b|unit\s+sale\s+price", re.IGNORECASE)
_USP_VALUE = re.compile(
    r"(?:\busp\b|unit\s+sale\s+price)[^\n\d]{0,30}?(\d+(?:\.\d+)?)\s*(?:/|per)\s*(kg|ml|g|l|9)\b",
    re.IGNORECASE,
)
_USP_BY_CURRENCY = re.compile(
    r"(?:₹|\brs\.?)\s*(\d+(?:\.\d+)?)\s*(?:/|per)\s*(kg|ml|g|l|9)\b", re.IGNORECASE
)
_UNIT_BASE = {"g": ("g", 1.0), "gm": ("g", 1.0), "gms": ("g", 1.0), "kg": ("g", 1000.0),
              "ml": ("ml", 1.0), "l": ("ml", 1000.0), "ltr": ("ml", 1000.0)}


def _unit_sale_price(fields: Dict[str, Any], mrp: float) -> Tuple[Optional[str], Dict[str, Any]]:
    """(problem, details): None when the USP is printed and agrees with MRP ÷ quantity."""
    raw_text = str(fields.get("raw_text") or "")
    match = _USP_VALUE.search(raw_text) or _USP_BY_CURRENCY.search(raw_text)
    if not match:
        why = ("A unit sale price heading is on the label, but its value couldn't be read."
               if _USP_HEADING.search(raw_text)
               else "No unit sale price (₹ per g / ml) was found beside the MRP.")
        return why + " Confirm it on the pack.", {"usp_found": False}

    usp = float(match.group(1))
    usp_unit = "g" if match.group(2).lower() == "9" else match.group(2).lower()
    details: Dict[str, Any] = {"usp_found": True, "usp": usp, "usp_unit": usp_unit}
    qty = re.match(r"\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)", str(fields.get("net_quantity") or ""))
    if not qty or qty.group(2).lower() not in _UNIT_BASE or usp_unit not in _UNIT_BASE:
        return None, details  # printed; nothing to check it against
    qty_base, qty_factor = _UNIT_BASE[qty.group(2).lower()]
    usp_base, usp_factor = _UNIT_BASE[usp_unit]
    if qty_base != usp_base:
        return None, details
    quantity = float(qty.group(1)) * qty_factor / usp_factor
    if quantity <= 0:
        return None, details
    expected = mrp / quantity
    details["usp_expected"] = round(expected, 4)
    # A printed USP is rounded to paise.
    if abs(usp - expected) <= max(0.01, expected * 0.05):
        return None, details
    return (
        f"The unit sale price reads ₹{usp:g}/{usp_unit}, but MRP ÷ quantity gives "
        f"₹{expected:.2f}/{usp_unit}. Printed digits are often misread, so confirm it "
        "on the pack."
    ), details


def check_mrp(fields: Dict[str, Any]) -> Dict[str, Any]:
    raw = fields.get("mrp") if fields.get("mrp") is not None else _text(fields, "mrp_raw")
    ref = f"Rule 6(1)(e), {LMPC}"
    required = "MRP Rs. <amount> inclusive of all taxes"

    if raw is None or str(raw).strip() == "":
        where = _printed_elsewhere(fields, _PRICE_ELSEWHERE)
        if where:
            return _result(
                5, "MRP_DECLARATION", "Retail sale price (MRP)", ref, REVIEW,
                required_value=required,
                failure_reason=_elsewhere_reason("price", where),
                details={"printed_elsewhere": where},
            )
        if _heading_on_label(fields, _MRP_HEADING):
            return _result(
                5, "MRP_DECLARATION", "Retail sale price (MRP)", ref, REVIEW,
                required_value=required,
                failure_reason=(
                    "An MRP heading is on the label, but its amount couldn't be read. "
                    "Confirm the price on the pack."
                ),
            )
        return _result(
            5, "MRP_DECLARATION", "Retail sale price (MRP)", ref, FAIL,
            required_value=required,
            failure_reason="No maximum retail price declared.",
        )

    m = re.search(r"(\d+(?:\.\d{1,2})?)", str(raw).replace(",", ""))
    if not m:
        return _result(
            5, "MRP_DECLARATION", "Retail sale price (MRP)", ref, FAIL,
            detected_value=str(raw), required_value=required,
            failure_reason="MRP present but no numeric amount could be read.",
        )

    amount = float(m.group(1))
    if amount <= 0:
        return _result(
            5, "MRP_DECLARATION", "Retail sale price (MRP)", ref, FAIL,
            detected_value=str(raw), required_value=required,
            failure_reason="Declared MRP is zero or negative.",
        )

    # The "inclusive of all taxes" wording is mandatory, but OCR frequently
    # misses small print, so its absence is REVIEW rather than FAIL.
    raw_text = str(fields.get("raw_text") or "")
    has_inclusive = _declares_inclusive_of_taxes(raw_text)
    usp_problem, usp_details = _unit_sale_price(fields, amount)
    details = {"amount": amount, "inclusive_text_found": has_inclusive, **usp_details}
    required = "MRP Rs. <amount> inclusive of all taxes, with the unit sale price"

    problems = []
    if not has_inclusive:
        problems.append(
            "Amount found but the mandatory 'inclusive of all taxes' "
            "wording was not detected. Verify on the physical package."
        )
    if usp_problem:
        problems.append(usp_problem)
    if problems:
        return _result(
            5, "MRP_DECLARATION", "Retail sale price (MRP)", ref, REVIEW,
            detected_value=f"Rs. {amount}", required_value=required,
            failure_reason=" ".join(problems),
            details=details,
        )
    usp_text = f", USP ₹{usp_details['usp']:g}/{usp_details['usp_unit']}"
    return _result(
        5, "MRP_DECLARATION", "Retail sale price (MRP)", ref, PASS,
        detected_value=f"Rs. {amount} inclusive of all taxes{usp_text}",
        required_value=required,
        details=details,
    )


# ── Date helpers ─────────────────────────────────────────────────────────
_DATE_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
    "%m/%Y", "%m-%Y", "%b %Y", "%B %Y",
    "%d %b %Y", "%d %B %Y",
    # A month abbreviation between separators ("11/JUN/26", Amul).
    "%d/%b/%y", "%d/%b/%Y", "%d-%b-%y", "%d-%b-%Y", "%d.%b.%y", "%d.%b.%Y", "%d %b %y",
    # ...with the separator before the year unread ("11/JUN25", scan #35).
    "%d/%b%y", "%d/%b%Y", "%d-%b%y", "%d.%b%y",
)


def _parse_date(raw: str) -> Optional[datetime]:
    s = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ── Rule 6 — Month / year of manufacture ─────────────────────────────────
def check_mfg_date(fields: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    raw = _text(fields, "mfg_date", "mfg_date_raw")
    ref = f"Rule 6(1)(d), {LMPC}"
    required = "Month and year of manufacture, packing, or import"
    now = now or datetime.now()

    if not raw:
        where = _printed_elsewhere(fields, _DATES_ELSEWHERE)
        if where:
            return _result(
                6, "MFG_DATE", "Month and year of manufacture / packing", ref, REVIEW,
                required_value=required,
                failure_reason=_elsewhere_reason("manufacture date", where),
                details={"printed_elsewhere": where},
            )
        if _heading_on_label(fields, _MFG_DATE_HEADING):
            return _result(
                6, "MFG_DATE", "Month and year of manufacture / packing", ref, REVIEW,
                required_value=required,
                failure_reason=(
                    "A manufacture/packing date heading is on the label, but the date "
                    "couldn't be read. Confirm it on the pack."
                ),
            )
        return _result(
            6, "MFG_DATE", "Month and year of manufacture / packing", ref, FAIL,
            required_value=required,
            failure_reason="No manufacture or packing date declared.",
        )

    parsed = _parse_date(raw)
    if parsed is None:
        return _result(
            6, "MFG_DATE", "Month and year of manufacture / packing", ref, REVIEW,
            detected_value=raw, required_value=required,
            failure_reason="Date present but not in a recognised format.",
        )
    if parsed > now:
        # OCR misreads printed digits: "Pkd.11/JUN/26" read as "…/28" (scan
        # #34), a use-by date taken as the manufacture date (#29). A future
        # date is more often a misread than a pre-dated pack, so a person checks.
        return _result(
            6, "MFG_DATE", "Month and year of manufacture / packing", ref, REVIEW,
            detected_value=raw, required_value=required,
            failure_reason=(
                "The manufacture date reads as a future date. Printed digits are "
                "often misread from a photo, so confirm the date on the pack."
            ),
            details={"parsed": parsed.isoformat()},
        )
    return _result(
        6, "MFG_DATE", "Month and year of manufacture / packing", ref, PASS,
        detected_value=raw, required_value=required,
        details={"parsed": parsed.isoformat()},
    )


# ── Rule 7 — Best before / expiry ────────────────────────────────────────
def check_expiry_date(fields: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    raw = _text(fields, "expiry_date", "expiry_date_raw")
    ref = f"Rule 6(1)(da), {LMPC}"
    required = "Best before / use by date for commodities with limited shelf life"
    now = now or datetime.now()

    if not raw:
        where = _printed_elsewhere(fields, _DATES_ELSEWHERE)
        if where:
            return _result(
                7, "EXPIRY_DATE", "Best before / use by date", ref, REVIEW,
                required_value=required,
                failure_reason=_elsewhere_reason("use-by date", where),
                details={"printed_elsewhere": where},
            )
        if _heading_on_label(fields, _EXPIRY_HEADING):
            return _result(
                7, "EXPIRY_DATE", "Best before / use by date", ref, REVIEW,
                required_value=required,
                failure_reason=(
                    "A use-by or best-before heading is on the label, but the date "
                    "couldn't be read. Confirm it on the pack."
                ),
            )
        # Not every commodity needs one (e.g. hardware), so this is REVIEW.
        return _result(
            7, "EXPIRY_DATE", "Best before / use by date", ref, REVIEW,
            required_value=required,
            failure_reason=(
                "No expiry date declared. Mandatory only for commodities with "
                "a limited shelf life — confirm the commodity type."
            ),
        )

    parsed = _parse_date(raw)
    if parsed is None:
        return _result(
            7, "EXPIRY_DATE", "Best before / use by date", ref, REVIEW,
            detected_value=raw, required_value=required,
            failure_reason="Date present but not in a recognised format.",
        )
    # An expiry that isn't after the manufacture date can't be right: one of
    # the two was misread or mistyped. Scan #35 had both typed as 11/06/26 and
    # was reported expired, which became a GO notice. A person checks the pack.
    mfg_raw = _text(fields, "mfg_date", "mfg_date_raw")
    made = _parse_date(mfg_raw) if mfg_raw else None
    if made is not None and parsed <= made:
        return _result(
            7, "EXPIRY_DATE", "Best before / use by date", ref, REVIEW,
            detected_value=raw, required_value=required,
            failure_reason=(
                f"The expiry date ({raw}) is not after the manufacture date ({mfg_raw}), "
                "so one of the two was misread or mistyped. Check both dates on the pack."
            ),
            details={"parsed": parsed.isoformat(), "mfg_parsed": made.isoformat()},
        )
    if parsed < now:
        return _result(
            7, "EXPIRY_DATE", "Best before / use by date", ref, FAIL,
            detected_value=raw, required_value=required,
            failure_reason=(
                f"Product expired on {parsed.date().isoformat()} — "
                "offering an expired commodity for sale is a violation."
            ),
            details={"parsed": parsed.isoformat(), "expired": True},
        )
    return _result(
        7, "EXPIRY_DATE", "Best before / use by date", ref, PASS,
        detected_value=raw, required_value=required,
        details={"parsed": parsed.isoformat(), "expired": False},
    )


# ── Rule 8 — Consumer care ───────────────────────────────────────────────
def check_consumer_care(fields: Dict[str, Any]) -> Dict[str, Any]:
    phone = _text(fields, "consumer_care_phone", "consumerCarePhone")
    email = _text(fields, "consumer_care_email", "consumerCareEmail")
    ref = f"Rule 6(2), {LMPC}"
    required = "Consumer care name with telephone number and/or email address"

    if not phone and not email:
        if _heading_on_label(fields, _CONSUMER_CARE_HEADING):
            return _result(
                8, "CONSUMER_CARE", "Consumer care contact details", ref, REVIEW,
                required_value=required,
                failure_reason=(
                    "A consumer care heading is on the label, but no phone number or "
                    "email could be read from this photo. Confirm it on the pack."
                ),
            )
        return _result(
            8, "CONSUMER_CARE", "Consumer care contact details", ref, FAIL,
            required_value=required,
            failure_reason="No consumer care phone number or email declared.",
        )

    detected = ", ".join(x for x in (phone, email) if x)
    # Count digits, not a run: "1800 258 3333" is spaced (scan #35).
    if phone and len(re.sub(r"\D", "", phone)) < 6:
        return _result(
            8, "CONSUMER_CARE", "Consumer care contact details", ref, REVIEW,
            detected_value=detected, required_value=required,
            failure_reason="Detected phone number looks too short to be valid.",
        )
    return _result(
        8, "CONSUMER_CARE", "Consumer care contact details", ref, PASS,
        detected_value=detected, required_value=required,
        details={"has_phone": bool(phone), "has_email": bool(email)},
    )


# ── Rules 9-11 — CV-dependent, deliberately REVIEW ───────────────────────
def check_font_size(
    fields: Dict[str, Any],
    measurement: Optional[Dict[str, Any]] = None,
    calibration: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ref = f"Rule 7(2) and Table I, {LMPC}"
    required = "Minimum letter height per principal display panel area"
    if measurement and measurement.get("min_height_mm") is not None:
        h = float(measurement["min_height_mm"])
        threshold = float(measurement.get("threshold_mm", 1.0))
        if h >= threshold:
            return _result(
                9, "FONT_SIZE", "Minimum font size of declarations", ref, PASS,
                detected_value=f"{h:.2f} mm", required_value=f">= {threshold:.2f} mm",
                details=measurement,
            )

        # A photo only estimates letter height: the barcode may be printed at
        # 80-200% of its standard size, and perspective and the cap-height
        # approximation add error. So a reading under the minimum is sent to a
        # person to measure on the pack, never reported as a breach.
        if measurement.get("inconclusive"):
            reason = (
                f"Smallest declaration measures {h:.2f} mm against a "
                f"{threshold:.2f} mm minimum — within measurement "
                "tolerance, so confirm against the physical pack."
            )
        else:
            reason = (
                f"Smallest declaration ('{measurement.get('smallest_text', '')}') "
                f"reads {h:.2f} mm, under the {threshold:.2f} mm minimum. A photo can "
                "only estimate letter size (the barcode may be printed larger or "
                "smaller than standard), so measure it on the pack before treating "
                "it as a breach."
            )
        return _result(
            9, "FONT_SIZE", "Minimum font size of declarations", ref, REVIEW,
            detected_value=f"{h:.2f} mm", required_value=f">= {threshold:.2f} mm",
            failure_reason=reason,
            details=measurement,
        )
    return _result(
        9, "FONT_SIZE", "Minimum font size of declarations", ref, REVIEW,
        required_value=required, failure_reason=_unmeasured_font_size(calibration),
        details={"requires_cv": True, "calibration_available": False},
    )


def check_readability(fields: Dict[str, Any], measurement: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ref = f"Rule 9(1), {LMPC}"
    required = "Legible, prominent text contrasting conspicuously with background"
    if measurement and measurement.get("contrast_ratio") is not None:
        r = float(measurement["contrast_ratio"])
        threshold = float(measurement.get("threshold", 4.5))

        # A phone photo understates print contrast, so a low reading goes to a
        # human unless the whole label is faint beyond that error.
        if measurement.get("inconclusive"):
            return _result(
                10, "READABILITY", "Legibility and contrast of declarations", ref, REVIEW,
                detected_value=f"{r:.2f}:1", required_value=f">= {threshold:.1f}:1",
                failure_reason=(
                    f"Lowest measured contrast is {r:.2f}:1, under {threshold:.1f}:1, but "
                    "phone photos understate print contrast (glare, exposure), so this "
                    "is not proof of a breach. Confirm legibility on the physical pack."
                ),
                details=measurement,
            )

        status = PASS if r >= threshold else FAIL
        median = measurement.get("median_contrast_ratio")
        if status == PASS:
            reason = None
        elif median is None:
            reason = f"Contrast ratio {r:.2f}:1 is below the {threshold:.1f}:1 minimum."
        else:
            reason = (
                f"Declarations measure a median {float(median):.2f}:1 (lowest {r:.2f}:1), "
                "too faint to be explained by photo error."
            )
        return _result(
            10, "READABILITY", "Legibility and contrast of declarations", ref, status,
            detected_value=f"{r:.2f}:1", required_value=f">= {threshold:.1f}:1",
            failure_reason=reason,
            details=measurement,
        )
    return _result(
        10, "READABILITY", "Legibility and contrast of declarations", ref, REVIEW,
        required_value=required, failure_reason=_UNMEASURED_CONTRAST,
        details={"requires_cv": True, "calibration_available": False},
    )


def check_placement(fields: Dict[str, Any], measurement: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ref = f"Rule 8(1), {LMPC}"
    required = "Mandatory declarations grouped on the principal display panel"
    if measurement and measurement.get("on_principal_panel") is not None:
        ok = bool(measurement["on_principal_panel"])
        return _result(
            11, "PLACEMENT", "Placement on principal display panel", ref,
            PASS if ok else FAIL,
            detected_value="grouped on PDP" if ok else "scattered / off-panel",
            required_value=required,
            failure_reason=None if ok else (
                "Mandatory declarations are not grouped on the principal "
                "display panel."
            ),
            details=measurement,
        )
    return _result(
        11, "PLACEMENT", "Placement on principal display panel", ref, REVIEW,
        required_value=required, failure_reason=_UNMEASURED_PLACEMENT,
        details={"requires_cv": True, "calibration_available": False},
    )


# ── Rule 12 — LMPC registration ──────────────────────────────────────────
def check_lmpc_registration(
    fields: Dict[str, Any], is_imported: Optional[bool] = None
) -> Dict[str, Any]:
    lmpc = _text(fields, "lmpc_number", "lmpc_registration")
    ref = f"Rule 27, {LMPC}"
    required = "LMPC registration number of manufacturer / packer / importer"

    if lmpc:
        # Format varies by state; only sanity-check that it carries digits.
        if not re.search(r"\d{3,}", lmpc):
            return _result(
                12, "LMPC_REGISTRATION", "LMPC registration number", ref, REVIEW,
                detected_value=lmpc, required_value=required,
                failure_reason="Value present but does not look like a registration number.",
            )
        return _result(
            12, "LMPC_REGISTRATION", "LMPC registration number", ref, PASS,
            detected_value=lmpc, required_value=required,
        )

    if is_imported:
        return _result(
            12, "LMPC_REGISTRATION", "LMPC registration number", ref, FAIL,
            required_value=required,
            failure_reason=(
                "Imported package carries no LMPC registration number, which "
                "Rule 27 requires of importers."
            ),
        )
    return _result(
        12, "LMPC_REGISTRATION", "LMPC registration number", ref, REVIEW,
        required_value=required,
        failure_reason=(
            "No LMPC registration number detected. Required of packers and "
            "importers — confirm the responsible party's category."
        ),
    )


# ── Rule 13 — GSTIN format & checksum ────────────────────────────────────
def check_gstin_format(gstin: Optional[str]) -> Dict[str, Any]:
    """Rule 13 — GSTIN format & checksum validation.

    NOTE: Format/checksum only. This does NOT verify whether the GSTIN is
    live, active, cancelled, or issued to the manufacturer claiming it. A
    live registry lookup requires the GST Council API (out of scope).
    """
    required = (
        "15-char GSTIN — 2-digit state code, valid PAN, entity char, 'Z', "
        "valid Mod-36 checksum. Format/checksum only; not a live-registry check."
    )

    if not gstin or not str(gstin).strip():
        return _result(
            13, "GSTIN_FORMAT", "GSTIN format & checksum", CGST_RULE_46, EXEMPT,
            required_value=required, score=None,
            details={"note": "No GSTIN captured from label — skipped."},
        )

    # Something that isn't even GSTIN-shaped is most likely another printed
    # number (e.g. a packaging registration), not evidence of a bad GSTIN.
    compact = re.sub(r"[\s\-./]", "", str(gstin)).upper()
    if len(compact) != 15 or not compact.isalnum():
        return _result(
            13, "GSTIN_FORMAT", "GSTIN format & checksum", CGST_RULE_46, REVIEW,
            detected_value=str(gstin), required_value=required,
            failure_reason=(
                f"'{gstin}' doesn't have a GSTIN's shape (15 letters and digits), so "
                "it is likely another registration number. Confirm whether the label "
                "declares a GSTIN."
            ),
            details={"compact": compact, "live_registry_verified": False},
        )

    verdict = validate_gstin_verbose(compact)
    if verdict["valid"]:
        return _result(
            13, "GSTIN_FORMAT", "GSTIN format & checksum", CGST_RULE_46, PASS,
            detected_value=str(gstin), required_value=required,
            details={
                "normalized": verdict["normalized"],
                "checksum_ok": True,
                "live_registry_verified": False,
            },
        )
    return _result(
        13, "GSTIN_FORMAT", "GSTIN format & checksum", CGST_RULE_46, FAIL,
        detected_value=str(gstin), required_value=required,
        failure_reason=verdict["reason"],
        details={
            "normalized": verdict["normalized"],
            "checksum_expected": verdict["checksum_expected"],
            "live_registry_verified": False,
        },
    )


# ── Orchestrator ─────────────────────────────────────────────────────────
def evaluate_all(
    fields: Dict[str, Any],
    *,
    is_imported: Optional[bool] = None,
    cv_measurements: Optional[Dict[str, Dict[str, Any]]] = None,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Run all 13 checks and return RuleCheck-shaped dicts in rule order.

    Args:
        fields: OCR-extracted label fields. Accepts both the backend's
            snake_case keys and the mobile app's camelCase variants.
        is_imported: whether the commodity is imported. Affects rules 2 and
            12; when None those return REVIEW instead of guessing.
        cv_measurements: optional {"font_size": {...}, "readability": {...},
            "placement": {...}} from the calibration pipeline. Absent
            measurements make rules 9-11 return REVIEW.
        now: injectable clock for deterministic date tests.

    Returns:
        List of 13 dicts, ordered by rule_number.
    """
    cv = cv_measurements or {}
    return [
        check_manufacturer_details(fields),
        check_country_of_origin(fields, is_imported=is_imported),
        check_generic_name(fields),
        check_net_quantity(fields),
        check_mrp(fields),
        check_mfg_date(fields, now=now),
        check_expiry_date(fields, now=now),
        check_consumer_care(fields),
        check_font_size(fields, cv.get("font_size"), calibration=cv.get("calibration")),
        check_readability(fields, cv.get("readability")),
        check_placement(fields, cv.get("placement")),
        check_lmpc_registration(fields, is_imported=is_imported),
        check_gstin_format(fields.get("gst_number") or fields.get("gstNumber")),
    ]


def summarize(results: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count outcomes — handy for the dashboard and for tests."""
    counts = {PASS: 0, FAIL: 0, REVIEW: 0, EXEMPT: 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts
