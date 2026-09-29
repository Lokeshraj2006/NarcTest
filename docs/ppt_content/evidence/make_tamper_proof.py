"""Chain + tamper proof image for the deck, from a REAL run on saved records (changes are in memory only).

Run from backend/:  venv\\Scripts\\python.exe ..\\docs\\ppt_content\\evidence\\make_tamper_proof.py
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
from PIL import Image, ImageDraw, ImageFont
from app.database import SessionLocal
from app.models.test_record import TestRecord
from app.services import record_service as rs

TID = 11
db = SessionLocal()
t = db.get(TestRecord, TID)
prev, nxt = db.get(TestRecord, TID - 1), db.get(TestRecord, TID + 1)
real_read = rs.read_image
NAMES = {'image_hash': 'photo', 'record_hash': 'hash', 'signature': 'signature', 'chain': 'chain', 'fields_match': 'fields'}


def check():
    v = rs.verify_record(db, t)
    return v['ok'], [NAMES[k] for k, ok in v['checks'].items() if not ok]


rows = [('Nothing (original)',) + check()]
rs.read_image = lambda x: (lambda b: bytes(b[:len(b) // 2]) + bytes([b[len(b) // 2] ^ 1]) + bytes(b[len(b) // 2 + 1:]))(real_read(x))
rows.append(('1 byte of the photo',) + check())
rs.read_image = real_read
orig = t.signed_payload
t.signed_payload = orig.replace('"POSITIVE"', '"NEGATIVE"', 1)
rows.append(('Result inside sealed copy',) + check())
t.signed_payload = orig
t.result = 'NEGATIVE'
rows.append(('Result in database row',) + check())
t.result = 'POSITIVE'
sig = t.signature
t.signature = sig[:-4] + ('AAAA' if sig[-4:] != 'AAAA' else 'BBBB')
rows.append(('The signature',) + check())
t.signature = sig
assert check()[0], 'record must verify again after restore'
db.rollback()

F = lambda s, b=False: ImageFont.truetype('C:/Windows/Fonts/' + ('arialbd.ttf' if b else 'arial.ttf'), s)
M = lambda s: ImageFont.truetype('C:/Windows/Fonts/consola.ttf', s)
ACC, INK, GREY, RULE = (0x7A, 0x2F, 0x00), (0x1F, 0x1F, 0x1F), (0x6B, 0x6B, 0x6B), (0xD0, 0xD0, 0xD0)
GREEN, RED = (0x2E, 0x7D, 0x32), (0xC6, 0x28, 0x28)
if '--tall' in sys.argv:  # bigger text for a narrow slide column: chain on top, tamper table below
    W, H = 2200, 790
    img = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    bw, gap, y0 = 420, 64, 10
    for i, r in enumerate((prev, t, nxt)):
        x = 20 + i * (bw + gap)
        d.rounded_rectangle([x, y0, x + bw, y0 + 196], 14, outline=ACC if r is t else RULE, width=5 if r is t else 3)
        d.text((x + 22, y0 + 14), f'Test #{r.id}', font=F(50, True), fill=INK)
        d.text((x + 22, y0 + 82), 'prev ' + r.prev_record_hash[:8], font=M(44), fill=ACC if r is not prev else GREY)
        d.text((x + 22, y0 + 136), 'hash ' + r.record_hash[:8], font=M(44), fill=ACC if r is not nxt else GREY)
        if i < 2:
            ax = x + bw + 8
            d.line([(ax, y0 + 98), (ax + gap - 20, y0 + 98)], fill=ACC, width=5)
            d.polygon([(ax + gap - 20, y0 + 86), (ax + gap - 4, y0 + 98), (ax + gap - 20, y0 + 110)], fill=ACC)
    sx = 20 + 3 * bw + 2 * gap + 50
    d.text((sx, y0 + 4), f'Ed25519 signature of test {TID}', font=F(40), fill=GREY)
    d.text((sx, y0 + 52), t.signature[:24] + '...', font=M(44), fill=INK)
    d.text((sx, y0 + 108), 'Photo SHA-256', font=F(40), fill=GREY)
    d.text((sx, y0 + 156), t.image_sha256[:24] + '...', font=M(44), fill=INK)
    c0, c1, c2, ty = 20, 900, 1330, 250
    d.text((c0, ty), f'What we changed (test #{TID})', font=F(42, True), fill=INK)
    d.text((c1, ty), 'Check page', font=F(42, True), fill=INK)
    d.text((c2, ty), 'Failed check', font=F(42, True), fill=INK)
    for i, (what, ok, failed) in enumerate(rows):
        y = ty + 64 + i * 76
        d.line([(c0, y - 8), (W - 20, y - 8)], fill=RULE, width=2)
        d.text((c0, y), what, font=F(44), fill=INK)
        d.text((c1, y), 'GENUINE' if ok else 'TAMPERED', font=F(46, True), fill=GREEN if ok else RED)
        d.text((c2, y + 2), 'none, all 5 passed' if ok else ', '.join(failed), font=F(42), fill=GREY)
    d.text((c0, ty + 64 + 5 * 76 + 6), f"We tried this on our real saved records on {time.strftime('%d %b %Y')}, only in memory. "
           'Each test keeps the hash of the test before it.', font=F(34), fill=GREY)
    out = Path(__file__).with_name('tamper_proof_tall.png')
    img.save(out)
    print('saved', out)
    raise SystemExit(0)

W, H = 2200, 470
img = Image.new('RGB', (W, H), 'white')
d = ImageDraw.Draw(img)

# left: three chained records + the real signature
bw, gap, y0 = 300, 52, 14
for i, r in enumerate((prev, t, nxt)):
    x = 20 + i * (bw + gap)
    d.rounded_rectangle([x, y0, x + bw, y0 + 150], 12, outline=ACC if r is t else RULE, width=4 if r is t else 2)
    d.text((x + 18, y0 + 12), f'Test #{r.id}', font=F(38, True), fill=INK)
    d.text((x + 18, y0 + 62), 'prev ' + r.prev_record_hash[:8], font=M(32), fill=ACC if r is not prev else GREY)
    d.text((x + 18, y0 + 104), 'hash ' + r.record_hash[:8], font=M(32), fill=ACC if r is not nxt else GREY)
    if i < 2:
        ax = x + bw + 8
        d.line([(ax, y0 + 75), (ax + gap - 16, y0 + 75)], fill=ACC, width=4)
        d.polygon([(ax + gap - 16, y0 + 65), (ax + gap - 4, y0 + 75), (ax + gap - 16, y0 + 85)], fill=ACC)
d.text((20, 190), f'Ed25519 signature on #{TID}  (key {t.key_id})', font=F(32), fill=GREY)
d.text((20, 232), t.signature[:40] + '...', font=M(34), fill=INK)
d.text((20, 290), 'Photo SHA-256', font=F(32), fill=GREY)
d.text((20, 332), t.image_sha256[:40] + '...', font=M(34), fill=INK)
d.text((20, 400), 'Each test stores the hash of the test before it, so edits break the chain.',
       font=F(28), fill=GREY)

# right: what we changed -> what the check page said
x0, x1, x2 = 1110, 1545, 1800
d.line([(1072, 14), (1072, 440)], fill=RULE, width=2)
d.text((x0, 14), f'What we changed (#{TID})', font=F(32, True), fill=INK)
d.text((x1, 14), 'Check page', font=F(32, True), fill=INK)
d.text((x2, 14), 'Failed check', font=F(32, True), fill=INK)
for i, (what, ok, failed) in enumerate(rows):
    y = 72 + i * 66
    d.line([(x0, y - 8), (W - 20, y - 8)], fill=RULE, width=1)
    d.text((x0, y), what, font=F(32), fill=INK)
    if ok:
        d.text((x1, y), 'GENUINE', font=F(34, True), fill=GREEN)
        d.text((x2, y + 2), 'none (5/5 pass)', font=F(30), fill=GREY)
    else:
        d.text((x1, y), 'TAMPERED', font=F(34, True), fill=RED)
        d.text((x2, y + 2), ', '.join(failed), font=F(30), fill=GREY)
d.text((x0, 410), f"Real run on our saved records, {time.strftime('%d %b %Y')}. Changes made in memory only.",
       font=F(26), fill=GREY)

out = Path(__file__).with_name('tamper_proof.png')
img.save(out)
for r in rows:
    print(r)
print('saved', out)
