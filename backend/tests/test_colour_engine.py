"""Colour engine tests on synthetic card photos (demo/test_images).

Run:  cd backend && venv/Scripts/python.exe -m pytest tests/test_colour_engine.py -q -s
If the photos are missing they are generated first (demo/make_test_images.py).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.services import colour_engine as ce

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo"
IMAGES = DEMO / "test_images"
MANIFEST = IMAGES / "manifest.json"


def _profile(code, name, outcomes, max_de, margin):
    return {
        "code": code, "name": name, "max_delta_e": max_de, "min_margin": margin,
        "outcomes": [{"label": l, "category": c, "srgb": s, "lab": ce.srgb_to_lab(s)} for l, c, s in outcomes],
    }


PROFILES = {
    "DEMO-MARQUIS-SIM": _profile("DEMO-MARQUIS-SIM", "Marquis test (simulated swatches)", [
        ("Opium-type drug (purple)", "POSITIVE", [98, 45, 120]),
        ("Amphetamine-type drug (orange)", "POSITIVE", [178, 94, 40]),
        ("No reaction (no colour change)", "NEGATIVE", [236, 232, 214]),
    ], 14, 4),
    "DEMO-IODINE": _profile("DEMO-IODINE", "Iodine-Starch screen (live demo)", [
        ("Starch found (blue-black)", "POSITIVE", [40, 35, 60]),
        ("No starch (amber)", "NEGATIVE", [200, 130, 40]),
    ], 18, 5),
}

RESULT_KEYS = {"result", "outcome_label", "confidence", "reason", "measured_lab",
               "measured_rgb", "delta_e_by_outcome", "quality"}
QUALITY_KEYS = {"card_found", "markers_found", "blur_score", "glare_pct", "ccm_fit_de"}


@pytest.fixture(scope="module")
def results():
    if not MANIFEST.exists():
        subprocess.run([sys.executable, str(DEMO / "make_test_images.py")], check=True)
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = []
    for r in rows:
        res = ce.classify((IMAGES / r["file"]).read_bytes(), PROFILES[r["kit"]])
        out.append((r, res))

    print("\n{:<34} {:<9} {:<9} {:<13} {:<13} {:>6} {:>5}  {}".format(
        "image", "kind", "light", "expected", "got", "dE", "conf", "reason"))
    for r, res in out:
        d = min(res["delta_e_by_outcome"].values()) if res["delta_e_by_outcome"] else None
        print("{:<34} {:<9} {:<9} {:<13} {:<13} {:>6} {:>5}  {}".format(
            r["file"], r["kind"], r["lighting"], r["expected"], res["result"],
            "-" if d is None else f"{d:.1f}", res["confidence"], res["reason"] or ""))
    good = [(r, res) for r, res in out if r["kind"] == "good"]
    ok_good = sum(res["result"] == r["expected"] and res["outcome_label"] == r["expected_label"] for r, res in good)
    bad = [(r, res) for r, res in out if r["kind"] != "good"]
    ok_bad = sum(res["result"] == "INCONCLUSIVE" for r, res in bad)
    total_ok = ok_good + ok_bad
    print(f"\nGood-light accuracy : {ok_good}/{len(good)} = {100 * ok_good / len(good):.0f}%")
    print(f"Bad photos -> NOT SURE: {ok_bad}/{len(bad)} = {100 * ok_bad / len(bad):.0f}%")
    print(f"Overall accuracy    : {total_ok}/{len(out)} = {100 * total_ok / len(out):.0f}%")
    return out


def test_srgb_to_lab_white_and_black():
    assert ce.srgb_to_lab([255, 255, 255]) == pytest.approx([100, 0, 0], abs=0.05)
    assert ce.srgb_to_lab([0, 0, 0]) == pytest.approx([0, 0, 0], abs=0.05)


def test_ciede2000_reference_pairs():
    # Sharma, Wu & Dalal (2005) test data
    assert ce.delta_e2000([50, 2.6772, -79.7751], [50, 0, -82.7485]) == pytest.approx(2.0425, abs=1e-3)
    assert ce.delta_e2000([50, 2.5, 0], [73, 25, -18]) == pytest.approx(27.1492, abs=1e-3)
    assert ce.delta_e2000([2.0776, 0.0795, -1.1350], [0.9033, -0.0636, -0.5514]) == pytest.approx(0.9082, abs=1e-3)


def test_bad_bytes_is_inconclusive():
    res = ce.classify(b"not an image", PROFILES["DEMO-IODINE"])
    assert res["result"] == "INCONCLUSIVE" and res["reason"]
    assert set(res) == RESULT_KEYS


def test_output_shape(results):
    for _, res in results:
        assert set(res) == RESULT_KEYS
        assert set(res["quality"]) == QUALITY_KEYS
        assert 0 <= res["confidence"] <= 99
        if res["result"] == "INCONCLUSIVE":
            assert res["reason"] and res["outcome_label"] is None
        else:
            assert res["reason"] is None and len(res["measured_rgb"]) == 3


def test_good_light_accuracy(results):
    good = [(r, res) for r, res in results if r["kind"] == "good"]
    ok = sum(res["result"] == r["expected"] and res["outcome_label"] == r["expected_label"] for r, res in good)
    assert ok / len(good) >= 0.90


@pytest.mark.parametrize("kind", ["blurred", "glare", "missing", "ambiguous", "no_match"])
def test_bad_photos_never_guess(results, kind):
    rows = [(r, res) for r, res in results if r["kind"] == kind]
    assert rows
    for r, res in rows:
        assert res["result"] == "INCONCLUSIVE", r["file"]


def test_reasons_match_problem(results):
    by_file = {r["file"]: res for r, res in results}
    assert by_file["card_missing.jpg"]["reason"] == ce.REASONS["no_card"]
    assert by_file["marker_covered.jpg"]["reason"] == ce.REASONS["no_card"]
    assert by_file["marker_covered.jpg"]["quality"]["markers_found"] == 3
    assert by_file["glare_orange.jpg"]["reason"] == ce.REASONS["glare"]
    assert by_file["blurred_purple.jpg"]["reason"] == ce.REASONS["blur"]
