"""
FieldProof — Authenticity / Forgery-Detection Service

Given a scanned barcode plus OCR-extracted label fields, compare them
against the trusted ProductRegistry to decide whether the packaging is
authentic, forged / tampered, or simply unknown.

Zero FastAPI dependency — plain functions callable from any router,
worker, or unit test. The caller passes an SQLAlchemy Session.

Statuses returned:
    "verified_authentic"    nothing on the label contradicts the registry
    "tampered_suspected"    barcode found but price, quantity, a licence
                            number, the veg mark or the manufacturer
                            contradicts the registry
    "unverified_product"    barcode not present in the registry

Product name and address are free text that OCR often misreads, so a
difference there is recorded in `text_divergences`, not treated as tampering.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.product_registry import ProductRegistry

# ── Tolerances ─────────────────────────────────────────────────────────────
_MRP_ABS_TOLERANCE = 0.01           # allow ±1 paisa rounding
_MRP_REL_TOLERANCE = 0.005          # allow ±0.5% for OCR reading noise
_TEXT_SIMILARITY_THRESHOLD = 0.85   # SequenceMatcher ratio for fuzzy matches
_WORD_SIMILARITY_THRESHOLD = 0.8    # per-word ratio when matching OCR'd names
# Genuine labels vary these freely ("Pvt. Ltd." / "Private Limited").
_LEGAL_FORM_WORDS = frozenset({
    "private", "pvt", "limited", "ltd", "llp", "company",
    "corporation", "corp", "inc", "and", "the",
})

# Status constants
STATUS_AUTHENTIC = "verified_authentic"
STATUS_TAMPERED = "tampered_suspected"
STATUS_UNVERIFIED = "unverified_product"


@dataclass
class FieldMismatch:
    """A single field that failed the registry cross-check."""
    field: str
    expected: Optional[str]
    detected: Optional[str]
    note: Optional[str] = None


@dataclass
class AuthenticityResult:
    """Structured verdict returned by verify_against_registry()."""
    status: str
    barcode: str
    registry_id: Optional[int] = None
    matched_product_name: Optional[str] = None
    mismatches: List[FieldMismatch] = field(default_factory=list)
    text_divergences: List[FieldMismatch] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "barcode": self.barcode,
            "registry_id": self.registry_id,
            "matched_product_name": self.matched_product_name,
            "mismatches": [asdict(m) for m in self.mismatches],
            "text_divergences": [asdict(m) for m in self.text_divergences],
            "message": self.message,
        }


# ── Normalization helpers ─────────────────────────────────────────────────
def _norm_text(v: Optional[str]) -> str:
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip().casefold()


def _text_matches(expected: Optional[str], detected: Optional[str]) -> bool:
    e, d = _norm_text(expected), _norm_text(detected)
    if not e and not d:
        return True
    if not e or not d:
        return False
    if e == d or e in d or d in e:
        return True
    return SequenceMatcher(None, e, d).ratio() >= _TEXT_SIMILARITY_THRESHOLD


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _distinctive_words(value: Optional[str]) -> List[str]:
    text = _norm_text(value).replace("'", "").replace("’", "")
    return [
        w for w in re.findall(r"[0-9a-z]+", text)
        if len(w) >= 3 and w not in _LEGAL_FORM_WORDS
    ]


def _word_overlap(expected: Optional[str], detected: Optional[str]) -> Optional[float]:
    """Share of the registry value's distinctive words found (fuzzily) in the label text."""
    wanted, seen = _distinctive_words(expected), _distinctive_words(detected)
    if not wanted or not seen:
        return None
    hits = sum(
        1 for w in wanted
        if any(SequenceMatcher(None, w, s).ratio() >= _WORD_SIMILARITY_THRESHOLD for s in seen)
    )
    return hits / len(wanted)


# Label text that can't be a company name: footnotes and nutrition lines OCR
# places after a "MARKETED BY:" heading ("size is 20g; 20 Serving… %RDA").
_NOT_A_COMPANY_NAME = re.compile(r"[%#;@]|\d+(?:\.\d+)?\s*(?:g|kg|mg|ml|kcal)\b", re.IGNORECASE)
_MAX_COMPANY_NAME_WORDS = 8


def _reads_like_company_name(value: Optional[str]) -> bool:
    text = str(value or "")
    return not _NOT_A_COMPANY_NAME.search(text) and len(text.split()) <= _MAX_COMPANY_NAME_WORDS


def _parse_quantity(raw: Optional[str]) -> Optional[tuple[float, str]]:
    """Return (value, canonical_unit) or None. Canonicalizes g/kg and ml/l."""
    if not raw:
        return None
    m = re.match(r"\s*([\d]+(?:\.\d+)?)\s*([a-zA-Z]+)?\s*", str(raw))
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    unit = (m.group(2) or "").strip().lower()
    if unit in ("kg",):
        value, unit = value * 1000, "g"
    elif unit in ("l", "ltr", "litre", "liter"):
        value, unit = value * 1000, "ml"
    elif unit in ("gm", "gms", "grams", "gram"):
        unit = "g"
    elif unit in ("mls", "millilitre", "milliliter"):
        unit = "ml"
    return value, unit


