# FieldProof - Full Project Notes (Team HexTech, SIH 2026)

Everything we discussed and built, from the start of the SIH26231 work to 30 Sep 2026.
Written so a teammate (or NotebookLM) can understand the whole project without the chat.

---

## 1. Basic facts

| Item | Value |
|---|---|
| Team | HexTech |
| Team ID | **K26234** (the old file name "K26231" was just a mix-up) |
| Problem Statement | **SIH26231 - Digital Companion for Field Drug Testing** |
| Ministry | MHA / NCB (Narcotics Control Bureau) |
| Our solution name | **FieldProof** |
| Old PS (dropped) | SIH26034 - LabelGuard AI (packaged-label compliance, Legal Metrology) |
| Status | **Approved for the finals** with deck `K26234_SIH26231_v16b.pptx` (60/90) |
| Repo folder | `C:\Users\LOKESHRAJ M\SIH26231` (git, local only, not pushed) |

---

## 2. The problem (simple words)

- Police and NCB officers use small **chemical drug test kits** in the field. The liquid changes colour (for example purple, orange or no change).
- Today the officer **judges the colour by eye**. Lighting (street lamp, torch, sunlight) and personal judgement change what they see.
- There is **no standard colour value** to compare with.
- There is often **no clear digital record** of who did the test, where, when, and what the photo showed. So later, in court, it is hard to prove.
- India had **1,20,010 NDPS cases in 2023** (source: NCRB, Crime in India 2023). Each one needs a field test.

**Example scenario:** an officer at a highway checkpoint at night finds white powder. Under a yellow street lamp the kit colour looks brownish. Is it purple (opium type) or orange (amphetamine type)? With FieldProof he takes one photo of the kit next to a Rs 10 colour card. The app corrects the colour, says POSITIVE / NEGATIVE / NOT SURE, and saves a sealed record with time, GPS, officer ID and the photo's fingerprint (hash). Later anyone can scan the QR on the PDF to check the record was not changed.

---

## 3. The solution - what FieldProof does

1. Officer logs in on the Android app.
2. Picks the kit (for example Marquis).
3. Takes a photo with the **colour card and kit result in the yellow guide box**.
4. The phone checks for blur first (new). If blurry or dark, it asks to take it again.
5. Server finds the card, **fixes the colours using the card**, reads the kit colour and decides POSITIVE / NEGATIVE / NOT SURE.
6. Server saves a **sealed record**: photo SHA-256 hash, time from internet, GPS, officer ID, device ID, kit, result, signature and a link to the previous record (hash chain).
7. Supervisor/admin see all tests on a **web dashboard** (search, filter, map, review of NOT SURE tests, CSV export).
8. Each test has a **PDF report with QR**. Page 2 is a filled **BSA 2023 Section 63 certificate details page**.
9. Anyone can open the **check page (QR)**: it re-checks 5 things and says "Record is genuine" or "TAMPERED".

**Our Approach (6 steps on slide):** Test Kit -> Take Photo -> Check Colour -> Get Result -> Save Proof -> Admin Review.

---

## 4. How the colour card fixes the colours

- The card has **24 colour squares whose true colours we already know**, plus **4 black corner markers (ArUco, DICT_4X4_50, IDs 0-3)** and a window where the kit result goes.
- Card and kit are photographed **together, under the same light**.
- Steps:
  1. Find the 4 corner markers and straighten the card (homography), even if tilted.
  2. Measure what the camera saw for each of the 24 squares.
  3. Compare with their true colours. Example: under a yellow lamp the white square looks yellowish, so the app learns "this light adds yellow".
  4. Build a **3x4 colour correction matrix** (least squares) for this photo.
  5. Apply the same correction to the kit colour.
  6. Convert to CIELAB and compare with the kit's known result colours using **Delta E 2000**.
