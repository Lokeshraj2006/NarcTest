"""
FieldProof — Computer Vision Service

Turns pixel measurements into physical ones so rules 9-11 can be decided
instead of deferred.

The key idea is the **barcode as a physical ruler**. A GS1 symbol is printed
to a standardised physical width (EAN-13 at 100% magnification is 37.29 mm
including quiet zones), so detecting it in the image yields a mm-per-pixel
scale for everything else on the same face of the pack:

    mm_per_px = reference_width_mm / barcode_width_px

With that scale, an OCR block's pixel height converts directly to millimetres
and can be compared against the minimum letter heights of Rule 7(2).

Honest limits, stated up front:
  * The scale holds only for text on the same plane as the barcode. A
    strongly angled photo inflates or deflates it, so a plausibility band is
    enforced and an implausible scale yields no verdict rather than a wrong one.
  * OCR block height covers the whole line box, which is taller than the
    letter height Rule 7(2) actually specifies. A cap-height ratio is applied.
    That approximation, perspective, and a barcode printed at 80-200% of its
    standard size all add error, so Rule 9 never fails a pack from a photo:
    a reading under the minimum goes to REVIEW (see `_VERDICT_MARGIN`).
  * Principal-display-panel detection is genuinely not solved here. Rule 11
    therefore measures whether declarations are *grouped*, a proxy for
    Rule 8(1), which puts every declaration on that panel, and says so.

Plain functions, no FastAPI, OpenCV + numpy only.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

# ── Physical reference widths, in millimetres, at 100% magnification ──────
# Source: GS1 General Specifications, symbol dimensions including quiet zones.
BARCODE_WIDTH_MM: Dict[str, float] = {
    "ean13": 37.29,
    "ean8": 26.73,
    "upca": 37.29,
    "upce": 22.11,
    "code128": 0.0,   # variable width — unusable as a ruler
}

# OCR line boxes include ascender/descender padding. Cap height is typically
# ~0.70 of the reported block height for Latin text.
_CAP_HEIGHT_RATIO = 0.70

# Refuse to trust a scale outside this band — a 4000px-wide photo of a retail
# pack should land well inside it. Outside means the barcode box is wrong or
# the shot is too oblique to measure from.
_MIN_MM_PER_PX = 0.005
_MAX_MM_PER_PX = 0.500

# A reading under the minimum but within this margin is marked borderline.
# Rule 9 gives REVIEW either way; the margin only changes the wording.
_VERDICT_MARGIN = 0.15   # 15%

# Phone photos understate print contrast: on two genuine packs, legible
# black-on-white declarations measured only 2.2-4.0:1. So a reading under the
# threshold is not proof of a breach — only a label whose typical declaration
# falls below this floor is.
_PHOTO_CONTRAST_FLOOR = 1.5

# Minimum letter heights by principal display panel area, Rule 7(2). These
# are the Table II values (net quantity by length, area or number); Table I
# (weight or volume) adds 1.5 mm and 2.5 mm bands. Only the 1 mm floor, common
# to both, is used while the panel area isn't measured.
_MIN_HEIGHT_BY_PDP_AREA_CM2: Sequence[Tuple[float, float]] = (
    (100.0, 1.0),     # up to 100 cm2  -> 1.0 mm
    (500.0, 2.0),     # up to 500 cm2  -> 2.0 mm
    (2500.0, 4.0),    # up to 2500 cm2 -> 4.0 mm
    (float("inf"), 6.0),
)

# Declarations Rule 9 cares about, matched loosely against OCR text.
_DECLARATION_PATTERNS = (
    r"m\.?r\.?p|maximum\s+retail",
    r"net\s*(qty|wt|weight|vol)",
    r"mfg|manufactur|packed|pkd",
    r"best\s*before|use\s*by|expiry|exp\b",
    r"fssai|lic\.?\s*no",
    r"consumer|customer\s*care|toll\s*free",
    r"country\s+of\s+origin|made\s+in",
)


@dataclass
class Calibration:
    """Physical scale derived from a barcode of known width."""
    mm_per_px: Optional[float] = None
    reference: Optional[str] = None
    barcode_width_px: Optional[float] = None
    reference_width_mm: Optional[float] = None
    usable: bool = False
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TextBlock:
    """One OCR block with its pixel geometry."""
    text: str
    x: float
    y: float
    width: float
    height: float

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Optional[TextBlock]:
        try:
            return cls(
                text=str(d.get("text", "")),
                x=float(d.get("x", d.get("left", 0))),
                y=float(d.get("y", d.get("top", 0))),
                width=float(d.get("width", 0)),
                height=float(d.get("height", 0)),
            )
        except (TypeError, ValueError):
            return None


def parse_text_blocks(raw: Optional[Sequence[Dict[str, Any]]]) -> List[TextBlock]:
    if not raw:
        return []
    out = []
    for d in raw:
        if isinstance(d, dict):
            b = TextBlock.from_dict(d)
            if b and b.width > 0 and b.height > 0:
                out.append(b)
    return out


# ── Calibration ──────────────────────────────────────────────────────────
def calibrate_from_barcode(
    barcode_bbox: Optional[Sequence[float]],
    barcode_format: Optional[str] = None,
) -> Calibration:
    """Derive mm-per-pixel from a barcode of standardised physical width."""
    if not barcode_bbox or len(barcode_bbox) < 4:
        return Calibration(reason="No barcode bounding box supplied.")

    width_px = float(barcode_bbox[2])
    if width_px <= 0:
        return Calibration(reason="Barcode bounding box has zero width.")

    fmt = (barcode_format or "ean13").lower().replace("-", "").replace("_", "")
    ref_mm = BARCODE_WIDTH_MM.get(fmt)
    if not ref_mm:
        return Calibration(
            barcode_width_px=width_px,
            reference=fmt,
            reason=(
                f"Barcode format '{fmt}' has no fixed physical width, so it "
                "cannot serve as a dimensional reference."
            ),
        )

    mm_per_px = ref_mm / width_px
    if not (_MIN_MM_PER_PX <= mm_per_px <= _MAX_MM_PER_PX):
        return Calibration(
            mm_per_px=mm_per_px,
            reference=fmt,
            barcode_width_px=width_px,
            reference_width_mm=ref_mm,
            reason=(
                f"Derived scale {mm_per_px:.4f} mm/px is outside the plausible "
                "range — the barcode box is likely wrong or the photo too "
                "oblique to measure from."
            ),
        )

    return Calibration(
        mm_per_px=mm_per_px,
        reference=fmt,
        barcode_width_px=width_px,
        reference_width_mm=ref_mm,
        usable=True,
        reason=f"Calibrated against {fmt.upper()} at {ref_mm} mm.",
    )


def required_height_mm(pdp_area_cm2: Optional[float]) -> float:
    """Minimum letter height for a principal display panel of this area."""
    if pdp_area_cm2 is None:
        return _MIN_HEIGHT_BY_PDP_AREA_CM2[0][1]
    for limit, height in _MIN_HEIGHT_BY_PDP_AREA_CM2:
        if pdp_area_cm2 <= limit:
            return height
    return _MIN_HEIGHT_BY_PDP_AREA_CM2[-1][1]


def _is_declaration(text: str) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in _DECLARATION_PATTERNS)


# ── Rule 9 — font size ───────────────────────────────────────────────────
def measure_font_sizes(
    calibration: Calibration,
    blocks: Sequence[TextBlock],
    pdp_area_cm2: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Measure declaration letter heights in mm.

    Returns a dict the compliance rules can consume, or None when the image
    cannot be measured — in which case rule 9 stays at REVIEW rather than
    guessing.
    """
    if not calibration.usable or not calibration.mm_per_px:
        return None

    declarations = [b for b in blocks if _is_declaration(b.text)]
    measured = declarations or list(blocks)
    if not measured:
        return None

    threshold = required_height_mm(pdp_area_cm2)
    heights = [
        {
            "text": b.text[:40],
            "height_mm": round(b.height * calibration.mm_per_px * _CAP_HEIGHT_RATIO, 3),
        }
        for b in measured
    ]
    smallest = min(heights, key=lambda h: h["height_mm"])

    # Clearly under the minimum, or within the margin: Rule 9 reports both as
    # REVIEW, since cap-height ratio and perspective both introduce error.
    clearly_under = smallest["height_mm"] < threshold * (1 - _VERDICT_MARGIN)

    return {
        "min_height_mm": smallest["height_mm"],
        "threshold_mm": threshold,
        "smallest_text": smallest["text"],
        "measured_blocks": len(measured),
        "used_declarations_only": bool(declarations),
        "mm_per_px": round(calibration.mm_per_px, 5),
        "reference": calibration.reference,
        "cap_height_ratio": _CAP_HEIGHT_RATIO,
        "inconclusive": not clearly_under and smallest["height_mm"] < threshold,
        "all_heights": sorted(heights, key=lambda h: h["height_mm"])[:8],
    }


