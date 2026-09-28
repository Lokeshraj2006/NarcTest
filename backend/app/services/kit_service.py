"""
FieldProof — Kit profile helpers (Lab values, seeding, dict form).
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.kit_profile import KitProfile


def _local_srgb_to_lab(rgb: List[float]) -> List[float]:
    """Small sRGB (0-255) -> CIELAB (D65) fallback."""

    def lin(c: float) -> float:
        c = max(0.0, min(255.0, float(c))) / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(v) for v in rgb)
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    xn, yn, zn = 0.95047, 1.0, 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29

    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    return [round(116 * fy - 16, 2), round(500 * (fx - fy), 2), round(200 * (fy - fz), 2)]


def srgb_to_lab(rgb: List[float]) -> List[float]:
    """Use the colour engine's converter when it is there, else the local one."""
    try:
        from app.services import colour_engine

        lab = colour_engine.srgb_to_lab(list(rgb))
        return [round(float(v), 2) for v in lab]
    except Exception:
        return _local_srgb_to_lab(rgb)


def with_lab(outcomes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return outcomes with 'lab' filled in from 'srgb' when missing."""
    out = []
    for o in outcomes:
        o = dict(o)
        o["category"] = str(o.get("category", "")).upper()
        o["srgb"] = [int(round(float(v))) for v in o.get("srgb", [0, 0, 0])]
        if not o.get("lab"):
            o["lab"] = srgb_to_lab(o["srgb"])
        out.append(o)
    return out


def kit_to_dict(kit: KitProfile) -> Dict[str, Any]:
    return {
        "id": kit.id,
        "code": kit.code,
        "name": kit.name,
        "reagent": kit.reagent,
        "read_time_s": kit.read_time_s,
        "outcomes": kit.outcomes or [],
        "max_delta_e": kit.max_delta_e,
        "min_margin": kit.min_margin,
        "is_active": kit.is_active,
        "version": kit.version,
        "updated_at": kit.updated_at.isoformat() if kit.updated_at else None,
    }


DEMO_KITS: List[Dict[str, Any]] = [
    {
        "code": "DEMO-MARQUIS-SIM",
        "name": "Marquis test (simulated swatches)",
        "reagent": "Printed swatch stand-in for Marquis reagent (demo only)",
        "read_time_s": 15,
        "outcomes": [
            {"label": "Opium-type drug (purple)", "category": "POSITIVE", "srgb": [98, 45, 120]},
            {"label": "Amphetamine-type drug (orange)", "category": "POSITIVE", "srgb": [178, 94, 40]},
            {"label": "No reaction (no colour change)", "category": "NEGATIVE", "srgb": [236, 232, 214]},
        ],
        "max_delta_e": 14,
        "min_margin": 4,
    },
    {
        "code": "DEMO-IODINE",
        "name": "Iodine–Starch screen (live demo)",
        "reagent": "Betadine (povidone-iodine) diluted 1:5",
        "read_time_s": 10,
        "outcomes": [
            {"label": "Starch found (blue-black)", "category": "POSITIVE", "srgb": [40, 35, 60]},
            {"label": "No starch (amber)", "category": "NEGATIVE", "srgb": [200, 130, 40]},
        ],
        "max_delta_e": 18,
        "min_margin": 5,
    },
]


def seed_demo_kits(db: Session) -> None:
    """Create the 2 demo kits if missing (idempotent, never bumps versions)."""
    for spec in DEMO_KITS:
        kit = db.query(KitProfile).filter(KitProfile.code == spec["code"]).first()
        if kit is None:
            kit = KitProfile(**{**spec, "outcomes": with_lab(spec["outcomes"])}, is_active=True, version=1)
            db.add(kit)
        elif any(not o.get("lab") for o in (kit.outcomes or [])):
            kit.outcomes = with_lab(kit.outcomes)
    db.commit()
