# Validation results: "Tested, not just claimed"

Answer to the review comment: *"deck lacks quantitative data / test results / confusion matrix to back the 90%+ accuracy claim"*.

Slide image: `validation.png` (1920 x 1080). Raw numbers: `validation_results.json`. Script to run it again: `validation_run.py`.
Run date: 28 Sep 2026. Engine: `backend/app/services/colour_engine.py` (current thresholds, max_ccm_fit_de = 9.0). Kit profiles: the seeded `DEMO-MARQUIS-SIM` and `DEMO-IODINE` from `kit_service.py`.

---

## 1. Synthetic test set (37 photos, `demo/test_images/`)

Each photo was run through `colour_engine.classify` with the kit profile named in `manifest.json`. A photo counts as "correct" only if the result matches (POSITIVE / NEGATIVE / INCONCLUSIVE), and for good photos the drug type (label) must match too.

### Good photos: did it give the right result?

| Lighting | Photos | Correct | Accuracy |
|---|---|---|---|
| Daylight | 5 | 5 | 100% |
| Tungsten bulb (yellow) | 5 | 5 | 100% |
| Cool white tube | 5 | 5 | 100% |
| Dim light | 5 | 5 | 100% |
| Sodium street lamp (orange) | 5 | 5 | 100% |
| **All good photos** | **25** | **25** | **100%** |

(Each lighting has: Marquis purple, Marquis orange, Marquis no reaction, Iodine starch, Iodine amber.)

### Bad photos: did it honestly say NOT SURE?

| Problem in the photo | Photos | Said NOT SURE | Reason the app gave |
|---|---|---|---|
| Blurry | 4 | 4 | "Photo is blurry" (3), "Colour card not found" (1, very heavy blur) |
| Glare / shine | 2 | 2 | "Shine/glare on the card" |
| Card missing | 1 | 1 | "Colour card not found" |
| Corner marker covered | 1 | 1 | "Colour card not found" |
| In-between colour (purple + orange mix) | 2 | 2 | "Colour does not match any result of this kit" |
| Colour not in kit (green) | 2 | 2 | "Colour does not match any result of this kit" |
| **All bad photos** | **12** | **12** | |

Small note: for the 2 "in-between" photos we expected the reason "in between two results". The app still said NOT SURE (correct), but because the colour was far from both (dE 22 and 23, limit is 14), it gave the "does not match" reason instead.

### Confusion matrix (synthetic, 37 photos)

| Truth \ App said | POSITIVE | NEGATIVE | NOT SURE |
|---|---|---|---|
| **POSITIVE** (15) | **15** | 0 | 0 |
| **NEGATIVE** (10) | 0 | **10** | 0 |
| **Should be NOT SURE** (12) | 0 | 0 | **12** |

37 / 37 correct, 0 wrong. No false positive, no false negative.

**Honest note:** the engine's thresholds were tuned on these same synthetic photos (the code comment says so). So this is a "the engine works as designed" check, not an independent accuracy number.

### Speed

| What | Median | Range |
|---|---|---|
| All 37 synthetic photos | **120 ms** per photo | 58 to 298 ms |
| 25 good synthetic photos | 130 ms | 100 to 298 ms |
| 6 real photos (1080 x 1920) | 142 ms | 115 to 197 ms |

Measured on the team laptop CPU (AMD, Python 3.11), colour engine only, median of 3 runs per photo. Upload and network time are not included.

---

## 2. Real photos (6, `docs/ppt_content/real_tests/`)

Ground truth = the red caption printed under the swatch in each photo ("SIMULATED - demo only: ..."). We opened every photo and read it.

Note: these are **not** paper cards. 2 photos show the card PDF on a **phone screen** (test_7, test_8), 4 photos show it on a **laptop screen** (test_9 to test_12).

