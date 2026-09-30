# Team_189360 deck: what changed and why

**Sources**
- **Layout and style:** the team's `189360_Team_PPT.pdf`. It has the same 6 slides, the same sections in the same places, and similar font sizes. The phased-implementation picture with icons (`assets/phased_189360.png`) was taken from that PDF.
- **Content from v16b:** the NCRB figure, the real-scan results, the pilot plan, the legal and privacy line, and the BSA s.63 sample report link.
- **Fixes:** from the two judge-panel reviews.

**How it was built**
- `build_team_189360.py` builds the deck from `docs/deck_v16b/K26234_SIH26231_v16b.pptx`, because that file has the same SIH template (logo, oval, footer, fonts).
- Slides 7 and 8 are backup slides for judges' questions. Delete them if extra slides are not allowed.
- `Team_189360_preview.pdf` is a LibreOffice render. Fonts can look slightly different in PowerPoint.

## Review point and what we did

| Review point | Change | Slide |
|---|---|---|
| Numbers don't reconcile (25 vs 19 vs "14 correct") | "37 computer-made photos in 5 lights and 25 real phone scans. Real scans: 14 right, 11 NOT SURE, 0 wrong." The 29 Sep panel is labelled as 19 of the 25. The full ledger is on slide 7 | 3, 7 |
| "Our Goals - Measured Results" mixes goals and results | Renamed "Measured Results" | 3 |
| Are the 3 NOT SURE positives the 3 blurry photos? | Yes. Records 13, 14 and 20, reason "Photo is blurry" (`stress_test.json`) | 7 |
| "76% sure" is undefined | "The % shown is a match score, not a probability." Formula in the speaker notes | 3 |
| Residual error after correction | Card fit (average ΔE of the 24 known colours after correction) was 5.9 to 8.7 on real photos, limit 9 | 7 |
| ΔE 14 margin is thin | Colour gap chart. Each real kit gets its own limit from FSL data. Trial plan on slide 8 | 7, 8 |
| "0 wrong" oversold, small n | "Small test, not proof." Rule of three (up to about 21%). Pilot asks for 60+ tests per kit | 3, 4, 7 |
| Pilot metric mixes app error and kit error | "Check 2 things apart: app vs an expert reading the same kit, and kit vs FSL lab" | 4 |
| ₹9,200 is hardware-only | "about ₹9,200, cards and server only (estimate)". Exclusions listed in the notes | 4 |
| NOT SURE goes to a senior officer who eyeballs it | "Supervisor can only order a retest, sample goes to FSL" (matches `routers/reviews.py`) | 4 |
| No threat model | Status column (Built or Planned) on the challenges table. Full threat table on slide 8 | 4, 8 |
| Reaction timing not mentioned | Row added: each kit has a read time and the app timer takes the photo on time (already built) | 4 |
| Offline arrives before phone signing | Offline box says month 1-2, signed on the phone | 5 |
| QR shows 127.0.0.1 | Local address removed from the screenshot. Slide says the demo QR opens a public HTTPS check page (`backend/scripts/public_link.py`) | 5 |
| Architecture typos ("Managemenet", "Ruels") | Rebuilt as editable shapes with only built parts, so "Gallery Upload" and "Secure Synchronization" were dropped | 3 |
| "Is this AI?" | "No AI model, on purpose" under the architecture | 3 |
| Unverifiable benefit claims ("secure", "reduces paperwork") | Replaced with things we can show: "Any change to a record is caught", "PDF with QR and BSA s.63 page" | 5 |
| Government cloud with no provider | "NIC or state data centre in India (to confirm)" | 4 |
| Novelty is just colour reading | "Not just a colour reader. A field result anyone can check later." "What we add" line under the references | 2, 6 |
| "Operationa l" typo, semicolons in slide text | Fixed | 4, 6 |
| Reference [1] author "Karisen" | Checked. IEEE Xplore and PubMed index it as "Karisen", so the citation matches the DOI record | 6 |
| NCRB 1,20,010 | Checked. Matches NCRB Crime in India 2023 (also in a PIB reply on NDPS cases) | 2 |

Every slide has speaker notes: what to say, plus short answers to the likely judge questions.

## Still open (not fixed by the deck)

- No real-reagent data yet. The FSL trial plan is on slide 8.
- Before the demo, run `backend/scripts/public_link.py` and download the PDF again so the QR works on judges' phones. The free link lasts about 60 minutes.
- Check that the Google Drive sample report does not show the 127.0.0.1 address.
- The app still shows "% sure". Renaming it to "match score" is a small app change.