def _quantity_matches(expected: Optional[str], detected: Optional[str]) -> bool:
    e, d = _parse_quantity(expected), _parse_quantity(detected)
    if e is None and d is None:
        return True
    if e is None or d is None:
        return False
    ev, eu = e
    dv, du = d
    if eu and du and eu != du:
        return False
    return abs(ev - dv) <= max(_MRP_ABS_TOLERANCE, ev * _MRP_REL_TOLERANCE)


def _parse_mrp(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    m = re.search(r"(\d+(?:\.\d+)?)", str(raw).replace(",", ""))
    return float(m.group(1)) if m else None


def _mrp_matches(expected: Optional[float], detected: Any) -> bool:
    d = _parse_mrp(detected)
    if expected is None and d is None:
        return True
    if expected is None or d is None:
        return False
    return abs(expected - d) <= max(_MRP_ABS_TOLERANCE, expected * _MRP_REL_TOLERANCE)


def _license_matches(expected: Optional[str], detected: Optional[str]) -> bool:
    """FSSAI / GST codes must match exactly (ignoring whitespace + case)."""
    e = re.sub(r"\s+", "", (expected or "")).upper()
    d = re.sub(r"\s+", "", (detected or "")).upper()
    if not e and not d:
        return True
    if not e or not d:
        return False
    return e == d


# Every FSSAI licence is 14 digits; any other length is an OCR misread.
_FSSAI_LICENCE = re.compile(r"\d{14}")


def _registered_fssai_licences(registered: ProductRegistry) -> List[str]:
    """The registered licence plus any others printed on the same genuine pack."""
    extra = (registered.additional_fssai_license_numbers or "").split(",")
    return [
        re.sub(r"\s+", "", licence)
        for licence in [registered.fssai_license_number or "", *extra]
        if licence.strip()
    ]


def _fssai_matches(expected: str, detected: Optional[str]) -> bool:
    return re.sub(r"\s+", "", str(detected or "")) in expected.split(", ")


def _one_digit_from(detected: str, registered: List[str]) -> Optional[str]:
    """The registered licence a read differs from in exactly one digit, if any.

    OCR slips a single digit on small print (scan #37 read the Ob & Gob tub's
    ...476 as ...478); a different licence differs in more than one place.
    """
    for licence in registered:
        if len(licence) == len(detected) and sum(a != b for a, b in zip(licence, detected)) == 1:
            return licence
    return None


# ── Public API ────────────────────────────────────────────────────────────
def lookup_registry(db: Session, barcode: str) -> Optional[ProductRegistry]:
    """Return the ProductRegistry row for a barcode, or None."""
    if not barcode:
        return None
    normalized = re.sub(r"\s+", "", str(barcode))
    return db.query(ProductRegistry).filter(ProductRegistry.barcode == normalized).first()


def verify_against_registry(
    db: Session,
    barcode: str,
    detected_fields: Dict[str, Any],
    fssai_mark: Optional[str] = None,
) -> AuthenticityResult:
    """
    Compare an OCR-extracted label against the trusted ProductRegistry.

    Args:
        db: active SQLAlchemy session.
        barcode: GTIN/EAN/UPC scanned from the package.
        detected_fields: dict of OCR-read values. Recognized keys:
            product_name, manufacturer_name, manufacturer_address,
            mrp, net_quantity, fssai_license_number, gst_number.
            Unknown keys are ignored so callers can pass a superset.
        fssai_mark: optional result from fssai_mark_service — one of
            "vegetarian", "non_vegetarian", "not_found". When provided
            it is cross-checked against ProductRegistry.is_vegetarian
            and any mismatch is treated as a tampering signal.

    Returns:
        AuthenticityResult with .status and any field mismatches recorded.
    """
    result = AuthenticityResult(status=STATUS_UNVERIFIED, barcode=barcode or "")

    registered = lookup_registry(db, barcode)
    if registered is None:
        result.message = (
            "Barcode not found in reference registry — product could not be verified."
        )
        return result

    result.registry_id = registered.id
    result.matched_product_name = registered.product_name

    exact_checks = [
        ("mrp", registered.mrp, detected_fields.get("mrp"), _mrp_matches),
        ("net_quantity", registered.net_quantity,
         detected_fields.get("net_quantity"), _quantity_matches),
        # A pack can print more than one licence (brand owner and unit).
        ("fssai_license_number", ", ".join(_registered_fssai_licences(registered)) or None,
         detected_fields.get("fssai_license_number"), _fssai_matches),
        ("gst_number", registered.gst_number,
         detected_fields.get("gst_number"), _license_matches),
    ]
    compared: List[str] = []

    for field_name, expected, detected, comparator in exact_checks:
        # A missing detected value is not a mismatch — the OCR simply didn't
        # read it. Tampering is a *contradiction* between what's on the label
        # and what the registry has, not silence on the label side.
        if _blank(detected) or expected in (None, "", 0):
            continue
        if field_name == "fssai_license_number" and not _FSSAI_LICENCE.fullmatch(
            re.sub(r"\s+", "", str(detected))
        ):
            result.text_divergences.append(FieldMismatch(
                field=field_name, expected=str(expected), detected=str(detected),
                note=(
                    "Not a 14-digit FSSAI licence number, likely an OCR misread; "
                    "not treated as tampering."
                ),
            ))
            continue
        if field_name == "fssai_license_number" and not comparator(expected, detected):
            near = _one_digit_from(re.sub(r"\s+", "", str(detected)), str(expected).split(", "))
            if near is not None:
                result.text_divergences.append(FieldMismatch(
                    field=field_name, expected=str(expected), detected=str(detected),
                    note=(
                        f"One digit differs from the registered licence {near}, likely "
                        "an OCR misread; not treated as tampering."
                    ),
                ))
                continue
        # A price below the registered MRP harms no buyer: Rule 6(3) lets a
        # sticker lower the MRP, and a covered or cut-off price reads short
        # ("Rs.10" of "Rs.109.00"). Only a higher price is an anomaly.
        if field_name == "mrp" and not comparator(expected, detected):
            price = _parse_mrp(detected)
            if price is not None and price < float(expected):
                result.text_divergences.append(FieldMismatch(
                    field=field_name, expected=str(expected), detected=str(detected),
                    note=(
                        "Lower than the registered MRP: a sticker lowering the MRP is allowed "
                        "under Rule 6(3), or the price was misread. Not treated as tampering."
                    ),
                ))
                continue
        compared.append(field_name)
        if not comparator(expected, detected):
            result.mismatches.append(FieldMismatch(
                field=field_name,
                expected=str(expected),
                detected=str(detected),
                note=(
                    "Higher than the registered MRP. Rule 6(3) forbids altering a declaration, "
                    "except with a sticker that lowers the MRP."
                    if field_name == "mrp"
                    else "Detected value diverges from registry value beyond tolerance."
                ),
            ))

    text_checks = [
        ("product_name", registered.product_name, detected_fields.get("product_name")),
        ("manufacturer_name", registered.manufacturer_name,
         detected_fields.get("manufacturer_name")),
        ("manufacturer_address", registered.manufacturer_address,
         detected_fields.get("manufacturer_address")),
    ]
    for field_name, expected, detected in text_checks:
        if _blank(detected) or not expected:
            continue
        overlap = _word_overlap(expected, detected)
        if overlap == 1.0 or _text_matches(expected, detected):
            continue
        entry = FieldMismatch(field=field_name, expected=str(expected), detected=str(detected))
        # A manufacturer sharing none of the registered name's words is a
        # contradiction; anything short of that is indistinguishable from an
        # OCR misread. So is text that isn't a company name at all.
        if field_name != "manufacturer_name" or overlap != 0.0:
            entry.note = "Reads differently from the registry; not treated as tampering."
            result.text_divergences.append(entry)
        elif not _reads_like_company_name(detected):
            entry.note = (
                "Doesn't read like a company name, likely other label text; "
                "not treated as tampering."
            )
            result.text_divergences.append(entry)
        else:
            entry.note = "Shares no words with the registered manufacturer name."
            result.mismatches.append(entry)

    if fssai_mark and fssai_mark != "not_found":
        compared.append("fssai_veg_mark")
        expected_mark = "vegetarian" if registered.is_vegetarian else "non_vegetarian"
        if fssai_mark != expected_mark:
            result.mismatches.append(FieldMismatch(
                field="fssai_veg_mark",
                expected=expected_mark,
                detected=fssai_mark,
                note="FSSAI veg/non-veg dot color does not match registry classification.",
            ))

    if result.mismatches:
        result.status = STATUS_TAMPERED
        result.message = (
            f"Barcode matched registry entry #{registered.id} but "
            f"{len(result.mismatches)} field(s) contradict it — tampering suspected."
        )
        return result

    result.status = STATUS_AUTHENTIC
    if compared:
        result.message = f"Agrees with the registry on: {', '.join(compared)}."
    else:
        result.message = (
            "Barcode matched the registry, but no price, quantity or licence "
            "number could be read to compare."
        )
    if result.text_divergences:
        fields = ", ".join(d.field for d in result.text_divergences)
        result.message += (
            f" Read differently from the registry, likely OCR, not treated as tampering: {fields}."
        )
    return result
