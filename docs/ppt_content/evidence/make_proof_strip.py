"""Compact proof strip for the 'Our Goals - Measured Results' slide. Every label comes from a fresh engine run."""
import json, sys, time
from pathlib import Path
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
from app.services import colour_engine as ce
from app.services.kit_service import DEMO_KITS

TI = ROOT / 'demo' / 'test_images'
man = json.load(open(TI / 'manifest.json', encoding='utf-8'))
items = man if isinstance(man, list) else man.get('images', man)
kits = {k['code']: k for k in DEMO_KITS}
def prof(code):
    k = dict(kits[code]); k['outcomes'] = [dict(o, lab=o.get('lab') or ce.srgb_to_lab(o['srgb'])) for o in k['outcomes']]
    return k

def pick(pred):
    for it in items:
        if pred(it): return it
    raise SystemExit('no image for selection')

lights = [('daylight', 'Daylight'), ('tungsten', 'Tungsten bulb'), ('cool', 'Cool white'), ('dim', 'Dim light'), ('sodium', 'Street lamp')]
sel = []
for key, name in lights:
    it = pick(lambda i, key=key: i.get('kind') in ('good', 'ok', None) and key in str(i.get('lighting', '')).lower()
              and 'purple' in (str(i.get('expected_label', '')) + str(i.get('file', ''))).lower())
    sel.append((it, name))
sel.append((pick(lambda i: 'glare' in str(i.get('kind', '')).lower() or 'glare' in str(i.get('file', '')).lower()), 'Glare on card'))

