"""Minimal redraw of 3 slide images (same real numbers as the old ones).

  validation_min.png     2400 x 1040   from validation_results.json (+ tamper tests in validation.md)
  card_pipeline_min.png  2400 x 1000   re-runs colour_engine steps on real_tests/test_11.jpg
  security_legal_min.png 2400 x 660    facts from security_privacy_legal.md

Style: white, near-black text, grey secondary, thin #D9D9D9 rules, one accent (#7A2F00).
No icons, pills, shadows, gradients or fills. Only colour that is data (kit swatches) is coloured.

Run from repo root:
  backend/venv/Scripts/python.exe docs/ppt_content/make_minimal_images.py
Old images are not touched. The script checks every text box for overlap / clipping.
"""
import json
import statistics as st
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

INK, GREY, RULE = (0x1F, 0x1F, 0x1F), (0x6B, 0x6B, 0x6B), (0xD9, 0xD9, 0xD9)
ACC, TAN = (0x7A, 0x2F, 0x00), (0xCE, 0xAB, 0x6B)
BORDER = (0xB0, 0xB0, 0xB0)  # 1 px swatch border only
FONT = "C:/Windows/Fonts/arial.ttf"
FONTB = "C:/Windows/Fonts/arialbd.ttf"
MIN_BODY = 30


def F(size, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, size)


class Canvas:
    """Pillow canvas that remembers every text / image box so we can check overlaps."""

    def __init__(self, w, h, margin=60):
        self.w, self.h, self.margin = w, h, margin
        self.im = Image.new("RGB", (w, h), "white")
        self.d = ImageDraw.Draw(self.im)
        self.boxes = []  # (name, (x0,y0,x1,y1))

    def text(self, xy, s, size, bold=False, fill=INK, anchor="ls", name=None):
        assert size >= MIN_BODY, (s, size)
        f = F(size, bold)
        self.d.text(xy, s, font=f, fill=fill, anchor=anchor)
        bb = self.d.textbbox(xy, s, font=f, anchor=anchor)
        self.boxes.append((name or s, bb))
        return bb

    def width(self, s, size, bold=False):
        return self.d.textlength(s, font=F(size, bold))

    def paste(self, img, xy, name):
        self.im.paste(img, xy)
        bb = (xy[0], xy[1], xy[0] + img.width, xy[1] + img.height)
        self.d.rectangle([bb[0], bb[1], bb[2] - 1, bb[3] - 1], outline=RULE, width=2)
        self.boxes.append((name, bb))
        return bb

    def block(self, bb, name):
        self.boxes.append((name, bb))

    def check(self, label):
        problems = []
        for n, (x0, y0, x1, y1) in self.boxes:
            if x0 < self.margin - 1 or y0 < 20 or x1 > self.w - self.margin + 1 or y1 > self.h - 20:
                problems.append(f"out of bounds: {n!r} {(x0, y0, x1, y1)}")
        for i in range(len(self.boxes)):
            for j in range(i + 1, len(self.boxes)):
                (n1, a), (n2, b) = self.boxes[i], self.boxes[j]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    problems.append(f"overlap: {n1!r} x {n2!r}")
        print(f"[{label}] {len(self.boxes)} boxes, {len(problems)} problems")
        for p in problems:
            print("   ", p)
        return problems

    def save(self, name):
        out = HERE / name
        self.im.save(out, optimize=True)
        print("saved", out, self.im.size)


def dashed_v(d, x, y0, y1, fill, width=2, dash=10, gap=8):
    y = y0
    while y < y1:
        d.line([x, y, x, min(y + dash, y1)], fill=fill, width=width)
        y += dash + gap


