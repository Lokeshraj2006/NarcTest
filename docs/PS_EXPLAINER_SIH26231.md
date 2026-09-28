# SIH26231 — Digital Companion for Field Drug Testing
### Explainer + PPT content pack (team HexTech, solution name: FieldProof)

> Research date: 27 Sep 2026. Facts marked ✅ were read from the primary source (bare act / gazette / judgment / PIB / official manual).
> Facts marked ⚠️ come from secondary sources or need one more check before going on a slide.

---

## 1. The problem statement in plain words

When NCB, police ANTF, DRI, Customs or Excise officers seize a suspicious powder, pill or plant, they do a quick **field test**:
- They put a pinch of it into a small chemical kit (an ampoule or pouch of reagent).
- The reagent **changes colour**: purple might mean "opiate", blue might mean "cocaine".
- The officer **looks at it with his own eyes** and writes "tested positive for heroin" in the seizure papers (panchnama / seizure memo).

Three things are wrong with that:
1. **Subjective.** Two officers can call the same colour "purple" or "brown". Street lamps, torches, sun glare and colour blindness change what they see.
2. **Not standardised.** There is no number, no reference and no threshold. It is just the officer's opinion.
3. **No proof.** Nothing proves that the test was actually done, at that place, at that time, by that officer, on that sample. So the field result can't be relied on as documentary evidence.

**What they want you to build:** an app that sits next to the existing kit (no new device). It should:
- **Photograph** the kit result together with a **printed reference colour card**, so lighting can be corrected.
- **Classify** the result automatically as POSITIVE / NEGATIVE / INCONCLUSIVE.
- Create a **tamper-evident record**: SHA-256 hash of the photo + GPS + time + officer ID, digitally signed.
- Keep a **searchable log** of all tests.

**What NOT to build:** a lab replacement. The app gives a **presumptive** (preliminary) result. The legal proof is still the FSL lab report (GC-MS / FTIR etc.). Say this on every slide where it matters. Judges will check for it.

### Key terms (for you and for the PPT)
| Term | Meaning in one line |
|---|---|
| Colorimetric / spot test | Reagent + sample → colour change that hints at a drug class |
| Presumptive vs confirmatory | Presumptive = quick field screening (can be wrong); confirmatory = lab instrument that identifies the exact molecule |
| SWGDRUG Category C | International forensic classification: colour tests give only "low selectivity / class information" ✅ |
| Reference colour card | Printed card with patches of *known* colour; the app uses it to undo the effect of the lighting |
| ArUco markers | Black-and-white square codes at the card corners so OpenCV can find and straighten the card |
| Colour-correction matrix (CCM) | Small matrix, fitted by least squares, that maps "camera colours" → "true colours" using the card patches |
| CIELAB | Colour space designed around human perception; distances in it mean something |
| ΔE2000 (CIEDE2000) | Standard "how different are two colours" number; ΔE ≈ 1 is roughly the smallest difference a person can notice |
| SHA-256 hash | Fingerprint of the photo: change 1 pixel and the hash changes completely |
| Digital signature (Ed25519) | Server signs the record with a private key; anyone with the public key can check nothing was changed |
| NTP time | Time taken from an internet time server, not the phone clock (which the user can change) |
| Tamper-evident | Tampering can't necessarily be *prevented*, but it can always be *detected* |
| Chain of custody | Unbroken record of who handled the evidence, when and where |
| Section 52A NDPS | Seized drugs must be inventoried, photographed and sampled before/with certification by a Magistrate |
| BNSS s.105 | Search & seizure must be video-recorded, preferably on a mobile phone |
| BSA s.63 certificate | Certificate needed to admit electronic records in court; its Schedule form asks for the **hash value** |

---

## 2. Example scenario (use this as the "story" slide and the demo narration)

**Setting:** 11:40 PM, an inter-state checkpoint on a national highway in Punjab. An ANTF Sub-Inspector stops a bus. In one passenger's bag are **5 small packets of brownish powder** ("smack"). The only light is an orange sodium street lamp and a torch.

