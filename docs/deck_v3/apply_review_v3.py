"""Apply only the SIH review (61/90) fixes to the team's K26231 deck. Everything else untouched."""
import copy
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.oxml.ns import qn
from lxml import etree

SRC = 'K26231_PS_original.pptx'
OUT = 'K26231_PS_v3.pptx'
p = Presentation(SRC)

HEAD = RGBColor(0x79, 0x2E, 0x00)      # deck heading brown
SUB = RGBColor(0x97, 0x48, 0x25)       # deck sub-heading brown
BODY = RGBColor(0x00, 0x00, 0x00)
GREY = RGBColor(0x6B, 0x6B, 0x6B)
FONT = 'Calibri'


def _walk(shapes):
    for s in shapes:
        yield s
        if s.shape_type == 6:  # group
            yield from _walk(s.shapes)


def sid(slide, i):
    return next(s for s in _walk(slide.shapes) if s.shape_id == i)


def drop(slide, *ids):
    for i in ids:
        el = sid(slide, i)._element
        el.getparent().remove(el)


def run(par, text, size, bold=False, color=BODY, italic=False):
    r = par.add_run()
    r.text = text
    r.font.name = FONT
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    return r


def bullet(par, indent=0.28):
    pPr = par._p.get_or_add_pPr()
    pPr.set('marL', str(int(Inches(indent + 0.05))))
    pPr.set('indent', str(-int(Inches(indent))))
    f = etree.SubElement(pPr, qn('a:buFont')); f.set('typeface', 'Arial')
    c = etree.SubElement(pPr, qn('a:buChar')); c.set('char', '•')


def textbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    return tb, tf


def bullets_block(tf, heading, items, head_size, body_size, head_color=HEAD, space_after=4, first=True,
                  note=None):
    """items: list of (bold_label, text)."""
    par = tf.paragraphs[0] if first else tf.add_paragraph()
    run(par, heading[0], head_size, bold=True, color=head_color)
    if len(heading) > 1:
        run(par, heading[1], body_size - 2, color=GREY)
    par.space_after = Pt(6)
    for label, text in items:
        par = tf.add_paragraph()
        bullet(par)
        par.space_after = Pt(space_after)
        if label:
            run(par, label, body_size, bold=True)
        run(par, text, body_size)
    if note:
        par = tf.add_paragraph()
        par.space_before = Pt(2)
        run(par, note, body_size - 4, color=GREY, italic=True)


# ------------------------------------------------------------------ Slide 2
# Review: "no thresholds ... or per-kit profile values are shown" -> one line under Our Approach.
s2 = p.slides[1]
tb, tf = textbox(s2, 9.25, 3.55, 10.0, 0.58)
par = tf.paragraphs[0]
par.alignment = PP_ALIGN.CENTER
run(par, 'Kit profile (stored as data): ', 13, bold=True, color=SUB)
run(par, 'demo Marquis kit = purple (98,45,120) · orange (178,94,40) · no change (236,232,214), '
         'saved in CIELAB, with limits ΔE2000 ≤ 14 and a 4-point lead. New kits are added from the Admin website.', 13)

# ------------------------------------------------------------------ Slide 3
# Review: algorithm concretely (card detection, lighting math, ΔE cut-offs) + legal claim substantiated.
s3 = p.slides[2]
head = sid(s3, 9).text_frame.paragraphs[0]
for r in head.runs:
    r.text = ''
head.runs[0].text = 'How It Decides & Legal Evidence'
head.alignment = PP_ALIGN.CENTER
hs = sid(s3, 9); hs.left = Inches(10.55); hs.width = Inches(3.80)
drop(s3, 19)                                   # old single text box ("Encrypted Storage" was not true yet)
steps = [
    ('1  ', 'Find 4 ArUco corners', '→ straighten the card'),
    ('2  ', '24 known colours → 3×4', 'colour fix (least squares)'),
    ('3  ', 'ΔE2000 ≤ 14 + 4-pt lead', '→ POS / NEG, else INCONCLUSIVE'),
    ('4  ', 'SHA-256 photo hash', '→ BSA 2023 s.63 certificate'),
    ('5  ', 'Internet time + GPS', '+ Inspector ID, all signed'),
    ('6  ', 'Ed25519 seal + hash chain', '→ no edit / delete'),
    ('7  ', 'QR verify (5 checks)', 'BNSS s.105 · IT Act s.3'),
]
for i, (num, line1, line2) in enumerate(steps):
    y = 3.24 + 0.96 * i
    tb, tf = textbox(s3, 10.86, y + 0.02, 3.14, 0.66, anchor=MSO_ANCHOR.MIDDLE)
    par = tf.paragraphs[0]
    par.alignment = PP_ALIGN.CENTER
    run(par, num, 13.5, bold=True, color=HEAD)
    run(par, line1, 13.5)
    par.add_line_break()
    run(par, line2, 13.5)