# =================================================================== 1. validation
def make_validation():
    data = json.loads((HERE / "validation_results.json").read_text(encoding="utf-8"))
    S, R = data["synthetic"], data["real"]
    good = [r for r in S if r["kind"] == "good"]
    bad = [r for r in S if r["kind"] != "good"]
    lights = sorted({r["lighting"] for r in good})
    g_ok, b_ok = sum(r["correct"] for r in good), sum(r["correct"] for r in bad)
    live = [r["live_verdict"] for r in R]
    n_ok, n_ns, n_wr = live.count("correct"), live.count("not_sure"), live.count("wrong")
    med_s = st.median(r["ms"] for r in S) / 1000
    # Tamper: pytest tests/test_verify.py (validation.md section 3): photo byte, DB result edit,
    # signed payload edit -> all 3 caught; 4/4 verify tests pass.
    tamper_ok, tamper_n = 3, 3
    cats = ["POSITIVE", "NEGATIVE", "INCONCLUSIVE"]
    cm = [[sum(1 for r in S if r["expected"] == a and r["got"] == p) for p in cats] for a in cats]
    assert len(lights) == 5 and g_ok == len(good) == 25 and b_ok == len(bad) == 12
    assert (n_ok, n_ns, n_wr) == (5, 1, 0)
    print(f"validation: good {g_ok}/{len(good)}, bad {b_ok}/{len(bad)}, real {n_ok}/{n_ns}/{n_wr}, "
          f"median {med_s:.3f} s, cm {cm}")

    c = Canvas(2400, 1040, margin=110)
    d = c.d
    X = [120, 880, 1640]
    BIG = 130

    def stat(x, base, big, label, sub):
        c.text((x, base), big, BIG, True, ACC)
        c.text((x, base + 68), label, 36, False, INK)
        c.text((x, base + 118), sub, 30, False, GREY)

    stat(X[0], 200, f"{g_ok}/{len(good)}", "correct in 5 lights",
         "daylight, tungsten, cool, dim, street lamp")
    stat(X[1], 200, f"{b_ok}/{len(bad)}", "bad photos said Not sure",
         "blur, glare, no card, odd colour")
    stat(X[2], 200, f"{n_ok}/{len(R)}", f"real photos correct, {n_wr} wrong",
         f"{n_ns} said Not sure and asked for a retake")

    d.line([120, 398, 2280, 398], fill=RULE, width=2)

    stat(X[0], 590, f"{med_s:.2f} s", "analysis per photo",
         f"median of {len(S)} photos, laptop CPU")
    stat(X[1], 590, f"{tamper_ok}/{tamper_n}", "tamper attempts caught",
         "photo byte, database edit, signed record")

    # confusion matrix, column 3 of row 2
    mx = X[2]
    c.text((mx, 470), f"Synthetic set, {len(S)} photos: truth vs app", 30, False, GREY)
    rl_w, cw, ch = 190, 150, 92
    gx, gy = mx + rl_w, 560
    heads = ["Pos", "Neg", "Not sure"]
    rows = ["Positive", "Negative", "Not sure"]
    c.text((mx, gy - 18), "Truth", 30, True, GREY)
    for j, h in enumerate(heads):
        c.text((gx + j * cw + cw / 2, gy - 18), h, 30, False, GREY, anchor="ms")
    for k in range(4):  # plain thin grid
        d.line([gx, gy + k * ch, gx + 3 * cw, gy + k * ch], fill=RULE, width=2)
        d.line([gx + k * cw, gy, gx + k * cw, gy + 3 * ch], fill=RULE, width=2)
    for i, rname in enumerate(rows):
        cy = gy + i * ch + ch / 2
        c.text((gx - 24, cy), rname, 30, False, INK, anchor="rm")
        for j in range(3):
            n = cm[i][j]
            diag = i == j
            c.text((gx + j * cw + cw / 2, cy), str(n), 48 if diag else 40, diag,
                   ACC if diag else GREY, anchor="mm", name=f"cm{i}{j}")

    c.text((120, 990), f"Limits: synthetic images and a card on a screen, not real reagent. "
                       f"Rules were tuned on the synthetic set. Real sample is small (n = {len(R)}).",
           30, False, GREY, name="caption")
    probs = c.check("validation_min")
    c.save("validation_min.png")
    return probs