### BEFORE (today)
1. The SI opens the Marquis-type ampoule from the drug detection kit and drops in a pinch from packet 1. The colour looks "sort of purple-brown" under the orange lamp. He writes "tested positive for heroin".
2. Packets 2–5 "look the same", so they are recorded as giving identical results. (The 2022 NDPS sampling rules let identical colour-test results be bunched into lots for sampling, so this reading decides how samples are drawn.)
3. There is no photo of the kit, no time proof and no GPS. The officer's handwriting and the panch witnesses are the only record.
4. **Months later in court:**
   - The FSL report shows that 2 of the 5 packets were only cutting agents (caffeine / paracetamol-type fillers).
   - The defence asks: "Was a field test really done? Under what light? Who decided it was purple? Why were all 5 lotted together?"
   - The panch witnesses turn hostile.
   - The prosecution has no objective record, and the case weakens.

### AFTER (with FieldProof)
1. The SI opens **FieldProof** and logs in. The JWT identifies him, and the app records his officer ID and the device ID.
2. He picks the kit profile **"Marquis — opiate screen"**.
3. He places the used ampoule/spot on the **printed reference card** in the marked window. The camera screen shows an outline guide. The app waits for the kit's **read time** (e.g. 30–60 s) with a countdown, then captures.
4. The server:
   - finds the 4 ArUco markers and straightens the card
   - measures 24 known patches and fits the colour-correction matrix, which removes the orange cast of the street lamp
   - reads the kit window in CIELAB
   - compares it with ΔE2000 against the profile's outcome colours
5. Screen: **🔴 POSITIVE: consistent with opiate group, confidence 91%, ΔE = 4.2 (nearest reference: "opiate violet")**. Below it: *"Presumptive field result — not a substitute for laboratory confirmatory testing."*
6. A **signed record** is created and can't be edited afterwards:
   - SHA-256 of the original photo
   - GPS 31.xx, 75.xx
   - NTP time 23:43:07 IST
   - officer ID, device ID, kit profile, result and confidence
   - Ed25519 signature
7. The record gets a **QR code**. The SI writes the record number in the seizure memo and on the sample-bag seal, and the BNSS s.105 video can show the screen.

### The INCONCLUSIVE twist
- Packet 4: the torch creates **glare** on the card. The app says **⚪ INCONCLUSIVE: glare detected on reference card, retake.** The SI retakes.
- Now the colour sits halfway between "opiate violet" and "negative/unchanged". The top two matches are too close, so the app **still says INCONCLUSIVE** ("ambiguous colour: ΔE to top two outcomes differs by only 1.1"). It **refuses to guess**.
- Packet 4 is therefore **not bunched** with the positives. It is sampled separately and flagged for the supervisor.
- Weeks later the FSL confirms that packet 4 was only a cutting agent. The app's honesty avoided a wrong lot and a wrong charge.

### Payoff in court / at the FSL
- The judge or the FSL scans the QR → **/verify** page:
  - ✅ image hash matches
  - ✅ signature valid
  - ✅ time/GPS/officer recorded
  - ✅ calibrated colour values and the reference comparison are shown
- If anyone had edited even **one byte** of the stored photo or record, the page would show **❌ TAMPERED**.
- The PDF report can pre-fill the **hash details the BSA s.63 certificate asks for** (algorithm SHA-256 + hash value).

---

## 3. Why this matters (facts you can put on slides)

### 3a. The legal hook (Indian law)
- ✅ **NDPS (Seizure, Storage, Sampling and Disposal) Rules, 2022** — G.S.R. 899(E), 23 Dec 2022:
  - Rule 3(1): seized material "shall be classified based on physical properties and **results of the drug detection kit**". The field-kit result is written into the law.
  - Rule 10 (sampling): packages giving **identical colour-test results** may be bunched in lots of up to 10, with one duplicate sample per lot. A wrong visual reading therefore changes how sampling is done.
  - Rule 14: the chemical lab should report **within 15 days**. In reality there are big backlogs (see 3b), so the field result carries the case for weeks or months.
