"""
FieldProof — FSSAI Veg / Non-Veg Mark Detection

The FSSAI mandates a small symbol on packaged food labels: a filled dot
inside a square outline, both printed in the same colour —
    green     → vegetarian
    brown/red → non-vegetarian

Without a caller-supplied region, a candidate only counts when it has that
whole shape: a filled, roughly circular dot at least 1% of the photo's
shorter side across, a same-colour square outline whose four sides are
unbroken lines, a light gap inside the outline and light label outside it.
Colour alone is not enough — red packaging and patterned fabric satisfied the
earlier colour-only check, and bold red heading text satisfied an outline
check that didn't require unbroken sides. When nothing qualifies the result
is "not_found", never a guess.

Known limit: on glossy pouches a pale, glare-broken outline can fall below
the colour threshold, so a real mark may come back "not_found".

Zero FastAPI dependency — plain functions callable from any router,
worker, or unit test. Uses opencv-python-headless + numpy only.

Public API:
    detect_fssai_mark(image, region=None) -> FssaiMarkResult
    detect_fssai_mark_from_path(path, region=None) -> FssaiMarkResult
    detect_fssai_mark_from_bytes(data, region=None) -> FssaiMarkResult
    combine_photo_results(results) -> FssaiMarkResult   (evidence + extra photos)

Returned status is one of:
    "vegetarian" | "non_vegetarian" | "not_found"
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any, Dict, Optional, Sequence, Tuple, Union

import cv2
import numpy as np

# ── Status constants ──────────────────────────────────────────────────────
STATUS_VEG = "vegetarian"
STATUS_NON_VEG = "non_vegetarian"
STATUS_NOT_FOUND = "not_found"

# ── HSV colour ranges (OpenCV H: 0-179, S/V: 0-255) ──────────────────────
_GREEN_HSV = ((35, 60, 40), (90, 255, 255))
# The veg mark's thin outline washes out under blur while its dot stays vivid:
# on scan #32 the dot read saturation 230+ and the outline only 13-25. The
# outline alone may be this pale; it must still form four unbroken sides.
# Not applied to red/brown, whose pale tones are skin and wood.
_PALE_GREEN_OUTLINE_HSV = ((35, 20, 40), (90, 255, 255))
# ...but a pale outline must be a line, not a pale-green field: a plain green
# dot on a mint label would otherwise pass. Scan #32 read 0.42 in the gap (blur
# spreads the dot's colour) and 0.16 outside; a mint field reads ~1.0 on both.
_MAX_PALE_GAP = 0.6
_MAX_PALE_OUTSIDE = 0.35
# Brown/red — red wraps H=0, so two windows.
_RED_HSV_LOW = ((0, 80, 40), (12, 255, 255))
_RED_HSV_HIGH = ((160, 80, 40), (179, 255, 255))
_BROWN_HSV = ((5, 60, 20), (25, 255, 180))
# Unsaturated and bright: the label substrate between dot and outline.
_LIGHT_HSV = ((0, 0, 120), (179, 90, 255))

# ── Caller-supplied region ────────────────────────────────────────────────
_MIN_DOT_PIXELS = 40
_MIN_FILL_RATIO = 0.015
_DECISION_MARGIN = 1.25

# ── Auto-location: the shape of the mark ──────────────────────────────────
_MIN_DOT_DIAMETER_PX = 6
# Smaller than this share of the photo's shorter side is too small to classify.
_MIN_DOT_DIAMETER_FRACTION = 0.01
_MAX_DOT_AREA_FRACTION = 0.02          # the mark is a small symbol, never a colour field
_DOT_FILL_RANGE = (0.55, 0.92)         # a filled disc covers ~0.785 of its bounding box
_DOT_ASPECT_RANGE = (0.7, 1.4)
_OUTLINE_HALF_SIDE_RANGE = (0.8, 1.6)  # outline half-side, in dot diameters
_MIN_OUTLINE_COVERAGE = 0.6
_MIN_OUTLINE_SIDE_COVERAGE = 0.4       # every side present, not pattern lines crossing
_MIN_OUTLINE_SIDE_RUN = 0.6            # each side one unbroken line, not text strokes
_MAX_GAP_COLOURED = 0.35
_MIN_GAP_LIGHT = 0.5
_MAX_OUTSIDE_COLOURED = 0.35           # a thin outline, not the edge of a colour field
_MIN_OUTSIDE_LIGHT = 0.5

# ── Second chance, for a candidate the upright checks reject ──────────────
# Scan #39 (Haldiram's front, as an extra photo): the photo was tilted, so an
# upright square cut across the outline (weakest side 0.24 unbroken), and the
# mark sits on a small white tile, so the light ring at 0.3 of a dot diameter
# landed on the red pack. The outline's own quadrilateral is warped to a
# square, and the light ring may then sit anywhere just outside the outline.
# Every other check is unchanged.
# Its outline also read hue 91-94 on the side the light fell on (80-88 on the
# other), just past green's 90, so the warped outline may run into teal.
_TEAL_OUTLINE_HSV = ((35, 20, 40), (97, 255, 255))
_WARP_SIDE_RANGE = (1.6, 3.4)          # outline side, in dot diameters
_WARP_MAX_SIDE_RATIO = 1.35            # longest / shortest side, for perspective
_THIN_BORDER_RANGE = (0.06, 0.35)      # light ring offset past the outline, in dot diameters

_KERNEL = np.ones((3, 3), np.uint8)

Region = Tuple[int, int, int, int]  # (x, y, w, h)


@dataclass
class FssaiMarkResult:
    """Structured verdict returned by detect_fssai_mark()."""
    status: str
    confidence: float                       # 0.0 – 1.0
    detected_region: Optional[Region] = None
    green_pixel_ratio: float = 0.0
    red_pixel_ratio: float = 0.0
    message: str = ""
    # Set by combine_photo_results: which photo showed the mark (0 = the
    # evidence photo, 1.. = extra photos of other faces) and how many were checked.
    photo: Optional[int] = None
    photos_checked: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Loaders ───────────────────────────────────────────────────────────────
def _load_from_path(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not read image at {path!r}")
    return img


def _load_from_bytes(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")
    return img


def _crop(image: np.ndarray, region: Optional[Region]) -> Tuple[np.ndarray, Optional[Region]]:
    if region is None:
        return image, None
    x, y, w, h = region
    h_img, w_img = image.shape[:2]
    x = max(0, min(x, w_img - 1))
    y = max(0, min(y, h_img - 1))
    w = max(1, min(w, w_img - x))
    h = max(1, min(h, h_img - y))
    return image[y : y + h, x : x + w].copy(), (x, y, w, h)


# ── Colour analysis ──────────────────────────────────────────────────────
def _hsv_mask(hsv: np.ndarray, bounds) -> np.ndarray:
    return cv2.inRange(hsv, np.array(bounds[0]), np.array(bounds[1]))


def _colour_masks(bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (green, red_or_brown, light) masks."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    non_veg = cv2.bitwise_or(
        cv2.bitwise_or(_hsv_mask(hsv, _RED_HSV_LOW), _hsv_mask(hsv, _RED_HSV_HIGH)),
        _hsv_mask(hsv, _BROWN_HSV),
    )
    return _hsv_mask(hsv, _GREEN_HSV), non_veg, _hsv_mask(hsv, _LIGHT_HSV)


def _colour_ratios(bgr_roi: np.ndarray) -> Tuple[float, float]:
    """Return (green_ratio, red_or_brown_ratio) of ROI pixels."""
    green, non_veg, _ = _colour_masks(bgr_roi)
    total = float(bgr_roi.shape[0] * bgr_roi.shape[1]) or 1.0
    return cv2.countNonZero(green) / total, cv2.countNonZero(non_veg) / total


# ── Shape checks ─────────────────────────────────────────────────────────
def _square_perimeter(mask: np.ndarray, cx: float, cy: float, half: float) -> Tuple[float, float]:
    """(share of set pixels on an axis-aligned square's perimeter, share on its weakest side)."""
    h_img, w_img = mask.shape[:2]
    x0, x1 = int(round(cx - half)), int(round(cx + half))
    y0, y1 = int(round(cy - half)), int(round(cy + half))
    if x0 < 0 or y0 < 0 or x1 >= w_img or y1 >= h_img or x1 - x0 < 4:
        return 0.0, 0.0
    sides = [
        mask[y0, x0 : x1 + 1],
        mask[y1, x0 : x1 + 1],
        mask[y0 : y1 + 1, x0],
        mask[y0 : y1 + 1, x1],
    ]
    counts = [np.count_nonzero(s) for s in sides]
    overall = float(sum(counts)) / sum(s.size for s in sides)
    weakest = float(min(c / s.size for c, s in zip(counts, sides)))
    return overall, weakest


def _weakest_side_run(mask: np.ndarray, cx: float, cy: float, half: float) -> float:
    """Longest unbroken run on the square's weakest side, as a share of its length."""
    h_img, w_img = mask.shape[:2]
    x0, x1 = int(round(cx - half)), int(round(cx + half))
    y0, y1 = int(round(cy - half)), int(round(cy + half))
    if x0 < 0 or y0 < 0 or x1 >= w_img or y1 >= h_img or x1 - x0 < 4:
        return 0.0
    weakest = 1.0
    for side in (
        mask[y0, x0 : x1 + 1],
        mask[y1, x0 : x1 + 1],
        mask[y0 : y1 + 1, x0],
        mask[y0 : y1 + 1, x1],
    ):
        run = best = 0
        for on in side > 0:
            run = run + 1 if on else 0
            best = max(best, run)
        weakest = min(weakest, best / side.size)
    return weakest


def _shape_checks(
    mask: np.ndarray,
    outline: np.ndarray,
    outline_mask: np.ndarray,
    light: np.ndarray,
    cx: float,
    cy: float,
    diameter: float,
    thin_border: bool = False,
) -> Optional[Tuple[float, float]]:
    """The mark's shape around one dot, sampled on upright squares.

    Returns (outline coverage, outline half-side), or None when any part of
    the shape is missing. ``outline`` is the dilated ``outline_mask``.
    """
    (coverage, weakest_side), half = max(
        (
            (_square_perimeter(outline, cx, cy, s), s)
            for s in np.arange(
                diameter * _OUTLINE_HALF_SIDE_RANGE[0],
                diameter * _OUTLINE_HALF_SIDE_RANGE[1] + 1.0,
                1.0,
            )
        ),
        key=lambda candidate: candidate[0][0],
    )
    if coverage < _MIN_OUTLINE_COVERAGE or weakest_side < _MIN_OUTLINE_SIDE_COVERAGE:
        return None
    # Bold text beside a letter covers a square's perimeter in pieces;
    # a printed outline is one unbroken line on every side.
    if _weakest_side_run(outline, cx, cy, half) < _MIN_OUTLINE_SIDE_RUN:
        return None

    gap_half = (diameter / 2.0 + half) / 2.0
    if _square_perimeter(mask, cx, cy, gap_half)[0] > _MAX_GAP_COLOURED:
        return None
    if _square_perimeter(light, cx, cy, gap_half)[0] < _MIN_GAP_LIGHT:
        return None
    # A pale outline must be a line, not the edge of a pale-green field.
    pale_outline = outline_mask is not mask
    if pale_outline and _square_perimeter(outline_mask, cx, cy, gap_half)[0] > _MAX_PALE_GAP:
        return None

    # Light ground outside the outline: at a fixed distance, or (thin_border)
    # anywhere from just past the line, for a mark on a small white tile.
    offsets = (
        np.arange(max(2.0, _THIN_BORDER_RANGE[0] * diameter), _THIN_BORDER_RANGE[1] * diameter + 1.0, 1.0)
        if thin_border
        else [max(3.0, 0.3 * diameter)]
    )
    for offset in offsets:
        ring = half + offset
        if (
            _square_perimeter(mask, cx, cy, ring)[0] <= _MAX_OUTSIDE_COLOURED
            and _square_perimeter(light, cx, cy, ring)[0] >= _MIN_OUTSIDE_LIGHT
            and not (pale_outline and _square_perimeter(outline_mask, cx, cy, ring)[0] > _MAX_PALE_OUTSIDE)
        ):
            return coverage, half
    return None


def _dot_ok(w: int, h: int, area: int) -> bool:
    return (
        _DOT_ASPECT_RANGE[0] <= w / h <= _DOT_ASPECT_RANGE[1]
        and _DOT_FILL_RANGE[0] <= area / float(w * h) <= _DOT_FILL_RANGE[1]
    )


def _outline_masks(
    bgr: np.ndarray, status: str, teal: bool = False
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(dot colour mask, raw outline mask, light mask) for one status."""
    green, non_veg, light = _colour_masks(bgr)
    if status == STATUS_VEG:
        bounds = _TEAL_OUTLINE_HSV if teal else _PALE_GREEN_OUTLINE_HSV
        return green, _hsv_mask(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV), bounds), light
    return non_veg, non_veg, light


def _ordered_corners(points: np.ndarray) -> np.ndarray:
    """Top-left, top-right, bottom-right, bottom-left."""
    total = points.sum(axis=1)
    diff = np.diff(points, axis=1).ravel()  # y - x
    return np.float32([
        points[np.argmin(total)], points[np.argmin(diff)],
        points[np.argmax(total)], points[np.argmax(diff)],
    ])


def _outline_quad(outline_mask: np.ndarray, cx: float, cy: float, diameter: float) -> Optional[np.ndarray]:
    """Corners of the roughly square outline around the dot, or None.

    Glare can break the printed outline into pieces (scan #39's right side),
    so the corners come from the outline-coloured pixels in a band around the
    dot, apart from the dot itself: their convex hull, reduced to four
    corners. The square must be about the size a mark's outline is relative
    to its dot and contain the dot near its middle; whether it really is an
    unbroken outline is left to the shape checks after warping.
    """
    h_img, w_img = outline_mask.shape[:2]
    reach = int(diameter * _WARP_SIDE_RANGE[1] * 0.6) + 2
    x0, y0 = max(0, int(cx) - reach), max(0, int(cy) - reach)
    x1, y1 = min(w_img, int(cx) + reach + 1), min(h_img, int(cy) + reach + 1)
    local = cv2.morphologyEx(outline_mask[y0:y1, x0:x1], cv2.MORPH_CLOSE, _KERNEL)
    px, py = cx - x0, cy - y0
    _, labels = cv2.connectedComponents(local, connectivity=8)
    dot_label = labels[int(py), int(px)]
    ys, xs = np.nonzero((local > 0) & (labels != dot_label) if dot_label else local > 0)
    # Chebyshev distance: the outline of an upright square is a constant distance.
    band = np.maximum(np.abs(xs - px), np.abs(ys - py))
    keep = (band >= _WARP_SIDE_RANGE[0] * diameter / 2.0) & (band <= _WARP_SIDE_RANGE[1] * diameter / 2.0)
    if np.count_nonzero(keep) < 4 * diameter:  # far too few pixels for four sides
        return None
    points = np.stack([xs[keep], ys[keep]], axis=1).astype(np.float32)
    hull = cv2.convexHull(points)
    quad = cv2.approxPolyDP(hull, 0.04 * cv2.arcLength(hull, True), True)
    corners = (
        quad.reshape(4, 2).astype(np.float32) if len(quad) == 4
        else cv2.boxPoints(cv2.minAreaRect(points)).astype(np.float32)
    )
    sides = [float(np.linalg.norm(corners[k] - corners[(k + 1) % 4])) for k in range(4)]
    if min(sides) < _WARP_SIDE_RANGE[0] * diameter or max(sides) > _WARP_SIDE_RANGE[1] * diameter:
        return None
    if max(sides) / min(sides) > _WARP_MAX_SIDE_RATIO:
        return None
    centre = corners.mean(axis=0)
    if math.hypot(centre[0] - px, centre[1] - py) > 0.2 * float(np.mean(sides)):
        return None
    return _ordered_corners(corners + np.float32([x0, y0]))


def _rectified_mark(image: np.ndarray, status: str, corners: np.ndarray) -> Optional[float]:
    """Run the shape checks with the outline warped to an upright square.

    A mark photographed at a slant fails the upright-square checks even when
    every part of it is there. The outline's own corners give the warp, so
    the same checks then see it square-on. Returns the outline coverage.
    """
    side = float(np.mean([np.linalg.norm(corners[k] - corners[(k + 1) % 4]) for k in range(4)]))
    margin = int(round(0.45 * side)) + 4
    size = int(round(side)) + 2 * margin
    target = np.float32([
        [margin, margin], [margin + side, margin],
        [margin + side, margin + side], [margin, margin + side],
    ])
    warped = cv2.warpPerspective(
        image, cv2.getPerspectiveTransform(corners, target), (size, size),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
    )
    mask, outline_mask, light = _outline_masks(warped, status, teal=True)
    if status != STATUS_VEG:
        outline_mask = mask  # same object: the pale-outline guard is veg-only
    dots = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _KERNEL)
    count, _, stats, centroids = cv2.connectedComponentsWithStats(dots, connectivity=8)
    middle = size / 2.0

    def off_middle(k: int) -> float:
        return math.hypot(centroids[k][0] - middle, centroids[k][1] - middle)

    # A dot-shaped component near the middle; an unbroken outline is centred
    # there too, and is larger, so shape decides, not size.
    candidates = [
        k for k in range(1, count)
        if off_middle(k) <= 0.25 * side
        and min(int(stats[k][2]), int(stats[k][3])) >= _MIN_DOT_DIAMETER_PX
        and _dot_ok(int(stats[k][2]), int(stats[k][3]), int(stats[k][4]))
    ]
    if not candidates:
        return None
    i = min(candidates, key=off_middle)
    _, _, w, h, _ = (int(v) for v in stats[i])
    # Sampled around the square's own centre: a dot printed a little off-centre
    # would otherwise put one side of the sampling square beside the outline.
    checked = _shape_checks(
        mask, cv2.dilate(outline_mask, _KERNEL), outline_mask, light,
        middle, middle, (w + h) / 2.0, thin_border=True,
    )
    return checked[0] if checked else None


def _locate_mark(image: np.ndarray) -> Optional[Tuple[str, Region, float]]:
    """Find the best dot-in-square candidate; returns (status, region, outline coverage)."""
    green, non_veg, light = _colour_masks(image)
    max_dot_area = image.shape[0] * image.shape[1] * _MAX_DOT_AREA_FRACTION
    min_dot_diameter = max(
        _MIN_DOT_DIAMETER_PX, min(image.shape[:2]) * _MIN_DOT_DIAMETER_FRACTION
    )
    best: Optional[Tuple[str, Region, float]] = None

    pale_green = _hsv_mask(cv2.cvtColor(image, cv2.COLOR_BGR2HSV), _PALE_GREEN_OUTLINE_HSV)
    for status, mask, outline_mask in (
        (STATUS_VEG, green, pale_green),
        (STATUS_NON_VEG, non_veg, non_veg),
    ):
        dots = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _KERNEL)
        # Dilated so a thin, slightly rotated outline still registers.
        outline = cv2.dilate(outline_mask, _KERNEL)
        count, _, stats, centroids = cv2.connectedComponentsWithStats(dots, connectivity=8)

        for i in range(1, count):
            _, _, w, h, area = (int(v) for v in stats[i])
            if min(w, h) < min_dot_diameter or area > max_dot_area:
                continue
            if not _dot_ok(w, h, area):
                continue

            cx, cy = (float(c) for c in centroids[i])
            diameter = (w + h) / 2.0
            checked = _shape_checks(mask, outline, outline_mask, light, cx, cy, diameter)
            if checked is not None:
                coverage, half = checked
                side = int(round(2 * half)) + 1
                region = (int(round(cx - half)), int(round(cy - half)), side, side)
            else:
                # Second chance for a mark seen at a slant, or on a small tile.
                corners = _outline_quad(outline_mask, cx, cy, diameter)
                coverage = _rectified_mark(image, status, corners) if corners is not None else None
                if coverage is None:
                    continue
                x, y, bw, bh = cv2.boundingRect(corners.astype(np.int32))
                region = (x, y, bw, bh)

            if best is None or coverage > best[2]:
                best = (status, region, coverage)

    return best


def _classify_region(image: np.ndarray, region: Region) -> FssaiMarkResult:
    """Classify a caller-supplied ROI by which colour dominates it."""
    roi, used_region = _crop(image, region)
    green_ratio, non_veg_ratio = _colour_ratios(roi)

    roi_pixels = roi.shape[0] * roi.shape[1]
    max_ratio = max(green_ratio, non_veg_ratio)
    max_area = max_ratio * roi_pixels

    if max_ratio < _MIN_FILL_RATIO or max_area < _MIN_DOT_PIXELS:
        return FssaiMarkResult(
            status=STATUS_NOT_FOUND,
            confidence=0.0,
            detected_region=used_region,
            green_pixel_ratio=round(green_ratio, 4),
            red_pixel_ratio=round(non_veg_ratio, 4),
            message="No coloured dot with sufficient area detected in region.",
        )

    if green_ratio >= non_veg_ratio * _DECISION_MARGIN:
        winner_status = STATUS_VEG
    elif non_veg_ratio >= green_ratio * _DECISION_MARGIN:
        winner_status = STATUS_NON_VEG
    else:
        return FssaiMarkResult(
            status=STATUS_NOT_FOUND,
            confidence=min(0.5, max_ratio * 10),
            detected_region=used_region,
            green_pixel_ratio=round(green_ratio, 4),
            red_pixel_ratio=round(non_veg_ratio, 4),
            message="Ambiguous colour signal — neither green nor red/brown dominant.",
        )

    total = green_ratio + non_veg_ratio
    return FssaiMarkResult(
        status=winner_status,
        confidence=round(float(max_ratio / total if total > 0 else 0.0), 3),
        detected_region=used_region,
        green_pixel_ratio=round(green_ratio, 4),
        red_pixel_ratio=round(non_veg_ratio, 4),
        message=f"FSSAI mark classified as {winner_status}.",
    )


# ── Public entry points ──────────────────────────────────────────────────
def detect_fssai_mark(
    image: np.ndarray,
    region: Optional[Region] = None,
) -> FssaiMarkResult:
    """Detect the FSSAI veg/non-veg mark in a BGR OpenCV image.

    Args:
        image: BGR numpy array (as returned by cv2.imread).
        region: optional (x, y, w, h) ROI known to contain the mark. Without
            it the mark is located by shape; see the module docstring.
    """
    if image is None or image.size == 0:
        return FssaiMarkResult(
            status=STATUS_NOT_FOUND,
            confidence=0.0,
            message="Empty or missing image.",
        )

    if region is not None:
        return _classify_region(image, region)

    located = _locate_mark(image)
    if located is None:
        return FssaiMarkResult(
            status=STATUS_NOT_FOUND,
            confidence=0.0,
            message=(
                "No FSSAI mark found — looked for a filled dot inside a "
                "same-colour square outline on a light ground."
            ),
        )

    status, found_region, coverage = located
    roi, used_region = _crop(image, found_region)
    green_ratio, non_veg_ratio = _colour_ratios(roi)
    return FssaiMarkResult(
        status=status,
        confidence=round(coverage, 3),
        detected_region=used_region,
        green_pixel_ratio=round(green_ratio, 4),
        red_pixel_ratio=round(non_veg_ratio, 4),
        message=f"FSSAI mark classified as {status}.",
    )


def detect_fssai_mark_from_path(
    path: str,
    region: Optional[Region] = None,
) -> FssaiMarkResult:
    return detect_fssai_mark(_load_from_path(path), region)


def detect_fssai_mark_from_bytes(
    data: bytes,
    region: Optional[Region] = None,
) -> FssaiMarkResult:
    return detect_fssai_mark(_load_from_bytes(data), region)


def _photo_name(index: int) -> str:
    return "the main photo" if index == 0 else f"extra photo {index}"


def combine_photo_results(results: Sequence[FssaiMarkResult]) -> FssaiMarkResult:
    """One verdict from the evidence photo (index 0) and any extra photos.

    The mark is printed on one face of the pack, so it counts from whichever
    photo shows it. Photos that disagree — vegetarian on one, non-vegetarian on
    another — mean one reading is wrong, so the result is not_found rather
    than a pick between them.
    """
    if not results:
        return FssaiMarkResult(
            status=STATUS_NOT_FOUND, confidence=0.0,
            message="No photo to check.", photos_checked=0,
        )
    count = len(results)
    found = [(i, r) for i, r in enumerate(results) if r.status != STATUS_NOT_FOUND]
    if not found:
        message = results[0].message
        if count > 1:
            message = (
                f"No FSSAI mark found on any of the {count} photos — looked for a "
                "filled dot inside a same-colour square outline on a light ground."
            )
        return replace(results[0], photo=None, photos_checked=count, message=message)

    if len({r.status for _, r in found}) > 1:
        readings = "; ".join(
            f"{_photo_name(i)}: {r.status.replace('_', '-')}" for i, r in found
        )
        return FssaiMarkResult(
            status=STATUS_NOT_FOUND,
            confidence=0.0,
            photos_checked=count,
            message=(
                f"The photos disagree ({readings}), so the mark is not decided. "
                "A person should check the pack."
            ),
        )

    index, best = max(found, key=lambda f: f[1].confidence)
    message = best.message
    if count > 1:
        message = f"FSSAI mark classified as {best.status} on {_photo_name(index)}."
    return replace(best, photo=index, photos_checked=count, message=message)


# ── Convenience: full pipeline (mark detection + authenticity cross-check) ─
def classify_and_crosscheck(
    image: Union[np.ndarray, bytes, str],
    registry_is_vegetarian: Optional[bool],
    region: Optional[Region] = None,
) -> Dict[str, Any]:
    """Detect the FSSAI mark and compare it against the registry expectation.

    Returns a dict with 'detection' (FssaiMarkResult.to_dict()) and
    'matches_registry' (True/False/None). None means either the registry
    has no is_vegetarian value or the mark was not detected.
    """
    if isinstance(image, str):
        result = detect_fssai_mark_from_path(image, region)
    elif isinstance(image, bytes):
        result = detect_fssai_mark_from_bytes(image, region)
    else:
        result = detect_fssai_mark(image, region)

    matches: Optional[bool]
    if registry_is_vegetarian is None or result.status == STATUS_NOT_FOUND:
        matches = None
    else:
        expected = STATUS_VEG if registry_is_vegetarian else STATUS_NON_VEG
        matches = (result.status == expected)

    return {"detection": result.to_dict(), "matches_registry": matches}
