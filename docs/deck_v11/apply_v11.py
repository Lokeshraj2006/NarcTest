"""v11: same as v10, but every line we added since 28 Sep is reworded in plain, simple Indian English
(no arrows, dots, tildes or semicolons). The team's own text is not touched. Images are re-made with the
same plain wording.
"""
from pptx import Presentation
from pptx.util import Inches

SRC = '../deck_v10/K26234_SIH26231_v10.pptx'
OUT = 'K26234_SIH26231_v11.pptx'
EV = '../ppt_content/evidence/'
p = Presentation(SRC)


def sid(slide, i):
    return next(s for s in slide.shapes if s.shape_id == i)


def put(slide, shape_id, para, *texts):
    """Set the runs of one paragraph: texts go into runs in order, extra runs are emptied."""
    runs = sid(slide, shape_id).text_frame.paragraphs[para].runs
    for r, t in zip(runs, texts):
        r.text = t
    for r in runs[len(texts):]:
        r.text = ''


def swap_picture(slide, name, path):
    old = next(s for s in slide.shapes if s.name == name)
    x, y, w = old.left, old.top, old.width
    old._element.getparent().remove(old._element)
    pic = slide.shapes.add_picture(path, x, y, width=w)
    pic.name = name


s2, s3, s4, s5 = p.slides[1], p.slides[2], p.slides[3], p.slides[4]

# Slide 2
put(s2, 39, 0, '4 steps', ' - choose kit, take photo inside the box, see result, it gets saved. '
                          'One test takes around 16 seconds (we checked in 19 scans).')
put(s2, 39, 1, 'Bad photo?', ' - app says NOT SURE, tells the reason (blurry, shiny or card not seen) '
                             'and asks to take the photo again.')
put(s2, 39, 2, 'Easy to read', ' - result comes in big letters with colour, in simple English. '
                               'Next we will try it with 10 officers.')
put(s2, 40, 0, 'Test Log (right side) can search and filter by date, officer, kit and result, '
               'and download as CSV or PDF with QR.')
put(s2, 41, 0, 'India had 1,20,010 NDPS cases in 2023 (NCRB). Each needs a field test.')
put(s2, 42, 0, 'Eye check is guesswork, lab is slow, ', 'FieldProof gives result on the spot for ₹10 with proof')

# Slide 3
put(s3, 19, 0, 'Testing: 37 computer made photos and 25 real phone scans.')
put(s3, 19, 1, 'Accuracy: all 25 computer made photos correct. Real scans had 0 wrong answers '
               '(14 correct, others said NOT SURE).')
put(s3, 20, 1, 'Right now it is a lab prototype (TRL 4) tested on 1 phone. Next we test real kits with FSL on more phones.')
put(s3, 22, 0, 'Proof from Real Phone Scans (29 Sep 2026)')
swap_picture(s3, 'Real scans', EV + 'real_scans.png')

# Slide 4
put(s4, 55, 0, 'Where', ' - 1 district in Tamil Nadu, with local police and the nearest FSL')
put(s4, 55, 1, 'Who', ' - 20 officers, for 3 months')
put(s4, 55, 2, 'Check', ' - every field result is checked again in the FSL lab')
put(s4, 55, 3, 'Success', ' - 95% or more same as lab, NOT SURE below 10%, every record passes the check')
put(s4, 55, 4, 'Then', ' - first district, then state, then whole country (phases on the left)')
put(s4, 55, 5, 'Cost', ' - around ₹10,000 for 3 months, for cards and server (rough estimate)')
put(s4, 56, 0, 'After pilot, ', 'the state police or NCB IT budget can pay for it.')
put(s4, 56, 1, 'It is open source with no licence fee, so running cost is low.')

# Slide 5
put(s5, 33, 0, 'we tried it on our saved records')
put(s5, 22, 2, 'Police System Integration - our CSV export already has time, GPS, officer, result, photo hash '
               'and verify link. Linking with e-Sakshya and CCTNS needs NIC or MHA approval.')
swap_picture(s5, 'Tamper proof', EV + 'tamper_proof_tall.png')
s5.notes_slide.notes_text_frame.text = '\n'.join([
    'Q&A NOTES (only for us, not shown on the slide)',
    '',
    'Privacy and how long we keep data',
    'Data - we do not store fingerprint or face data, or the suspect name. Only a sample code. '
    'Officer ID, GPS and time are kept as proof.',
    'Who can see - officer sees only own tests, supervisor and admin see all tests, public QR shows only '
    'the check page. Hiding the officer name there is planned.',
    'Law - police work does not need consent under the DPDP Act (section 7(c) and 17(1)(c)), '
    'but data must be kept safe (section 8(5)).',
    'How long - till the case and appeal are over, then the photo is deleted. This is planned.',
    '',
    'Chain of custody (for court)',
    'Key - secret key is only on our server, not in the app. Anyone can check using the public key. '
    "Next step is a hardware key box (HSM) and the officer's own DSC.",
    'Check - QR page checks the photo and record again, and also the signature and chain link (see Tamper Test).',
    'Court - it gives the SHA-256 hash needed for the court certificate under BSA 2023 section 63. '
    'e-Sakshya and CCTNS link is planned.',
    'Offline (only design now) - if there is no network, the test is saved on the phone with its hash and sent later. '
    'Same test sent twice is saved only once. If the phone is lost, admin blocks the login (planned).',
])

p.save(OUT)
print('saved', OUT)
