# Team_189360 deck: what changed from v16b and why

Base: `docs/deck_v16b/K26234_SIH26231_v16b.pptx` (approved, 60/90). Built by `build_team_189360.py`.
Same SIH template, same 6 main slides in the same order, plus 2 backup slides for judges' questions.
`Team_189360_preview.pdf` is a LibreOffice render. Fonts can look slightly different in PowerPoint.

## Review point and what we did

| Review point | Change | Slide |
|---|---|---|
| Numbers don't reconcile (25 vs 19 vs "14 correct") | One ledger: 6 scans on 28 Sep + 19 on 29 Sep = 25. Right answers 5 + 9 = 14, NOT SURE 1 + 10 = 11, wrong 0 | 3, 7 |
| Are the 3 NOT SURE positives the 3 blurry photos? | Yes. Records 13, 14 and 20, reason "Photo is blurry" (`stress_test.json`, as-taken rows) | 7 |
| "76% sure" is undefined | Called a match score (closeness and lead), not a probability. Formula in the speaker notes | 3 |
| No residual error after correction | Card fit = average ΔE of the 24 known colours after correction: 5.9 to 8.7 on real photos, limit 9 | 3, 7 |
| ΔE 14 margin is thin | Colour gap chart (right 4.7 to 8.9, trick 16 to 31, wrong 34 to 48). States each real kit gets its own limit from FSL data | 7, 8 |
| "0 wrong" oversold, small n | Rule of three stated: 0 wrong in 14 answers means error could still be up to about 21%. Pilot asks for 60+ tests per kit | 4, 7 |
| Pilot metric mixes app error and kit error | Measured apart: app vs expert on the same kit, and kit vs FSL lab | 4 |
| ₹9,200 is hardware-only | Says "cards and server only (estimate)" and lists what is not included | 4 |
| NOT SURE goes to a senior officer who eyeballs it | Supervisor can only order a retest or confirm NOT SURE (matches `routers/reviews.py`). Sample goes to FSL | 2, 4 |
| No threat model | Status column (Built, Flag only, Planned) on the challenges table. Full threat table on the backup slide, open items marked Open | 4, 8 |
| Offline arrives before phone signing | Offline mode and phone chip signing built together in month 1-2 | 5, 8 |
| Reaction timing not mentioned | Per-kit read time and app timer (already built, `read_time_s`, `capture_screen.dart`) | 2, 3, 4 |
| QR shows 127.0.0.1 | Old local address removed from the screenshot. Slide says the demo QR opens a public HTTPS check page (`backend/scripts/public_link.py`) | 5 |
| Architecture typos ("Managemenet", "Ruels") | Diagram rebuilt as editable shapes. Only built parts are shown, so "Gallery Upload", "Secure Synchronization" and "Audit Logs" were dropped | 3 |
| "Is this AI?" | "No AI model, on purpose", with the reason | 3 |
| Novelty is just colour reading | Comparison table vs eye check and FSL lab, plus "What we add" line under the research table | 2, 6 |
| "Eye check is guesswork, lab is slow" | Removed. The comparison table says the same thing with plain facts | 2 |
| Kit lot and expiry not captured | Listed as planned | 8 |
| Reference [1] author "Karisen" | Checked. IEEE Xplore and PubMed index it as "Karisen", so the citation matches the DOI record | 6 |
| NCRB 1,20,010 | Checked. Matches NCRB Crime in India 2023 (also in a PIB reply on NDPS cases) | 2 |
| Semicolons in slide text (team style rule) | Removed | 6 |
| Tagline | "Corrected colour. Honest NOT SURE. A record anyone can check." | 6 |

Every slide now has speaker notes: what to say, plus short answers to the likely judge questions.

## Still open (not fixed by the deck)

- No real-reagent data yet. The FSL trial plan is on backup slide 8.
- Before the demo, run `backend/scripts/public_link.py` and download the PDF again so the QR works on judges' phones. The free link lasts about 60 minutes.
- Check that the Google Drive sample report does not show the 127.0.0.1 address.
- Whether the 3 blurry photos were retaken and then read correctly was not logged.
- The app still shows "% sure". Renaming it to "match score" is a small app change.