# =================================================================== 2. card pipeline
def run_card_steps(photo):
    """Same steps as make_card_pipeline.py / colour_engine.measure()."""
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services import colour_engine as ce

    profile = {"max_delta_e": 14, "min_margin": 4, "outcomes": [
        {"label": "Opium-type drug (purple)", "category": "POSITIVE", "srgb": [98, 45, 120]},
        {"label": "Amphetamine-type drug (orange)", "category": "POSITIVE", "srgb": [178, 94, 40]},
        {"label": "No reaction (no colour change)", "category": "NEGATIVE", "srgb": [236, 232, 214]}]}
    for o in profile["outcomes"]:
        o["lab"] = [round(v, 2) for v in ce.srgb_to_lab(o["srgb"])]

    T, spec = ce.THRESHOLDS, ce.load_spec()
    image_bytes = photo.read_bytes()
    bgr = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    scale, side, det = 1.0, max(bgr.shape[:2]), bgr
    if side > T["max_image_side"]:
        scale = T["max_image_side"] / side
        det = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    found = ce._detect_markers(det, spec)
    if len(found) < len(spec["markers"]) and scale == 1.0 and side > 1200:
        s2 = 1200 / side
        f2 = ce._detect_markers(cv2.resize(bgr, None, fx=s2, fy=s2, interpolation=cv2.INTER_AREA), spec)
        if len(f2) > len(found):
            found, scale = f2, s2
    assert len(found) == 4
    found_px = {i: c / scale for i, c in found.items()}

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
    de_b = float(np.mean(ce._de2000(ce._linear_to_lab(m_lin), ce._linear_to_lab(k_lin))))
    de_a = float(np.mean(ce._de2000(ce._linear_to_lab(corrected), ce._linear_to_lab(k_lin))))

    win_raw = ce._median_rgb(rgb, ce._rect_px(spec["window"], ppm, T["window_inner"])) / 255.0
    win_lin = np.clip(np.append(ce._srgb_to_linear(win_raw), 1.0) @ X, 0, 1)
    rgb_after = np.round(ce._linear_to_srgb(win_lin) * 255).astype(int)
    rgb_before = np.round(win_raw * 255).astype(int)

    res = ce.classify(image_bytes, profile)
    return dict(bgr=bgr, found_px=found_px, warped=warped, spec=spec, ppm=ppm, T=T,
                blur=blur, de_b=de_b, de_a=de_a, rgb_before=rgb_before, rgb_after=rgb_after,
                res=res, profile=profile)


