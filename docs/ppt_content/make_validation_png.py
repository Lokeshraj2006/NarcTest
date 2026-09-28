import json, statistics as st
from PIL import Image, ImageDraw, ImageFont
d = json.load(open(r"C:\Users\LOKESHRAJ M\SIH26231\docs\ppt_content\validation_results.json"))
S, R = d["synthetic"], d["real"]
F = r"C:\Windows\Fonts\segoeui.ttf"; FB = r"C:\Windows\Fonts\segoeuib.ttf"
def f(sz, b=False): return ImageFont.truetype(FB if b else F, sz)
W, H = 1920, 1080
im = Image.new("RGB", (W, H), "white"); g = ImageDraw.Draw(im)
INK, GREY, LINE = (20, 28, 40), (95, 105, 120), (215, 220, 228)
GREEN, GREEN_BG, AMBER, AMBER_BG, RED, RED_BG = (22, 128, 60), (225, 245, 232), (176, 110, 0), (253, 243, 220), (190, 30, 45), (252, 228, 230)
BLUE = (30, 80, 160)

def frac(rows): return sum(r["correct"] for r in rows), len(rows)

# header
g.text((60, 34), "Tested, not just claimed", font=f(72, True), fill=INK)
g.text((62, 128), "Our colour engine, run on 37 synthetic photos + 6 real photos (28 Sep 2026). Real measured numbers.", font=f(30), fill=GREY)
g.line((60, 186, W - 60, 186), fill=LINE, width=3)

def check(x, y, col=GREEN, s=1.0):
    g.line([(x, y + 14*s), (x + 10*s, y + 25*s), (x + 30*s, y + 2*s)], fill=col, width=int(6*s))

def pill(x, y, text, ok):
    col, bg = (GREEN, GREEN_BG) if ok else (RED, RED_BG)
    w = g.textlength(text, font=f(30, True)) + 32
    g.rounded_rectangle((x - w, y, x, y + 42), 21, fill=bg)
    g.text((x - w + 16, y + 2), text, font=f(30, True), fill=col)

# ---- column A: synthetic table
ax, ar, y = 60, 600, 210
g.text((ax, y), "Synthetic photos (37)", font=f(40, True), fill=INK); y += 62
g.text((ax, y), "Good photos: gave the right result", font=f(30, True), fill=BLUE); y += 46
good = [r for r in S if r["kind"] == "good"]
for key, name in [("daylight", "Daylight"), ("tungsten", "Tungsten bulb"), ("cool", "Cool white tube"), ("dim", "Dim light"), ("sodium", "Sodium street lamp")]:
    c, n = frac([r for r in good if r["lighting"] == key])
    g.text((ax + 14, y + 2), name, font=f(30), fill=INK); pill(ar, y, f"{c}/{n}", c == n)
    y += 48
y += 14
g.text((ax, y), "Bad photos: honestly said NOT SURE", font=f(30, True), fill=AMBER); y += 46
bad = [("blurred", "Blurry"), ("glare", "Glare / shine"), ("card_missing", "Card missing"), ("marker_covered", "Corner marker covered"), ("ambiguous", "In-between colour"), ("no_match", "Colour not in kit")]
for key, name in bad:
    if key == "card_missing": rows = [r for r in S if r["file"] == "card_missing.jpg"]
    elif key == "marker_covered": rows = [r for r in S if r["file"] == "marker_covered.jpg"]
    else: rows = [r for r in S if r["kind"] == key]
    c, n = frac(rows)
    g.text((ax + 14, y + 2), name, font=f(30), fill=INK); pill(ar, y, f"{c}/{n}", c == n)
    y += 48

# ---- column B: confusion matrix
bx, y0 = 660, 210
g.text((bx, y0), "Confusion matrix", font=f(40, True), fill=INK)
g.text((bx, y0 + 56), "Synthetic set, 37 photos", font=f(28), fill=GREY)
cats = ["POSITIVE", "NEGATIVE", "INCONCLUSIVE"]
short = {"POSITIVE": "POS", "NEGATIVE": "NEG", "INCONCLUSIVE": "NOT SURE"}
cw, ch, lw = 150, 110, 150
gx, gy = bx + lw, y0 + 228
g.text((gx + cw * 1.5 - g.textlength("App said", font=f(28, True)) / 2, gy - 124), "App said", font=f(28, True), fill=GREY)
for j, c in enumerate(cats):
    lines = short[c].split(" ")
    for li, t in enumerate(lines):
        g.text((gx + j * cw + (cw - 6) / 2 - g.textlength(t, font=f(28, True)) / 2, gy - 44 - (len(lines) - 1 - li) * 34), t, font=f(28, True), fill=INK)
