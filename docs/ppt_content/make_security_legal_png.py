"""Draw docs/ppt_content/security_legal.png (1920x1080, white) with Pillow only."""
import math
from PIL import Image, ImageDraw, ImageFont

OUT = r"C:\Users\LOKESHRAJ M\SIH26231\docs\ppt_content\security_legal.png"
W, H = 1920, 1080
F = r"C:\Windows\Fonts\segoeui.ttf"
FB = r"C:\Windows\Fonts\segoeuib.ttf"


def font(size, bold=False):
    return ImageFont.truetype(FB if bold else F, size)


INK = (28, 32, 40)
GREY = (85, 90, 100)
LINE = (215, 219, 226)
BLUE = (21, 101, 192)
GREEN = (46, 125, 50)
ORANGE = (191, 90, 0)
STEP_COLS = [(21, 101, 192), (0, 121, 107), (94, 53, 177), (198, 40, 40), (55, 71, 79)]

img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)


def wrap(text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def pill(x, y, text, fg, bg, size=28):
    f = font(size, True)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle([x, y, x + tw + 36, y + size + 22], radius=(size + 22) // 2, fill=bg)
    d.text((x + 18, y + 8), text, font=f, fill=fg)


# Title
d.text((60, 36), "How a FieldProof record is protected  -  and the law it supports",
       font=font(50, True), fill=INK)
d.line([60, 118, W - 60, 118], fill=LINE, width=3)

# ---------------- Left panel ----------------
LX, RX = 60, 1010
d.text((LX, 138), "How a record is protected", font=font(40, True), fill=BLUE)
pill(LX + 530, 142, "working in prototype", GREEN, (232, 245, 233))

steps = [
    ("Login + role", "Only admin makes accounts. An officer sees only own tests."),
    ("Photo fingerprint (SHA-256)", "Change even 1 byte of the photo and the fingerprint changes."),
    ("Trusted time + GPS", "Internet time (NTP, else HTTPS). Fake-GPS apps get flagged."),
    ("Digital seal (Ed25519)", "Server signs the record. Any edit breaks the seal."),
    ("Chained log + public verify page", "Each record locks the one before it. Scan QR, open /v/<id>."),
]

R = 48
top, gap = 215, 158
for i, (title, sub) in enumerate(steps):
    cy = top + i * gap + R
    cx = LX + R + 4
    col = STEP_COLS[i]
    if i < len(steps) - 1:  # connector
        d.line([cx, cy + R + 4, cx, cy + gap - R - 4], fill=LINE, width=6)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=col)
    wcol = "white"
    if i == 0:  # padlock
        d.rounded_rectangle([cx - 22, cy - 4, cx + 22, cy + 26], radius=5, fill=wcol)
        d.arc([cx - 15, cy - 28, cx + 15, cy + 6], 180, 360, fill=wcol, width=7)
        d.line([cx - 15, cy - 11, cx - 15, cy - 2], fill=wcol, width=7)
        d.line([cx + 15, cy - 11, cx + 15, cy - 2], fill=wcol, width=7)
        d.ellipse([cx - 4, cy + 5, cx + 4, cy + 13], fill=col)
    elif i == 1:  # hash sign
        d.text((cx, cy - 2), "#", font=font(62, True), fill=wcol, anchor="mm")
    elif i == 2:  # clock
        d.ellipse([cx - 28, cy - 28, cx + 28, cy + 28], outline=wcol, width=6)
        d.line([cx, cy, cx, cy - 18], fill=wcol, width=6)
        d.line([cx, cy, cx + 14, cy + 8], fill=wcol, width=6)
    elif i == 3:  # seal with tick
        pts = []
        for k in range(24):
            a = math.pi * 2 * k / 24
            rr = 32 if k % 2 == 0 else 26
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        d.polygon(pts, fill=wcol)
        d.line([cx - 13, cy + 1, cx - 3, cy + 11, cx + 15, cy - 11], fill=col, width=7)
    else:  # chain links
        d.rounded_rectangle([cx - 34, cy - 12, cx + 4, cy + 12], radius=12, outline=wcol, width=6)
        d.rounded_rectangle([cx - 4, cy - 12, cx + 34, cy + 12], radius=12, outline=wcol, width=6)
    tx = LX + 2 * R + 34
    d.text((tx, cy - 50), f"{i + 1}. {title}", font=font(36, True), fill=INK)
    for j, line in enumerate(wrap(sub, font(28), RX - tx)):
        d.text((tx, cy - 2 + j * 36), line, font=font(28), fill=GREY)

# divider
d.line([1050, 140, 1050, 960], fill=LINE, width=3)

# ---------------- Right panel ----------------
PX, PR = 1090, W - 60
d.text((PX, 138), "Law it supports", font=font(40, True), fill=ORANGE)
pill(PX + 330, 142, "supports - not a court ruling", ORANGE, (255, 243, 224))

laws = [
    ("BNSS 2023, Sec 105", "Seizure must be recorded on video, preferably a phone. Our record ID + QR fit in."),
    ("BSA 2023, Sec 63", "Court certificate asks for the hash value. We give SHA-256."),
    ("IT Act 2000, Sec 3", "Same method as a digital signature. Legal use needs a CCA DSC / eSign (planned)."),
    ("NDPS Rules 2022, Rule 3(1)", "Seized drug is classified using the kit result. We record it."),
    ("DPDP Act 2023", "Less data: photo is framed on card + kit. Role-based access."),
]
ly = 215
for name, line in laws:
    d.text((PX, ly), name, font=font(34, True), fill=INK)
    for j, t in enumerate(wrap(line, font(28), PR - PX)):
        d.text((PX, ly + 46 + j * 36), t, font=font(28), fill=GREY)
    ly += gap

# Footer
d.line([60, 975, W - 60, 975], fill=LINE, width=3)
d.text((60, 992), "Prototype seal = Ed25519 key on our server.  Production = CCA-licensed DSC / eSign + HSM, TLS, encryption at rest.",
       font=font(28), fill=INK)
d.text((60, 1032), "Result is presumptive (field test only) - the FSL lab report confirms it.",
       font=font(28, True), fill=(198, 40, 40))

img.save(OUT, optimize=True)
print("saved", OUT, img.size)