- Decision: result only if **Delta E <= 14 and a 4-point lead** over the next colour (demo Marquis kit; Iodine kit uses 18 / 5). Otherwise **NOT SURE**.
- Safety checks that give NOT SURE: card not found, blur score < 300, glare > 3%, card fit (colour correction error) > 9.
- Measured: after correction the right colour was **4.7 to 8.9** away, wrong colours **34 to 42**, trick cards **16 to 31**. Limit 14 sits in the gap (14 is our own limit, set from these gaps; Delta E 2000 itself is the CIE standard formula).
- Limit: card and kit must be in the same light. Very strong single-colour light can break the correction; then the card-fit check says NOT SURE.
- One line for judges: *"The card has 24 colours we already know. The app sees how the light changed those colours, removes that same change from the kit colour, and only then decides."*

---

## 5. Innovations / novelty points

- **Rs 10 reusable colour card** to handle lighting and phone differences.
- **NOT SURE (INCONCLUSIVE)** instead of guessing a result for blurry, shiny or in-between photos.
- **Verifiable evidence:** photo hash, GPS, trusted time, officer ID, Ed25519 signature, hash chain, QR check page.
- **Multiple kits:** new kit colour profiles added from the admin website without changing the app.
- **Local language support:** the app switches to Tamil with one tap.
- **Court help:** every PDF has a filled BSA Section 63 certificate details page.
- Comparison line: *Eye check is guesswork, lab is slow, FieldProof gives result on the spot for Rs 10 with proof.*
- Why no AI model: AI needs lots of real drug photos to learn. Our colour maths needs none, and every answer can be explained with numbers.

---

## 6. Tech stack

| Part | Tech |
|---|---|
| Mobile app | Flutter (Dart), app ID `gov.in.ncb.fieldproof` (Dart package still named `labelguard_mobile`) |
| Backend | FastAPI (Python), SQLAlchemy |
| Database | PostgreSQL 18, database `fieldproof_db`, port 5433 (SQLite fallback) |
| Image / colour | OpenCV + NumPy, CIELAB, Delta E 2000 |
| Dashboard | React + Vite, Leaflet + OpenStreetMap map |
| PDF | ReportLab + QR |
| Security | JWT + bcrypt login, roles (field_officer, supervisor, admin), SHA-256, Ed25519 |
| Time | NTP, then HTTPS Date header (Google/Cloudflare/Microsoft), then server clock |

---

## 7. Tamper-evident record (chain of custody)

- **Photo SHA-256** made on the phone (client hash) and again on the server; they must match.
- **22 fields** are sealed in canonical JSON: test ID, time, time source, device time, GPS, accuracy, mock-GPS flag, officer, device, kit, kit version, photo hash, result, label, confidence, reason, measured colour, lab sample ID, previous record hash.
- **Ed25519 signature** on the sealed JSON (key only on the server; public key at `/verify/pubkey`).
- **Hash chain:** each record stores the previous record's hash.
- **Check page** `/v/{id}` and JSON `/verify/{id}` run 5 checks: photo hash, record hash, signature, chain, fields match.
- **Tamper test (real run on saved records, on copies):** original = GENUINE; 1 byte of photo changed = TAMPERED (photo); result inside sealed copy changed = TAMPERED (hash, signature, fields); result in DB row changed = TAMPERED (fields); signature changed = TAMPERED.
- Honest gaps found in the code (to fix for finals):
  - check page compared only 6 fields, not all 22, and showed DB values;
  - public QR page shows officer name and exact GPS, with running-number links;
  - if the key file is lost, the server silently makes a new key (old records would show TAMPERED);
  - key is a server key, not the officer's own DSC; not in a hardware box (HSM).
- Legal hooks (checked): NDPS SSSD Rules 2022 Rule 3(1); BNSS 2023 s.105 (search and seizure video, e-Sakshya); BSA 2023 s.63 (certificate for electronic records, needs hash value, signed by person in charge + expert); IT Act s.3; DPDP Act 2023.
- Say "supports BSA s.63", never "court-admissible" or "court approved".

---

## 8. Privacy and data