# ── Rule 10 — readability / contrast ─────────────────────────────────────
def _relative_luminance(bgr: Sequence[float]) -> float:
    """WCAG relative luminance from a BGR triple."""
    def channel(c: float) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    b, g, r = channel(bgr[0]), channel(bgr[1]), channel(bgr[2])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def measure_readability(
    image: np.ndarray,
    blocks: Sequence[TextBlock],
    threshold: float = 4.5,
) -> Optional[Dict[str, Any]]:
    """Contrast ratio between glyphs and their background, per WCAG.

    Otsu-thresholds each declaration's crop to separate ink from substrate,
    then takes the mean colour of each population. Returns the worst block.
    """
    if image is None or image.size == 0 or not blocks:
        return None

    h_img, w_img = image.shape[:2]
    results: List[Dict[str, Any]] = []

    for b in blocks:
        if not _is_declaration(b.text):
            continue
        x, y = max(0, int(b.x)), max(0, int(b.y))
        w, h = int(b.width), int(b.height)
        if w < 6 or h < 6:
            continue
        x2, y2 = min(w_img, x + w), min(h_img, y + h)
        if x2 <= x or y2 <= y:
            continue

        crop = image[y:y2, x:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        ink = crop[mask == 0]
        paper = crop[mask == 255]
        # A crop that is essentially one colour has no measurable contrast.
        if ink.size < 30 or paper.size < 30:
            continue

        l_ink = _relative_luminance(ink.reshape(-1, 3).mean(axis=0))
        l_paper = _relative_luminance(paper.reshape(-1, 3).mean(axis=0))
        lighter, darker = max(l_ink, l_paper), min(l_ink, l_paper)
        ratio = (lighter + 0.05) / (darker + 0.05)

        results.append({"text": b.text[:40], "contrast_ratio": round(ratio, 2)})

    if not results:
        return None

    worst = min(results, key=lambda r: r["contrast_ratio"])
    return {
        **readability_verdict([r["contrast_ratio"] for r in results], threshold),
        "worst_text": worst["text"],
        "measured_blocks": len(results),
        "all_ratios": sorted(results, key=lambda r: r["contrast_ratio"])[:8],
    }


def readability_verdict(ratios: Sequence[float], threshold: float = 4.5) -> Dict[str, Any]:
    """Roll per-declaration contrast ratios into the Rule 10 measurement fields."""
    worst = float(min(ratios))
    median = float(np.median(ratios))
    return {
        "contrast_ratio": worst,
        "median_contrast_ratio": round(median, 2),
        "threshold": threshold,
        "fail_floor": _PHOTO_CONTRAST_FLOOR,
        "inconclusive": worst < threshold and median >= _PHOTO_CONTRAST_FLOOR,
    }


# ── Rule 11 — grouping (proxy for placement) ─────────────────────────────
def measure_placement(
    blocks: Sequence[TextBlock],
    image_width_px: Optional[int] = None,
    image_height_px: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """How tightly the mandatory declarations cluster together.

    Rule 8(1) puts every declaration on the principal display panel.
    Identifying that panel from a single photo is not solved here, so this
    measures dispersion instead — an honest proxy, labelled as such in the
    result.
    """
    declarations = [b for b in blocks if _is_declaration(b.text)]
    if len(declarations) < 2 or not image_width_px or not image_height_px:
        return None

    diag = math.hypot(image_width_px, image_height_px)
    if diag <= 0:
        return None

    cx = sum(b.cx for b in declarations) / len(declarations)
    cy = sum(b.cy for b in declarations) / len(declarations)
    spread = sum(math.hypot(b.cx - cx, b.cy - cy) for b in declarations) / len(
        declarations
    )
    spread_ratio = spread / diag

    # Beyond a third of the image diagonal the declarations are spread across
    # the pack rather than grouped on one panel.
    grouped = spread_ratio <= 0.33

    return {
        "on_principal_panel": grouped,
        "mean_spread_ratio": round(spread_ratio, 3),
        "declaration_blocks": len(declarations),
        "method": "dispersion_proxy",
        "note": (
            "Measures how tightly the mandatory declarations cluster. This is "
            "a proxy for Rule 8(1), declarations on the principal display "
            "panel, not true principal-display-panel detection."
        ),
    }


# ── Orchestration ────────────────────────────────────────────────────────
def analyse(
    image: Optional[np.ndarray],
    barcode_bbox: Optional[Sequence[float]] = None,
    barcode_format: Optional[str] = None,
    text_blocks: Optional[Sequence[Dict[str, Any]]] = None,
    image_width_px: Optional[int] = None,
    image_height_px: Optional[int] = None,
    pdp_area_cm2: Optional[float] = None,
) -> Dict[str, Any]:
    """Produce the `cv_measurements` mapping the compliance rules expect.

    Keys are omitted when a measurement could not be made, which is what
    keeps the corresponding rule at REVIEW instead of inventing a verdict.
    """
    blocks = parse_text_blocks(text_blocks)
    calibration = calibrate_from_barcode(barcode_bbox, barcode_format)

    if image is not None and image.size:
        h, w = image.shape[:2]
        image_height_px = image_height_px or h
        image_width_px = image_width_px or w

    out: Dict[str, Any] = {"calibration": calibration.to_dict()}

    font = measure_font_sizes(calibration, blocks, pdp_area_cm2)
    if font:
        out["font_size"] = font

    if image is not None:
        readability = measure_readability(image, blocks)
        if readability:
            out["readability"] = readability

    placement = measure_placement(blocks, image_width_px, image_height_px)
    if placement:
        out["placement"] = placement

    return out