def make_card_pipeline():
    photo = HERE / "real_tests" / "test_11.jpg"
    r = run_card_steps(photo)
    ref = json.loads((HERE / "card_pipeline_numbers.json").read_text(encoding="utf-8"))
    # cross-check with the saved numbers
    assert round(r["blur"], 1) == ref["blur_score"]
    assert round(r["de_b"], 2) == ref["patch_de_before_mean"] and round(r["de_a"], 2) == ref["patch_de_after_mean"]
    assert r["rgb_before"].tolist() == ref["window_rgb_before"] and r["rgb_after"].tolist() == ref["window_rgb_after"]
    res = r["res"]
    assert res["delta_e_by_outcome"] == ref["engine_result"]["delta_e_by_outcome"]
    assert res["confidence"] == ref["engine_result"]["confidence"] == 76 and res["result"] == "POSITIVE"
    T = r["T"]
    print(f"card: blur {r['blur']:.1f} (min {T['min_blur_score']}), patch dE {r['de_b']:.2f} -> {r['de_a']:.2f} "
          f"(max {T['max_ccm_fit_de']}), dE {res['delta_e_by_outcome']}, {res['result']} {res['confidence']}%")

    c = Canvas(2400, 1000, margin=90)
    d = c.d
    PW = [460, 460, 460, 610]
    GAP = 70
    PX = [100]
    for w in PW[:-1]:
        PX.append(PX[-1] + w + GAP)
    IMG_TOP, IMG_H = 150, 400
    KEY = 720  # baseline of key numbers, same in all panels

    def head(i, title):
        x = PX[i]
        c.text((x, 100), str(i + 1), 44, True, ACC)
        c.text((x + 50, 100), title, 36, True, INK)

    def fit(img, w, h):
        k = min(w / img.width, h / img.height)
        return img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS), k

    def keyblock(i, big, label, sub):
        x = PX[i]
        c.text((x, KEY), big, 96, True, ACC)
        c.text((x, KEY + 58), label, 32, False, INK)
        if sub:
            c.text((x, KEY + 104), sub, 30, False, GREY)

    # ---- 1 find corners (crop, then draw 3 px outlines at display scale)
    bgr, fp = r["bgr"], r["found_px"]
    allc = np.vstack(list(fp.values()))
    x0, y0 = allc.min(axis=0); x1, y1 = allc.max(axis=0)
    px_, py_ = 0.06 * (x1 - x0), 0.12 * (y1 - y0)
    cx0, cy0 = max(0, int(x0 - px_)), max(0, int(y0 - py_))
    cx1, cy1 = min(bgr.shape[1], int(x1 + px_)), min(bgr.shape[0], int(y1 + 0.03 * (y1 - y0)))
    crop = Image.fromarray(cv2.cvtColor(bgr[cy0:cy1, cx0:cx1], cv2.COLOR_BGR2RGB))
    im1, k1 = fit(crop, PW[0], IMG_H)
    dd = ImageDraw.Draw(im1)
    for q in fp.values():
        pts = [((px - cx0) * k1, (py - cy0) * k1) for px, py in q]
        dd.line(pts + [pts[0]], fill=ACC, width=3, joint="curve")
    head(0, "Find corners")
    c.paste(im1, (PX[0], IMG_TOP), "img1")
    keyblock(0, "4/4", "corner markers found", "real phone photo")

    # ---- 2 straighten
    warped_pil = Image.fromarray(cv2.cvtColor(r["warped"], cv2.COLOR_BGR2RGB))
    im2, _ = fit(warped_pil, PW[1], IMG_H)
    head(1, "Straighten")
    c.paste(im2, (PX[1], IMG_TOP), "img2")
    keyblock(1, f"{r['blur']:.0f}", "sharpness score", f"min {T['min_blur_score']:.0f}")

    # ---- 3 learn the light (thin circles on the 24 patches)
    im3, k3 = fit(warped_pil, PW[2], IMG_H)
    dd = ImageDraw.Draw(im3)
    ppm = r["ppm"]
    for p in r["spec"]["patches"]:
        cx = (p["x_mm"] + p["w_mm"] / 2) * ppm * k3
        cy = (p["y_mm"] + p["h_mm"] / 2) * ppm * k3
        rr = 6
        dd.ellipse([cx - rr - 1, cy - rr - 1, cx + rr + 1, cy + rr + 1], outline=INK, width=1)
        dd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline="white", width=2)
    head(2, "Learn the light")
    c.paste(im3, (PX[2], IMG_TOP), "img3")
    keyblock(2, f"{r['de_b']:.1f} \u2192 {r['de_a']:.1f}", "colour error, 24 patches",
             f"dE2000, max {T['max_ccm_fit_de']:.0f}")

    # ---- 4 compare
    x = PX[3]
    head(3, "Compare")
    sw = 120
    for j, (name, col) in enumerate([("before", r["rgb_before"]), ("after", r["rgb_after"])]):
        sx = x + j * (sw + 60)
        d.rectangle([sx, IMG_TOP, sx + sw, IMG_TOP + sw], fill=tuple(int(v) for v in col), outline=BORDER, width=1)
        c.block((sx, IMG_TOP, sx + sw + 1, IMG_TOP + sw + 1), f"swatch {name}")
        c.text((sx, IMG_TOP + sw + 42), name, 30, False, GREY)
    c.text((x + 2 * (sw + 60) + 10, IMG_TOP + sw / 2), "kit window colour", 30, False, GREY, anchor="lm")

    short = {"Opium-type drug (purple)": "Opium-type",
             "Amphetamine-type drug (orange)": "Amphetamine",
             "No reaction (no colour change)": "No reaction"}
    lab_w = max(c.width(s, 30) for s in short.values()) + 24
    val_w = c.width("68.3", 30, True) + 16
    bx0 = x + lab_w
    bar_w = PW[3] - lab_w - val_w
    vmax = 70.0
    limit = r["profile"]["max_delta_e"]
    row0, pitch = 420, 58
    lx = bx0 + round(bar_w * limit / vmax)
    de = res["delta_e_by_outcome"]
    for i, o in enumerate(r["profile"]["outcomes"]):
        cy = row0 + i * pitch
        best = o["label"] == res["outcome_label"]
        c.text((x, cy), short[o["label"]], 30, False, INK, anchor="lm")
        bw = max(3, round(bar_w * min(de[o["label"]], vmax) / vmax))
        d.rectangle([bx0, cy - 6, bx0 + bw, cy + 6], fill=ACC if best else GREY)
        c.text((max(bx0 + bw, lx) + 14, cy), f"{de[o['label']]:.1f}", 30, best, ACC if best else INK, anchor="lm")
    dashed_v(d, lx, row0 - 30, row0 + 2 * pitch + 24, GREY, width=2)
    c.text((lx, row0 + 2 * pitch + 60), f"limit {limit}", 30, False, GREY, anchor="ms")
    c.text((x, row0 - 46), "colour gap (dE2000)", 30, False, GREY)

    conf = res["confidence"]
    c.text((x, KEY), "Positive", 96, True, ACC)
    c.text((x, KEY + 58), f"opium-type \u2013 {conf}% sure", 32, False, INK)
    c.text((x, KEY + 104), "simulated swatch", 30, False, GREY)

    c.text((100, 960), "Real phone photo (test_11.jpg) of the card shown on a laptop screen. "
                       "All numbers from the FieldProof colour engine.", 30, False, GREY, name="caption")
    probs = c.check("card_pipeline_min")
    c.save("card_pipeline_min.png")
    return probs