- ✅ **NCB "Drug Law Enforcement Field Officers' Handbook"** (narcoticsindia.nic.in/DLEA/1.pdf) has a full chapter on *Drug Identification and Field Testing*. Its checklist asks whether all suspect substances were field-tested with Drug Detection Kits / Precursor Testing Kits, whether the colour results were matched, and whether it was all **documented**. FieldProof automates exactly that documentation.
- ✅ **BNSS 2023, Section 105**: search and seizure, including the seizure list, must be recorded by audio-video electronic means, **preferably mobile phone**, and forwarded to the Magistrate. The law already expects phones to create evidence.
- ✅ **Bharatiya Sakshya Adhiniyam 2023, Sections 61–63**: electronic records are admissible, subject to the s.63 certificate. The **Schedule certificate asks for the hash value** of the record, with tick-boxes for SHA1 / **SHA256** / MD5, plus a hash report.
- ⚠️ **Supreme Court, July 2026** (reported by SCC Online on 8 Jul 2026) upheld the s.63(4) certificate requirement and called the hash value an "electronic fingerprint". *Get the case name before using it on a slide.*
- ✅ **IT Act 2000, Section 3**: a legal "digital signature" = asymmetric crypto system + hash function, verifiable with the public key. Ed25519 is exactly this *technique*. **However**, a *legally recognised* digital signature in India needs a certificate from a CCA-licensed Certifying Authority (DSC / eSign). Be honest: "prototype uses Ed25519; production would use a CCA-licensed DSC / eSign or an HSM-backed departmental key".
- ✅ **Section 52A case law** (the courts care about procedure and proof):
  - *Union of India v. Mohanlal* (SC, 28 Jan 2016): found no uniform procedure for seizure and sampling; issued directions.
  - *Simarnjit Singh v. State of Punjab* (SC, 9 May 2023): **conviction quashed**. Samples drawn at the time of seizure (not before a Magistrate) created "serious doubt".
  - *Bharat Aambale v. State of Chhattisgarh* (SC, 6 Jan 2025, 2025 INSC 78): non-compliance with 52A is not automatically fatal. Once non-compliance is shown, the **prosecution must prove substantial compliance, or that it doesn't affect the case**, beyond reasonable doubt. → Objective, verifiable records help the prosecution discharge that burden.
  - ⚠️ Also relevant: *Yusuf @ Asif v. State* (SC, 13 Oct 2023) and *Mangilal v. State of MP* (SC, 12 Jul 2023), both on 52A lapses. Confirm the holdings before quoting.
- ✅ Field kits appear in real official records:
  - DRI Mumbai (PIB, 16 Apr 2025): a white powder "was tested using the NDPS Field Test Kit" and tested positive for cocaine (2,178 g).
  - Delhi HC (2026) bail orders also cite "NDPS Field Testing Kit" results.

### 3b. Scale
- ✅ NDPS cases registered in India (NCRB via PIB, 1 Apr 2026): **72,721 (2019) → 1,15,236 (2022) → 1,20,010 (2023)**, i.e. +65% in 4 years.
- ✅ NCB conviction rate: **60.5% (2024) → 65.5% (2025) → 68.6% (Q1 2026)** (PIB, 20 Apr 2026). Evidence quality is a government priority.
- ⚠️ ~**3.9 lakh NDPS cases pending** in courts (Outlook, 3 Aug 2026). Lab delays are cited as a cause.
- ✅ Forensic capacity: **7 CFSLs, 32 State FSLs, 97 Regional FSLs**; the 7 CFSLs alone received 69,826 cases in 5 years (Lok Sabha USQ 3452, 17 Dec 2024).
- ⚠️ Kerala HC (Feb 2026) pressed the state to fill vacant FSL posts: "no forensic report, no trial".
- ✅ Related government systems:
  - **e-Sakshya** evidence app, launched 4 Aug 2024; used in **15,899 police stations across 35 States/UTs** (PIB)
  - **MANAS** helpline 1933 (launched 18 Jul 2024)
  - **NIDAAN** database of arrested narco-offenders
  - **NCORD** coordination mechanism
  - Nasha Mukt Bharat Abhiyaan