- No face data, no fingerprint, no suspect name (only a sample code). Officer ID, GPS and time are kept as proof.
- Officer sees only own tests; supervisor and admin see all.
- DPDP Act: police work does not need consent (s.7(c), s.17(1)(c)), but data must be kept safe (s.8(5)).
- Planned: data on government cloud (NIC) in India; photos deleted after the case and appeal end; hide officer name on public QR page; encrypt photos (AES-GCM); access log.
- CERT-In 2022: logs kept 180 days in India.

---

## 9. Offline mode (planned, NOT built)

- Right now, with no network the test is not saved.
- Plan: save the test on the phone with its photo hash in a queue, send when the network is back, server checks the hash and seals it; same test sent twice is saved once; phone lost = admin blocks the login.
- Tools if asked: local SQLite queue, Connectivity Plus (only tells if Wi-Fi/data is on, so the app must still retry), Android WorkManager for background sending. Simpler demo: a "Send now" button.
- Wrong to say today: "SQLite saves the test securely" as if built.
- Effort to build: about 1.5 to 2 days.

---

## 10. What was built (prototype)

- Full working chain: phone app -> FastAPI -> PostgreSQL -> dashboard.
- Phone connects over USB: `adb reverse tcp:8000 tcp:8000` (`usb_connect.bat`). College Wi-Fi blocks port 22 and NTP.
- `start_fieldproof.bat` starts backend (8000) + dashboard (5173) + USB link.
- Demo logins: officer1 to officer6, supervisor1, admin1; password in `DEMO_LOGINS.txt` (gitignored, never share in chat).
- Public verify-only link: `backend/scripts/public_link.py` (gateway on 8001 + Pinggy tunnel over port 443; link changes each run, free links end after 60 min).
- Printable card: `demo/PRINT_THIS/` (reference card PDF + simulated swatch cards: purple, orange, plain, ambiguous, green no-match).
- **Added on 29 Sep 2026:**
  - **Tamil language** switch in the app (all officer screens, NOT SURE reasons, kit colour names). File `mobile/lib/l10n/lang.dart`.
  - **Section 63 certificate page** as page 2 of every PDF (hashes, phone model from photo EXIF, time, GPS, key, blank Part A and Part B for officer and expert).
  - **Phone blur check** right after the photo with "Take again / Send anyway" (`mobile/lib/services/photo_check.dart`, limit 230, card area only). Built, **not yet installed** on the phone.
  - **"Take photo again"** button on a NOT SURE result.
  - Dashboard favicon (old LabelGuard icon was showing from browser cache).
- Backend tests: 34 passed.

---

## 11. Testing and results

- **Computer-made photos:** 37 (25 good in 5 lights, 12 bad). All 25 good matched; all 12 bad said NOT SURE. These are easy for the colour fix, so they overstate real accuracy.
- **Real phone scans:** 25 total (6 earlier + 19 on 29 Sep). One phone (Nothing A015), card shown on a laptop screen, one room with window light, cards checked by eye.
  - 14 matched the card, 11 said NOT SURE (7 were trick cards made to test this). No wrong result seen in this small test.
  - About 16 seconds per full test (1 team member).
- **Stress test:** 19 real photos x 9 conditions (as taken, darker, brighter, yellow bulb, cool tube light, tilted, shaky, cheap camera, grainy) = 171 checks. 70 matched, 101 NOT SURE (63 were trick cards). Every NOT SURE on a clear card came from blur (26 from 3 photos already blurry, rest from copies blurred on purpose). Sharp photos matched 69 of 72.
- **Phone blur check** (replayed on the 171 photos): caught 36 of 38 blurry ones, stopped 3 of 70 good ones.
- Confusion matrix (171 checks): Positive card 40 POS / 0 NEG / 32 NOT SURE; Plain card 0 / 30 / 6; Trick card 0 / 0 / 63.
- **Speed:** server result about 2.5 s typical, 5 s max. Colour check 0.12 s per photo. Photo about 0.85 MB.
- Honest caveats (always say): simulated swatches, 1 phone, small test; real kits can still give wrong results; FSL trial not done yet.
- Important lesson: do not write "0 errors / perfect". Say "no wrong result seen in this small test".

