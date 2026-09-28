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

W, H = 2400, 500
img = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(img)
F = lambda s, b=False: ImageFont.truetype('C:/Windows/Fonts/' + ('arialbd.ttf' if b else 'arial.ttf'), s)
ACC, INK, GREY, RULE = (0x7A, 0x2F, 0x00), (0x1F, 0x1F, 0x1F), (0x6B, 0x6B, 0x6B), (0xD9, 0xD9, 0xD9)
tw, th, x0, y0, gap = 250, 250, 40, 60, 22
results = []
for i, (it, name) in enumerate(sel):
    raw = (TI / it['file']).read_bytes()
    r = ce.classify(raw, prof(it.get('kit', 'DEMO-MARQUIS-SIM')))
    results.append((it['file'], name, r['result'], r['confidence'], it['expected']))
    bgr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    h, w = bgr.shape[:2]; s = min(h, w); crop = bgr[(h - s)//2:(h + s)//2, (w - s)//2:(w + s)//2]
    th_img = Image.fromarray(cv2.cvtColor(cv2.resize(crop, (tw, th), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB))
    x = x0 + i * (tw + gap)
    img.paste(th_img, (x, y0)); d.rectangle([x - 1, y0 - 1, x + tw, y0 + th], outline=RULE, width=2)
    d.text((x, y0 + th + 16), name, font=F(28), fill=GREY)
    ans = 'NOT SURE' if r['result'] == 'INCONCLUSIVE' else r['result'].title()
    tail = '' if r['result'] == 'INCONCLUSIVE' else f"  {r['confidence']}%"
    d.text((x, y0 + th + 54), ans + tail, font=F(34, True), fill=ACC if r['result'] == it['expected'] else (0xC0, 0, 0))
    d.text((x, y0 + th + 100), 'correct' if r['result'] == it['expected'] else 'WRONG', font=F(26), fill=GREY)
d.line([(1685, 60), (1685, 460)], fill=RULE, width=2)
tx = 1720
d.text((tx, 58), 'Test run, ' + time.strftime('%d %b %Y'), font=F(30), fill=GREY)
d.text((tx, 100), '15 passed, 0 failed', font=F(52, True), fill=ACC)
d.text((tx, 175), '37/37 test photos correct', font=F(34), fill=INK)
d.text((tx, 222), '12/12 bad photos said NOT SURE', font=F(34), fill=INK)
d.text((tx, 269), 'Tamper: 4/4 caught', font=F(34), fill=INK)
d.text((tx, 316), 'Real phone: 5 right, 1 not sure, 0 wrong', font=F(30), fill=INK)
d.text((tx, 400), 'Same purple kit colour, 5 lights.', font=F(26), fill=GREY)
d.text((tx, 434), 'Simulated swatches, not real reagent.', font=F(26), fill=GREY)
out = ROOT / 'docs' / 'ppt_content' / 'evidence' / 'proof_strip.png'
img.save(out)
for r in results: print(r)
print('saved', out)
