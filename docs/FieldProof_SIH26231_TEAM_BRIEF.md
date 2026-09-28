# FieldProof — SIH 2026 · PS SIH26231 · Team HexTech
## Team brief (read this first, then give it to your AI)

> **Deadline: 28 Sep 2026, 3:00 PM IST** — PPT + working prototype.
> **PPT status:** DONE (6 slides, simple English, old SIH template). Files: `SIH26231_FieldProof_HexTech.pptx` + `.pdf` (Lokesh has them).
> **Prototype status:** NOT STARTED yet. We are reusing our old SIH26034 project (LabelGuard / LMCS) as the base.
> **Language rule for anything user-facing (UI text, PPT, README):** simple, casual Indian English — a school student should understand it in the first read.

---

## 0. How to use this file with your AI

Paste this whole file into your AI, then add your task, for example:

```
You are helping Team HexTech build "FieldProof" for Smart India Hackathon 2026 (PS SIH26231).
Read the brief below fully. My task is: <PASTE ONE TASK FROM SECTION 10>.
Stack: Flutter app, FastAPI + PostgreSQL (SQLAlchemy + Alembic), OpenCV, React + Leaflet dashboard.
Follow the specs in the brief exactly (field names, endpoints, decision rules), so my part plugs into
my teammates' parts. Keep it simple and demo-ready by 3 PM. Ask me before inventing new APIs.
```

---

## 1. The problem statement (official text)

**SIH26231 — "Digital Companion for Field Drug Testing"** · Ministry of Home Affairs / Narcotics Control Bureau (NCB) · Category: Software · Theme we used: MedTech / BioTech / HealthTech

**Background:** Field drug-testing kits currently in use rely on visual interpretation of a colour-change reaction. This makes results subjective, difficult to standardise across officers, and leaves no verifiable record that a test was actually conducted at a given place and time. As a result, field test outcomes cannot presently be relied upon as documentary evidence.

**Build a mobile app** that works alongside existing colorimetric field-test kits (**no new hardware**) and:
1. Captures an image of the test result using the phone camera, **with a reference colour card in the frame** for lighting calibration.
2. **Automatically classifies** the result into outcome categories (e.g. positive, negative, inconclusive).
3. Generates a **tamper-evident digital record**: timestamp, GPS location, operator ID, and a **cryptographic hash of the image**.
4. Keeps a **simple, searchable log** of tests.

**Deliverable:** working mobile/web prototype showing image capture, automated classification, and generation of a **signed digital record**.
**Note:** output is a *presumptive* field result + supporting record. It does **not** replace lab confirmatory testing.

---

## 2. The problem in simple words

- Police/NCB officers find a suspicious powder. They drop a pinch into a small chemical kit. The chemical **changes colour** (e.g. purple can hint at heroin-type drugs).
- Today the officer **looks at the colour with his own eyes** and writes "positive" on paper.
- Problems:
  1. **Subjective** — street lamp / torch light, colour blindness, "purple or brown?" → different officers give different answers.
  2. **Not standard** — no number, no reference, no threshold.
  3. **No proof** — nobody can prove the test was done at that place, time, by that officer, on that sample. So it can't be used as evidence.
- **Our app:** officer takes one photo of the kit next to a **₹10 printed colour card** → app fixes the lighting using the card → gives **POSITIVE / NEGATIVE / INCONCLUSIVE (not sure)** → saves a **sealed, signed record** (photo fingerprint + GPS + internet time + officer ID) that anyone can check by scanning a QR code.
- The app **never replaces the lab**. It gives a first-level (presumptive) result + proof.

### Key terms (simple meaning)
| Term | Simple meaning |
|---|---|
| Colorimetric / colour test | Chemical + sample → colour changes → hints which drug type |
| Presumptive vs confirmatory | Presumptive = quick first-level field check (can be wrong). Confirmatory = lab machine test (final answer) |
| Reference colour card | Printed card with boxes of *known* colours — like a "colour ruler" |
| ArUco markers | 4 QR-like black-white squares at card corners so OpenCV can find and straighten the card |
| Colour-correction matrix (CCM) | Small maths formula (fitted by least squares) that converts "camera colours" into "true colours" using the card boxes |
| CIELAB (Lab) | Colour system that matches human vision; distances in it are meaningful |
| ΔE2000 (Delta E) | Standard number for "how different are two colours". Small = very similar (~1 = just noticeable) |
| SHA-256 hash | Digital fingerprint of the photo. Change even 1 pixel → fingerprint changes completely |
| Ed25519 signature | Server's digital stamp on the record. Anyone with the public key can check it was not changed |
| NTP time | Time from an internet time server, not the phone clock (phone clock can be changed) |
| Tamper-evident | We may not stop someone from changing data, but if they do, we will catch it |
| Chain of custody | Record of who handled the sample, when and where |
| INCONCLUSIVE | App says "Not Sure" honestly instead of guessing |

