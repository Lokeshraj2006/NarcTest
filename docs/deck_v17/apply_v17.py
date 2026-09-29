"""v17: built on v16. Fixes the gaps from the latest 60/90 review that a slide can fix.

Slide 3  Tech Stack moved up (lines up with the other headings); an Offline design box added under it
Slide 4  Challenges table rows made shorter; Scale estimate added (real numbers); sustainability note
         now says owner, money and upkeep
Slide 5  Tamper Test says the photo hash is signed inside each record; future scope gives a real
         e-Sakshya / CCTNS plan
Numbers: colour check 0.12 s per photo (median of 37 runs), photo about 0.85 MB (median of our 19 scans),
NCRB 2023 = 1,20,010 NDPS cases (about 330 a day), server Rs 3,000 a month = Rs 36,000 a year (estimate).
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_AUTO_SIZE

SRC = '../deck_v16/K26234_SIH26231_v16.pptx'
OUT = 'K26234_SIH26231_v17.pptx'
TAMPER = '../ppt_content/evidence/tamper_proof_tall.png'
HEAD, INK, GREY = RGBColor(0x79, 0x2E, 0x00), RGBColor(0, 0, 0), RGBColor(0x55, 0x55, 0x55)
p = Presentation(SRC)


def sid(slide, i):
    return next(s for s in slide.shapes if s.shape_id == i)


def box(slide, x, y, w, h):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap, tf.auto_size = True, MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = Inches(0.06)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    return tf


def lines(tf, rows, size, color=INK, space=2):
    """rows: list of [(text, bold), ...] - one list per paragraph."""
    for i, row in enumerate(rows):
        par = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        par.space_after = Pt(space)
        for text, bold in row:
            r = par.add_run()
            r.text = text
            r.font.name, r.font.size, r.font.bold = 'Calibri', Pt(size), bool(bold)
            r.font.color.rgb = HEAD if bold == 'head' else color


def set_para(shape, prefix, text):
    for par in shape.text_frame.paragraphs:
        if par.text.strip().startswith(prefix) and par.runs:
            par.runs[0].text = text
            for r in par.runs[1:]:
                r.text = ''
            return
    raise SystemExit('not found: ' + prefix)


s3, s4, s5 = p.slides[2], p.slides[3], p.slides[4]

# ------------------------------------------------------------------ Slide 3: offline design in the core design
sid(s3, 17).top = Inches(2.01)                      # "Technology Stack" heading, same line as other headings
sid(s3, 11).top = Inches(2.55)                      # stack box, now ends at 8.15
frame = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(16.98), Inches(8.32), Inches(2.72), Inches(2.0))
frame.adjustments[0] = 0.06
frame.fill.background()
frame.line.color.rgb = HEAD
frame.line.width = Pt(1.5)
frame.name = 'Offline design box'
tf = box(s3, 17.02, 8.36, 2.64, 1.92)
lines(tf, [[('Offline Design', 'head')],
           [('No network? The phone keeps the photo and its hash in a queue.', False)],
           [('Network back: it sends them in the background.', False)],
           [('Server checks the hash, then seals the record.', False)],
           [('(design ready, we build it next)', False)]], 12.5)
tf.paragraphs[0].runs[0].font.size = Pt(16)
tf.paragraphs[-1].runs[0].font.color.rgb = GREY

# ------------------------------------------------------------------ Slide 4: shorter table rows + scale estimate
gf = sid(s4, 10)
tbl = gf.table
tbl.rows[0].height = Inches(0.7)
for r in list(tbl.rows)[1:]:
    r.height = Inches(0.6)
for r in tbl.rows:                                  # less padding so PowerPoint keeps the shorter rows
    for c in r.cells:
        c.margin_top = c.margin_bottom = Inches(0.03)
gf.height = Inches(0.7 + 0.6 * 5)                   # table now ends at 6.24
tf = box(s4, 10.0, 6.36, 9.5, 0.95)
lines(tf, [[('Scale (estimate): ', 'head'), ('India had 1,20,010 NDPS cases in 2023 (NCRB), about 330 a day.', False)],
           [('Our colour check takes 0.12 s per photo, so one small server can check thousands of photos an hour. '
             'Each photo is about 0.85 MB, so all of India needs about 100 GB a year.', False)]], 13.5)

note = sid(s4, 56)                                  # sustainability: owner, money, upkeep
for par in list(note.text_frame.paragraphs)[1:]:
    par._p.getparent().remove(par._p)
note.text_frame.paragraphs[0].runs[0].text = ''
note.text_frame.paragraphs[0].runs[1].text = ''
nt = note.text_frame
first = True
for label, text in (('After the pilot: ', 'police or NCB IT budget, server about ₹36,000 a year (estimate).'),
                    ('Owner: ', 'state police IT cell runs the app, the FSL keeps kit colours correct.'),
                    ('Upkeep: ', 'security update every 3 months. MoU with police and FSL is planned.')):
    par = nt.paragraphs[0] if first else nt.add_paragraph()
    par.space_after = Pt(0)
    for t, b in ((label, True), (text, False)):
        r = par.add_run()
        r.text = t
        r.font.name, r.font.size, r.font.bold = 'Calibri', Pt(12), b
        r.font.color.rgb = GREY
    first = False
note.top, note.height = Inches(7.30), Inches(0.66)
note.left, note.width = Inches(13.25), Inches(6.45)

# ------------------------------------------------------------------ Slide 5: photo hash in the signed record + integration plan
sid(s5, 33).text_frame.paragraphs[0].runs[0].text = 'the photo hash is signed inside each record'
old = next(s for s in s5.shapes if s.name == 'Tamper proof')
x, y, w = old.left, old.top, old.width
old._element.getparent().remove(old._element)
s5.shapes.add_picture(TAMPER, x, y, width=w).name = 'Tamper proof'
fs = sid(s5, 22)
set_para(fs, 'Offline Mode', 'Offline Mode (month 1) - build the offline design shown on slide 3.')
set_para(fs, 'Police System Integration', 'Police System Integration - match our fields to e-Sakshya, get NIC or MHA '
                                          'approval, then send each sealed record with its photo hash.')

p.save(OUT)
print('saved', OUT)
