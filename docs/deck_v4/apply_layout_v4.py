"""Layout-only fixes for the team's v4 deck (59/90 review). No wording is changed.

1. Canva's embedded "Calibri (MS)" is not used by PowerPoint (falls back to wider Arial),
   so headings break ("Proble / m") and bullets spill out of boxes -> use real Calibri.
2. Move / resize shapes so nothing overlaps; move the prototype-flow screenshots off the
   references slide; add the measured-results proof image.
"""
import copy
import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn

SRC = 'v4_original.pptx'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'K26231_PS_v4.pptx'
PROOF = '../ppt_content/evidence/proof_grid.png'
p = Presentation(SRC)
E = 914400

FONT_MAP = {  # Canva name -> (real font, bold, italic)
    'Calibri (MS)': ('Calibri', None, None),
    'Calibri (MS) Bold': ('Calibri', '1', None),
    'Calibri (MS) Italics': ('Calibri', None, '1'),
    'Canva Sans': ('Calibri', None, None),
}


def fix_fonts(slide):
    for tag in ('a:latin', 'a:ea', 'a:cs', 'a:sym'):
        for el in slide._element.iter(qn(tag)):
            face = el.get('typeface')
            if face in FONT_MAP:
                new, b, i = FONT_MAP[face]
                el.set('typeface', new)
                rpr = el.getparent()
                if b:
                    rpr.set('b', b)
                if i:
                    rpr.set('i', i)


def _walk(shapes):
    for s in shapes:
        yield s
        if s.shape_type == 6:
            yield from _walk(s.shapes)


def sid(slide, i):
    return next(s for s in _walk(slide.shapes) if s.shape_id == i)


def drop(slide, *ids):
    for i in ids:
        el = sid(slide, i)._element
        el.getparent().remove(el)


def place(shape, x=None, y=None, w=None, h=None):
    if x is not None: shape.left = Inches(x)
    if y is not None: shape.top = Inches(y)
    if w is not None: shape.width = Inches(w)
    if h is not None: shape.height = Inches(h)


def one_line(shape, align=None):
    """Heading that must never break into two lines."""
    tf = shape.text_frame
    tf.word_wrap = False
    tf.auto_size = MSO_AUTO_SIZE.NONE
    if align is not None:
        for par in tf.paragraphs:
            par.alignment = align


def next_id(slide):
    return max(int(e.get('id')) for e in slide._element.iter(qn('p:cNvPr'))) + 1


def copy_to(src, dst, el):
    """Copy one shape element to another slide, carrying its image / link relationships."""
    el = copy.deepcopy(el)
    for node in el.iter():
        for attr in (qn('r:embed'), qn('r:link'), qn('r:id')):
            rid = node.get(attr)
            if not rid:
                continue
            rel = src.part.rels[rid]
            new = (dst.part.relate_to(rel.target_ref, rel.reltype, is_external=True) if rel.is_external
                   else dst.part.relate_to(rel.target_part, rel.reltype))
            node.set(attr, new)
    el.find('.//' + qn('p:cNvPr')).set('id', str(next_id(dst)))
    dst.shapes._spTree.insert_element_before(el, 'p:extLst')
    return next(s for s in dst.shapes if s._element is el)


def link_box(slide, x, y, w, h, url, name):
    """Invisible click area - PowerPoint's PDF export drops some text links (table cells, this deck's video link)."""
    box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    box.name = name
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    sf = box.fill._xPr.find(qn('a:solidFill'))[0]
    sf.append(sf.makeelement(qn('a:alpha'), {'val': '0'}))
    box.line.fill.background()
    box.click_action.hyperlink.address = url
    return box


for s in p.slides:
    fix_fonts(s)
s2, s3, s4, s5, s6 = p.slides[1], p.slides[2], p.slides[3], p.slides[4], p.slides[5]

# ------------------------------------------------------------------ Slide 2
# Left: Problem, Solution, then the demo video row (moved here to free the right side).
place(sid(s2, 19), y=2.00)                       # Problem heading
place(sid(s2, 17), y=2.58)                       # Problem text
place(sid(s2, 14), y=5.24)                       # divider
place(sid(s2, 21), y=5.38)                       # Solution heading
place(sid(s2, 20), y=5.49)                       # Solution text
demo, link, qr = sid(s2, 26), sid(s2, 27), sid(s2, 25)
one_line(demo)
one_line(link)
place(demo, x=1.26, y=9.21, w=3.35)
place(link, x=4.70, y=9.23, w=2.30)
place(qr, x=7.35, y=8.74)
video = next(r.hyperlink.address for par in link.text_frame.paragraphs for r in par.runs if r.hyperlink.address)
link_box(s2, 4.70, 9.18, 2.30, 0.50, video, 'Video link click area')
link_box(s2, 7.35, 8.74, qr.width / E, qr.height / E, video, 'Video QR click area')

# Right: Our Approach -> Prototype Flow screenshots (moved from slide 6) -> Novelty.
place(sid(s2, 24), y=2.05)                       # Our Approach heading
place(sid(s2, 13), y=2.60)                       # 6-step approach boxes
head = copy_to(s6, s2, sid(s6, 23)._element)     # "Prototype Flow - real screenshots ..."
one_line(head)
place(head, x=9.40, y=3.70, w=9.85)
H, top, x0, x1 = 1.95, 4.22, 9.40, 19.25
imgs = [copy_to(s6, s2, sid(s6, i)._element) for i in (8, 10, 11, 9)]   # home, capture, result, dashboard
arrows = [copy_to(s6, s2, sid(s6, i)._element) for i in (12, 14, 12)]
widths = [H * im.width / im.height for im in imgs]
aw, ah = 0.35, 0.23
slot = (x1 - x0 - sum(widths)) / 3
x = x0
for k, (im, w) in enumerate(zip(imgs, widths)):
    place(im, x=x, y=top, w=w, h=H)
    x += w
    if k < 3:
        place(arrows[k], x=x + (slot - aw) / 2, y=top + H / 2 - ah / 2, w=aw, h=ah)
        x += slot
