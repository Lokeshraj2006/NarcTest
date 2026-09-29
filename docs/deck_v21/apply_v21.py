"""v21: built on v20. Answers the 59/90 review.

Slide 2  'Bad photo?' line: the phone now checks for blur right after the photo (new in the app, 29 Sep 2026)
Slide 3  stress-test text explains the NOT SURE answers (all from blur) and gives the new phone check's numbers
Slide 4  privacy and data block (storage, who sees, deletion); team bullets get a little less line gap to fit it
Slide 5  tamper image caption no longer says 'in memory' (it was read as 'records live in memory')
Numbers: stress_test.json + phone blur check replayed on the same 171 photos (catches 36 of 38 blurry, stops 3 of 70 good).
"""
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.util import Inches, Pt

SRC = '../deck_v20/K26234_SIH26231_v20.pptx'
OUT = 'K26234_SIH26231_v21.pptx'
HEAD, INK = RGBColor(0x79, 0x2E, 0x00), RGBColor(0, 0, 0)
E = 914400
p = Presentation(SRC)


def sid(slide, i):
    return next(s for s in slide.shapes if s.shape_id == i)


def starts(slide, text):
    return next(s for s in slide.shapes if s.has_text_frame and s.text_frame.text.strip().startswith(text))


def set_runs(par, *texts):
    runs = par.runs
    for r, t in zip(runs, texts):
        r.text = t
    for r in runs[len(texts):]:
        r.text = ''


s2, s3, s4, s5 = p.slides[1], p.slides[2], p.slides[3], p.slides[4]

# ------------------------------------------------------------------ Slide 2
ux = sid(s2, 39).text_frame.paragraphs[1]
set_runs(ux, 'Bad photo?', ' - the phone checks for blur right after the photo and asks to take it again. '
                           'The server also says NOT SURE with the reason.')

# ------------------------------------------------------------------ Slide 3
res = sid(s3, 30).text_frame.paragraphs
set_runs(res[0], 'Stress test, 171 checks: ', '70 matched the card, 101 said NOT SURE (63 were trick cards). '
                                               'Every NOT SURE on a clear card came from a blurry photo.')
set_runs(res[1], 'Colour gap (Delta E), limit 14: ', 'right colour 4.7 to 8.9, others 34 to 42, trick cards 16 to 31.')
g = res[2]
g.runs[0].text = 'New in the app: '
g.runs[0].font.bold = True
g.runs[0].font.color.rgb = HEAD
extra = g.add_run()
extra.text = ('the phone checks blur right after the photo. On these photos it caught 36 of 38 blurry ones and '
              'stopped 3 of 70 good ones (officer can still send). Small test on 1 phone, real kits can still give '
              'wrong results.')
extra.font.name, extra.font.size, extra.font.color.rgb = 'Calibri', Pt(12), INK
for par in res:
    par.space_after = Pt(1)

# ------------------------------------------------------------------ Slide 4
bul = sid(s4, 21)
for par in bul.text_frame.paragraphs:                 # team bullets: same size, a bit less line gap
    par.line_spacing = 1.05
note = starts(s4, 'Legal:')                           # keep only the Legal line at the top
for par in list(note.text_frame.paragraphs)[1:]:
    par._p.getparent().remove(par._p)
tb = s4.shapes.add_textbox(Inches(0.62), Inches(5.72), Inches(9.0), Inches(0.8))
tf = tb.text_frame
tf.word_wrap, tf.auto_size = True, MSO_AUTO_SIZE.NONE
tf.margin_left = tf.margin_right = Inches(0.04)
par = tf.paragraphs[0]
for text, bold, col in (('Privacy and data: ', True, HEAD),
                        ('no face or suspect name is stored, only a sample code. In real use, data stays on '
                         'government cloud in India. Officer sees only own tests, supervisor and admin see all. '
                         'Photos are deleted after the case and appeal end (planned).', False, INK)):
    r = par.add_run()
    r.text = text
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = 'Calibri', Pt(14), bold, col

# ------------------------------------------------------------------ Slide 5
old = next(s for s in s5.shapes if s.name == 'Tamper proof')
x, y, w = old.left, old.top, old.width
old._element.getparent().remove(old._element)
s5.shapes.add_picture('../ppt_content/evidence/tamper_proof_tall.png', x, y, width=w).name = 'Tamper proof'

p.save(OUT)
print('saved', OUT)