# ------------------------------------------------------------------ Slide 4
s4 = p.slides[3]
# (a) Feasibility -> Feasibility & Sustainability (review: cost per test, server cost, retention, ownership).
old = sid(s4, 19)
x, y, w = old.left / 914400, old.top / 914400, old.width / 914400
drop(s4, 19, 18)                               # text + Canva bullet dots
tb, tf = textbox(s4, x, y, w, 2.78)
bullets_block(tf, ('Feasibility & Sustainability',), [
    ('Technical – ', 'built on our tested code + OpenCV; runs on any Android phone.'),
    ('Easy to use – ', 'one photo, result in seconds; new kits added from the website.'),
    ('Cost – ', '₹10 reusable card + ~₹3,000/month server → under ₹1 per test (est.)'),
    ('Upkeep – ', 'owned by NCB / State ANTF IT cell; FSL updates kit colours per batch; open-source, no licence fee.'),
    ('Data retention – ', 'records kept till the case + appeal end; role-based access; photo shows only card + kit (DPDP 2023).'),
], head_size=22, body_size=15.5, space_after=2)
tb2, tf2 = textbox(s4, 0.92, 4.86, 8.2, 0.5)
run(tf2.paragraphs[0], 'Potential Challenges & Strategies', 22, bold=True, color=HEAD)

# (b) Goals -> measured results (review: dataset size, per-lighting accuracy, thresholds, tamper test).
old = sid(s4, 17)
x, y, w = old.left / 914400, old.top / 914400, old.width / 914400
drop(s4, 17, 12)                               # text + Canva bullet dots
tb, tf = textbox(s4, x, y - 0.12, 9.05, 3.95)
bullets_block(tf, ('Our Goals – Measured Results', '   (tested 28 Sep 2026)'), [
    ('Dataset – ', '37 test photos in 5 lights + 6 real phone photos.'),
    ('Accuracy – ', '25/25 right: 5/5 each in daylight, tungsten, cool, dim and street lamp. '
                    'Real photos: 5/6 right, 1 NOT SURE, 0 wrong.'),
    ('Decision limits – ', 'ΔE ≤ 14 + 4-pt lead (demo kit); card fit ≤ 9; glare ≤ 3%.'),
    ('Speed – ', 'result + sealed record in 2.5 s typical, 5 s max (goal: 10 s).'),
    ('Tamper test – ', '1 photo byte, result or seal changed → verify FAILS (4/4).'),
], head_size=22, body_size=17.5, space_after=3,
    note='Kit colours are simulated swatches (test photos + card on a screen); real kits need an FSL calibration trial.')

# typo in the table (review praised "camera-only + photo fingerprint")
tbl = sid(s4, 6).table
for row in tbl.rows:
    for cell in row.cells:
        for par in cell.text_frame.paragraphs:
            if par.text.startswith('n-app') and par.runs:
                par.runs[0].text = 'I' + par.runs[0].text

# ------------------------------------------------------------------ Slide 5
# Review: offline / e-Sakshya / secure-chip are future scope -> mark clearly as not in this demo.
s5 = p.slides[4]
fs = sid(s5, 46).text_frame.paragraphs[0]
run(fs, '  (not in this demo)', 14, color=GREY)

# ------------------------------------------------------------------ Slide 6
# Review: clarify which parts are simulated vs real.
s6 = p.slides[5]
pf = sid(s6, 20)
pf.width = Inches(8.4)
pf.text_frame.word_wrap = False
run(pf.text_frame.paragraphs[0], '  – real screenshots of our working build; only kit colours are simulated', 13, color=GREY)

p.save(OUT)
print('saved', OUT)
