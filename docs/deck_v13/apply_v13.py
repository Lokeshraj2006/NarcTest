"""v13: slide 6 references in IEEE format (details checked on Crossref / PubMed, 29 Sep 2026). Built on v12.
Links go to the DOI (no tracking parts). Plain hyphens and straight quotes are used.
"""
from pptx import Presentation
from pptx.util import Pt

SRC = '../deck_v12/K26234_SIH26231_v12.pptx'
OUT = 'K26234_SIH26231_v13.pptx'

REFS = [
    ('[1] H. Karisen and T. Dong, "Illumination and device independence for colorimetric detection of urinary '
     'biomarkers with smartphone," in Proc. 38th Annu. Int. Conf. IEEE Eng. Med. Biol. Soc. (EMBC), Orlando, FL, '
     'USA, 2016, pp. 5184-5187, doi: 10.1109/EMBC.2016.7591895.', '10.1109/EMBC.2016.7591895'),
    ('[2] S. Nath, K. Summers, J. Baek, and G.-J. Ahn, "Digital evidence chain of custody: Navigating new realities '
     'of digital forensics," in Proc. IEEE 6th Int. Conf. Trust, Privacy Secur. Intell. Syst. Appl. (TPS-ISA), '
     'Washington, DC, USA, 2024, pp. 11-20, doi: 10.1109/TPS-ISA62245.2024.00012.', '10.1109/TPS-ISA62245.2024.00012'),
    ('[3] A. Choodum, K. Parabun, N. Klawach, N. Nic Daeid, P. Kanatharana, and W. Wongniramaikul, "Real time '
     'quantitative colourimetric test for methamphetamine detection using digital and mobile phone technology," '
     'Forensic Sci. Int., vol. 235, pp. 8-13, Feb. 2014, doi: 10.1016/j.forsciint.2013.11.018.',
     '10.1016/j.forsciint.2013.11.018'),
    ('[4] S. T. Krauss et al., "Objective method for presumptive field-testing of illicit drug possession using '
     'centrifugal microdevices and smartphone analysis," Anal. Chem., vol. 88, no. 17, pp. 8689-8697, Sep. 2016, '
     'doi: 10.1021/acs.analchem.6b01982.', '10.1021/acs.analchem.6b01982'),
    ('[5] N. Bugeja et al., "Teaching old presumptive tests new digital tricks with computer vision for forensic '
     'applications," Digital Discovery, vol. 2, no. 4, pp. 1143-1151, 2023, doi: 10.1039/D3DD00066D.',
     '10.1039/D3DD00066D'),
]

p = Presentation(SRC)
s6 = p.slides[5]
tbl = next(s for s in s6.shapes if s.has_table).table
for i, (text, doi) in enumerate(REFS):
    cell = tbl.rows[i + 1].cells[2]
    pars = cell.text_frame.paragraphs
    link_run = next(r for pa in pars for r in pa.runs if r.hyperlink.address)
    keep_p = link_run._r.getparent()
    for pa in pars:                                   # keep only the paragraph holding the link run
        if pa._p is not keep_p:
            pa._p.getparent().remove(pa._p)
    for r in list(keep_p.findall('{http://schemas.openxmlformats.org/drawingml/2006/main}r')):
        if r is not link_run._r:
            keep_p.remove(r)
    link_run.text = text
    link_run.hyperlink.address = 'https://doi.org/' + doi
    link_run.font.size = Pt(13)
    box = next(s for s in s6.shapes if s.name == f'Research link {i + 1}')
    box.click_action.hyperlink.address = 'https://doi.org/' + doi

p.save(OUT)
print('saved', OUT)