---

## 3. Example scenario (use for pitch + demo narration)

**Setting:** 11:40 PM, highway checkpoint in Punjab. SI Rajesh (ANTF — state anti-narcotics police) finds **5 packets of brown powder** in a bus passenger's bag. Only an orange street lamp + torch.

**Before (today):** He uses the kit, colour looks "purple-brown", writes "positive for heroin" for all 5 packets (they "look same"), handwritten seizure memo, no photo, no GPS, no proof. Months later the lab says 2 packets were only filler powder. The defence lawyer asks: "Under that orange light, how did you decide? Where is the proof?" Case becomes weak.

**After (FieldProof):**
1. Logs in (app knows officer ID + phone ID). Picks kit "Marquis – opiate test".
2. Places kit next to the printed colour card; the camera screen shows a guide box + **countdown timer** (kit read time).
3. App finds the card, fixes the orange light, reads the colour, compares with the kit's expected colours.
4. Screen: **🔴 POSITIVE – opium-type drug – 91% sure**, shows measured colour next to reference colours + line *"Presumptive field result — not a substitute for laboratory confirmatory testing."*
5. Sealed record created (photo fingerprint, GPS, internet time, officer ID, phone ID, kit, result) + digitally signed + QR code. Record number is written on the sample seal.

**Twist:** Packet 4 — torch glare → app says **INCONCLUSIVE: glare on card, retake**. After retake, colour is in-between → still **INCONCLUSIVE: colour between two results**. App refuses to guess → packet 4 sampled separately, senior officer checks → lab later confirms it was filler. Honesty saved a wrong charge.

**Court day:** Judge scans QR → verify page: ✅ photo not changed, ✅ signature valid, ✅ time/place/officer shown. If even 1 byte was changed → ❌ TAMPERED.

---

## 4. Our solution: FieldProof — the 4 innovations (ALL must work in the demo by 3 PM)

