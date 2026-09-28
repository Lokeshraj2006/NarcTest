"""FieldProof - make the printed reference colour card.

Run:  backend/venv/Scripts/python.exe demo/make_card.py

Creates (in demo/):
  card_spec.json          - layout of the card (also copied to backend/app/services/)
  reference_card.pdf      - A4 landscape, card at 100% scale. Print this.
  reference_card.png      - picture preview of the card
  fake_kit_swatches.pdf   - one full card per demo swatch (SIMULATED - demo only)
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BACKEND_SPEC = ROOT / "backend" / "app" / "services" / "card_spec.json"

CARD_W_MM, CARD_H_MM, PX_PER_MM = 190, 120, 8
MARKERS = [
    {"id": 0, "corner": "tl", "x_mm": 5, "y_mm": 5, "size_mm": 22},
    {"id": 1, "corner": "tr", "x_mm": 163, "y_mm": 5, "size_mm": 22},
    {"id": 2, "corner": "br", "x_mm": 163, "y_mm": 93, "size_mm": 22},
    {"id": 3, "corner": "bl", "x_mm": 5, "y_mm": 93, "size_mm": 22},
]

# ColorChecker-like sRGB values (row by row, 6 per row)
CHECKER = [
    [115, 82, 68], [194, 150, 130], [98, 122, 157], [87, 108, 67], [133, 128, 177], [103, 189, 170],
    [214, 126, 44], [80, 91, 166], [193, 90, 99], [94, 60, 108], [157, 188, 64], [224, 163, 46],
    [56, 61, 150], [70, 148, 73], [175, 54, 60], [231, 199, 31], [187, 86, 149], [8, 133, 161],
    [243, 243, 242], [200, 200, 200], [160, 160, 160], [122, 122, 121], [85, 85, 85], [52, 52, 52],
]
WHITE_PATCH_ID = "P19"

PATCH_X0, PATCH_Y0, PATCH_W, PATCH_H, GAP = 30, 20, 13, 18, 2
WINDOW = {"x_mm": 122, "y_mm": 37, "w_mm": 45, "h_mm": 45}

# Demo swatches (CONTRACT section 3)
SWATCHES = [
    ("Opium-type drug (purple)", [98, 45, 120]),
    ("Amphetamine-type drug (orange)", [178, 94, 40]),
    ("No reaction (no colour change)", [236, 232, 214]),
    ("AMBIGUOUS (in between purple and orange)", [138, 70, 80]),
    ("NO-MATCH (green, not a result of this kit)", [60, 160, 80]),
]

TITLE = "FieldProof reference colour card v1"
FOOTER = "FieldProof reference colour card v1 - print at 100%, matte paper"


def build_spec() -> dict:
    patches = []
    for i, rgb in enumerate(CHECKER):
        r, c = divmod(i, 6)
        patches.append({
            "id": f"P{i + 1:02d}",
            "x_mm": PATCH_X0 + c * (PATCH_W + GAP),
            "y_mm": PATCH_Y0 + r * (PATCH_H + GAP),
            "w_mm": PATCH_W, "h_mm": PATCH_H,
            "srgb": rgb,
        })
    return {
        "version": 1,
        "card_w_mm": CARD_W_MM, "card_h_mm": CARD_H_MM,
        "px_per_mm": PX_PER_MM,
        "aruco_dict": "DICT_4X4_50",
        "markers": MARKERS,
        "patches": patches,
        "window": dict(WINDOW),
        "white_patch_id": WHITE_PATCH_ID,
    }


def check_no_overlap(spec: dict) -> None:
    rects = [(f"M{m['id']}", m["x_mm"], m["y_mm"], m["size_mm"], m["size_mm"]) for m in spec["markers"]]
    rects += [(p["id"], p["x_mm"], p["y_mm"], p["w_mm"], p["h_mm"]) for p in spec["patches"]]
    w = spec["window"]
    rects.append(("WINDOW", w["x_mm"], w["y_mm"], w["w_mm"], w["h_mm"]))
    for name, x, y, ww, hh in rects:
        assert x >= 0 and y >= 0 and x + ww <= spec["card_w_mm"] and y + hh <= spec["card_h_mm"], name
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            if a[1] < b[1] + b[3] and b[1] < a[1] + a[3] and a[2] < b[2] + b[4] and b[2] < a[2] + a[4]:
                raise AssertionError(f"overlap {a[0]} / {b[0]}")


def marker_bits(marker_id: int) -> np.ndarray:
    """6x6 array (1 = white) incl. 1-cell black border."""
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    img = cv2.aruco.generateImageMarker(d, marker_id, 6, borderBits=1)
    return (img > 127).astype(np.uint8)


# ---------------------------------------------------------------- raster
def render_card_rgb(spec: dict, window_rgb=None, caption: str | None = None) -> np.ndarray:
    """Return the card as an RGB uint8 image at px_per_mm."""
    ppm = spec["px_per_mm"]
    W, H = spec["card_w_mm"] * ppm, spec["card_h_mm"] * ppm
    img = np.full((H, W, 3), 255, np.uint8)
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    for m in spec["markers"]:
        s = int(m["size_mm"] * ppm)
        mk = cv2.aruco.generateImageMarker(d, m["id"], s, borderBits=1)
        x, y = int(m["x_mm"] * ppm), int(m["y_mm"] * ppm)
        img[y:y + s, x:x + s] = mk[:, :, None]
    for p in spec["patches"]:
        x, y = int(p["x_mm"] * ppm), int(p["y_mm"] * ppm)
        img[y:y + int(p["h_mm"] * ppm), x:x + int(p["w_mm"] * ppm)] = p["srgb"]
    w = spec["window"]
    x, y, ww, hh = (int(w[k] * ppm) for k in ("x_mm", "y_mm", "w_mm", "h_mm"))
    if window_rgb is not None:
        img[y:y + hh, x:x + ww] = window_rgb
    # dashed border
    step = 3 * ppm
    for t in range(0, ww, step):
        cv2.line(img, (x + t, y), (x + min(t + step // 2, ww), y), (60, 60, 60), 2)
        cv2.line(img, (x + t, y + hh), (x + min(t + step // 2, ww), y + hh), (60, 60, 60), 2)
    for t in range(0, hh, step):
        cv2.line(img, (x, y + t), (x, y + min(t + step // 2, hh)), (60, 60, 60), 2)
        cv2.line(img, (x + ww, y + t), (x + ww, y + min(t + step // 2, hh)), (60, 60, 60), 2)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, "PLACE KIT RESULT HERE", (x, y - int(2 * ppm)), font, 0.62, (30, 30, 30), 2, cv2.LINE_AA)
    cv2.putText(img, TITLE, (30 * ppm, 14 * ppm), font, 0.9, (30, 30, 30), 2, cv2.LINE_AA)
    cv2.putText(img, FOOTER, (30 * ppm, 108 * ppm), font, 0.6, (80, 80, 80), 1, cv2.LINE_AA)
    if caption:
        cv2.putText(img, caption[:40], (x, y + hh + int(5 * ppm)), font, 0.45, (200, 0, 0), 1, cv2.LINE_AA)
    return img


# ---------------------------------------------------------------- PDF
def draw_card_pdf(c, spec: dict, window_rgb=None, caption: str | None = None) -> None:
    from reportlab.lib.units import mm

    page_w, page_h = 297 * mm, 210 * mm
    ox = (297 - spec["card_w_mm"]) / 2
    oy = (210 - spec["card_h_mm"]) / 2

    def rect(x_mm, y_mm, w_mm, h_mm, **kw):
        c.rect((ox + x_mm) * mm, page_h - (oy + y_mm + h_mm) * mm, w_mm * mm, h_mm * mm, **kw)

    def text(x_mm, y_mm, s, size, font="Helvetica", colour=(0, 0, 0)):
        c.setFont(font, size)
        c.setFillColorRGB(*colour)
        c.drawString((ox + x_mm) * mm, page_h - (oy + y_mm) * mm, s)

    # cut line
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.setLineWidth(0.3)
    c.setDash()
    rect(0, 0, spec["card_w_mm"], spec["card_h_mm"], stroke=1, fill=0)
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(ox * mm, page_h - (oy - 3) * mm, "cut along the grey line")

    # markers (vector, 6x6 cells)
    for m in spec["markers"]:
        bits = marker_bits(m["id"])
        cell = m["size_mm"] / 6.0
        for r in range(6):
            for col in range(6):
                if bits[r, col] == 0:
                    c.setFillColorRGB(0, 0, 0)
                    rect(m["x_mm"] + col * cell, m["y_mm"] + r * cell, cell + 0.02, cell + 0.02, stroke=0, fill=1)
    # patches
    for p in spec["patches"]:
        c.setFillColorRGB(*[v / 255 for v in p["srgb"]])
        rect(p["x_mm"], p["y_mm"], p["w_mm"], p["h_mm"], stroke=0, fill=1)
    # window
    w = spec["window"]
    if window_rgb is not None:
        c.setFillColorRGB(*[v / 255 for v in window_rgb])
        rect(w["x_mm"], w["y_mm"], w["w_mm"], w["h_mm"], stroke=0, fill=1)
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.setLineWidth(0.6)
    c.setDash(3, 2)
    rect(w["x_mm"], w["y_mm"], w["w_mm"], w["h_mm"], stroke=1, fill=0)
    c.setDash()
    text(w["x_mm"], w["y_mm"] - 1.5, "PLACE KIT RESULT HERE", 8, "Helvetica-Bold")
    text(30, 14, TITLE, 11, "Helvetica-Bold")
    text(30, 108, FOOTER, 7, colour=(0.3, 0.3, 0.3))
    if caption:
        text(w["x_mm"], w["y_mm"] + w["h_mm"] + 4, caption[:48], 6, "Helvetica-Bold", colour=(0.75, 0, 0))
        c.setFont("Helvetica-Bold", 14)
        c.setFillColorRGB(0.75, 0, 0)
        c.drawString(ox * mm, page_h - (oy + spec["card_h_mm"] + 10) * mm, caption)


def main() -> None:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    spec = build_spec()
    check_no_overlap(spec)
    (HERE / "card_spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    shutil.copyfile(HERE / "card_spec.json", BACKEND_SPEC)

    c = canvas.Canvas(str(HERE / "reference_card.pdf"), pagesize=landscape(A4))
    c.setTitle("FieldProof reference colour card v1")
    draw_card_pdf(c, spec)
    c.showPage()
    c.save()

    png = render_card_rgb(spec)
    cv2.imwrite(str(HERE / "reference_card.png"), cv2.cvtColor(png, cv2.COLOR_RGB2BGR))

    c = canvas.Canvas(str(HERE / "fake_kit_swatches.pdf"), pagesize=landscape(A4))
    c.setTitle("FieldProof SIMULATED kit swatches - demo only")
    for name, rgb in SWATCHES:
        draw_card_pdf(c, spec, rgb, f"SIMULATED - demo only: {name}")
        c.showPage()
    c.save()
    print("Wrote card_spec.json, reference_card.pdf/.png, fake_kit_swatches.pdf in", HERE)


if __name__ == "__main__":
    main()
