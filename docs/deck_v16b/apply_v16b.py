"""v16b: v16 (scored 60/90) + only one line on slide 5 with the sample report link. Nothing else changed."""
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

SRC = '../deck_v16/K26234_SIH26231_v16.pptx'
OUT = 'K26234_SIH26231_v16b.pptx'
REPORT = 'https://drive.google.com/file/d/1NIR2OyYZRdmEM1R3cz9ghb7rZqyY1D1Z/view?usp=sharing'
HEAD, INK, LINK = RGBColor(0x79, 0x2E, 0x00), RGBColor(0, 0, 0), RGBColor(0x05, 0x63, 0xC1)
E = 914400
p = Presentation(SRC)
s5 = p.slides[4]
fut = next(s for s in s5.shapes if s.shape_id == 11)
mp = next(s for s in s5.shapes if s.shape_id == 19)

# map: trim a little sky and road (same width) so the link line fits under it
L, T, R, B = 0.178, 0.14, 0.015, 0.43
src = mp._element.find('.//' + qn('a:blipFill')).find(qn('a:srcRect'))
for k, v in zip('ltrb', (L, T, R, B)):
    src.set(k, str(int(v * 100000)))
mp.height = int(mp.width * (530 * (1 - T - B)) / (960 * (1 - L - R)))

x, y, w, h = fut.left, mp.top + mp.height + Inches(0.05), fut.width, Inches(0.44)
tb = s5.shapes.add_textbox(x, y, w, h)
tf = tb.text_frame
tf.word_wrap, tf.auto_size = True, MSO_AUTO_SIZE.NONE
tf.margin_left = tf.margin_right = Inches(0.03)
tf.margin_top = tf.margin_bottom = Inches(0)
par = tf.paragraphs[0]
for text, kind in (('Court Certificate: ', 'head'),
                   ('every PDF report now has a filled BSA section 63 page (photo hash, phone, time, GPS) '
                    'for the officer and expert to sign. ', None),
                   ('Open a full sample report (PDF, 2 pages)', 'link')):
    r = par.add_run()
    r.text = text
    r.font.name, r.font.size, r.font.bold = 'Calibri', Pt(13), kind == 'head'
    r.font.color.rgb = HEAD if kind == 'head' else (LINK if kind == 'link' else INK)
    if kind == 'link':
        r.font.underline = True
        r.hyperlink.address = REPORT

box = s5.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)   # click area, so the link also works in the PDF
box.name = 'Sample report link area'
box.fill.solid()
box.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
sf = box.fill._xPr.find(qn('a:solidFill'))[0]
sf.append(sf.makeelement(qn('a:alpha'), {'val': '0'}))
box.line.fill.background()
box.click_action.hyperlink.address = REPORT

p.save(OUT)
print('saved', OUT, '| map bottom', round((mp.top + mp.height) / E, 2), 'line', round(y / E, 2), round((y + h) / E, 2))
