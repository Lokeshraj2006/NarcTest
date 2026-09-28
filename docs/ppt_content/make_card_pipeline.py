"""Make card_pipeline.png: how FieldProof finds the colour card and uses it to fix colours.

Re-runs the SAME steps as backend/app/services/colour_engine.measure() on one real
phone photo (imports the engine's own helper functions and thresholds), keeps the
in-between images, and draws a 4-panel figure. Prints every number it uses.

Run from repo root:
  backend/venv/Scripts/python.exe docs/ppt_content/make_card_pipeline.py [photo]
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.services import colour_engine as ce  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
PHOTO = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DIR / "real_tests" / "test_11.jpg"

# Marquis demo kit profile, exactly as seeded by backend/app/services/kit_service.py
PROFILE = {
    "max_delta_e": 14, "min_margin": 4,
    "outcomes": [
        {"label": "Opium-type drug (purple)", "category": "POSITIVE", "srgb": [98, 45, 120]},
        {"label": "Amphetamine-type drug (orange)", "category": "POSITIVE", "srgb": [178, 94, 40]},
        {"label": "No reaction (no colour change)", "category": "NEGATIVE", "srgb": [236, 232, 214]},
    ],
}
for o in PROFILE["outcomes"]:
    o["lab"] = [round(v, 2) for v in ce.srgb_to_lab(o["srgb"])]

# ------------------------------------------------------------------ step-by-step (same as measure())
T = ce.THRESHOLDS
spec = ce.load_spec()
image_bytes = PHOTO.read_bytes()
bgr = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)

scale, side, det_img = 1.0, max(bgr.shape[:2]), bgr
if side > T["max_image_side"]:
    scale = T["max_image_side"] / side
    det_img = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
found = ce._detect_markers(det_img, spec)
if len(found) < len(spec["markers"]) and scale == 1.0 and side > 1200:
    s2 = 1200 / side
    f2 = ce._detect_markers(cv2.resize(bgr, None, fx=s2, fy=s2, interpolation=cv2.INTER_AREA), spec)
    if len(f2) > len(found):
        found, scale = f2, s2
assert len(found) == 4, f"only {len(found)} markers found"
found_px = {i: c / scale for i, c in found.items()}  # corners in original photo pixels

ppm = spec["px_per_mm"]
src, dst = [], []
for m in spec["markers"]:
    x, y, s = m["x_mm"], m["y_mm"], m["size_mm"]
    dst.append(np.array([[x, y], [x + s, y], [x + s, y + s], [x, y + s]], float) * ppm)
    src.append(found_px[m["id"]])
H, _ = cv2.findHomography(np.vstack(src).astype(np.float32), np.vstack(dst).astype(np.float32), 0)
W, Hh = int(spec["card_w_mm"] * ppm), int(spec["card_h_mm"] * ppm)
warped = cv2.warpPerspective(bgr, H, (W, Hh), flags=cv2.INTER_LINEAR)
rgb = cv2.cvtColor(warped, cv2.COLOR_BGR2RGB)

grey = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
k = T["blur_px_per_mm"]
small = cv2.resize(grey, (int(spec["card_w_mm"] * k), int(spec["card_h_mm"] * k)), interpolation=cv2.INTER_AREA)
blur = float(cv2.Laplacian(small, cv2.CV_64F).var())

measured = np.array([ce._median_rgb(rgb, ce._rect_px(p, ppm, T["patch_inner"])) for p in spec["patches"]]) / 255.0
known = np.array([p["srgb"] for p in spec["patches"]], float) / 255.0
m_lin, k_lin = ce._srgb_to_linear(measured), ce._srgb_to_linear(known)
A = np.hstack([m_lin, np.ones((len(m_lin), 1))])
X, *_ = np.linalg.lstsq(A, k_lin, rcond=None)
corrected = np.clip(A @ X, 0, 1)
patch_de_before = ce._de2000(ce._linear_to_lab(m_lin), ce._linear_to_lab(k_lin))
patch_de_after = ce._de2000(ce._linear_to_lab(corrected), ce._linear_to_lab(k_lin))
fit = float(np.mean(patch_de_after))

win_raw = ce._median_rgb(rgb, ce._rect_px(spec["window"], ppm, T["window_inner"])) / 255.0
win_lin = np.clip(np.append(ce._srgb_to_linear(win_raw), 1.0) @ X, 0, 1)
lab_after = ce._linear_to_lab(win_lin)
rgb_after = np.round(ce._linear_to_srgb(win_lin) * 255).astype(int)
rgb_before = np.round(win_raw * 255).astype(int)
lab_before = ce._linear_to_lab(ce._srgb_to_linear(win_raw))

# the real engine, end to end, as a cross-check
res = ce.classify(image_bytes, PROFILE)
de_after = res["delta_e_by_outcome"]
de_before = {o["label"]: round(ce.delta_e2000(lab_before, o["lab"]), 2) for o in PROFILE["outcomes"]}

numbers = {
    "photo": PHOTO.name,
    "photo_size": [int(bgr.shape[1]), int(bgr.shape[0])],
    "markers_found": len(found), "marker_ids": sorted(int(i) for i in found),
    "detection_scale": round(scale, 3),
    "blur_score": round(blur, 1), "blur_min": T["min_blur_score"],
    "ccm_fit_de": round(fit, 2), "ccm_fit_max": T["max_ccm_fit_de"],
    "patch_de_before_mean": round(float(np.mean(patch_de_before)), 2),
    "patch_de_after_mean": round(float(np.mean(patch_de_after)), 2),
    "window_rgb_before": rgb_before.tolist(), "window_lab_before": [round(float(v), 2) for v in lab_before],
    "window_rgb_after": rgb_after.tolist(), "window_lab_after": [round(float(v), 2) for v in lab_after],
    "de_before_correction": de_before,
    "engine_result": {k2: res[k2] for k2 in ("result", "outcome_label", "confidence", "reason",
                                             "measured_rgb", "measured_lab", "delta_e_by_outcome", "quality")},
    "outcome_labs": {o["label"]: o["lab"] for o in PROFILE["outcomes"]},
}
print(json.dumps(numbers, indent=1))
(OUT_DIR / "card_pipeline_numbers.json").write_text(json.dumps(numbers, indent=1), encoding="utf-8")

# ------------------------------------------------------------------ drawing
FONT_DIR = Path("C:/Windows/Fonts")
def F(size, bold=False):
    return ImageFont.truetype(str(FONT_DIR / ("arialbd.ttf" if bold else "arial.ttf")), size)

INK, MUTED, GREEN, RED, LINE = (25, 25, 35), (95, 95, 110), (20, 150, 60), (200, 40, 40), (210, 210, 215)
CW, CH = 2400, 1000
fig = Image.new("RGB", (CW, CH), "white")
d = ImageDraw.Draw(fig)

def pil(img_bgr):
    return Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))

def fit_into(im, w, h):
    r = min(w / im.width, h / im.height)
    return im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)

def header(x, num, title, w):
    d.ellipse([x, 22, x + 62, 84], fill=INK)
    tw = d.textlength(str(num), font=F(38, True))
    d.text((x + 31 - tw / 2, 32), str(num), font=F(38, True), fill="white")
    # wrap title into max 2 lines
    words, lines, cur = title.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if d.textlength(t, font=F(34, True)) > w - 80 and cur:
            lines.append(cur); cur = wd
        else:
            cur = t
    lines.append(cur)
    for i, ln in enumerate(lines):
        d.text((x + 76, 20 + i * 40), ln, font=F(34, True), fill=INK)

def centred(text, cx, y, font, fill=INK):
    d.text((cx - d.textlength(text, font=font) / 2, y), text, font=font, fill=fill)

# panel geometry
PX = [30, 620, 1210, 1790]
PW = [560, 560, 550, 580]
TOP = 120
for x in PX[1:]:
    d.line([x - 20, 30, x - 20, CH - 115], fill=LINE, width=3)

# ---- panel 1: original photo (cropped around the card) + markers
ann = bgr.copy()
for mid, c in found_px.items():
    pts = c.astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(ann, [pts], True, (40, 200, 40), 12)
    cx = int(c[:, 0].mean())
    top = mid in (0, 1)  # label above top markers, below bottom markers
    ly = int(c[:, 1].min() - 20) if top else int(c[:, 1].max() + 20)
    txt = f"ID {mid}"
    (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 1.6, 4)
    bx0, by0 = cx - tw // 2 - 12, (ly - th - 24) if top else ly
    cv2.rectangle(ann, (bx0, by0), (bx0 + tw + 24, by0 + th + 24), (40, 170, 40), -1)
    cv2.putText(ann, txt, (bx0 + 12, by0 + th + 12), cv2.FONT_HERSHEY_DUPLEX, 1.6, (255, 255, 255), 4)
allc = np.vstack(list(found_px.values()))
x0, y0 = allc.min(axis=0); x1, y1 = allc.max(axis=0)
pad_x, pad_y = 0.06 * (x1 - x0), 0.30 * (y1 - y0)
crop = ann[max(0, int(y0 - pad_y)):min(ann.shape[0], int(y1 + pad_y)),
           max(0, int(x0 - pad_x)):min(ann.shape[1], int(x1 + pad_x))]
header(PX[0], 1, "Find the 4 corner squares", PW[0])
im1 = fit_into(pil(crop), PW[0], 600)
fig.paste(im1, (PX[0] + (PW[0] - im1.width) // 2, TOP + 20))
d.rectangle([PX[0] + (PW[0] - im1.width) // 2, TOP + 20, PX[0] + (PW[0] + im1.width) // 2, TOP + 20 + im1.height],
            outline=LINE, width=2)
yb = TOP + 40 + im1.height
d.text((PX[0], yb), f"Found {len(found)} of 4 markers", font=F(34, True), fill=GREEN)
d.text((PX[0], yb + 50), "Real phone photo, cropped", font=F(28), fill=MUTED)
d.text((PX[0], yb + 88), "(card shown on a laptop screen)", font=F(28), fill=MUTED)

# ---- panel 2: warped card
header(PX[1], 2, "Straighten the card", PW[1])
im2 = fit_into(pil(warped), PW[1], 400)
fig.paste(im2, (PX[1], TOP + 20))
d.rectangle([PX[1], TOP + 20, PX[1] + im2.width, TOP + 20 + im2.height], outline=LINE, width=2)
yb = TOP + 50 + im2.height
for i, ln in enumerate(["Tilted photo becomes a flat,",
                        "straight card, every time.",
                        "Now every colour box is",
                        "at a known place."]):
    d.text((PX[1], yb + i * 44), ln, font=F(30), fill=INK)
d.text((PX[1], yb + 4 * 44 + 20), f"Sharpness score {blur:.0f}", font=F(32, True), fill=GREEN)
d.text((PX[1], yb + 4 * 44 + 64), f"(needs {T['min_blur_score']:.0f} or more)", font=F(28), fill=MUTED)

# ---- panel 3: patches circled + before/after strip
header(PX[2], 3, "Learn the light from 24 known colours", PW[2])
circ = warped.copy()
for p in spec["patches"]:
    cx = int((p["x_mm"] + p["w_mm"] / 2) * ppm); cy = int((p["y_mm"] + p["h_mm"] / 2) * ppm)
    cv2.circle(circ, (cx, cy), 30, (255, 255, 255), 9)
    cv2.circle(circ, (cx, cy), 30, (20, 20, 20), 4)
wx0, wy0, wx1, wy1 = ce._rect_px(spec["window"], ppm, T["window_inner"])
im3 = fit_into(pil(circ), PW[2], 350)
fig.paste(im3, (PX[2], TOP + 20))
d.rectangle([PX[2], TOP + 20, PX[2] + im3.width, TOP + 20 + im3.height], outline=LINE, width=2)

strip_ids = ["P07", "P08", "P10", "P14", "P15", "P16"]
idx = {p["id"]: i for i, p in enumerate(spec["patches"])}
sy = TOP + 20 + im3.height + 30
lbl_w, sw, gap = 150, 58, 10
rows = [("Camera", measured), ("Fixed", ce._linear_to_srgb(corrected)), ("True", known)]
for r, (name, arr) in enumerate(rows):
    y = sy + r * 74
    d.text((PX[2], y + 12), name, font=F(30, True), fill=INK)
    for j, pid in enumerate(strip_ids):
        col = tuple(int(round(v * 255)) for v in np.clip(arr[idx[pid]], 0, 1))
        xx = PX[2] + lbl_w + j * (sw + gap)
        d.rectangle([xx, y, xx + sw, y + 60], fill=col, outline=(150, 150, 150), width=1)
yb = sy + 3 * 74 + 10
d.text((PX[2], yb), f"Avg error of 24 boxes:", font=F(30), fill=INK)
d.text((PX[2], yb + 42), f"{np.mean(patch_de_before):.1f} before  →  {fit:.1f} after",
       font=F(32, True), fill=GREEN)
d.text((PX[2], yb + 86), f"(dE2000, must be {T['max_ccm_fit_de']:.0f} or less)", font=F(28), fill=MUTED)

# ---- panel 4: window before/after + dE bars + result
header(PX[3], 4, "Fix the kit colour and compare", PW[3])
cy0 = TOP + 20
chip = 150
for j, (name, col) in enumerate([("Before", rgb_before), ("After", rgb_after)]):
    xx = PX[3] + 30 + j * 280
    d.rectangle([xx, cy0, xx + chip, cy0 + chip], fill=tuple(int(v) for v in col), outline=(120, 120, 120), width=2)
    centred(name, xx + chip / 2, cy0 + chip + 8, F(30, True))
    centred(f"RGB {col[0]},{col[1]},{col[2]}", xx + chip / 2, cy0 + chip + 46, F(28), MUTED)
d.text((PX[3] + 30 + chip + 42, cy0 + chip / 2 - 34), "→", font=F(60, True), fill=INK)

by = cy0 + chip + 110
d.text((PX[3], by), "Colour gap (dE2000) to each result:", font=F(30, True), fill=INK)
short = {"Opium-type drug (purple)": "Opium-type (purple)",
         "Amphetamine-type drug (orange)": "Amphetamine-type (orange)",
         "No reaction (no colour change)": "No reaction"}
bar_x, bar_w, vmax = PX[3] + 10, PW[3] - 110, 75.0
limit = PROFILE["max_delta_e"]
by += 50
lx = bar_x + int(bar_w * limit / vmax)
for i, o in enumerate(PROFILE["outcomes"]):
    y = by + i * 92
    val = de_after[o["label"]]
    best = o["label"] == res["outcome_label"]
    d.text((bar_x, y), short[o["label"]], font=F(28, best), fill=INK)
    bw = max(4, int(bar_w * min(val, vmax) / vmax))
    d.rectangle([bar_x, y + 36, bar_x + bw, y + 72], fill=tuple(o["srgb"]), outline=(150, 150, 150))
    d.line([lx, y + 30, lx, y + 78], fill=RED, width=4)
    d.text((max(bar_x + bw, lx) + 10, y + 36), f"{val:.1f}", font=F(30, True), fill=INK)
d.text((lx - 40, by + 3 * 92 - 12), f"limit {limit}", font=F(28, True), fill=RED)
ry = by + 3 * 92 + 30
d.rounded_rectangle([PX[3], ry, PX[3] + PW[3], ry + 110], radius=16, fill=(240, 248, 242), outline=GREEN, width=3)
d.text((PX[3] + 20, ry + 10), f"{res['result']}: {short.get(res['outcome_label'], res['outcome_label'])}",
       font=F(34, True), fill=INK)
d.text((PX[3] + 20, ry + 60), f"Confidence {res['confidence']}%   (simulated swatch)", font=F(28), fill=MUTED)

d.line([30, CH - 95, CW - 30, CH - 95], fill=LINE, width=2)
centred(f"Real phone photo ({PHOTO.name}), all numbers from the FieldProof colour engine. "
        "Swatch is SIMULATED (card shown on a laptop screen), not a real drug sample.",
        CW / 2, CH - 72, F(30), MUTED)
out = OUT_DIR / "card_pipeline.png"
fig.save(out, optimize=True)
print("saved", out, fig.size)