---

## 12. Legal, safety and demo notes

- We cannot use real drugs (NDPS s.8). Demo uses printed/screen **simulated swatches**, or safe real chemistry like **Betadine + starch** (iodine kit).
- Possible real-reaction trials: college lab with faculty (Marquis on aspirin/sugar - dangerous acid, only with supervision), or **FSL** (Regional FSL Coimbatore exists; TN Forensic Sciences Department, forensic@tn.nic.in). Letter must go through HOD. Never claim FSL contact or results that did not happen.
- e-Sakshya / CCTNS: NIC police-only systems, no public API found. Plan: match our fields, get NIC/MHA approval, send each sealed record with its hash. Our CSV export has time, GPS, officer, result, photo hash and verify link.

---

## 13. Pilot, cost, scale, sustainability

- **Pilot (proposed):** 1 district in Tamil Nadu with local police and nearest FSL, 20 officers, 3 months, every field result checked again in the FSL lab. Success = 95% or more same as lab, NOT SURE below 10%, every record passes the check.
- **Cost:** 20 cards x Rs 10 = Rs 200; server Rs 3,000 a month x 3 = Rs 9,000; total about Rs 9,200 (estimate). Per test: Rs 10 reusable card + officer's own phone + free app.
- **After pilot:** police or NCB IT budget, server about Rs 36,000 a year (estimate). Owner: state police IT cell; FSL keeps kit colours correct. Upkeep: security update every 3 months; MoU with police and FSL planned (not signed).
- **Scale (estimate):** about 330 NDPS cases a day in India; one small server can check thousands of photos an hour; about 100 GB of photos a year for all of India.
- Phases: prototype -> department pilot -> district -> state -> national.

---

## 14. Future scope (our plan after SIH)

- Month 1: offline mode.
- Month 2: phone security chip signing (Android Keystore, ECDSA P-256, since Ed25519 in Keystore needs Android 13+ and StrongBox has no Ed25519).
- Month 3: Hindi and voice help (Tamil done).
- During pilot: compare field results with FSL lab results.
- After pilot: e-Sakshya / CCTNS link with NIC/MHA approval.
- Also: outside time-stamp (RFC 3161), hardware key box (HSM), officer DSC, supervisor counter-seal, encrypt photos, access log, fix public QR page.

---

## 15. Research references (IEEE format, used on slide 6)

1. H. Karisen and T. Dong, "Illumination and device independence for colorimetric detection of urinary biomarkers with smartphone," in Proc. 38th Annu. Int. Conf. IEEE EMBC, Orlando, FL, USA, 2016, pp. 5184-5187, doi: 10.1109/EMBC.2016.7591895.
2. S. Nath, K. Summers, J. Baek, and G.-J. Ahn, "Digital evidence chain of custody: Navigating new realities of digital forensics," in Proc. IEEE 6th Int. Conf. TPS-ISA, Washington, DC, USA, 2024, pp. 11-20, doi: 10.1109/TPS-ISA62245.2024.00012.
3. A. Choodum, K. Parabun, N. Klawach, N. Nic Daeid, P. Kanatharana, and W. Wongniramaikul, "Real time quantitative colourimetric test for methamphetamine detection using digital and mobile phone technology," Forensic Sci. Int., vol. 235, pp. 8-13, Feb. 2014, doi: 10.1016/j.forsciint.2013.11.018.
4. S. T. Krauss et al., "Objective method for presumptive field-testing of illicit drug possession using centrifugal microdevices and smartphone analysis," Anal. Chem., vol. 88, no. 17, pp. 8689-8697, Sep. 2016, doi: 10.1021/acs.analchem.6b01982.
5. N. Bugeja et al., "Teaching old presumptive tests new digital tricks with computer vision for forensic applications," Digital Discovery, vol. 2, no. 4, pp. 1143-1151, 2023, doi: 10.1039/D3DD00066D.