### 3c. Why visual reading fails (evidence)
- ✅ UNODC manuals: colour results vary with test conditions, amount and impurities. Reagents must be checked with known substances and **a blank run to preclude false positives**. Cocaine colour tests are "especially prone" to false positives.
- ✅ US NIJ Standard-0604.01 for colour test kits: kits must state they are presumptive only and can give **false positives and false negatives**.
- ✅ ProPublica (2016): poor light on the street (flashing police lights, sun glare, street lamps) often prevents the fine colour distinctions officers need to make.
- ✅ Sodium street lamps emit almost a **single wavelength (589 nm)**, so colours are close to indistinguishable under them.
- ✅ Research survey (2023, PMC10408571): people shown the same spot-test colour described it in many different ways.
- ⚠️ Roughly 1 in 12 men worldwide has some colour-vision deficiency (a commonly cited figure; Indian school-screening studies exist).
- ✅ Global trend: **Colorado HB26-1020 (2026)** is the first US law to stop arrests for low-level possession based *solely* on colorimetric field tests. Penn Law's Quattrone Center estimates ~30,000 false arrests a year in the US from presumptive field tests. → The world is moving to "field tests must be objective + documented".
- ✅ Indian example (Kerala, 2023): beauty-parlour owner **Sheela Sunny spent 72 days in jail** after Excise claimed that seized items were LSD stamps. The lab found no drugs and the HC later quashed the case.

---

## 4. What already exists (competitors) and your gap

| Existing thing | What it does | Why it doesn't solve *this* PS |
|---|---|---|
| **DetectaChem MobileDetect** (USA) | Own drug-test pouches + free app with automated reading & reporting | Works only with **their proprietary pouches**; US-centric; no Indian legal alignment (BSA s.63 / 52A) |
| **IDenta "App & Know"** (Israel) | App to help interpret IDenta's own colour kits | Vendor-locked to their kits |
| **TruNarc** (Thermo, handheld Raman), **MX908** (handheld mass spec) | Instrument identifies the drug and stores time-stamped results | **New hardware** (lakhs of rupees per unit), excluded by the PS |
| **Parichayan** on-site NDPS kit (NFSU-RIC, India, 2025) | Indigenous colour kit | A kit, not a digital reader. FieldProof can support it as just another **kit profile** |
| **e-Sakshya** (MHA/NIC) | Geo-tagged, time-stamped photo/video evidence capture | Records *what the camera saw*; it doesn't **measure colour or classify a test** |
| **eyeWitness to Atrocities** app, **C2PA / Content Credentials**, **Axon Evidence** | Verifiable capture / audit trail of media | General-purpose; no colour science, no kit logic |
| Research (Choodum 2014; Krauss 2016; Fyfe 2025) | Smartphone colour reading of spot tests in the lab | Research prototypes; none produce a signed legal record for Indian field use |

**The gap you fill (write these as your novelty bullets):**
1. **Kit-agnostic**: works with whatever colour kit the officer already carries; adding a new kit means adding a DB row, not writing code.
2. **Calibrated, numeric colour reading** (reference card + CCM + ΔE2000) instead of an officer's opinion.
3. **Honest INCONCLUSIVE**: refuses to guess, with a stated reason (card not found, blur, glare, far from all references, ambiguous).
4. **Evidence-grade record**: SHA-256 + NTP time + GPS + officer + device, **signed**, and aligned with the **hash field of the BSA s.63 certificate**.
5. **Links field to lab**: the test record ID goes on the seal/sample, and the lab result is later fed back → accuracy statistics for each kit and each officer.
6. **Built on a working, already-tested pipeline** (from SIH26034) → low risk, fast to deploy.

---

## 5. Innovation ideas (ranked)

**Legend:** Demo = can show tomorrow? (✅ yes / 🟡 partial / ❌ PPT-only, "future scope") · hrs = rough effort for your team

