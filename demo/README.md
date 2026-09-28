# FieldProof demo kit

Everything you need to show FieldProof working, **without any real drugs**.

> FieldProof gives only a **presumptive field result**. It is not a substitute for laboratory confirmatory testing.

## What is in this folder

| File | What it is |
|---|---|
| `reference_card.pdf` | The colour card. Print it and put the test kit on it. |
| `reference_card.png` | Picture preview of the same card. |
| `fake_kit_swatches.pdf` | 5 ready-made cards with a colour already in the kit box (SIMULATED - demo only). |
| `card_spec.json` | Where each square and colour sits on the card (the app reads this). |
| `make_card.py` | Makes the card, the preview and the swatch cards again. |
| `make_test_images.py` | Makes fake photos in `test_images/` to test the colour engine. |

## How to run the scripts (PowerShell, step by step)

1. Open **PowerShell** (press the Windows key, type `powershell`, press Enter).
2. Copy-paste these lines one by one and press Enter after each:

```powershell
cd "C:\Users\LOKESHRAJ M\SIH26231"
.\backend\venv\Scripts\python.exe demo\make_card.py
.\backend\venv\Scripts\python.exe demo\make_test_images.py
cd backend
.\venv\Scripts\python.exe -m pytest tests\test_colour_engine.py -q -s
```

The last command prints a table of every test photo and the accuracy at the end.

## 1. Print the card

- Open `reference_card.pdf` and print on **A4, landscape**.
- In the print box choose **"Actual size" / 100%**. Do NOT pick "Fit to page".
- Use plain **matte** paper (not glossy, it shines).
- Check it with a ruler: the card should be **19 cm wide and 12 cm tall**.
- Cut along the thin grey line. Keep the 4 black-and-white corner squares clean and uncovered.

## 2. Demo with the swatch cards (easiest)

1. Print `fake_kit_swatches.pdf` the same way (100%, matte). You get 5 pages:
   - purple -> should show **POSITIVE (Opium-type drug)**
   - orange -> should show **POSITIVE (Amphetamine-type drug)**
   - off-white -> should show **NEGATIVE (No reaction)**
   - AMBIGUOUS (brownish red) -> should show **NOT SURE**
   - NO-MATCH (green) -> should show **NOT SURE**
2. In the app pick the kit **"Marquis test (simulated swatches)"**.
3. Keep the card flat on a table, hold the phone straight above it, fit the whole card in the guide box and capture.
4. Try it under a tube light, a yellow bulb and near a window: the answer should stay the same.
5. To show the safety checks: cover one corner square with your thumb, or shake the phone, or shine a torch on the card. The app should say **NOT SURE** and tell you what to fix.

## 3. Live demo: Betadine + cornflour (safe kitchen chemistry)

This is a real colour-change test (iodine turns blue-black with starch). No drugs involved.

You need: Betadine (povidone-iodine) solution, water, cornflour, 2 small white bottle caps or a white plastic spoon, a dropper.

1. Mix Betadine with water **1 part Betadine : 5 parts water**. This is the "reagent".
2. Cap A: a pinch of **cornflour** mixed with a few drops of water.
3. Cap B: a pinch of **sugar or salt** (no starch).
4. Put 2-3 drops of the reagent in each cap.
   - Cap A turns **blue-black** -> starch found.
   - Cap B stays **amber / orange-brown** -> no starch.
5. Place one cap inside the **"PLACE KIT RESULT HERE"** box on the printed card.
6. In the app pick the kit **"Iodine-Starch screen (live demo)"**, wait for the 10 second timer, and capture.
   - Cap A -> **POSITIVE (Starch found)**
   - Cap B -> **NEGATIVE (No starch)**

Safety: Betadine stains clothes and skin. Wear gloves, do not drink it, wipe spills.
Tip: fill the cap well so the colour covers the middle of the box, and avoid shiny reflections on the liquid.

## Notes

- The swatch cards are **SIMULATED - demo only**. They are printed colours, not real test results.
- If you change the card layout, run `make_card.py` again. It also copies `card_spec.json` into `backend/app/services/`.
