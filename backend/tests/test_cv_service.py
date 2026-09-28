"""
Tests for app.services.cv_service.

The calibration maths is the part that must be right: if mm-per-pixel is
wrong, rule 9 produces confident but false verdicts. These tests pin the
arithmetic and, just as importantly, pin the refusals — the cases where the
service must decline to measure rather than guess.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.cv_service import (
    BARCODE_WIDTH_MM,
    Calibration,
    TextBlock,
    analyse,
    calibrate_from_barcode,
    measure_font_sizes,
    measure_placement,
    measure_readability,
    parse_text_blocks,
    readability_verdict,
    required_height_mm,
)
from app.services.compliance_rules import FAIL, PASS, REVIEW, check_font_size, check_readability


# ── Calibration ──────────────────────────────────────────────────────────
def test_ean13_calibration_arithmetic():
    # 1000 px wide EAN-13 == 37.29 mm, so 0.03729 mm per pixel.
    cal = calibrate_from_barcode([10, 10, 1000, 200], "ean13")
    assert cal.usable
    assert cal.mm_per_px == pytest.approx(37.29 / 1000)
    assert cal.reference_width_mm == 37.29


def test_ean8_uses_its_own_width():
    cal = calibrate_from_barcode([0, 0, 500, 100], "ean8")
    assert cal.usable
    assert cal.mm_per_px == pytest.approx(BARCODE_WIDTH_MM["ean8"] / 500)


def test_format_spelling_is_normalised():
    assert calibrate_from_barcode([0, 0, 800, 100], "EAN-13").usable
    assert calibrate_from_barcode([0, 0, 800, 100], "ean_13").usable


def test_code128_is_refused_as_a_ruler():
    # Code128 has no fixed physical width, so it cannot calibrate anything.
    cal = calibrate_from_barcode([0, 0, 800, 100], "code128")
    assert not cal.usable
    assert "no fixed physical width" in cal.reason


def test_missing_bbox_is_refused():
    assert not calibrate_from_barcode(None, "ean13").usable
    assert not calibrate_from_barcode([1, 2], "ean13").usable


def test_zero_width_is_refused():
    assert not calibrate_from_barcode([0, 0, 0, 50], "ean13").usable


def test_implausible_scale_is_refused_rather_than_trusted():
    # A 5 px "barcode" implies ~7.5 mm per pixel — physically absurd.
    cal = calibrate_from_barcode([0, 0, 5, 2], "ean13")
    assert not cal.usable
    assert "plausible range" in cal.reason


# ── Statutory height table ───────────────────────────────────────────────
@pytest.mark.parametrize(
    "area,expected",
    [(50, 1.0), (100, 1.0), (300, 2.0), (500, 2.0), (1500, 4.0), (9000, 6.0)],
)
def test_required_height_follows_pdp_area(area, expected):
    assert required_height_mm(area) == expected


def test_required_height_defaults_when_area_unknown():
    assert required_height_mm(None) == 1.0


# ── Font size ────────────────────────────────────────────────────────────
def _blocks(*specs):
    return [TextBlock(text=t, x=0, y=0, width=100, height=h) for t, h in specs]


def test_font_size_passes_when_clearly_large_enough():
    cal = calibrate_from_barcode([0, 0, 1000, 200], "ean13")  # 0.03729 mm/px
    # 100 px * 0.03729 * 0.70 cap ratio == 2.6 mm, well over the 1.0 mm floor.
    m = measure_font_sizes(cal, _blocks(("MRP Rs 50", 100)), pdp_area_cm2=50)
    assert m["min_height_mm"] > 2.0
    assert not m["inconclusive"]
    assert check_font_size({}, m)["status"] == PASS


def test_font_size_clearly_too_small_is_review_not_fail():
    cal = calibrate_from_barcode([0, 0, 1000, 200], "ean13")
    # 10 px -> ~0.26 mm, far below 1.0 mm. Still only an estimate from a photo
    # (the barcode's print size can vary), so a person measures it on the pack.
    m = measure_font_sizes(cal, _blocks(("Net Wt 50g", 10)), pdp_area_cm2=50)
    assert m["min_height_mm"] < 0.5
    assert not m["inconclusive"]
    r = check_font_size({}, m)
    assert r["status"] == REVIEW
    assert "under the" in r["failure_reason"]
    assert "measure it on the pack" in r["failure_reason"]


def test_borderline_measurement_is_review_not_fail():
    cal = calibrate_from_barcode([0, 0, 1000, 200], "ean13")
    # ~0.94 mm against a 1.0 mm floor: inside tolerance, so not a breach.
    m = measure_font_sizes(cal, _blocks(("MRP Rs 50", 36)), pdp_area_cm2=50)
    assert m["inconclusive"], f"expected borderline, got {m['min_height_mm']}"
    assert check_font_size({}, m)["status"] == REVIEW


def test_font_size_prefers_declaration_blocks_over_decoration():
    cal = calibrate_from_barcode([0, 0, 1000, 200], "ean13")
    # The tiny block is not a declaration, so it must not drive the verdict.
    m = measure_font_sizes(
        cal,
        _blocks(("MRP Rs 50", 100), ("tiny legal footnote", 5)),
        pdp_area_cm2=50,
    )
    assert m["used_declarations_only"] is True
    assert m["measured_blocks"] == 1
    assert m["min_height_mm"] > 2.0


def test_font_size_returns_none_without_calibration():
    assert measure_font_sizes(Calibration(), _blocks(("MRP", 50))) is None


def test_font_size_returns_none_without_blocks():
    cal = calibrate_from_barcode([0, 0, 1000, 200], "ean13")
    assert measure_font_sizes(cal, []) is None


def test_rule_9_stays_review_when_nothing_measurable():
    assert check_font_size({}, None)["status"] == REVIEW


# ── Readability ──────────────────────────────────────────────────────────
def _label(fg, bg):
    img = np.full((120, 400, 3), bg, dtype=np.uint8)
    cv2.putText(img, "MRP Rs 50", (12, 78), cv2.FONT_HERSHEY_SIMPLEX, 2.2, fg, 5)
    return img


def test_black_on_white_has_high_contrast():
    img = _label((0, 0, 0), (255, 255, 255))
    blocks = parse_text_blocks(
        [{"text": "MRP Rs 50", "x": 0, "y": 0, "width": 400, "height": 120}]
    )
    m = measure_readability(img, blocks)
    assert m is not None
    assert m["contrast_ratio"] > 10


def test_low_contrast_is_detected():
    # Light grey on white — the kind of print Rule 9(1)(b) exists to catch.
    img = _label((205, 205, 205), (255, 255, 255))
    blocks = parse_text_blocks(
        [{"text": "MRP Rs 50", "x": 0, "y": 0, "width": 400, "height": 120}]
    )
    m = measure_readability(img, blocks)
    assert m is not None
    assert m["contrast_ratio"] < 4.5


def test_readability_ignores_non_declaration_text():
    img = _label((0, 0, 0), (255, 255, 255))
    blocks = parse_text_blocks(
        [{"text": "decorative flourish", "x": 0, "y": 0, "width": 400, "height": 120}]
    )
    assert measure_readability(img, blocks) is None


def test_readability_returns_none_on_empty_image():
    blocks = parse_text_blocks(
        [{"text": "MRP", "x": 0, "y": 0, "width": 10, "height": 10}]
    )
    assert measure_readability(np.zeros((0, 0, 3), np.uint8), blocks) is None


def test_photo_readings_from_legible_packs_are_inconclusive():
    # Per-declaration ratios measured on two genuine Haldiram's packs (phone scans).
    for ratios in ([2.18, 3.13, 3.45, 3.77, 4.02], [2.86, 2.98, 3.38]):
        verdict = readability_verdict(ratios)
        assert verdict["inconclusive"] is True
        assert check_readability({}, verdict)["status"] == REVIEW


def test_uniformly_faint_label_still_fails():
    verdict = readability_verdict([1.2, 1.3, 1.25])
    assert verdict["inconclusive"] is False
    result = check_readability({}, verdict)
    assert result["status"] == FAIL
    assert "median" in result["failure_reason"]


def test_high_contrast_label_passes():
    assert check_readability({}, readability_verdict([6.0, 9.5]))["status"] == PASS


# ── Placement ────────────────────────────────────────────────────────────
def test_grouped_declarations_pass_placement():
    blocks = parse_text_blocks([
        {"text": "MRP Rs 50", "x": 100, "y": 100, "width": 80, "height": 20},
        {"text": "Net Wt 500g", "x": 100, "y": 130, "width": 80, "height": 20},
        {"text": "Best before 01/2027", "x": 100, "y": 160, "width": 80, "height": 20},
    ])
    m = measure_placement(blocks, 1000, 1000)
    assert m["on_principal_panel"] is True


def test_scattered_declarations_fail_placement():
    blocks = parse_text_blocks([
        {"text": "MRP Rs 50", "x": 10, "y": 10, "width": 60, "height": 20},
        {"text": "Net Wt 500g", "x": 930, "y": 960, "width": 60, "height": 20},
        {"text": "Best before 01/2027", "x": 20, "y": 950, "width": 60, "height": 20},
    ])
    m = measure_placement(blocks, 1000, 1000)
    assert m["on_principal_panel"] is False


def test_placement_declares_itself_a_proxy():
    blocks = parse_text_blocks([
        {"text": "MRP Rs 50", "x": 100, "y": 100, "width": 80, "height": 20},
        {"text": "Net Wt 500g", "x": 100, "y": 130, "width": 80, "height": 20},
    ])
    m = measure_placement(blocks, 1000, 1000)
    # Honesty about method matters as much as the verdict.
    assert m["method"] == "dispersion_proxy"
    assert "proxy" in m["note"]


def test_placement_needs_at_least_two_declarations():
    blocks = parse_text_blocks(
        [{"text": "MRP Rs 50", "x": 0, "y": 0, "width": 50, "height": 20}]
    )
    assert measure_placement(blocks, 1000, 1000) is None


# ── analyse() orchestration ──────────────────────────────────────────────
def test_analyse_omits_keys_it_cannot_measure():
    # No barcode -> no scale -> no font_size key -> rule 9 stays REVIEW.
    out = analyse(None, barcode_bbox=None, text_blocks=[
        {"text": "MRP Rs 50", "x": 0, "y": 0, "width": 100, "height": 40}
    ], image_width_px=800, image_height_px=800)
    assert "font_size" not in out
    assert out["calibration"]["usable"] is False


def test_analyse_produces_measurements_with_full_inputs():
    img = _label((0, 0, 0), (255, 255, 255))
    out = analyse(
        img,
        barcode_bbox=[0, 0, 1000, 200],
        barcode_format="ean13",
        text_blocks=[
            {"text": "MRP Rs 50", "x": 0, "y": 0, "width": 400, "height": 100},
            {"text": "Net Wt 500g", "x": 0, "y": 30, "width": 400, "height": 100},
        ],
        image_width_px=400,
        image_height_px=120,
    )
    assert out["calibration"]["usable"] is True
    assert "font_size" in out
    assert "readability" in out
    assert "placement" in out
