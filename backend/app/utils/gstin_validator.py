"""
FieldProof — GSTIN format & checksum validator.

Validates the 15-character Indian GSTIN structure and its Mod-36 checksum
digit. NOTE: This is a *format/checksum* check only — it does NOT confirm
the GSTIN is live, active, or issued to the claimed entity. A live-lookup
against the GST Council API is out of scope for this prototype (no free
public API); flag any downstream use accordingly.

Structure (15 chars):
    ┌─────┬──────────┬─┬─┬─┐
    │ SS  │  PAN(10) │E│Z│C│
    └─────┴──────────┴─┴─┴─┘
    SS  positions 1-2   two-digit state code (01–37, 97–99)
    PAN positions 3-12  10-char PAN — 5 letters + 4 digits + 1 letter
    E   position 13     entity number for the PAN — 1 alphanumeric
    Z   position 14     literal "Z"
    C   position 15     checksum char (Mod-36 over positions 1-14)

Public API:
    validate_gstin(gstin: str) -> bool
    validate_gstin_verbose(gstin: str) -> dict   # {valid, reason, checksum_expected}
    gstin_checksum(first14: str) -> str          # exposed for tests / debugging
"""

from __future__ import annotations

import re
from typing import Any, Dict

_GSTIN_RE = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)
_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # base-36
_ALPHA_INDEX = {c: i for i, c in enumerate(_ALPHABET)}
_FACTORS = (1, 2)  # alternating multipliers, position 1 uses factor 1


def gstin_checksum(first14: str) -> str:
    """Compute the expected checksum char for the first 14 GSTIN chars.

    Uses the official Mod-36 algorithm published by GSTN:
    for each char c at position i (0-indexed), take its base-36 value,
    multiply by factor 1 or 2 alternately, split product into (quotient,
    remainder) modulo 36 and add. The checksum is (36 - total % 36) % 36
    rendered as a base-36 char.
    """
    if len(first14) != 14:
        raise ValueError("gstin_checksum expects exactly 14 characters")
    total = 0
    for i, ch in enumerate(first14.upper()):
        if ch not in _ALPHA_INDEX:
            raise ValueError(f"non-alphanumeric char {ch!r} at position {i + 1}")
        value = _ALPHA_INDEX[ch]
        factor = _FACTORS[i % 2]
        product = value * factor
        total += (product // 36) + (product % 36)
    check_code = (36 - (total % 36)) % 36
    return _ALPHABET[check_code]


def _normalize(gstin: str) -> str:
    return re.sub(r"\s+", "", (gstin or "")).upper()


def _state_code_valid(code: str) -> bool:
    try:
        n = int(code)
    except ValueError:
        return False
    # State codes 01-37 cover states/UTs; 97 = Other Territory; 99 = Centre Jurisdiction.
    return 1 <= n <= 37 or n in (97, 99)


def validate_gstin(gstin: str) -> bool:
    """Return True iff the given GSTIN passes format + checksum + state-code checks."""
    return validate_gstin_verbose(gstin)["valid"]


def validate_gstin_verbose(gstin: str) -> Dict[str, Any]:
    """Full validation with a machine-readable failure reason.

    Returns:
        {
            "valid": bool,
            "normalized": <upper-cased, whitespace-stripped GSTIN>,
            "reason": <human-readable failure reason, or "" when valid>,
            "checksum_expected": <expected 15th char, when computable>,
        }
    """
    norm = _normalize(gstin)
    result: Dict[str, Any] = {
        "valid": False,
        "normalized": norm,
        "reason": "",
        "checksum_expected": None,
    }

    if not norm:
        result["reason"] = "Empty GSTIN."
        return result
    if len(norm) != 15:
        result["reason"] = f"GSTIN must be 15 characters (got {len(norm)})."
        return result
    if not _GSTIN_RE.match(norm):
        result["reason"] = (
            "GSTIN structure invalid — expected 2-digit state code, "
            "PAN (5 letters + 4 digits + 1 letter), entity char, 'Z', checksum."
        )
        return result
    if not _state_code_valid(norm[:2]):
        result["reason"] = f"Unknown state code {norm[:2]!r}."
        return result

    try:
        expected = gstin_checksum(norm[:14])
    except ValueError as exc:
        result["reason"] = str(exc)
        return result

    result["checksum_expected"] = expected
    if norm[14] != expected:
        result["reason"] = (
            f"Checksum mismatch — expected {expected!r}, found {norm[14]!r}."
        )
        return result

    result["valid"] = True
    return result