# =================================================================== 3. security + law
def make_security():
    c = Canvas(2400, 660, margin=110)
    d = c.d
    LX, RX, MID = 120, 1280, 1200
    c.text((LX, 110), "How a record is protected", 36, True, ACC)
    c.text((RX, 110), "Laws it supports", 36, True, ACC)
    left = ["Login + roles", "Photo fingerprint (SHA-256)", "Internet time + GPS",
            "Digital seal (Ed25519)", "Chained log + public verify page"]
    right = [("BNSS 2023 s.105", "seizure recorded on phone"),
             ("BSA 2023 s.63", "hash for the certificate"),
             ("IT Act 2000 s.3", "same method as a digital signature"),
             ("NDPS Rules 2022 r.3(1)", "classify by kit result"),
             ("DPDP Act 2023", "less data, role-based access")]
    y0, pitch = 196, 70
    for i, t in enumerate(left):
        y = y0 + i * pitch
        c.text((LX, y), str(i + 1), 34, True, ACC)
        c.text((LX + 50, y), t, 34, False, INK)
    tab = RX + max(c.width(n, 34) for n, _ in right) + 48
    for i, (n, g) in enumerate(right):
        y = y0 + i * pitch
        c.text((RX, y), n, 34, False, INK)
        c.text((tab, y), g, 30, False, GREY)
    d.line([MID, 70, MID, y0 + 4 * pitch + 20], fill=RULE, width=2)
    d.line([LX, 548, 2280, 548], fill=RULE, width=2)
    c.text((LX, 610), "Presumptive field result \u2013 FSL report confirms.   "
                      "Production: CCA eSign / DSC, TLS, encrypted storage.", 30, False, GREY, name="caption")
    probs = c.check("security_legal_min")
    c.save("security_legal_min.png")
    return probs


if __name__ == "__main__":
    all_probs = make_validation() + make_card_pipeline() + make_security()
    print("TOTAL problems:", len(all_probs))
    sys.exit(1 if all_probs else 0)