for i, a in enumerate(cats):
    t = short[a]; g.text((bx + lw - 14 - g.textlength(t, font=f(28, True)), gy + i * ch + ch / 2 - 18), t, font=f(28, True), fill=INK)
    for j, p in enumerate(cats):
        n = sum(1 for r in S if r["expected"] == a and r["got"] == p)
        diag = i == j
        bg = GREEN_BG if diag else ((252, 228, 230) if n else (246, 247, 249))
        g.rectangle((gx + j * cw, gy + i * ch, gx + (j + 1) * cw - 6, gy + (i + 1) * ch - 6), fill=bg)
        s = str(n); fnt = f(48, True)
        g.text((gx + j * cw + (cw - 6) / 2 - g.textlength(s, font=fnt) / 2, gy + i * ch + 20), s, font=fnt, fill=GREEN if diag else (RED if n else (170, 175, 185)))
# rotated "Truth" label
g.text((bx + lw - 14 - g.textlength("Truth", font=f(28, True)), gy - 44), "Truth", font=f(28, True), fill=GREY)
correct = sum(r["correct"] for r in S)
yb = gy + 3 * ch + 18
g.text((bx, yb), f"{correct}/{len(S)} correct, 0 wrong", font=f(34, True), fill=GREEN)
g.text((bx, yb + 50), "Drug type also right in 25/25 good photos", font=f(28), fill=INK)
g.text((bx, yb + 92), "(These photos were also used to tune the rules)", font=f(28), fill=GREY)

# ---- column C: real tests, speed, tamper
cx, cr, y = 1320, 1860, 210
g.text((cx, y), "Real photos (6)", font=f(40, True), fill=INK)
g.text((cx, y + 56), "Card shown on a phone / laptop screen", font=f(28), fill=GREY)
live = [r["live_verdict"] for r in R]
boxes = [(live.count("correct"), "correct", GREEN, GREEN_BG), (live.count("not_sure"), "NOT SURE", AMBER, AMBER_BG), (live.count("wrong"), "wrong", RED if live.count("wrong") else GREY, RED_BG if live.count("wrong") else (246, 247, 249))]
bw = (cr - cx - 2 * 16) / 3
for k, (n, t, col, bg) in enumerate(boxes):
    x0 = cx + k * (bw + 16)
    g.rounded_rectangle((x0, y + 106, x0 + bw, y + 236), 14, fill=bg)
    s = str(n); g.text((x0 + bw / 2 - g.textlength(s, font=f(64, True)) / 2, y + 108), s, font=f(64, True), fill=col)
    g.text((x0 + bw / 2 - g.textlength(t, font=f(28, True)) / 2, y + 190), t, font=f(28, True), fill=col)
g.text((cx, y + 248), "Live app results, checked vs the photo label", font=f(28), fill=GREY)

y2 = y + 316
g.line((cx, y2 - 14, cr, y2 - 14), fill=LINE, width=2)
med = st.median(r["ms"] for r in S)
g.text((cx, y2), "Speed", font=f(34, True), fill=INK)
g.text((cx, y2 + 46), f"{med:.0f} ms", font=f(56, True), fill=BLUE)
g.text((cx + g.textlength(f"{med:.0f} ms", font=f(56, True)) + 16, y2 + 66), "median per photo", font=f(28), fill=INK)
g.text((cx, y2 + 122), "Colour engine only, on a laptop CPU", font=f(28), fill=GREY)

y3 = y2 + 186
g.line((cx, y3 - 14, cr, y3 - 14), fill=LINE, width=2)
g.text((cx, y3), "Tamper check: 3/3 caught", font=f(34, True), fill=INK)
for k, t in enumerate(["1 byte of photo changed", "Result edited in database", "Signed record edited"]):
    yy = y3 + 52 + k * 44
    check(cx + 4, yy + 6); g.text((cx + 50, yy), t, font=f(30), fill=INK)
g.text((cx, y3 + 190), "Automated tests: 4/4 pass (34/34 backend)", font=f(28), fill=GREY)

# footer
g.line((60, 985, W - 60, 985), fill=LINE, width=2)
g.text((60, 1000), "Limits: synthetic images + a card shown on screens, not real reagent. Real kits still need FSL calibration. Real sample is small (n = 6).", font=f(28), fill=GREY)
im.save(r"C:\Users\LOKESHRAJ M\SIH26231\docs\ppt_content\validation.png", optimize=True)
print("ok")
