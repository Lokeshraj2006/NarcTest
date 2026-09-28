"""FieldProof colour engine (CONTRACT section 2).

Pure Python + OpenCV + numpy. No FastAPI here.

    srgb_to_lab(rgb)            sRGB 0-255 -> CIELAB (D65)
    delta_e2000(lab1, lab2)     CIEDE2000 colour difference
    measure(image_bytes)        quality checks + lighting-corrected window colour
    classify(image_bytes, prof) full decision: POSITIVE / NEGATIVE / INCONCLUSIVE

The engine never guesses: if anything looks wrong it says INCONCLUSIVE with a
simple reason. Output is only a presumptive field result.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

SPEC_PATH = Path(__file__).resolve().parent / "card_spec.json"

# Tuned on the synthetic photos from demo/make_test_images.py
THRESHOLDS = {
    "min_blur_score": 60.0,     # variance of Laplacian on the warped card (grey, 0-255)
    "max_glare_pct": 3.0,       # % of window+patch pixels with R,G,B all > 245 (white patch excluded)
    "glare_level": 245,
    "max_ccm_fit_de": 6.0,      # mean dE2000 of the corrected patches vs their known values
    "patch_inner": 0.60,        # use the inner 60% of each patch
    "window_inner": 0.40,       # use the inner 40% of the kit window
    "max_image_side": 2400,     # large phone photos are scaled down before marker detection
}

REASONS = {
    "no_image": "Could not open the photo — please retake",
    "no_card": "Colour card not found — keep all 4 corner squares in the photo",
    "blur": "Photo is blurry — hold the phone steady and retake",
    "glare": "Shine/glare on the card — tilt the phone a little and retake",
    "ccm": "Colour card could not be read properly — retake in even light",
    "no_match": "Colour does not match any result of this kit",
    "between": "Colour is in between two results — not sure",
}


# --------------------------------------------------------------------------- colour maths
def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


_M_RGB2XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
])
_WHITE_D65 = np.array([0.95047, 1.0, 1.08883])


def _linear_to_lab(lin: np.ndarray) -> np.ndarray:
    """Linear RGB (0-1), shape (...,3) -> Lab (...,3)."""
    xyz = np.asarray(lin, dtype=np.float64) @ _M_RGB2XYZ.T / _WHITE_D65
    eps, kappa = 216 / 24389, 24389 / 27
    f = np.where(xyz > eps, np.cbrt(xyz), (kappa * xyz + 16) / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def srgb_to_lab(rgb) -> list[float]:
    """sRGB 0-255 -> CIELAB (D65) as [L, a, b]."""
    lin = _srgb_to_linear(np.asarray(rgb, dtype=np.float64) / 255.0)
    return [round(float(v), 3) for v in _linear_to_lab(lin)]


def _de2000(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """Vectorised CIEDE2000 (kL = kC = kH = 1)."""
    lab1 = np.asarray(lab1, dtype=np.float64)
    lab2 = np.asarray(lab2, dtype=np.float64)
    L1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    L2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    C1 = np.hypot(a1, b1)
    C2 = np.hypot(a2, b2)
    Cbar = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cbar ** 7 / (Cbar ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp = L2 - L1
    dCp = C2p - C1p
    dhp = h2p - h1p
    dhp = np.where(dhp > 180, dhp - 360, dhp)
    dhp = np.where(dhp < -180, dhp + 360, dhp)
    dhp = np.where(C1p * C2p == 0, 0.0, dhp)
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dhp) / 2)
    Lbp = (L1 + L2) / 2
    Cbp = (C1p + C2p) / 2
    hsum = h1p + h2p
    hbp = np.where(np.abs(h1p - h2p) > 180,
                   np.where(hsum < 360, (hsum + 360) / 2, (hsum - 360) / 2),
                   hsum / 2)
    hbp = np.where(C1p * C2p == 0, hsum, hbp)
    T = (1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    dtheta = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
    Sl = 1 + (0.015 * (Lbp - 50) ** 2) / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
                   + Rt * (dCp / Sc) * (dHp / Sh))


def delta_e2000(lab1, lab2) -> float:
    """CIEDE2000 difference between two Lab colours."""
    return float(_de2000(np.asarray(lab1, float), np.asarray(lab2, float)))


# --------------------------------------------------------------------------- card
@lru_cache(maxsize=1)
def load_spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def _empty_quality(markers_found: int = 0) -> dict:
    return {"card_found": False, "markers_found": markers_found,
            "blur_score": None, "glare_pct": None, "ccm_fit_de": None}


def _fail(reason_key: str, quality: dict) -> dict:
    return {"ok": False, "reason": REASONS[reason_key], "reason_code": reason_key,
            "quality": quality, "measured_lab": None, "measured_rgb": None}


def _detect_markers(bgr: np.ndarray, spec: dict):
    """Return {id: 4x2 corners in given image pixels}."""
    dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, spec["aruco_dict"]))
    params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(dictionary, params)
    grey = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(grey)
    found = {}
    if ids is not None:
        wanted = {m["id"] for m in spec["markers"]}
        for c, i in zip(corners, ids.flatten()):
            i = int(i)
            if i in wanted and i not in found:
                found[i] = c.reshape(4, 2).astype(np.float64)
    return found


def _rect_px(el: dict, ppm: float, inner: float) -> tuple[int, int, int, int]:
    w, h = el["w_mm"] * ppm, el["h_mm"] * ppm
    x0 = el["x_mm"] * ppm + w * (1 - inner) / 2
    y0 = el["y_mm"] * ppm + h * (1 - inner) / 2
    return int(round(x0)), int(round(y0)), int(round(x0 + w * inner)), int(round(y0 + h * inner))


def _median_rgb(img_rgb: np.ndarray, r: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = r
    return np.median(img_rgb[y0:y1, x0:x1].reshape(-1, 3), axis=0)


def measure(image_bytes: bytes) -> dict:
    """Quality checks + lighting-corrected colour of the kit window.

    Returns {"ok", "reason", "reason_code", "quality", "measured_lab", "measured_rgb"}.
    When ok is False, reason is a simple English sentence and colours are None.
    """
    spec = load_spec()
    arr = np.frombuffer(image_bytes or b"", dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR) if arr.size else None
    if bgr is None:
        return _fail("no_image", _empty_quality())

    # scale big photos down for detection, keep scale for homography
    scale = 1.0
    side = max(bgr.shape[:2])
    det_img = bgr
    if side > THRESHOLDS["max_image_side"]:
        scale = THRESHOLDS["max_image_side"] / side
        det_img = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    found = _detect_markers(det_img, spec)
    if len(found) < len(spec["markers"]) and scale == 1.0 and side > 1200:
        # second try on a smaller copy (helps with very sharp / noisy photos)
        s2 = 1200 / side
        f2 = _detect_markers(cv2.resize(bgr, None, fx=s2, fy=s2, interpolation=cv2.INTER_AREA), spec)
        if len(f2) > len(found):
            found, scale = f2, s2
    if len(found) < len(spec["markers"]):
        return _fail("no_card", _empty_quality(len(found)))

    ppm = spec["px_per_mm"]
    src, dst = [], []
    for m in spec["markers"]:
        x, y, s = m["x_mm"], m["y_mm"], m["size_mm"]
        card_pts = np.array([[x, y], [x + s, y], [x + s, y + s], [x, y + s]], dtype=np.float64) * ppm
        src.append(found[m["id"]] / scale)
        dst.append(card_pts)
    src = np.vstack(src).astype(np.float32)
    dst = np.vstack(dst).astype(np.float32)
    H, _ = cv2.findHomography(src, dst, 0)
    if H is None:
        return _fail("no_card", _empty_quality(len(found)))
    W, Hh = int(spec["card_w_mm"] * ppm), int(spec["card_h_mm"] * ppm)
    warped = cv2.warpPerspective(bgr, H, (W, Hh), flags=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(warped, cv2.COLOR_BGR2RGB)

    quality = {"card_found": True, "markers_found": len(found),
               "blur_score": None, "glare_pct": None, "ccm_fit_de": None}

    # blur
    grey = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(grey, cv2.CV_64F).var())
    quality["blur_score"] = round(blur, 1)
    if blur < THRESHOLDS["min_blur_score"]:
        return _fail("blur", quality)

    # glare (window + patches, white patch excluded)
    lvl = THRESHOLDS["glare_level"]
    white_id = spec.get("white_patch_id", "P19")
    total = bright = 0
    areas = [spec["window"]] + [p for p in spec["patches"] if p["id"] != white_id]
    for el in areas:
        x0, y0, x1, y1 = _rect_px(el, ppm, 0.9)
        roi = rgb[y0:y1, x0:x1].reshape(-1, 3)
        total += len(roi)
        bright += int(np.count_nonzero(np.all(roi > lvl, axis=1)))
    glare = 100.0 * bright / max(total, 1)
    quality["glare_pct"] = round(glare, 2)
    if glare > THRESHOLDS["max_glare_pct"]:
        return _fail("glare", quality)

    # colour correction: 3x4 affine CCM in linear RGB
    measured = np.array([_median_rgb(rgb, _rect_px(p, ppm, THRESHOLDS["patch_inner"]))
                         for p in spec["patches"]]) / 255.0
    known = np.array([p["srgb"] for p in spec["patches"]], dtype=np.float64) / 255.0
    m_lin = _srgb_to_linear(measured)
    k_lin = _srgb_to_linear(known)
    A = np.hstack([m_lin, np.ones((len(m_lin), 1))])
    X, *_ = np.linalg.lstsq(A, k_lin, rcond=None)  # 4x3
    corrected = np.clip(A @ X, 0, 1)
    fit = float(np.mean(_de2000(_linear_to_lab(corrected), _linear_to_lab(k_lin))))
    quality["ccm_fit_de"] = round(fit, 2)
    if not np.isfinite(fit) or fit > THRESHOLDS["max_ccm_fit_de"]:
        return _fail("ccm", quality)

    win = _median_rgb(rgb, _rect_px(spec["window"], ppm, THRESHOLDS["window_inner"])) / 255.0
    win_lin = np.clip(np.append(_srgb_to_linear(win), 1.0) @ X, 0, 1)
    lab = _linear_to_lab(win_lin)
    srgb = np.round(_linear_to_srgb(win_lin) * 255).astype(int)
    return {"ok": True, "reason": None, "reason_code": None, "quality": quality,
            "measured_lab": [round(float(v), 2) for v in lab],
            "measured_rgb": [int(v) for v in srgb]}


# --------------------------------------------------------------------------- decision
def _outcome_lab(o: dict) -> list[float]:
    lab = o.get("lab")
    if lab and len(lab) == 3:
        return [float(v) for v in lab]
    return srgb_to_lab(o["srgb"])


def classify(image_bytes: bytes, profile: dict) -> dict:
    """Full decision for one photo and one kit profile (CONTRACT section 2)."""
    m = measure(image_bytes)
    out = {
        "result": "INCONCLUSIVE",
        "outcome_label": None,
        "confidence": 0,
        "reason": m["reason"],
        "measured_lab": m["measured_lab"],
        "measured_rgb": m["measured_rgb"],
        "delta_e_by_outcome": {},
        "quality": m["quality"],
    }
    if not m["ok"]:
        return out
    outcomes = profile.get("outcomes") or []
    if not outcomes:
        out["reason"] = REASONS["no_match"]
        return out

    lab = m["measured_lab"]
    dists = [(delta_e2000(lab, _outcome_lab(o)), o) for o in outcomes]
    out["delta_e_by_outcome"] = {o["label"]: round(d, 2) for d, o in dists}
    dists.sort(key=lambda t: t[0])
    d1, best = dists[0]
    d2 = dists[1][0] if len(dists) > 1 else float("inf")
    max_de = float(profile.get("max_delta_e", 14))
    min_margin = float(profile.get("min_margin", 4))

    if d1 > max_de:
        out["reason"] = REASONS["no_match"]
        return out
    if d2 - d1 < min_margin:
        out["reason"] = REASONS["between"]
        return out

    margin_part = min(1.0, (d2 - d1) / (3 * min_margin)) if np.isfinite(d2) else 1.0
    closeness_part = 1.0 - 0.5 * (d1 / max_de)
    conf = int(round(99 * margin_part * closeness_part))
    out.update({
        "result": best["category"],
        "outcome_label": best["label"],
        "confidence": max(1, min(99, conf)),
        "reason": None,
    })
    return out
