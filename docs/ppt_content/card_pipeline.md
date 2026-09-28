# How the colour card is found and used to fix colours (real example)

Figure: `card_pipeline.png` (2400 x 1000, 4 panels).
Made by: `make_card_pipeline.py` (reuses the app's own colour engine, `backend/app/services/colour_engine.py`, step by step).
Raw numbers: `card_pipeline_numbers.json`.

## Which photo

- `real_tests/test_11.jpg`, a real phone photo (1080 x 1920) taken by the team.
- The card was shown **on a laptop screen**, not printed on paper. The red caption on the card says
  "SIMULATED - demo only: Opium-type drug (purple)". So the right answer is purple (Opium-type).
- This is a **simulated swatch**, not a real drug sample. Kit profile: Marquis demo (simulated colours).

## Real numbers (same as the saved record #11 in `real_tests/records.json`)

| Step | What we got | Rule in the app |
|---|---|---|
| Corner squares (ArUco markers) found | **4 of 4** (IDs 0, 1, 2, 3) | all 4 needed |
| Sharpness (blur) score | **1064.5** | 300 or more |
| Shine / glare | **0.0 %** | 3 % or less |
| Average error of 24 known boxes, before fix | **7.71** dE2000 | - |
| Average error of 24 known boxes, after fix (`ccm_fit_de`) | **6.53** dE2000 | 9 or less |
| Kit window colour, before fix | RGB **135, 67, 144**, Lab 39.88, 41.02, -30.29 | - |
| Kit window colour, after fix (`measured`) | RGB **119, 0, 131**, Lab **28.35, 58.02, -41.07** | - |

Colour gap (dE2000) from the fixed window colour to each kit result (limit 14, and best must beat second-best by at least 4):

| Kit result | True colour (RGB) | Gap after fix | Gap if we did NOT fix |
|---|---|---|---|
| Opium-type drug (purple), POSITIVE | 98, 45, 120 | **6.63** | 9.28 |
| Amphetamine-type drug (orange), POSITIVE | 178, 94, 40 | **46.64** | 40.68 |
| No reaction, NEGATIVE | 236, 232, 214 | **68.26** | 55.12 |

**Final result: POSITIVE, Opium-type drug (purple), confidence 76 %.** Matches the red caption (correct).

## Honest notes

- Done in the prototype: all 4 steps below run in the real backend for every photo. The figure is drawn from the exact same code and gives exactly the same numbers as the saved record.
- The fix helped, but only a little on this photo: box error 7.7 to 6.5, and the gap to purple went from 9.3 to 6.6. This photo was of a **screen**, and screens show colour differently from paper. Our card is made for matte printed paper.
- After the fix the purple came out a bit too strong (green = 0). It was still clearly nearest to purple (6.6 vs 46.6 and 68.3), so the answer was right.
- Planned (not done yet): tests with the card printed on paper, a real Marquis kit and real samples, under different lights (sun, tube light, torch).

## Slide bullets (simple words)

1. **Find the 4 corner squares.** The app looks for the 4 black-and-white corner codes (ArUco markers) on the card. In this real photo it found all 4 (IDs 0 to 3). If even one is missing, it asks the officer to retake.
2. **Straighten the card.** Using those 4 corners, the app flattens the tilted photo into a straight card. Now every colour box and the kit window are at a known place. It also checks the photo is sharp (score 1065, needs 300+) and has no shine (0 %).
3. **Learn the light from 24 known colours.** We know the true colour of all 24 boxes. The app compares "what the camera saw" with "true colour" and learns a colour fix for this light and this phone (average error 7.7 before, 6.5 after; must be 9 or less, else it says INCONCLUSIVE).
4. **Fix the kit colour and compare.** The same fix is applied to the kit window. The fixed colour is compared with each kit result. Purple gap 6.6 (under the limit of 14), orange 46.6, no reaction 68.3, so the result is **POSITIVE, Opium-type, 76 % confidence**. If no colour is close enough, or two are too close, it says INCONCLUSIVE instead of guessing.