place(sid(s2, 10), x=9.40, y=6.42, w=9.85, h=3.80)   # Novelty border
place(sid(s2, 22), x=9.65, y=6.50)                   # Novelty heading
place(sid(s2, 23), x=9.75, y=7.00, w=9.30)           # Novelty text

# ------------------------------------------------------------------ Slide 6
# Screenshots moved to slide 2 -> the references table gets the full width and fits the slide.
drop(s6, 8, 9, 10, 11, 12, 13, 14, 23)
gf = sid(s6, 7)
tbl = gf.table
cols = [7.0, 4.5, 7.0]
for c, w in zip(tbl.columns, cols):
    c.width = Inches(w)
tbl.rows[0].height = Inches(0.85)
for r in list(tbl.rows)[1:]:
    r.height = Inches(1.45)
place(gf, x=0.75, y=2.10, w=sum(cols), h=0.85 + 1.45 * 5)
# Study names were loose text boxes floating over column 1 -> put each one inside its own row.
labels = {sid(s6, i).text_frame.text.strip(): i for i in (18, 19, 20, 21, 22)}
for r in list(tbl.rows)[1:]:
    c0, c1, c2 = r.cells
    txb = c2.text_frame._txBody
    first = txb.find(qn('a:p'))
    if not ''.join(first.itertext()).strip():     # empty first line pushed the link off-centre
        txb.remove(first)
    for cell in (c0, c1, c2):
        for par in cell.text_frame.paragraphs:
            for run in par.runs:
                run.font.size = Pt(14)
                run.font.name = 'Calibri'
    name = next(n for n in labels if c2.text_frame.text.strip().startswith(n))
    lab_p = copy.deepcopy(sid(s6, labels[name]).text_frame.paragraphs[0]._p)
    for rpr in lab_p.iter(qn('a:rPr')):
        rpr.set('b', '1')
    body_p = c0.text_frame.paragraphs[0]._p
    body_ppr = body_p.find(qn('a:pPr'))
    ppr = lab_p.find(qn('a:pPr'))
    if ppr is None:
        ppr = lab_p.makeelement(qn('a:pPr'), {})
        lab_p.insert(0, ppr)
    for child in list(ppr):
        ppr.remove(child)
    for k in list(ppr.attrib):
        del ppr.attrib[k]
    ppr.set('algn', body_ppr.get('algn', 'l') if body_ppr is not None else 'l')
    sa = ppr.makeelement(qn('a:spcAft'), {})
    sa.append(sa.makeelement(qn('a:spcPts'), {'val': '600'}))
    ppr.append(sa)
    body_p.addprevious(lab_p)
drop(s6, *labels.values())
# PowerPoint's PDF export drops links inside table cells -> invisible click box over each Research cell.
for i, r in enumerate(list(tbl.rows)[1:]):
    url = next(run.hyperlink.address for par in r.cells[2].text_frame.paragraphs
               for run in par.runs if run.hyperlink.address)
    link_box(s6, 0.75 + cols[0] + cols[1], 2.10 + 0.85 + 1.45 * i, cols[2], 1.45, url, f'Research link {i + 1}')

# ------------------------------------------------------------------ Slide 5
# Centre the map screenshot (and its heading) over the Future Scope box below it.
fut, mp = sid(s5, 11), sid(s5, 19)
dx = (fut.left + (fut.width - mp.width) // 2) - mp.left
for i in (19, 29, 31):
    sid(s5, i).left += dx

# ------------------------------------------------------------------ Slide 4
for gid, tid in ((25, 40), (28, 41), (31, 42), (34, 43), (37, 44)):   # COST ... SCALE box titles
    t, box = sid(s4, tid), sid(s4, gid)
    one_line(t, PP_ALIGN.CENTER)
    place(t, x=box.left / E, w=box.width / E)
ops = sid(s4, 21).text_frame.paragraphs[3].runs   # bold ended one letter early: "Operationa" + "l"
if ops[1].text == 'erationa' and ops[2].text.startswith('l'):
    ops[1].text, ops[2].text = 'erational', ops[2].text[1:]
for row in sid(s4, 10).table.rows:                  # "n-app" lost its first letter in Canva
    for cell in row.cells:
        for par in cell.text_frame.paragraphs:
            if par.runs and par.runs[0].text.startswith('n-app'):
                par.runs[0].text = 'I' + par.runs[0].text

# ------------------------------------------------------------------ Slide 3
# Reference card (left) + proof photos from the test run (right), under Measured Results.
ref_head, card = sid(s3, 22), sid(s3, 13)
place(sid(s3, 23), y=6.80)                          # divider under the simulated-swatch note
one_line(ref_head, PP_ALIGN.CENTER)
cw, pw = 2.90, 3.30
place(ref_head, x=10.15, y=6.88, w=cw)
ch = cw * card.height / card.width
place(card, x=10.15, y=7.33 + (3.0 - ch) / 2, w=cw, h=ch)
proof_head = copy_to(s3, s3, ref_head._element)
runs = proof_head.text_frame.paragraphs[0].runs
runs[0].text = 'Proof of Results'
for r in runs[1:]:
    r.text = ''
place(proof_head, x=16.55 - pw, y=6.88, w=pw)
pic = s3.shapes.add_picture(PROOF, Inches(16.55 - pw), Inches(7.33), width=Inches(pw))
pic.name = 'Proof grid'

p.save(OUT)
print('saved', OUT)