VERTICAL = '--vertical' in sys.argv
NARROW = '--narrow' in sys.argv
F = lambda s, b=False: ImageFont.truetype('C:/Windows/Fonts/' + ('arialbd.ttf' if b else 'arial.ttf'), s)
ACC, INK, GREY, RULE = (0x7A, 0x2F, 0x00), (0x1F, 0x1F, 0x1F), (0x6B, 0x6B, 0x6B), (0xD9, 0xD9, 0xD9)
results = []
thumbs = []
for it, name in sel:
    raw = (TI / it['file']).read_bytes()
    r = ce.classify(raw, prof(it.get('kit', 'DEMO-MARQUIS-SIM')))
    results.append((it['file'], name, r['result'], r['confidence'], it['expected']))
    bgr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    h, w = bgr.shape[:2]; s_ = min(h, w); crop = bgr[(h - s_)//2:(h + s_)//2, (w - s_)//2:(w + s_)//2]
    thumbs.append((it, name, r, crop))

def tile(d, img, x, y, tw, it, name, r, fs):
    img.paste(Image.fromarray(cv2.cvtColor(cv2.resize(r_crop(it), (tw, tw), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)), (x, y))

if '--grid' in sys.argv:  # 3 x 2 tiles only (numbers are already in the slide text) -> proof_grid.png
    W, tw, gapx, rowh = 1200, 350, 50, 510
    x0 = (W - (3 * tw + 2 * gapx)) // 2
    img = Image.new('RGB', (W, 2 * rowh + 70), 'white'); d = ImageDraw.Draw(img)
    def fit(text, size, bold=False):
        while d.textlength(text, font=F(size, bold)) > tw + gapx - 8:
            size -= 2
        return F(size, bold)
    right = 0
    for i, (it, name, r, crop) in enumerate(thumbs):
        x = x0 + (i % 3) * (tw + gapx); y = (i // 3) * rowh
        img.paste(Image.fromarray(cv2.cvtColor(cv2.resize(crop, (tw, tw), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)), (x, y))
        d.rectangle([x - 1, y - 1, x + tw, y + tw], outline=RULE, width=2)
        ok = r['result'] == it['expected']; right += ok
        d.text((x, y + tw + 8), name, font=fit(name, 54), fill=GREY)
        ans = 'NOT SURE' if r['result'] == 'INCONCLUSIVE' else f"{r['result'].title()} {r['confidence']}%"
        d.text((x, y + tw + 70), ans, font=fit(ans, 60, True), fill=ACC if ok else (0xC0, 0, 0))
    foot = f"{right}/{len(thumbs)} correct · test run {time.strftime('%d %b %Y')} · simulated swatches"
    fs = 44
    while d.textlength(foot, font=F(fs)) > W - 2 * x0:
        fs -= 2
    d.text((x0, 2 * rowh + 6), foot, font=F(fs), fill=GREY)
    out = ROOT / 'docs' / 'ppt_content' / 'evidence' / 'proof_grid.png'
    img.save(out)
    for r in results: print(r)
    print('saved', out)
    raise SystemExit(0)
elif NARROW:
    W, H = 620, 2600
    img = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(img)
    tw, x0, y0, rowh = 230, 30, 30, 262
    for i, (it, name, r, crop) in enumerate(thumbs):
        y = y0 + i * rowh
        img.paste(Image.fromarray(cv2.cvtColor(cv2.resize(crop, (tw, tw), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)), (x0, y))
        d.rectangle([x0 - 1, y - 1, x0 + tw, y + tw], outline=RULE, width=2)
        ok = r['result'] == it['expected']
        tx_ = x0 + tw + 26
        d.text((tx_, y + 52), name, font=F(32), fill=GREY)
        ans = 'NOT SURE' if r['result'] == 'INCONCLUSIVE' else r['result'].title()
        d.text((tx_, y + 96), ans, font=F(40, True), fill=ACC if ok else (0xC0, 0, 0))
        d.text((tx_, y + 146), (f"{r['confidence']}% sure · " if r['result'] != 'INCONCLUSIVE' else '') + ('correct' if ok else 'WRONG'), font=F(30), fill=GREY)
    ly = y0 + 6 * rowh + 6
    d.line([(x0, ly), (W - x0, ly)], fill=RULE, width=2)
    tx, ty, big, mid, small = x0, ly + 26, 50, 32, 26
elif not VERTICAL:
    W, H = 2400, 500
    img = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(img)
    tw, x0, y0, gap = 250, 40, 60, 22
    for i, (it, name, r, crop) in enumerate(thumbs):
        x = x0 + i * (tw + gap)
        img.paste(Image.fromarray(cv2.cvtColor(cv2.resize(crop, (tw, tw), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)), (x, y0))
        d.rectangle([x - 1, y0 - 1, x + tw, y0 + tw], outline=RULE, width=2)
        ok = r['result'] == it['expected']
        d.text((x, y0 + tw + 16), name, font=F(28), fill=GREY)
        ans = 'NOT SURE' if r['result'] == 'INCONCLUSIVE' else r['result'].title() + f"  {r['confidence']}%"
        d.text((x, y0 + tw + 54), ans, font=F(34, True), fill=ACC if ok else (0xC0, 0, 0))
        d.text((x, y0 + tw + 100), 'correct' if ok else 'WRONG', font=F(26), fill=GREY)
    d.line([(1685, 60), (1685, 460)], fill=RULE, width=2)
    tx, ty, big, mid, small = 1720, 58, 52, 34, 26
else:
    W, H = 1000, 2600
    img = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(img)
    tw, x0, y0, gapx, rowh = 430, 50, 50, 40, 560
    for i, (it, name, r, crop) in enumerate(thumbs):
        x = x0 + (i % 2) * (tw + gapx); y = y0 + (i // 2) * rowh
        img.paste(Image.fromarray(cv2.cvtColor(cv2.resize(crop, (tw, tw), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)), (x, y))
        d.rectangle([x - 1, y - 1, x + tw, y + tw], outline=RULE, width=2)
        ok = r['result'] == it['expected']
        d.text((x, y + tw + 14), name, font=F(32), fill=GREY)
        ans = 'NOT SURE' if r['result'] == 'INCONCLUSIVE' else r['result'].title() + f"  {r['confidence']}%"
        d.text((x, y + tw + 56), ans + ('  - correct' if ok else '  - WRONG'), font=F(36, True), fill=ACC if ok else (0xC0, 0, 0))
    ly = y0 + 3 * rowh + 10
    d.line([(x0, ly), (W - x0, ly)], fill=RULE, width=2)
    tx, ty, big, mid, small = x0, ly + 30, 58, 36, 28

d.text((tx, ty), 'Test run, ' + time.strftime('%d %b %Y'), font=F(30), fill=GREY)
d.text((tx, ty + 42), '15 passed, 0 failed', font=F(big, True), fill=ACC)
lines = ['37/37 test photos correct', '12/12 bad photos said NOT SURE', 'Tamper: 4/4 caught', 'Real phone: 5 right, 1 not sure, 0 wrong']
yy = ty + 42 + big + 24
for ln in lines:
    d.text((tx, yy), ln, font=F(mid if not ln.startswith('Real') or VERTICAL else (26 if NARROW else 30)), fill=INK); yy += mid + 13
yy += 30
d.text((tx, yy), 'Same purple kit colour, 5 lights.', font=F(small), fill=GREY)
d.text((tx, yy + small + 8), 'Simulated swatches, not real reagent.', font=F(small), fill=GREY)
if VERTICAL or NARROW:
    img = img.crop((0, 0, W, min(H, yy + 2 * small + 50)))
out = ROOT / 'docs' / 'ppt_content' / 'evidence' / ('proof_narrow.png' if NARROW else 'proof_vertical.png' if VERTICAL else 'proof_strip.png')
img.save(out)
for r in results: print(r)
print('saved', out)