1. **Calibrated colour reading (app reads colour, not the eye)** — ₹10 printed reference card (ArUco + known colour patches) → colour correction → CIELAB → ΔE2000 score vs kit colours.
2. **Honest INCONCLUSIVE ("Not Sure")** — blur, glare, card missing, no match, or in-between colour → INCONCLUSIVE **with reason** → goes to Senior Officer (Supervisor) review. Never guesses.
3. **Tamper-evident signed record** — SHA-256 of original image + GPS + NTP time + officer ID + device ID + kit + result, **Ed25519-signed** and **hash-chained** (each record stores previous record's hash). QR → `/verify` page. Records can't be edited.
4. **Kit profiles as data** — any existing kit (Marquis, Scott's, etc.) is a DB row with its outcome colours + thresholds, editable by Admin on the dashboard. No app update needed.

**Cheap extras (if time):** reaction timer (from kit profile), explainable result card (measured vs reference colour chips), BSA s.63-style PDF (hash pre-filled), in-app camera only (no gallery), mock-GPS flag, phone-clock vs NTP drift flag, lab sample ID field.

**Future scope (PPT only):** offline mode, phone hardware-key co-signing, e-Sakshya / CCTNS integration, field-vs-lab accuracy tracking, Hindi + regional languages + voice, small ML model alongside ΔE rule (disagree → INCONCLUSIVE).

---

## 5. Architecture

```mermaid
flowchart LR
  A[Flutter App<br/>login · pick kit · camera guide + timer] -->|image + GPS + device id + JWT| B[FastAPI]
  B --> Q[Quality check<br/>blur / glare]
  Q --> C[Card detect<br/>ArUco + warp]
  C --> D[Colour correction<br/>CCM → CIELAB]
  D --> E[Classify<br/>ΔE2000 vs kit profile]
  E --> F[Seal record<br/>SHA-256 + NTP + GPS + officer<br/>Ed25519 sign + hash chain]
  F --> G[(PostgreSQL<br/>tests · kit_profiles · users · reviews)]
  G --> H[React Dashboard<br/>log + filters · Leaflet map · kit editor · review queue]
  G --> I[PDF report + QR]
  I --> J[/verify/{id} page<br/>re-hash + check signature + chain/]
```

**Technology workflow (as on PPT slide 3):**
1 Take photo (Flutter) → 2 Photo check (OpenCV blur/glare) → 3 Find card (ArUco) → 4 Fix colours (CCM → Lab) → 5 Decide result (ΔE2000) → 6 Seal record (hash + GPS + NTP + signature) → 7 Save on server (FastAPI + PostgreSQL) → 8 Officer website (React + Leaflet + PDF/QR + CSV)

**Roles:** `FIELD_OFFICER` (capture tests) · `SUPERVISOR` (reviews INCONCLUSIVE, confirm / order retest) · `ADMIN` (kit profiles, users, see everything).

---

## 6. Technical specs (so everyone's parts fit together)

### 6.1 Reference card (`demo/reference_card.pdf` + `demo/card_spec.json`)
- Size: A6 landscape (148 × 105 mm), matte paper, print card + swatches on the **same printer**.
- 4 ArUco markers, dictionary `DICT_4X4_50`, IDs **0 (top-left), 1 (top-right), 2 (bottom-right), 3 (bottom-left)**, ~15 mm each.
- 24 colour patches (6 × 4 grid, ColorChecker-like sRGB values) + a marked **"place kit result here"** window.
- `card_spec.json`: marker IDs + corner positions (mm), each patch `{id, x_mm, y_mm, w_mm, h_mm, srgb:[r,g,b]}`, kit window rect (mm), warp size (e.g. 1480 × 1050 px = 10 px/mm).
- `demo/fake_kit_swatches.pdf`: printed swatches labelled **"SIMULATED – demo only"** that stand in for kit outcomes (purple, orange-brown, no-change, in-between).

### 6.2 Colour engine (backend, Python + OpenCV) — `POST /tests` pipeline
1. **Quality:** blur = variance of Laplacian on card region (threshold e.g. < 80 → INCONCLUSIVE "photo is blurry"); glare = % of pixels with V > 250 on card/window (> 2% → "glare on card").
2. **Card detect:** `cv2.aruco` detect; need all 4 IDs, else INCONCLUSIVE "reference card not found". Homography → warp to canonical size.
3. **Measure patches:** median RGB of inner 60% of each patch.
4. **CCM:** linearise sRGB, fit 3×3 (or 3×4 affine) matrix by least squares from measured → known values. If mean ΔE2000 fit residual > ~6 → INCONCLUSIVE "calibration poor, retake".
5. **Kit window:** apply CCM, take median colour of inner region → convert to CIELAB (D65). If window is very non-uniform → INCONCLUSIVE "uneven colour".
6. **Classify:** ΔE2000 from measured Lab to each outcome's reference Lab in the kit profile. `d1` = best, `d2` = second best.
   - `d1 > max_delta_e` → **INCONCLUSIVE** "colour does not match any result"
   - `d2 − d1 < min_margin` → **INCONCLUSIVE** "colour is between two results"
   - else → outcome's category (**POSITIVE** / **NEGATIVE**) + outcome label
   - `confidence` (0–99) e.g. `100 × (d2 − d1) / (d2 + d1)`, reduced when `d1` is close to `max_delta_e` — tune on demo captures.
7. **Never guess.** Every INCONCLUSIVE has a `reason` string in simple English.
- Libraries: `opencv-contrib-python` (aruco), `numpy`, `colour-science` or `skimage.color.deltaE_ciede2000`.

### 6.3 Kit profile (DB table `kit_profiles`, admin-editable)
```json
{
  "id": "DEMO-IODINE-1",
  "name": "Iodine–Starch Screen (demo stand-in)",
  "reagent": "Povidone-iodine (Betadine) 1:5",
  "read_time_s": 10,
  "outcomes": [
    {"label": "Starch present", "category": "POSITIVE", "lab": [22, 8, -18]},
    {"label": "No reaction",    "category": "NEGATIVE", "lab": [60, 18, 55]}
  ],
  "max_delta_e": 15, "min_margin": 4, "active": true, "version": 1
}
```
- Seed 2 demo profiles: **Iodine–Starch (live demo)** and **Simulated Marquis (printed swatches)**: outcomes opiate-purple (POSITIVE), amphetamine orange-brown (POSITIVE), no change (NEGATIVE).
- **Lab values above are placeholders** → set real ones with a **calibrate-from-captures** step: take 5 photos of each printed swatch / real reaction through the pipeline, average the corrected Lab, save to profile.
- Changing a profile bumps `version`; each test stores the profile id **and** version.

### 6.4 Signed tamper-evident record (DB table `tests`, append-only)
Fields: `test_id (uuid)`, `created_at_ntp`, `device_time`, `time_source`, `lat`, `lon`, `gps_accuracy_m`, `gps_mock_flag`, `officer_id` (from JWT), `device_id`, `kit_profile_id`, `kit_profile_version`, `image_path`, `image_sha256`, `result`, `outcome_label`, `confidence`, `reason`, `measured_lab`, `delta_e_by_outcome`, `lab_sample_id` (optional), `prev_record_hash`, `record_hash`, `signature`, `key_id`.
- `record_hash` = SHA-256 of **canonical JSON** (sorted keys, no spaces, UTF-8) of all fields except `record_hash`/`signature`.
- `signature` = **Ed25519** (Python `cryptography` lib) over the canonical JSON. Private key only on server (file path from `.env`, never committed); public key published at `/verify/pubkey`.
- **Hash chain:** `prev_record_hash` = `record_hash` of the previous test → deleting/reordering any record breaks the chain.
- **No UPDATE/DELETE** on `tests` (no endpoints; optionally a DB trigger). Supervisor decisions go into a separate append-only `reviews` table.
- Image stored as original bytes; hash computed on the **original upload bytes** before any processing.

### 6.5 API (FastAPI)
| Method | Path | Who | What |
|---|---|---|---|
| POST | `/auth/login` | all | JWT (reuse old auth) |
| GET | `/kits` | officer | active kit profiles |
| POST/PUT | `/admin/kits`, `/admin/kits/{id}` | admin | create / edit profile |
| POST | `/admin/kits/{id}/calibrate` | admin | upload captures → average Lab per outcome |
| POST | `/tests` | officer | multipart: image + kit_id + lat/lon/accuracy/mock + device_id + device_time → result + signed record |
| GET | `/tests` | supervisor/admin | filters: date range, officer, kit, result, place (bbox/text) |
| GET | `/tests/{id}` | role-based | full record |
| GET | `/tests/{id}/pdf` | role-based | PDF report with QR → verify page |
| GET | `/tests/export.csv` | supervisor/admin | CSV export (same filters) |
| POST | `/tests/{id}/review` | supervisor | confirm / order retest + note (append-only) |
| GET | `/verify/{id}` | public | JSON: image hash OK?, signature OK?, chain OK? |
| GET | `/v/{id}` | public | simple HTML verify page (for QR) |

### 6.6 Flutter app screens
Login → Pick kit → Camera (overlay guide box for card, countdown from `read_time_s`, in-app camera only, no gallery) → Upload (with GPS + device id) → **Result screen**: colour-coded (red POSITIVE / green NEGATIVE / purple INCONCLUSIVE), confidence %, reason if inconclusive, measured vs reference colour chips, and the line **"Presumptive field result — not a substitute for laboratory confirmatory testing."** → "My tests" list.

### 6.7 React dashboard
Test log table with filters (date, officer, kit, result, place) · Leaflet/OpenStreetMap map of tests (colour pins) · test detail with image + record + PDF/QR · CSV export · **Kit profile editor** (admin) · **Review queue** for INCONCLUSIVE (supervisor) · public verify page.

---

## 7. Reuse from the old project (SIH26034 "LabelGuard AI / LMCS")

Old project folder: `C:\Users\LOKESHRAJ M\SIH` (some files also in Downloads). New folder: `C:\Users\LOKESHRAJ M\SIH26231` (next to the old one).
**Rules:** old folder, Downloads and Documents are **READ-ONLY** — copy only, never move/edit/delete. Don't copy `node_modules`, `venv/.venv`, `__pycache__`, `build/`, `dist/`, `.dart_tool/`, `.gradle/`, `.git/`, label datasets, OCR/model weights. Copy `.env` files but add them to `.gitignore`; never print secrets.

| Old part | Decision | New use |
|---|---|---|
| JWT auth + RBAC (bcrypt) | REUSE | same, roles → FIELD_OFFICER / SUPERVISOR / ADMIN |
| FastAPI + PostgreSQL + SQLAlchemy + Alembic | REUSE | new tables via migrations |
| Evidence sealing (SHA-256 + GPS + NTP, hash re-check) | REUSE → extend | + Ed25519 signature + hash chain |
| Image quality checks (blur, contrast) | REUSE | + glare check |
| Search / log APIs, CSV export, ReportLab PDF | REUSE | test log + PDF with QR |
| React dashboard shell + Leaflet map | REUSE | test log + map + kit editor + review queue |
| Flutter camera / login / upload screens | REUSE | + kit picker, guide overlay, timer, result screen |
| Scan → test record; PASS/FAIL/REVIEW/EXEMPT | ADAPT | POSITIVE / NEGATIVE / INCONCLUSIVE |
| Rules-as-data (toggle on dashboard) | ADAPT | **kit profiles as data** |
| Inspector → Controller workflow | ADAPT | Field Officer → Supervisor |
| OCR, barcode-as-ruler, font-size checks, 13 Legal Metrology rules, GSTIN, product registry / DataKart, consumer complaints, label datasets | DROP | not needed |

Branding: rename LMCS / LabelGuard / SIH26034 → **FieldProof / SIH26231** in UI text, titles, README, API title, DB name. **Don't rename Flutter/Android package IDs** (build risk) — list as TODO. `git init` + first commit; confirm backend, dashboard and app still start **before** adding features.

---

## 8. Demo plan (no real drugs — NDPS Act makes possession illegal; prescription pills like tramadol/alprazolam/codeine syrup are also controlled)

- **Kit 1 — live colour change (safe):** Betadine (povidone-iodine) diluted 1:5.
  - cornflour → **blue-black = POSITIVE**
  - sugar/salt → stays **amber = NEGATIVE**
  - sugar + pinch of cornflour → in-between → **INCONCLUSIVE**
- **Kit 2 — printed swatches** ("SIMULATED Marquis"): purple / orange-brown / no change / in-between.
- **Shopping (~₹200):** Betadine, cornflour, sugar, salt, white plastic spoons or tile, dropper, gloves, tissues. Colour print shop for card + swatches (matte paper, same printer).
- **Show on stage:**
  1. Same sample under daylight, warm bulb, phone torch, orange cellophane over lamp ("sodium street lamp") → same result (calibration works).
  2. Torch glare → INCONCLUSIVE "glare".
  3. Cover a marker → INCONCLUSIVE "card not found".
  4. Scan QR → verify OK. Change 1 byte of stored image → verify **TAMPERED**.
- Say: *"No controlled substances were used. We use a safe stand-in reaction and printed swatches. Real reagent profiles would be calibrated with a forensic lab."*
- Record a **backup video** of the full flow.

### 3-minute demo script
0:00 Problem (eye reading, no proof) → 0:30 open app, login, pick kit → 0:50 capture Betadine test on card → 1:10 result screen (POSITIVE, %, colour chips, disclaimer) → 1:30 same sample under orange light → same result → 1:50 glare → INCONCLUSIVE → 2:10 dashboard: log, map, kit editor → 2:30 PDF QR → verify OK → 2:45 tamper 1 byte → TAMPERED → 3:00 close: "Take photo → Fix colour → Get result → Keep proof."

---

## 9. PPT (done) — what's on each slide + remaining TODOs

1. Title — PS 26231, title, theme, Software, Team ID, HexTech
2. Proposed Solution — problem, 4 innovations, "Who does what" diagram, "How the app decides" diagram, result screen mock
3. Technical Approach — 8-step technology workflow, decision rules, how the ₹10 card works, "Proof that cannot be faked" diagram
4. Feasibility — feasibility points, challenges table, phased rollout, prototype goals (90%+ accuracy on demo samples in 4 lights, ≤10 s, 1-byte tamper detection, never guesses)
5. Impact — benefits, who gets helped, expected impact, future scope
6. Research & References — 7 papers (2 IEEE) with links + official sources

**TODO before submitting:** confirm **Team ID** (K26234 copied from old deck) · replace **Prototype Video Link** · replace result-screen mock numbers with a **real screenshot** · make sure prototype targets are actually met (or soften them).

---

## 10. Work split (parallel tasks — pick one, give it to your AI with this file)

| # | Task | Output / done when | Priority |
|---|---|---|---|
| T1 | **Demo material:** script to generate `reference_card.pdf` + `card_spec.json` + `fake_kit_swatches.pdf` (ReportLab + OpenCV aruco images) | Printed card detected by `cv2.aruco` with all 4 IDs | 🔴 first |
| T2 | **Colour engine** (`colour_engine.py`): quality → aruco → warp → patches → CCM → Lab → ΔE2000 → decision + reason + confidence | Function `classify(image_bytes, kit_profile) -> dict`; works on photos of the printed card | 🔴 |
| T3 | **Synthetic test images + unit tests:** same swatch under warm/cool/dim light, blurred, card missing → accuracy table printed | `pytest` passes, table printed | 🟠 |
| T4 | **Backend records:** `kit_profiles`, `tests`, `reviews` tables (Alembic), `POST /tests`, Ed25519 sign, hash chain, `/verify/{id}` + `/v/{id}`, PDF with QR, CSV | verify OK; 1-byte change → TAMPERED | 🔴 |
| T5 | **Flutter app:** login → kit picker → camera guide + timer → upload (GPS, device id) → result screen with disclaimer | end-to-end on a real phone | 🔴 |
| T6 | **Dashboard:** test log + filters, Leaflet map, kit profile editor, INCONCLUSIVE review queue | admin edits a kit, supervisor reviews a test | 🟠 |
| T7 | **Demo prep:** buy Betadine kit items, print card/swatches, calibrate profiles from captures, record backup video, README + `docs/DEMO_SCRIPT.md` | full demo runs in 3 min | 🟠 |

**Integration contract:** T2 returns
```json
{"result": "POSITIVE|NEGATIVE|INCONCLUSIVE", "outcome_label": "...", "confidence": 0-99,
 "reason": "simple English or null", "measured_lab": [L,a,b],
 "delta_e_by_outcome": {"label": value}, "quality": {"blur": x, "glare_pct": y, "card_found": true, "ccm_fit_de": z}}
```
T4 wraps this into the signed record; T5/T6 display it.

**Timeline (today):** by ~11:30 old project copied + running · by ~1:00 PM colour engine + signed record + app capture working end-to-end · by ~2:00 dashboard + PDF/QR + verify + demo calibrated · 2:00–2:45 test, record video, fill PPT link/screenshot · 3:00 submit.

---

## 11. Facts for Q&A (✅ checked from primary source · ⚠️ double-check)

- ✅ **NDPS (Seizure, Storage, Sampling & Disposal) Rules 2022** (G.S.R. 899(E), 23 Dec 2022), Rule 3(1): seized drugs are classified using "results of the drug detection kit". Sampling rule allows packets with identical colour-test results to be bunched (≤10 per lot). Rule 14: lab report within 15 days.
- ✅ **NCB Field Officers' Handbook** checklist asks whether substances were field-tested with Drug Detection Kits and whether it was documented. https://narcoticsindia.nic.in/DLEA/1.pdf
- ✅ **BNSS 2023 Sec 105:** search & seizure must be audio-video recorded, preferably on mobile phone.
- ✅ **BSA 2023 Sec 63** certificate (Schedule) asks for the **hash value** (SHA1 / SHA256 / MD5).
- ✅ **IT Act 2000 Sec 3:** digital signature = asymmetric crypto + hash. ⚠️ Legally recognised signatures need a CCA-licensed certificate (DSC / eSign) → our Ed25519 is the prototype; production path = DSC / eSign / HSM.
- ✅ Supreme Court: *Simarnjit Singh v. State of Punjab* (9 May 2023) — conviction quashed over sampling lapse; *Bharat Aambale v. State of Chhattisgarh* (6 Jan 2025, 2025 INSC 78) — prosecution must prove compliance with Sec 52A.
- ✅ NDPS cases in India: 72,721 (2019) → 1,20,010 (2023) (NCRB via PIB, 1 Apr 2026). NCB conviction rate 60.5% (2024) → 68.6% (Q1 2026) (PIB).
- ✅ e-Sakshya app (MHA, launched 4 Aug 2024) — records photos/video of evidence; used in 15,899 police stations. It does **not** measure or classify colour → we complement it.
- ✅ Colorado (USA) HB26-1020 (2026): no arrests based *only* on colorimetric field tests for small possession. ✅ Kerala 2023: Sheela Sunny jailed 72 days over "LSD stamps" that the lab found were not drugs.
- ✅ Competitors: DetectaChem MobileDetect / IDenta (only their own kits), TruNarc / MX908 (expensive hardware), e-Sakshya (no colour reading).

### Tough judge questions (short answers)
1. *What if the kit itself is wrong?* — We never claim identification; it's a presumptive result, recorded honestly; the lab confirms. Kit version is stored; future: field-vs-lab accuracy tracking.
2. *What stops a fake photo?* — In-app camera only, hash at capture, GPS/NTP, mock-GPS flag, record ID on the sample seal. We make cheating **detectable**.
3. *Is Ed25519 a legal digital signature?* — Same technique as IT Act Sec 3; legal status needs CCA DSC / eSign → production swap, same architecture.
4. *No internet?* — Future: sign locally, queue, sync later; time marked "device time, verified later".
5. *Different phones/cameras?* — Card is measured in every photo, so the phone/light difference is removed; bad fit → INCONCLUSIVE.
6. *Why not only AI/ML?* — Not enough real labelled data; ΔE rule is explainable in court. ML can be added alongside; disagreement → INCONCLUSIVE.
7. *Isn't the card new hardware?* — It's a ₹10 sheet of paper, and the PS itself asks for a reference card.
8. *Difference from e-Sakshya?* — e-Sakshya records media; FieldProof measures + classifies + signs a structured test record. It can attach to e-Sakshya.
9. *Colour-blind officer?* — The officer no longer judges colour; UI uses icons + text.
10. *How is the ΔE threshold chosen?* — Per kit profile, from calibration captures; editable as data.

---

## 12. Research used on the PPT (all links checked)
1. IEEE EMBC 2016 — Illumination and device independence for colorimetric detection with smartphone — https://ieeexplore.ieee.org/document/7591895
2. IEEE TPS-ISA 2024 — Digital Evidence Chain of Custody: Navigating New Realities of Digital Forensics — https://ieeexplore.ieee.org/document/10835509
3. Forensic Science International 2014 — Real-time quantitative colourimetric test for methamphetamine using mobile phone (Choodum et al.) — https://doi.org/10.1016/j.forsciint.2013.11.018
4. Analytical Chemistry 2016 — Objective presumptive field-testing of illicit drugs with smartphone analysis (Krauss et al.) — https://doi.org/10.1021/acs.analchem.6b01982
5. Digital Discovery 2023 — Teaching old presumptive tests new digital tricks with computer vision — https://pmc.ncbi.nlm.nih.gov/articles/PMC10408571/
6. Analytical & Bioanalytical Chemistry 2025 — RGB colour correction and gamut limitations in smartphone-based analysis (Fyfe et al.) — https://doi.org/10.1007/s00216-025-06021-9
7. Forensic Science International 2005 — False positives and false negatives with a cocaine-specific field test (Tsumura et al.) — https://doi.org/10.1016/j.forsciint.2004.11.011

Official: NDPS Act — https://www.indiacode.nic.in/handle/123456789/1791 · BNSS/BSA — https://www.mha.gov.in/sites/default/files/2024-04/250882_english_01042024_0.pdf · UNODC Rapid Testing Methods — https://www.unodc.org/documents/scientific/Rapid_Testing_Methods_of_Drugs_of_Abuse_E.pdf

---

**One-liner:** *"FieldProof turns a subjective colour guess into a calibrated, explainable and tamper-proof digital record — using only a phone and a ₹10 printed card — and honestly says 'not sure' instead of guessing."*
