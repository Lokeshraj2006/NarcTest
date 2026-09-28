"""
Tests for app.services.fssai_mark_service.

Uses synthetic BGR images (numpy arrays) drawn with OpenCV primitives
so the tests have no dependency on any external image asset.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.fssai_mark_service import (
    STATUS_NON_VEG,
    STATUS_NOT_FOUND,
    STATUS_VEG,
    classify_and_crosscheck,
    detect_fssai_mark,
    detect_fssai_mark_from_bytes,
)

FIXTURES = Path(__file__).parent / "fixtures" / "fssai"


# ── Image factories ──────────────────────────────────────────────────────
def _blank_label(w: int = 200, h: int = 200) -> np.ndarray:
    """White canvas the size of a label crop."""
    return np.full((h, w, 3), 255, dtype=np.uint8)


def _draw_square(img: np.ndarray, cx: int, cy: int, half: int) -> None:
    cv2.rectangle(img, (cx - half, cy - half), (cx + half, cy + half), (0, 0, 0), 2)


def _draw_dot(img: np.ndarray, cx: int, cy: int, radius: int, bgr_color) -> None:
    cv2.circle(img, (cx, cy), radius, bgr_color, thickness=-1)


def _veg_label() -> np.ndarray:
    img = _blank_label()
    _draw_square(img, 100, 100, 30)
    _draw_dot(img, 100, 100, 18, (60, 180, 60))  # green fill (BGR)
    return img


def _non_veg_label() -> np.ndarray:
    img = _blank_label()
    _draw_square(img, 100, 100, 30)
    _draw_dot(img, 100, 100, 18, (30, 30, 180))  # red fill (BGR)
    return img


def _empty_label() -> np.ndarray:
    img = _blank_label()
    _draw_square(img, 100, 100, 30)
    return img


# ── vegetarian ───────────────────────────────────────────────────────────
def test_detect_fssai_mark_green_returns_vegetarian():
    result = detect_fssai_mark(_veg_label(), region=(70, 70, 60, 60))
    assert result.status == STATUS_VEG
    assert result.confidence > 0.5
    assert result.green_pixel_ratio > result.red_pixel_ratio


def test_detect_fssai_mark_green_without_region():
    # Auto-locator should still find the box for this simple canvas.
    result = detect_fssai_mark(_veg_label())
    assert result.status in (STATUS_VEG, STATUS_NOT_FOUND)
    if result.status == STATUS_VEG:
        assert result.detected_region is not None


# ── non_vegetarian ───────────────────────────────────────────────────────
def test_detect_fssai_mark_red_returns_non_vegetarian():
    result = detect_fssai_mark(_non_veg_label(), region=(70, 70, 60, 60))
    assert result.status == STATUS_NON_VEG
    assert result.red_pixel_ratio > result.green_pixel_ratio


# ── not_found ────────────────────────────────────────────────────────────
def test_detect_fssai_mark_empty_square_returns_not_found():
    result = detect_fssai_mark(_empty_label(), region=(70, 70, 60, 60))
    assert result.status == STATUS_NOT_FOUND


def test_detect_fssai_mark_empty_image_returns_not_found():
    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    result = detect_fssai_mark(empty)
    assert result.status == STATUS_NOT_FOUND


def test_detect_fssai_mark_all_white_returns_not_found():
    blank = _blank_label()
    result = detect_fssai_mark(blank, region=(50, 50, 100, 100))
    assert result.status == STATUS_NOT_FOUND


# ── from_bytes loader ────────────────────────────────────────────────────
def test_detect_fssai_mark_from_bytes_roundtrip():
    img = _veg_label()
    ok, buf = cv2.imencode(".png", img)
    assert ok
    result = detect_fssai_mark_from_bytes(buf.tobytes(), region=(70, 70, 60, 60))
    assert result.status == STATUS_VEG


def test_detect_fssai_mark_from_bytes_bad_data_raises():
    with pytest.raises(ValueError):
        detect_fssai_mark_from_bytes(b"not an image", region=None)


# ── classify_and_crosscheck ──────────────────────────────────────────────
def test_crosscheck_matches_registry_veg():
    payload = classify_and_crosscheck(
        _veg_label(),
        registry_is_vegetarian=True,
        region=(70, 70, 60, 60),
    )
    assert payload["detection"]["status"] == STATUS_VEG
    assert payload["matches_registry"] is True


def test_crosscheck_mismatch_registry_says_veg_but_red_detected():
    payload = classify_and_crosscheck(
        _non_veg_label(),
        registry_is_vegetarian=True,
        region=(70, 70, 60, 60),
    )
    assert payload["detection"]["status"] == STATUS_NON_VEG
    assert payload["matches_registry"] is False


def test_crosscheck_not_found_returns_none_match():
    payload = classify_and_crosscheck(
        _empty_label(),
        registry_is_vegetarian=True,
        region=(70, 70, 60, 60),
    )
    assert payload["detection"]["status"] == STATUS_NOT_FOUND
    assert payload["matches_registry"] is None


def test_crosscheck_registry_unknown_returns_none_match():
    payload = classify_and_crosscheck(
        _veg_label(),
        registry_is_vegetarian=None,
        region=(70, 70, 60, 60),
    )
    assert payload["matches_registry"] is None


# ── auto-location requires the mark's shape, not just its colour ─────────
def _mark_on_packaging(bgr_colour, with_outline: bool = True) -> np.ndarray:
    img = np.full((240, 320, 3), (40, 40, 200), dtype=np.uint8)       # red pack
    cv2.rectangle(img, (100, 60), (180, 140), (255, 255, 255), -1)    # white panel
    if with_outline:
        cv2.rectangle(img, (120, 80), (160, 120), bgr_colour, 3)
    cv2.circle(img, (140, 100), 10, bgr_colour, -1)
    return img


def test_auto_locates_veg_mark_on_red_packaging():
    result = detect_fssai_mark(_mark_on_packaging((60, 160, 40)))
    assert result.status == STATUS_VEG
    x, y, w, h = result.detected_region
    assert x <= 140 <= x + w and y <= 100 <= y + h


def test_auto_locates_non_veg_mark():
    result = detect_fssai_mark(_mark_on_packaging((30, 60, 120)))
    assert result.status == STATUS_NON_VEG


def test_dot_without_square_outline_is_not_found():
    result = detect_fssai_mark(_mark_on_packaging((60, 160, 40), with_outline=False))
    assert result.status == STATUS_NOT_FOUND
    assert result.confidence == 0.0


def test_plain_red_packaging_is_not_found():
    img = np.full((240, 320, 3), (40, 40, 200), dtype=np.uint8)
    cv2.putText(img, "Haldiram's", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
    assert detect_fssai_mark(img).status == STATUS_NOT_FOUND


# Crops of real 1080x1920 phone scans, put back where they sat in the photo
# so size limits (relative to the whole frame) apply as in production. Each
# "not_found" case was once reported as non-vegetarian: by the colour-only
# detector, or (pack_a_fabric_top) by the first shape-based version.
def _in_phone_frame(fixture: str, x: int, y: int) -> np.ndarray:
    crop = cv2.imread(str(FIXTURES / fixture))
    frame = np.full((1920, 1080, 3), 30, dtype=np.uint8)
    h, w = crop.shape[:2]
    frame[y : y + h, x : x + w] = crop
    return frame


@pytest.mark.parametrize(
    "fixture, origin, expected",
    [
        pytest.param(
            "pack_a_back_veg_mark.png",
            (100, 380),
            STATUS_VEG,
            marks=pytest.mark.xfail(
                strict=True,
                reason=(
                    "Known miss: on this glossy pouch the outline is too pale and "
                    "glare-broken for the colour mask, so it reports not_found."
                ),
            ),
        ),
        # Scan #32, a blurred tub: vivid dot, outline washed to saturation 13-25.
        ("obgob_blurred_veg_mark.png", (560, 1250), STATUS_VEG),
        # Scan #39's extra photo, Haldiram's front: the mark is tilted, sits on a
        # small white tile on the red pack, and one side of its outline reads teal.
        ("scan39_front_tilted_veg_mark.png", (700, 380), STATUS_VEG),
        ("pack_a_red_print.png", (560, 380), STATUS_NOT_FOUND),
        ("pack_a_fabric_top.png", (0, 0), STATUS_NOT_FOUND),
        ("pack_a_red_heading.png", (100, 560), STATUS_NOT_FOUND),  # bold red "FIND MORE", scan #16
        ("scan4_red_edge_and_fabric.png", (500, 1260), STATUS_NOT_FOUND),
        ("scan3_patterned_fabric.png", (440, 0), STATUS_NOT_FOUND),
        ("scan2_patterned_fabric.png", (350, 1300), STATUS_NOT_FOUND),
    ],
)
def test_real_phone_photos(fixture, origin, expected):
    result = detect_fssai_mark(_in_phone_frame(fixture, *origin))
    assert result.status == expected, result


def _mark_on_small_tile(angle: float, with_outline: bool = True) -> np.ndarray:
    """A veg mark on a white tile with a thin white edge, on a red pack, tilted."""
    frame = np.full((1920, 1080, 3), (60, 40, 190), dtype=np.uint8)
    tile = np.full((120, 120, 3), (60, 40, 190), dtype=np.uint8)
    cv2.rectangle(tile, (8, 8), (111, 111), (245, 245, 245), -1)
    if with_outline:
        cv2.rectangle(tile, (16, 16), (103, 103), (80, 150, 50), 4)
    cv2.circle(tile, (60, 60), 22, (80, 150, 50), -1)
    turn = cv2.getRotationMatrix2D((60, 60), angle, 1.0)
    frame[500:620, 500:620] = cv2.warpAffine(tile, turn, (120, 120), borderValue=(60, 40, 190))
    return frame


@pytest.mark.parametrize("angle", [0, 8, 15])
def test_tilted_mark_on_a_small_tile_is_found(angle):
    result = detect_fssai_mark(_mark_on_small_tile(angle))
    assert result.status == STATUS_VEG, result


@pytest.mark.parametrize("angle", [0, 8, 15])
def test_tilted_dot_on_a_tile_without_outline_is_not_found(angle):
    assert detect_fssai_mark(_mark_on_small_tile(angle, with_outline=False)).status == STATUS_NOT_FOUND


def test_green_dot_on_a_mint_label_is_not_a_veg_mark():
    # The pale outline allowance must not turn a pale-green field into an outline.
    img = np.full((1920, 1080, 3), (200, 235, 210), dtype=np.uint8)
    cv2.circle(img, (540, 960), 22, (40, 170, 40), -1)
    assert detect_fssai_mark(img).status == STATUS_NOT_FOUND


def test_real_veg_mark_is_never_reported_as_non_veg():
    # A wrong colour on a registered product would be recorded as tampering.
    result = detect_fssai_mark(_in_phone_frame("pack_a_back_veg_mark.png", 100, 380))
    assert result.status != STATUS_NON_VEG, result
