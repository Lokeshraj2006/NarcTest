"""v6: answer the 60/90 review (PPT-only items). Existing wording kept; blocks added.

Slide 2  + caption: the Test Log screenshot is searchable/filterable + CSV/PDF/QR export
Slide 6  references table tightened -> strip with Chain of Custody | Privacy & Retention | Cost & Offline
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.oxml.ns import qn
from lxml import etree

SRC = '../deck_v5/K26234_SIH26231_v5.pptx'
OUT = 'K26234_SIH26231_v6.pptx'
p = Presentation(SRC)
HEAD, GREY, INK = RGBColor(0x79, 0x2E, 0x00), RGBColor(0x6B, 0x6B, 0x6B), RGBColor(0, 0, 0)


def box(slide, x, y, w, h):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap, tf.auto_size = True, MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    return tf


def run(par, text, size, bold=False, color=INK, italic=False):
    r = par.add_run()
    r.text = text
    r.font.name, r.font.size, r.font.bold, r.font.italic = 'Calibri', Pt(size), bold, italic
    r.font.color.rgb = color


def block(slide, x, y, w, h, title, items, size=12.5):
    tf = box(slide, x, y, w, h)
    par = tf.paragraphs[0]
    run(par, title, 17, bold=True, color=HEAD)
    par.space_after = Pt(3)
    for label, text in items:
        par = tf.add_paragraph()
        pPr = par._p.get_or_add_pPr()
        pPr.set('marL', str(int(Inches(0.2))))
        pPr.set('indent', str(-int(Inches(0.16))))
        etree.SubElement(pPr, qn('a:buFont')).set('typeface', 'Arial')
        etree.SubElement(pPr, qn('a:buChar')).set('char', '•')
        par.space_after = Pt(2)
        run(par, label, size, bold=True)
        run(par, text, size)


s2, s6 = p.slides[1], p.slides[5]

# ------------------------------------------------------------------ Slide 2: searchable log caption
tf = box(s2, 9.40, 6.17, 9.85, 0.24)
run(tf.paragraphs[0], 'Test Log (right): search + filter by date, officer, kit and result; export as CSV, PDF + QR.',
    11.5, color=GREY, italic=True)

# ------------------------------------------------------------------ Slide 6: tighten table, add strip
gf = next(s for s in s6.shapes if s.has_table)
tbl = gf.table
ROW = 0.95
for r in list(tbl.rows)[1:]:
    r.height = Inches(ROW)
    for cell in r.cells:
        for par in cell.text_frame.paragraphs:
            for rn in par.runs:
                rn.font.size = Pt(13 if rn.font.bold else 12.5)
gf.height = Inches(0.85 + ROW * 5)
for i in range(5):                                   # invisible PDF link boxes follow their rows
    lb = next(s for s in s6.shapes if s.name == f'Research link {i + 1}')
    lb.top, lb.height = Inches(2.10 + 0.85 + ROW * i), Inches(ROW)

top, h, w = 8.30, 2.05, 6.05
block(s6, 0.75, top, w, h, 'Chain of Custody & Court', [
    ('Key', ' - Ed25519 key stays only on the server, never in the app; anyone checks with the public key. '
            'Next: key in a hardware box (HSM) + officer DSC.'),
    ('Check', ' - QR page re-computes the photo hash + record hash, verifies the signature and the chain link.'),
    ('Court', ' - gives the SHA-256 hash for the BSA 2023 s.63 certificate. Time, place, officer and photo hash '
              'can be attached to the e-Sakshya case / CCTNS FIR (planned).'),
])
block(s6, 0.75 + w + 0.18, top, w, h, 'Privacy & Retention (DPDP 2023)', [
    ('Data', ' - no biometrics, no suspect name (only a sample code). Photo shows card + kit; '
             'officer ID, GPS, time kept as evidence.'),
    ('Who sees', ' - officer: own tests; supervisor/admin: all; public QR: the check page '
                 '(hiding officer name there is planned).'),
    ('Law', ' - police work needs no consent (s.7(c), s.17(1)(c)) but data must be kept safe (s.8(5)). '
            'Kept till case + appeal end, then photo removed (planned).'),
])
block(s6, 0.75 + 2 * (w + 0.18), top, w, h, 'Cost & Offline (estimates / design)', [
    ('Per test', ' - ₹10 reusable card + officer\'s own phone + free app; kits are already bought by police.'),
    ('Pilot', ' - 20 officers, 3 months: about ₹10,000 (cards ₹200 + server ~₹3,000/month), estimate.'),
    ('Offline (design)', ' - test saved on phone with its hash, sent when network is back; same test sent '
                         'twice is saved once. Phone lost: admin blocks the login (planned).'),
])

p.save(OUT)
print('saved', OUT)
