"""FieldProof - make synthetic test photos of the colour card.

Run:  backend/venv/Scripts/python.exe demo/make_test_images.py

Writes demo/test_images/*.jpg and demo/test_images/manifest.json (+ manifest.csv)
with the expected result for every photo. These are fake photos for testing
the colour engine only.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from make_card import build_spec, render_card_rgb  # noqa: E402

OUT = HERE / "test_images"
FRAME_W, FRAME_H = 1600, 1200

MARQUIS = {
    "purple": ("Opium-type drug (purple)", "POSITIVE", [98, 45, 120]),
    "orange": ("Amphetamine-type drug (orange)", "POSITIVE", [178, 94, 40]),
    "noreact": ("No reaction (no colour change)", "NEGATIVE", [236, 232, 214]),
}
IODINE = {
    "starch": ("Starch found (blue-black)", "POSITIVE", [40, 35, 60]),
    "amber": ("No starch (amber)", "NEGATIVE", [200, 130, 40]),
}
AMBIGUOUS = [138, 70, 80]
NO_MATCH = [60, 160, 80]

# name -> (per-channel gain in linear RGB, noise sigma in 0-255 units)
LIGHTS = {
    "daylight": ([0.92, 0.92, 0.92], 2.0),
    "tungsten": ([0.95, 0.74, 0.48], 2.5),
    "cool": ([0.70, 0.84, 0.97], 2.5),
    "dim": ([0.46, 0.46, 0.46], 5.0),
    "sodium": ([0.97, 0.60, 0.20], 3.0),
}


def to_lin(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def table_background(rng) -> np.ndarray:
    base = rng.integers(90, 150)
    tint = np.array([1.0, 0.95, 0.85]) if rng.random() < 0.5 else np.array([0.95, 0.95, 0.95])
    noise = rng.normal(0, 1, (FRAME_H // 8, FRAME_W // 8))
    noise = cv2.resize(noise, (FRAME_W, FRAME_H), interpolation=cv2.INTER_CUBIC)
    grain = np.sin(np.linspace(0, 40, FRAME_W))[None, :] * 6
    bg = base + noise[..., None] * 10 + grain[..., None]
    return np.clip(bg * tint, 0, 255).astype(np.uint8)


def place_card(card: np.ndarray, rng, frac=None) -> tuple[np.ndarray, np.ndarray]:
    """Perspective-warp the card onto the table. Returns (rgb frame, card corners)."""
    h, w = card.shape[:2]
    frac = frac or rng.uniform(0.40, 0.70)
    cw = FRAME_W * frac
    ch = cw * h / w
    ang = np.radians(rng.uniform(-15, 15))
    cx = FRAME_W / 2 + rng.uniform(-0.5, 0.5) * (FRAME_W - cw) * 0.6
    cy = FRAME_H / 2 + rng.uniform(-0.5, 0.5) * (FRAME_H - ch) * 0.4
    pts = np.array([[-cw / 2, -ch / 2], [cw / 2, -ch / 2], [cw / 2, ch / 2], [-cw / 2, ch / 2]])
    rot = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    pts = pts @ rot.T
    # tilt: shrink the far edge a bit (phone not exactly overhead)
    tilt = rng.uniform(0.0, 0.12)
    if rng.random() < 0.5:
        pts[0] *= (1 - tilt)
        pts[1] *= (1 - tilt)
    else:
        pts[1] *= (1 - tilt)
        pts[2] *= (1 - tilt)
    pts += rng.normal(0, cw * 0.01, pts.shape)
    pts += [cx, cy]
    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    H = cv2.getPerspectiveTransform(src, pts.astype(np.float32))
    frame = table_background(rng)
    warped = cv2.warpPerspective(card, H, (FRAME_W, FRAME_H), flags=cv2.INTER_AREA)
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), H, (FRAME_W, FRAME_H))
    mask = (mask.astype(np.float32) / 255.0)[..., None]
    frame = (warped * mask + frame * (1 - mask)).astype(np.uint8)
    return frame, pts


def apply_light(rgb: np.ndarray, light: str, rng) -> np.ndarray:
    gains, sigma = LIGHTS[light]
    lin = to_lin(rgb.astype(np.float64) / 255.0)
    # mild camera channel crosstalk
    mix = np.array([[0.94, 0.05, 0.01], [0.03, 0.94, 0.03], [0.01, 0.06, 0.93]])
    lin = lin @ mix.T
    lin = lin * np.array(gains)
    # gentle light fall-off across the frame (+/- 4 %)
    xs = np.linspace(-1, 1, rgb.shape[1])[None, :, None]
    lin = lin * (1 + 0.04 * xs * rng.choice([-1, 1]))
    out = to_srgb(lin) * 255 + rng.normal(0, sigma, rgb.shape)
    return np.clip(out, 0, 255).astype(np.uint8)


def save(name: str, rgb: np.ndarray) -> str:
    fn = f"{name}.jpg"
    cv2.imwrite(str(OUT / fn), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
    return fn


def main() -> None:
    OUT.mkdir(exist_ok=True)
    spec = build_spec()
    ppm = spec["px_per_mm"]
    rng = np.random.default_rng(2026)
    rows = []

    def add(name, kit, light, expected, label, kind, rgb):
        rows.append({"file": save(name, rgb), "kit": kit, "lighting": light, "kind": kind,
                     "expected": expected, "expected_label": label})

    def photo(window_rgb, light, frac=None):
        frame, pts = place_card(render_card_rgb(spec, window_rgb), rng, frac)
        return apply_light(frame, light, rng), pts

    # 1) good photos, every outcome under every light
    for kit, table in (("DEMO-MARQUIS-SIM", MARQUIS), ("DEMO-IODINE", IODINE)):
        for key, (label, cat, rgb) in table.items():
            for light in LIGHTS:
                img, _ = photo(rgb, light)
                add(f"{kit.split('-')[1].lower()}_{key}_{light}", kit, light, cat, label, "good", img)

    # 2) ambiguous and no-match swatches
    for light in ("daylight", "tungsten"):
        img, _ = photo(AMBIGUOUS, light)
        add(f"marquis_ambiguous_{light}", "DEMO-MARQUIS-SIM", light, "INCONCLUSIVE", None, "ambiguous", img)
    for light in ("daylight", "cool"):
        img, _ = photo(NO_MATCH, light)
        add(f"marquis_nomatch_{light}", "DEMO-MARQUIS-SIM", light, "INCONCLUSIVE", None, "no_match", img)

    # 3) blurred: soft (card still found, blur check fails) and very blurred (card lost)
    for key, kit, table in (("purple", "DEMO-MARQUIS-SIM", MARQUIS), ("starch", "DEMO-IODINE", IODINE),
                            ("orange", "DEMO-MARQUIS-SIM", MARQUIS)):
        img, _ = photo(table[key][2], "daylight", 0.65)
        add(f"blurred_{key}", kit, "daylight", "INCONCLUSIVE", None, "blurred",
            cv2.GaussianBlur(img, (0, 0), 3.5))
    img, _ = photo(MARQUIS["noreact"][2], "daylight")
    add("blurred_heavy_noreact", "DEMO-MARQUIS-SIM", "daylight", "INCONCLUSIVE", None, "blurred",
        cv2.GaussianBlur(img, (41, 41), 12))

    # 4) glare blob over the window
    for key, kit, table in (("orange", "DEMO-MARQUIS-SIM", MARQUIS), ("amber", "DEMO-IODINE", IODINE)):
        card = render_card_rgb(spec, table[key][2])
        h, w = card.shape[:2]
        frame, pts = place_card(card, rng, 0.6)
        img = apply_light(frame, "daylight", rng)
        H = cv2.getPerspectiveTransform(np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32),
                                        pts.astype(np.float32))
        win = spec["window"]
        c = np.array([[[(win["x_mm"] + win["w_mm"] / 2) * ppm, (win["y_mm"] + win["h_mm"] / 2) * ppm]]],
                     np.float32)
        cx, cy = cv2.perspectiveTransform(c, H)[0, 0]
        blob = np.zeros(img.shape[:2], np.float32)
        ax = int(win["w_mm"] * ppm * 0.6 * 0.6 * 0.6)
        cv2.ellipse(blob, (int(cx), int(cy)), (int(ax * 1.6), ax), 25, 0, 360, 1.0, -1)
        blob = cv2.GaussianBlur(blob, (31, 31), 8)[..., None]
        img = np.clip(img * (1 - blob) + 255 * blob, 0, 255).astype(np.uint8)
        add(f"glare_{key}", kit, "daylight", "INCONCLUSIVE", None, "glare", img)

    # 5) card missing: table + a coloured square
    frame = table_background(rng)
    cv2.rectangle(frame, (600, 400), (1000, 800), (98, 45, 120), -1)
    add("card_missing", "DEMO-MARQUIS-SIM", "daylight", "INCONCLUSIVE", None, "missing",
        apply_light(frame, "daylight", rng))

    # 6) one corner marker covered (thumb / paper over it)
    card = render_card_rgb(spec, MARQUIS["purple"][2])
    m = spec["markers"][2]
    x, y, s = (int(v * ppm) for v in (m["x_mm"], m["y_mm"], m["size_mm"]))
    cv2.rectangle(card, (x - 10, y - 10), (x + s + 10, y + s + 10), (205, 160, 140), -1)
    frame, _ = place_card(card, rng)
    add("marker_covered", "DEMO-MARQUIS-SIM", "daylight", "INCONCLUSIVE", None, "missing",
        apply_light(frame, "daylight", rng))

    (OUT / "manifest.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with open(OUT / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"Wrote {len(rows)} test photos to {OUT}")


if __name__ == "__main__":
    main()