---

## 16. PPT history (what changed and why)

| Version | Main change | Score |
|---|---|---|
| v3 | 61/90 review fixes | - |
| v4 | Team's deck: alignment, font fix (Canva "Calibri (MS)" -> Calibri), screenshots moved to slide 2, proof photos | 59 |
| v5 | UX block, pilot plan, tamper image | 60 |
| v6/v7 | Privacy, chain of custody, cost; declutter (text moved to speaker notes) | 60 |
| v9 | NCRB number, comparison line, TRL 4, funding | - |
| v10/v11 | Real phone scans + confusion matrix; plain-English rewrite | 60 |
| v12 | Even font sizes, funding line | - |
| v13 | IEEE references with DOI links (removed a `utm_source=chatgpt.com` link) | - |
| v14/v15 | NCRB citation, dated future scope, Tamil screenshot | 60 |
| v16 | Delta E numbers, cost breakdown, legal/privacy note | **60** |
| v17-v19 | Offline design box, scale, 171-check stress test, Section 63 page, Drive link to sample report | - |
| v20 | Removed "0 wrong" claims, showed NOT SURE 38/108 without cause | 59 |
| v21 | Explained NOT SURE (all blur), phone blur check, privacy block | 59 |
| **v16b** | v16 + only the sample report link | **60 - approved** |

Sample report link (anyone with the link): https://drive.google.com/file/d/1NIR2OyYZRdmEM1R3cz9ghb7rZqyY1D1Z/view?usp=sharing

Lessons about the AI checker:
- Score moves about 1 point per upload; the latest upload decides approval.
- It seems to read slide text, not text inside images.
- A weakness shown without its cause or fix lowers the score.
- Too much text lowers "Clarity".
- Uploads are now closed; do not risk new uploads.

A screenshot showing "approval withdrawn" (about XGBoost, PCAP, MCP/LLM) was **another team's result shared as a prank** - our approval is fine.

---

## 17. Rules we followed

- Never make up numbers; label estimates; never claim unbuilt features as done.
- Simple casual Indian English; the mentor spots AI-looking text, so no arrows, tildes, semicolons or dot separators in slide text.
- Old project folders and Downloads are read-only; copy only.
- Never print secrets (.env, demo password).
- Git pushes only with approval (nothing pushed).

---

## 18. Finals to-do list

1. Install the new app (blur check + retake) on the phone.
2. Real-kit trial with an FSL, or at least safe real chemistry (Betadine + starch).
3. Scan on 2-3 phones with the card printed on paper.
4. Build offline mode (1.5-2 days).
5. Phone security-chip signing (1-2 days).
6. Fix the 3 code gaps (22-field check, public QR page privacy, key handling).
7. Get a short written view from law faculty or a public prosecutor on the Section 63 record.
8. Explain the NOT SURE path in the demo: NOT SURE tests go to the supervisor's Review page.
9. Demo script (2 min): login -> pick kit -> photo -> result -> PDF with QR -> scan QR -> "Record is genuine" -> change 1 byte -> "TAMPERED".

## 19. Q&A quick answers

- **No colour card?** App cannot read the card, says NOT SURE, no result. Card is Rs 10 and stays in the kit box.
- **Two drugs with similar colours?** It is a first check; FSL confirms. If colours are close, the app needs a clear lead, otherwise NOT SURE.
- **Cost per test?** Rs 10 reusable card, existing phone, free app; kit cost same as today.
- **Why Delta E 14?** Right colours were within 9, wrong ones above 34 in our tests, so 14 sits in the gap.
- **Is it court-proof?** It supports the BSA s.63 certificate (hash, device, time); officer and expert must sign; FSL report confirms.
- **Real kits tested?** Not yet; small test on 1 phone with swatches; FSL trial is next.
- **Offline?** Designed, not built yet; plan is save on phone with hash, send later, server checks and seals.
