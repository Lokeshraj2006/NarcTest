"""Stress test on our REAL phone photos (records 13-31, 29 Sep 2026).

Each real photo is re-checked by the same colour engine the server uses, as taken and after computer-made
changes (darker, brighter, yellow bulb, cool tube light, tilted, shaky blur, cheap camera, grainy).
These are computer-changed copies of real photos, not new photos. Truth = card judged by eye (same labels
as make_real_scans.py). Run from backend/:
    venv\\Scripts\\python.exe ..\\docs\\ppt_content\\evidence\\make_stress_test.py
Writes stress_test.json and stress_test.png next to this file.
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
from app.database import SessionLocal
from app.models.kit_profile import KitProfile
from app.models.test_record import TestRecord
from app.services import colour_engine as ce
from app.services import record_service as rs

HERE = Path(__file__).parent
TRUTH = {13: 'purple', 14: 'orange', 15: 'orange', 16: 'plain', 17: 'between', 18: 'green', 19: 'green',
         20: 'orange', 21: 'orange', 22: 'plain', 23: 'plain', 24: 'orange', 25: 'between', 26: 'between',
         27: 'between', 28: 'orange', 29: 'purple', 30: 'green', 31: 'plain'}
LABEL = {'purple': 'Opium-type drug (purple)', 'orange': 'Amphetamine-type drug (orange)',
         'plain': 'No reaction (no colour change)'}
GROUP = {'purple': 'Positive card', 'orange': 'Positive card', 'plain': 'Plain card',
         'between': 'Trick card', 'green': 'Trick card'}


def to_lin(img):
    x = img.astype(np.float64) / 255.0
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def to_srgb(lin):
    lin = np.clip(lin, 0, 1)
    x = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    return (x * 255 + 0.5).astype(np.uint8)


def light(gain_bgr):
    return lambda img: to_srgb(to_lin(img) * np.array(gain_bgr))


def tilt(img):
    h, w = img.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[w * 0.06, h * 0.03], [w * 0.97, 0], [w * 0.92, h], [w * 0.02, h * 0.95]])
    return cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (w, h), borderMode=cv2.BORDER_REPLICATE)


def cheap(img):
    h, w = img.shape[:2]
    small = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 60])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def grainy(img):
    rng = np.random.default_rng(7)
    return np.clip(img.astype(np.int16) + rng.normal(0, 8, img.shape).astype(np.int16), 0, 255).astype(np.uint8)


CONDITIONS = [                                    # (name, change); gains are B, G, R in linear light
    ('As taken', None),
    ('Darker room', light([0.5, 0.5, 0.5])),
    ('Brighter light', light([1.4, 1.4, 1.4])),
    ('Yellow bulb', light([0.7, 1.0, 1.15])),
    ('Cool tube light', light([1.2, 1.0, 0.8])),
    ('Phone tilted', tilt),
    ('Shaky hand', lambda img: cv2.GaussianBlur(img, (0, 0), 1.5)),
    ('Cheap camera', cheap),
    ('Grainy photo', grainy),
]


def main():
    db = SessionLocal()
    recs = {r.id: r for r in db.query(TestRecord).filter(TestRecord.id.in_(list(TRUTH)))}
    kit = db.query(KitProfile).filter(KitProfile.code == recs[13].kit_code).first()
    profile = {'id': kit.id, 'code': kit.code, 'name': kit.name, 'reagent': kit.reagent,
               'read_time_s': kit.read_time_s, 'outcomes': kit.outcomes or [],
               'max_delta_e': kit.max_delta_e, 'min_margin': kit.min_margin,
               'is_active': kit.is_active, 'version': kit.version}
    rows = []
    for k in sorted(TRUTH):
        raw = rs.read_image(recs[k])
        base = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        for name, change in CONDITIONS:
            if change is None:
                data = raw
            else:
                ok, buf = cv2.imencode('.jpg', change(base), [cv2.IMWRITE_JPEG_QUALITY, 92])
                data = buf.tobytes()
            out = ce.classify(data, profile)
            t = TRUTH[k]
            got, lab = out['result'], out.get('outcome_label')
            if got == 'INCONCLUSIVE':
                verdict = 'not_sure'
            elif t in LABEL and lab == LABEL[t]:
                verdict = 'right'
            else:
                verdict = 'wrong'
            rows.append({'record': k, 'card': t, 'group': GROUP[t], 'condition': name, 'result': got,
                         'label': lab, 'verdict': verdict, 'reason': out.get('reason')})
    json.dump({'made': time.strftime('%Y-%m-%d %H:%M'), 'kit': kit.code, 'kit_version': kit.version,
               'note': 'computer-changed copies of real phone photos', 'rows': rows},
              open(HERE / 'stress_test.json', 'w', encoding='utf-8'), indent=1)

    print('checks', len(rows))
    for name, _ in CONDITIONS:
        c = Counter(r['verdict'] for r in rows if r['condition'] == name)
        print(f'{name:16s} right {c["right"]:2d}  not_sure {c["not_sure"]:2d}  wrong {c["wrong"]:2d}')
    groups = ['Positive card', 'Plain card', 'Trick card']
    M = {g: Counter(r['result'] for r in rows if r['group'] == g) for g in groups}
    for g in groups:
        print(g, dict(M[g]))
    print('wrong rows', [(r['record'], r['condition'], r['result'], r['label']) for r in rows if r['verdict'] == 'wrong'])


if __name__ == '__main__':
    main()