### A. Core (the PS itself; must work in the demo)
| # | Idea | Demo | hrs |
|---|---|---|---|
| 1 | Reference card with ArUco + 24 patches → CCM → CIELAB → ΔE2000 vs kit profile | ✅ | 5–6 |
| 2 | POSITIVE / NEGATIVE / INCONCLUSIVE + confidence + **reason** | ✅ | incl. |
| 3 | Signed record (SHA-256, NTP, GPS, officer, device, Ed25519) + `/verify` | ✅ | 2–3 (reuse sealing) |
| 4 | Searchable log + map + PDF with QR + CSV | ✅ | 2–3 (reuse) |
| 5 | Kit profiles as data (admin-editable) | ✅ | 2 (reuse rules-as-data) |

### B. High "wow", cheap: add these to the demo
| # | Idea | Why judges care | How | Demo | hrs |
|---|---|---|---|---|---|
| 6 | **Explainable result card**: show measured colour next to each reference swatch with ΔE numbers | Officer, judge and defence can all *see* why | Colour chips in the Flutter result screen and the PDF | ✅ | 1–2 |
| 7 | **Hash-chained log**: each record stores the previous record's hash | Deleting or reordering any record breaks the chain; verify shows "chain intact" | One extra column + a check in `/verify` | ✅ | 1–2 |
| 8 | **Reaction timer**: app enforces the kit's read window (from the kit profile) | Colours change over time; stops too-early / too-late readings | Countdown in the app; `read_time_s` in the profile | ✅ | 1–2 |
| 9 | **Anti-spoofing flags**: in-app camera only (no gallery upload); mock-GPS detection; phone clock vs NTP drift flag | Answers "what if the officer fakes it?" | Android `isMock`; compare clocks; flag in record | 🟡 | 2 |
| 10 | **BSA s.63-ready PDF**: pre-filled hash section (SHA-256 + value), device details, time | Directly speaks the language of the new evidence law | ReportLab (already have) | ✅ | 1–2 |
| 11 | **Sample-seal / lab sample ID link** + field-vs-lab result entry | Chain of custody; later measures app/kit accuracy | Extra fields + a small "concordance" stat on the dashboard | 🟡 | 2–3 |
| 12 | **Supervisor review of INCONCLUSIVE** | Two-person rule (you already have Inspector→Controller) | Reuse workflow | ✅ | 1–2 |