| Photo | Shown on | Truth (caption) | Live app said (records.json) | Verdict | Re-run today with current engine |
|---|---|---|---|---|---|
| test_7 | phone screen, 2 cards in the frame | Opium-type (purple) | NOT SURE: "Colour card could not be read properly" (card fit dE 6.16) | honest NOT SURE | POSITIVE purple, 77% |
| test_8 | phone screen | Opium-type (purple) | POSITIVE purple, 75% | correct | POSITIVE purple, 75% |
| test_9 | laptop screen | Amphetamine-type (orange) | POSITIVE orange, 81% | correct | POSITIVE orange, 81% |
| test_10 | laptop screen | Amphetamine-type (orange) | POSITIVE orange, 68% | correct | POSITIVE orange, 68% |
| test_11 | laptop screen | Opium-type (purple) | POSITIVE purple, 76% | correct | POSITIVE purple, 76% |
| test_12 | laptop screen | Opium-type (purple) | POSITIVE purple, 73% | correct | POSITIVE purple, 73% |

| Real photos | n | Correct | Honest NOT SURE | Wrong |
|---|---|---|---|---|
| Live app (what the officer saw) | 6 | **5** | **1** | **0** |
| Re-run today (current engine) | 6 | 6 | 0 | 0 |

**Honest notes:**
- We quote the **live app** numbers (5 / 1 / 0) on the slide. The re-run gets test_7 right only because the "card fit" limit is now 9.0. The live app rejected test_7 at a card fit of 6.16, so the limit was lower at that time and was raised later, after seeing real photos. So the 6/6 re-run is not an independent test.
- test_10 had a card fit of 8.67, very close to the 9.0 limit. Screens glow and are not like paper, so the card fit is much worse than on synthetic photos (5.9 to 8.7 vs under 1).
- Real confidences were 68% to 81%, lower than on clean synthetic photos.

---

## 3. Tamper detection (automated tests)

Command: `pytest tests/test_verify.py -v` in `backend/` (uses an in-memory test database, not the real one).
Result: **4 passed, 0 failed**. Full backend suite: **34 passed, 0 failed**.

| Tamper attempt | Test | Caught? | How |
|---|---|---|---|
| Change 1 byte of the saved photo | `test_changed_photo_byte_is_caught` | Yes | photo SHA-256 check fails, /v page shows TAMPERED |
| Edit the result in the database (POSITIVE to NEGATIVE) | `test_changed_result_column_is_caught` | Yes | "fields match" check fails, other records and the chain stay OK |
| Edit the signed record itself | `test_changed_signed_payload_breaks_hash_and_signature` | Yes | record hash and Ed25519 signature both fail |
| (Control) Fresh untouched records | `test_fresh_records_verify_and_chain` | passes as genuine | all checks OK, hash chain links OK |

---

## 4. Slide bullets (ready to paste)

- We tested our colour engine on 37 synthetic photos in 5 lighting types (daylight, tungsten, cool white, dim, sodium street lamp): 25 / 25 good photos gave the right result and the right drug type.
- For 12 bad photos (blurry, glare, card missing, marker covered, in-between or unknown colour), the app said NOT SURE every time (12 / 12). It never guessed.
- Confusion matrix on the synthetic set: 37 / 37 correct, 0 false positives, 0 false negatives.
- 6 real phone photos of the card on a screen: 5 correct, 1 honest NOT SURE (asked for retake), 0 wrong.
- Fast: 120 ms median per photo for the colour check (laptop CPU).
- Tamper-proof, and tested: 1-byte photo change, database result edit and signed record edit were all caught (3 / 3; 4 / 4 verify tests pass).

**Limitations (say this on the slide):** Synthetic images + a card shown on a phone / laptop screen, not a real reagent. The synthetic set was also used to tune the rules. Real reagent kits still need calibration with FSL. The real sample is small (n = 6). So we are not yet claiming 90%+ accuracy on real kits; that is the next step (FSL field trial).

---

## 5. Done in prototype vs planned

| Done in the prototype (measured above) | Planned |
|---|---|
| Colour correction with the reference card + POSITIVE / NEGATIVE / NOT SURE decision | Calibrate outcome colours with real reagent kits at FSL |
| Quality checks: blur, glare, card missing, marker covered, no match | Larger real test set (paper card, real kits, many phones and officers) |
| 37-photo synthetic test + 6 real photos | Independent test set not used for tuning; report accuracy with confidence range |
| Tamper checks (photo hash, DB edit, signed payload) with automated tests | Field trial with police / NCB |
