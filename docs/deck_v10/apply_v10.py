"""v10: answer the latest review with the 19 real phone scans (29 Sep 2026). Built on v9.

Slide 3  computer-made proof grid + reference card image -> real phone scans + confusion matrix;
         accuracy lines updated with real-scan numbers; honest '1 phone so far'
Slide 2  UX: measured time per test (~16 s, 1 team member) instead of the 2.5 s processing figure
Slide 5  Future Scope: e-Sakshya/CCTNS line now names the real CSV export fields
"""
from pptx import Presentation
from pptx.util import Inches, Pt

SRC = '../deck_v9/K26234_SIH26231_v9.pptx'
OUT = 'K26234_SIH26231_v10.pptx'
SCANS = '../ppt_content/evidence/real_scans.png'
p = Presentation(SRC)
E = 914400


def sid(slide, i):
    return next(s for s in slide.shapes if s.shape_id == i)


def starts(slide, text):
    return next(s for s in slide.shapes if s.has_text_frame and s.text_frame.text.strip().startswith(text))


def drop(shape):
    shape._element.getparent().remove(shape._element)


def set_para(shape, prefix, text, keep_label=False):
    """Replace the paragraph starting with prefix; keep_label keeps the first (bold) run."""
    for par in shape.text_frame.paragraphs:
        if par.text.strip().startswith(prefix) and par.runs:
            runs = par.runs
            if keep_label:
                runs[1].text = text
                for r in runs[2:]:
                    r.text = ''
            else:
                runs[0].text = text
                for r in runs[1:]:
                    r.text = ''
            return
    raise SystemExit(f'paragraph not found: {prefix}')


s2, s3, s5 = p.slides[1], p.slides[2], p.slides[4]

# ------------------------------------------------------------------ Slide 3
goals = sid(s3, 19)
set_para(goals, 'Testing:', 'Testing: 37 computer-made photos + 25 real phone scans.')
set_para(goals, 'Accuracy:', 'Accuracy: 25/25 computer-made right; 25 real scans: 0 wrong (14 right, rest NOT SURE).')
for par in goals.text_frame.paragraphs:
    par.line_spacing = 1.1
note = sid(s3, 20)
set_para(note, 'Now:', 'Now: TRL 4 lab prototype, 1 phone. Next: FSL real kits, more phones.')
note.top = Inches(5.02)
sid(s3, 23).top = Inches(6.38)                   # divider

head = sid(s3, 22)                               # was "Reference Card" -> heading for the real scans
head.text_frame.paragraphs[0].runs[0].text = 'Proof: Real Phone Scans (29 Sep 2026)'
for r in head.text_frame.paragraphs[0].runs[1:]:
    r.text = ''
drop(starts(s3, 'Proof of Results'))
drop(next(s for s in s3.shapes if s.name == 'Proof grid'))
drop(sid(s3, 13))                                # reference-card image (the card is visible in every scan)
x, w = 10.12, 6.55
pic = s3.shapes.add_picture(SCANS, Inches(x), Inches(6.90), width=Inches(w))
pic.name = 'Real scans'
head.left, head.top, head.width = Inches(x), Inches(6.44), Inches(w)

# ------------------------------------------------------------------ Slide 2
ux = starts(s2, '4 steps')
set_para(ux, '4 steps', ' - pick kit → take photo in the box → see result → saved. We timed it: ~16 s per test (19 scans).',
         keep_label=True)

# ------------------------------------------------------------------ Slide 5
fs = sid(s5, 22)
set_para(fs, 'Police System Integration',
         'Police System Integration - our CSV export (time, GPS, officer, result, photo hash, verify link) '
         'is ready to map to e-Sakshya / CCTNS; the link needs NIC/MHA approval.')
for par in fs.text_frame.paragraphs:
    par.line_spacing = 1.05
    for r in par.runs:
        r.font.size = Pt(14)

p.save(OUT)
print('saved', OUT)