### C. Strong PPT "future scope" ideas
| # | Idea | One-liner for PPT |
|---|---|---|
| 13 | **Shift-start kit check**: scan a blank + known-positive control swatch | "Catches expired or contaminated reagent before it wrongs anyone" (UNODC itself says to run blanks/controls) |
| 14 | **Kit batch + expiry capture** (scan the kit barcode) | Faulty batch? Every test done with it can be traced instantly |
| 15 | **Multi-reagent decision tree** (e.g. Marquis → Mecke → Simon's) | Combines 2–3 kit results into a narrower drug-class suggestion |
| 16 | **On-device co-signature** with the Android hardware Keystore + key attestation | Record signed by the *device* at capture **and** by the server → proves which phone took it, even offline |
| 17 | **Offline-first queue** with signed local records; sync later; mark "time source: device, pending NTP" | Border areas and highways have no network |
| 18 | **Daily Merkle root** anchored externally (e.g. emailed to HQ / OpenTimestamps) | Not even the server admin can quietly rewrite history. No "blockchain hype" needed |
| 19 | **e-Sakshya / CCTNS / ICJS integration** (attach record ID + PDF to the case) | Plugs into systems police already use |
| 20 | **Hotspot & trend map** for NCB / NCORD; "unknown colour" cluster alert | Field tests become intelligence: new substance showing up in a district? |
| 21 | **Kit & officer accuracy dashboard** (field vs FSL concordance) | Evidence-based kit procurement; targeted training |
| 22 | **Multilingual + voice guidance**, glove-friendly UI, colour-blind-safe (icons + text) | Usable by any officer anywhere |
| 23 | **Auto-blur faces/ID documents** in the photo (DPDP Act 2023) | Privacy by design |
| 24 | **ML ensemble** (kNN on calibrated Lab values alongside the ΔE rule); disagreement → INCONCLUSIVE | Two independent methods must agree before a positive |
| 25 | **C2PA content credentials** embedded in the photo | International provenance standard |
| 26 | **Training mode** with printed practice swatches; officer-vs-app agreement score | Standardises officers across states |

**Top 6 novelty points for the PPT:** 1 (calibrated reading) · 2 (honest INCONCLUSIVE) · 3+7 (signed + hash-chained record) · 5 (kit-agnostic profiles) · 10 (BSA s.63-ready) · 11/21 (field-to-lab feedback loop).
**Top 4 extras to actually demo tomorrow:** 6, 7, 8, 10 (all cheap, all very visible).

---

## 6. Suggested PPT outline (standard SIH idea-submission template; match it to the 2026 template you were given)

1. **Title**: PS ID SIH26231 · "Digital Companion for Field Drug Testing" · Theme · Software · Team HexTech · Solution: **FieldProof**
2. **Proposed solution**
   - The problem in 3 bullets (subjective, not standardised, no verifiable record)
   - The solution flow: Capture → Calibrate → Classify → Seal → Log → Verify
   - Novelty bullets (section 4)
   - Visual: before/after strip from the scenario
3. **Technical approach**
   - Architecture: Flutter app → FastAPI → OpenCV colour engine → PostgreSQL → React/Leaflet dashboard → PDF/QR verify
   - Colour pipeline diagram: ArUco → warp → patches → CCM → Lab → ΔE2000 → decision rules
   - Record structure + Ed25519 + hash chain
   - Tech stack logos
4. **Feasibility & viability**
   - Working prototype built on a pipeline already tested in SIH26034
   - No new hardware: a printed card costs about ₹10
   - Risks & mitigations: lighting → CCM + glare check; fake photos → in-app camera + mock-GPS + hash; no network → offline queue; legal signature → DSC/eSign path
5. **Impact & benefits**
   - For officers (objective, fast), courts (verifiable), FSLs (sample linkage), NCB (analytics), citizens (fewer false arrests)
   - Numbers: 1.2 lakh NDPS cases/yr; conviction-rate push; lab backlog
6. **Research & references**: NDPS SSSD Rules 2022; BNSS s.105; BSA s.63 + Schedule; IT Act s.3; SC 52A judgments; UNODC manuals; SWGDRUG; papers; competitor links

---

## 7. Tough judge questions — with answers

1. **"Your app says positive. What if the kit itself is wrong?"** — We never claim identification. It is a *presumptive* result about the kit's colour, calibrated and recorded; the FSL confirms. We record the kit batch and can run a shift-start control check. Field-vs-lab concordance data exposes bad kits.
2. **"What stops an officer photographing a different sample or a fake image?"** — Only the in-app camera can be used (no gallery upload). The hash is taken at capture. GPS/NTP are recorded, mock-GPS is flagged, and the record ID goes on the seal and in the BNSS s.105 video. We make cheating *detectable*, not impossible, and say so honestly.
3. **"Is Ed25519 a legal digital signature?"** — It is the same technique as IT Act s.3 (asymmetric crypto + hash). Legal recognition needs a CCA-licensed certificate, so production would use a departmental DSC / eSign or an HSM key. The architecture doesn't change.
4. **"No internet at the checkpoint?"** — Capture, classify and sign locally; queue; sync later. The time source is recorded as "device time, verified later" and the drift is shown.
5. **"Different phones have different cameras."** — That is exactly why we use the reference card: the CCM is fitted *per photo*, so the phone and lighting differences are measured and removed. If the fit is poor, the result is INCONCLUSIVE.
6. **"Why not just AI/ML?"** — There isn't enough labelled real data yet, and a black box is hard to defend in court. We use an explainable ΔE rule first; ML can later run alongside it, and disagreement → INCONCLUSIVE.
7. **"Isn't the printed card 'new hardware'?"** — It is a sheet of paper (≈₹10), printable at any station. The PS itself asks for a reference colour card in the frame.
8. **"How is this different from e-Sakshya?"** — e-Sakshya records video/photos of a scene. FieldProof *measures and classifies* the kit result and produces a structured, signed test record. It can attach to e-Sakshya / CCTNS rather than compete with them.
9. **"Who holds the keys? Can an admin alter records?"** — The private key lives only on the server (HSM in production). Records are append-only and hash-chained, and a daily root is published outside, so any change is visible.
10. **"Colour-blind officer?"** — The officer no longer has to judge colour at all. The UI uses icons + text, not just red/green.
11. **"How do you choose the ΔE threshold?"** — Per kit profile, from calibration captures of the kit's reference outcomes. The threshold is stored as data and is editable by an admin, not hard-coded.
12. **"Privacy?"** — The frame contains only the card and the kit. Faces can be auto-blurred, access is role-based, and data is encrypted at rest (DPDP Act 2023).

---

## 8. Sources (for the References slide)
- NDPS (SSSD) Rules 2022, G.S.R. 899(E), 23 Dec 2022 — gazette copy e.g. excise.mizoram.gov.in (…/narcotic-drugs-and-psychotropic-substances-seizure-storage-sampling-and-disposal-rules-2022-english.pdf)
- NCB, *Drug Law Enforcement Field Officers' Handbook* — https://narcoticsindia.nic.in/DLEA/1.pdf
- BNSS 2023 s.105; BSA 2023 ss.61–63 + Schedule — https://www.mha.gov.in/sites/default/files/2024-04/250882_english_01042024_0.pdf ; Indian Kanoon
- IT Act 2000 s.3 — https://indiankanoon.org/doc/1869099/
- *Union of India v. Mohanlal* (SC, 28.01.2016) · *Simarnjit Singh v. State of Punjab* (SC, 09.05.2023) · *Bharat Aambale v. State of Chhattisgarh* (SC, 06.01.2025, 2025 INSC 78) · *Yusuf @ Asif v. State* (SC, 13.10.2023) · *Mangilal v. State of MP* (SC, 12.07.2023) — Indian Kanoon
- SCC Online, 8 Jul 2026: "Hash value is an electronic fingerprint; Section 63(4) BSA certificate requirement is valid: Supreme Court"
- PIB: NDPS cases 2019–2023 (PRID 2247659, 01.04.2026); NCB conviction rate (PRID 2253927, 20.04.2026); e-Sakshya launch (PRID 2041322, 04.08.2024); e-Sakshya usage (PRID 2226442); MANAS launch (18.07.2024); DRI Mumbai cocaine field test (PRID 2122252, 16.04.2025)
- Lok Sabha USQ 3452 (17.12.2024), forensic lab infrastructure — mha.gov.in
- UNODC, *Rapid Testing Methods of Drugs of Abuse*; UNODC recommended methods (cocaine, ATS, cannabis) — unodc.org/documents/scientific
- SWGDRUG Recommendations v8.2 (Categories A/B/C) — swgdrug.org
- NIJ Standard-0604.01, *Color Test Reagents/Kits* — ojp.gov/pdffiles1/nij/183258.pdf
- ProPublica, "Busted" (7 Jul 2016); Penn Quattrone Center report on field drug tests; Colorado HB26-1020 (2026)
- Choodum et al., *Forensic Sci Int* 2014, 235:8–13 · Krauss et al., *Anal Chem* 2016, 88:8689 · Fyfe et al., *Anal Bioanal Chem* 2025, 417:5753 · PMC10408571 (2023, computer vision for presumptive tests)
- OpenCV `aruco` and `ccm` (colour correction) modules — docs.opencv.org
- DetectaChem MobileDetect; IDenta App & Know; Thermo TruNarc; 908 Devices MX908; NFSU-RIC *Parichayan* kit; eyeWitness to Atrocities; C2PA; OpenTimestamps; Android Key Attestation / Play Integrity
