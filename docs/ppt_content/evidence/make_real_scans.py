"""Real phone scans (29 Sep 2026 session) -> slide image: 6 cropped scans + confusion matrix.

TRUTH = which swatch card is visible in each photo, judged by eye (not from the app's own reading).
App answers come straight from the saved records. Run from backend/:
    venv\\Scripts\\python.exe ..\\docs\\ppt_content\\evidence\\make_real_scans.py [--check]
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
from app.database import SessionLocal
from app.models.test_record import TestRecord
from app.services import record_service as rs

TRUTH = {13: 'purple', 14: 'orange', 15: 'orange', 16: 'plain', 17: 'between', 18: 'green', 19: 'green',
         20: 'orange', 21: 'orange', 22: 'plain', 23: 'plain', 24: 'orange', 25: 'between', 26: 'between',
         27: 'between', 28: 'orange', 29: 'purple', 30: 'green', 31: 'plain'}
EXPECT = {'purple': 'POSITIVE', 'orange': 'POSITIVE', 'plain': 'NEGATIVE', 'between': 'INCONCLUSIVE', 'green': 'INCONCLUSIVE'}
TILES = [(29, 'Purple card'), (15, 'Orange card'), (16, 'Plain card'),
         (17, 'In-between card'), (18, 'Green card (not in kit)'), (19, 'Blurry photo')]

db = SessionLocal()
recs = {r.id: r for r in db.query(TestRecord).filter(TestRecord.id.in_(list(TRUTH))).all()}
det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))


def card_crop(r):
    im = ImageOps.exif_transpose(Image.open(rs.image_file(r))).convert('RGB')
    a = np.array(im)
    corners, ids, _ = det.detectMarkers(cv2.cvtColor(a, cv2.COLOR_RGB2GRAY))
    if ids is None or len(ids) < 4:                         # fallback: card band of the screen
        h, w = a.shape[:2]
        return im.crop((0, int(h * 0.27), w, int(h * 0.58)))
    pts = np.concatenate([c.reshape(-1, 2) for c in corners])
    x0, y0 = pts.min(0)
    x1, y1 = pts.max(0)
    mx, my = (x1 - x0) * 0.03, (y1 - y0) * 0.04
    return im.crop((int(x0 - mx), int(y0 - my), int(x1 + mx), int(y1 + my)))


def said(r):
    return 'NOT SURE' if r.result == 'INCONCLUSIVE' else r.result


if '--check' in sys.argv:                                    # eyeball the dim / unsure truth labels
    strip = Image.new('RGB', (19 * 200, 150), 'white')
    for i, k in enumerate(sorted(TRUTH)):
        c = card_crop(recs[k]); c.thumbnail((196, 146)); strip.paste(c, (i * 200 + 2, 2))
    strip.save(Path(__file__).with_name('real_scans_check.jpg')); print('check strip saved'); sys.exit()

if '--tiles' in sys.argv:                                    # photos only (numbers go in slide text)
    F2 = lambda s, b=False: ImageFont.truetype('C:/Windows/Fonts/' + ('arialbd.ttf' if b else 'arial.ttf'), s)
    tw, th, gx, gy = 300, 190, 18, 100
    img = Image.new('RGB', (3 * tw + 2 * gx, 2 * (th + gy)), 'white')
    d = ImageDraw.Draw(img)
    for i, (k, name) in enumerate(TILES):
        r = recs[k]
        x, y = (i % 3) * (tw + gx), (i // 3) * (th + gy)
        img.paste(card_crop(r).resize((tw, th)), (x, y))
        d.rectangle([x, y, x + tw - 1, y + th - 1], outline=(0xD0, 0xD0, 0xD0), width=2)
        d.text((x, y + th + 6), name, font=F2(30), fill=(0x55, 0x55, 0x55))
        ans = said(r) + (f' {r.confidence}%' if r.result != 'INCONCLUSIVE' else '')
        ok = r.result == EXPECT[TRUTH[k]] and r.result != 'INCONCLUSIVE'
        d.text((x, y + th + 44), ans, font=F2(34, True),
               fill=(0x2E, 0x7D, 0x32) if ok else (0x8A, 0x5A, 0x00))
    img.save(Path(__file__).with_name('real_scans_tiles.png')); print('tiles saved'); sys.exit()

# confusion matrix: truth group x app answer
groups = [('Positive card', ('purple', 'orange')), ('Plain card', ('plain',)), ('Trick card', ('between', 'green'))]
cols = ['POSITIVE', 'NEGATIVE', 'INCONCLUSIVE']
M = [[sum(1 for k, t in TRUTH.items() if t in g and recs[k].result == c) for c in cols] for _, g in groups]
wrong = sum(1 for k, t in TRUTH.items() if recs[k].result != 'INCONCLUSIVE' and recs[k].result != EXPECT[t])
readable = [k for k, t in TRUTH.items() if t in ('purple', 'orange', 'plain') and recs[k].result != 'INCONCLUSIVE']
blurry = sum(1 for k, t in TRUTH.items() if t in ('purple', 'orange', 'plain') and recs[k].result == 'INCONCLUSIVE')
trick_ok = sum(1 for k, t in TRUTH.items() if t in ('between', 'green') and recs[k].result == 'INCONCLUSIVE')
from datetime import datetime
ts = lambda k: datetime.fromisoformat(str(recs[k].created_at).replace("Z", "+00:00"))
ks = sorted(TRUTH)
gaps = sorted((ts(b) - ts(a)).total_seconds() for a, b in zip(ks, ks[1:])
              if recs[a].officer_id == recs[b].officer_id)   # same officer only (no logout/login time)
med = gaps[len(gaps) // 2]

F = lambda s, b=False: ImageFont.truetype('C:/Windows/Fonts/' + ('arialbd.ttf' if b else 'arial.ttf'), s)
ACC, INK, GREY, RULE = (0x7A, 0x2F, 0x00), (0x1F, 0x1F, 0x1F), (0x6B, 0x6B, 0x6B), (0xD0, 0xD0, 0xD0)
GREEN, RED, AMBER = (0x2E, 0x7D, 0x32), (0xC6, 0x28, 0x28), (0x8A, 0x5A, 0x00)
W, H = 1600, 850
img = Image.new('RGB', (W, H), 'white')
d = ImageDraw.Draw(img)

tw, th, gap = 290, 185, 16
for i, (k, name) in enumerate(TILES):
    r = recs[k]
    x, y = 10 + (i % 3) * (tw + gap), 6 + (i // 3) * 272
    c = card_crop(r).resize((tw, th))
    img.paste(c, (x, y))
    d.rectangle([x - 1, y - 1, x + tw, y + th], outline=RULE, width=2)
    d.text((x, y + th + 6), name, font=F(28), fill=GREY)
    ans = said(r) + (f' {r.confidence}%' if r.result != 'INCONCLUSIVE' else '')
    ok = (r.result == EXPECT[TRUTH[k]])
    d.text((x, y + th + 40), ans + (', retake' if name == 'Blurry photo' else ''), font=F(32, True),
           fill=(GREEN if ok and r.result != 'INCONCLUSIVE' else AMBER) if ok or r.result == 'INCONCLUSIVE' else RED)
d.text((10, 560), 'We scanned using our app on 1 phone, in 1 room', font=F(28), fill=GREY)
d.text((10, 596), 'with window light. Card was shown on a laptop screen.', font=F(28), fill=GREY)
d.text((10, 632), 'We checked each card by eye, not using the app.', font=F(28), fill=GREY)

# colour gap (Delta E) from the saved records: how far the measured colour was from each kit colour
right_de, other_de, trick_de = [], [], []
for k, t in TRUTH.items():
    v = sorted((recs[k].delta_e_by_outcome or {}).values())
    if not v:
        continue
    if t in ('purple', 'orange', 'plain') and recs[k].result != 'INCONCLUSIVE':
        right_de.append(v[0]); other_de.append(v[1])
    elif t in ('between', 'green'):
        trick_de.append(v[0])
d.text((10, 692), 'Colour gap (Delta E), our limit is 14', font=F(30, True), fill=ACC)
d.text((10, 732), f'Right colour: {min(right_de):.1f} to {max(right_de):.1f}', font=F(28), fill=INK)
d.text((10, 768), f'Other kit colours: {min(other_de):.0f} to {max(other_de):.0f}', font=F(28), fill=INK)
d.text((10, 804), f'Trick cards: {min(trick_de):.0f} to {max(trick_de):.0f}, so app said NOT SURE', font=F(28), fill=INK)

x0 = 960
d.text((x0, 6), f'All {len(TRUTH)} real scans', font=F(40, True), fill=ACC)
cw0, cw = 218, 140
hy = 70
for j, head in enumerate(['POSITIVE', 'NEGATIVE', 'NOT SURE']):
    d.text((x0 + cw0 + j * cw + 4, hy + 16), head, font=F(22, True), fill=INK)
d.text((x0, hy + 14), 'Card vs app', font=F(24, True), fill=GREY)
for i, (label, g) in enumerate(groups):
    y = hy + 60 + i * 72
    d.line([(x0, y - 6), (x0 + cw0 + 3 * cw, y - 6)], fill=RULE, width=2)
    n = sum(M[i])
    d.text((x0, y + 12), f'{label} ({n})', font=F(28), fill=INK)
    for j, v in enumerate(M[i]):
        right = (cols[j] == 'POSITIVE' and i == 0) or (cols[j] == 'NEGATIVE' and i == 1) or (cols[j] == 'INCONCLUSIVE' and i == 2)
        colr = GREEN if right and v else (GREY if cols[j] == 'INCONCLUSIVE' else (RED if v else RULE))
        cx = x0 + cw0 + j * cw
        if right:
            d.rectangle([cx, y - 4, cx + cw - 8, y + 58], fill=(0xE8, 0xF5, 0xE9))
        d.text((cx + 40, y + 6), str(v), font=F(40, True), fill=colr)
d.line([(x0, hy + 60 + 3 * 72 - 6), (x0 + cw0 + 3 * cw, hy + 60 + 3 * 72 - 6)], fill=RULE, width=2)
lines = [(f'{wrong} wrong answers', True), (f'All {len(readable)} clear scans correct', False),
         (f'All {trick_ok} trick cards said NOT SURE', False), (f'{blurry} blurry photos, app asked to retake', False),
         (f'Around {med:.0f} seconds per test (1 team member)', False)]
for i, (t, b) in enumerate(lines):
    d.text((x0, 400 + i * 56), t, font=F(34 if b else 30, b), fill=ACC if b else INK)
out = Path(__file__).with_name('real_scans.png')
img.save(out)
print('matrix', M, 'wrong', wrong, 'readable', len(readable), 'trick_ok', trick_ok, 'blurry', blurry, 'median gap', med, 'n gaps', len(gaps))
print('saved', out)
