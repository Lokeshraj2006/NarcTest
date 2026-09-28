# FieldProof — Integration Contract (BASIC PROTOTYPE, due 28 Sep 2026 3 PM)

Single source of truth so backend, colour engine, Flutter app and dashboard fit together.
**Keep it basic and working.** UI text = simple, casual Indian English (school-student readable).
Roles (lowercase strings everywhere): `field_officer`, `supervisor`, `admin`.

---

## 1. Printed reference card — `demo/card_spec.json` (also copied to `backend/app/services/card_spec.json`)

```json
{
  "version": 1,
  "card_w_mm": 190, "card_h_mm": 120,
  "px_per_mm": 8,
  "aruco_dict": "DICT_4X4_50",
  "markers": [
    {"id": 0, "corner": "tl", "x_mm": 5,   "y_mm": 5,  "size_mm": 22},
    {"id": 1, "corner": "tr", "x_mm": 163, "y_mm": 5,  "size_mm": 22},
    {"id": 2, "corner": "br", "x_mm": 163, "y_mm": 93, "size_mm": 22},
    {"id": 3, "corner": "bl", "x_mm": 5,   "y_mm": 93, "size_mm": 22}
  ],
  "patches": [ {"id": "P01", "x_mm": 0, "y_mm": 0, "w_mm": 0, "h_mm": 0, "srgb": [0,0,0]} ],
  "window":  {"x_mm": 0, "y_mm": 0, "w_mm": 0, "h_mm": 0}
}
```
- `x_mm,y_mm` = top-left of each element in card coordinates (origin = card top-left, mm). Marker positions above are FIXED; the colour engine agent fills in the 24 patches (6×4 grid, ColorChecker-like sRGB values incl. white, greys, black, primaries, skin/foliage) and the kit window (≈ 45×45 mm, on the right half, clearly labelled "PLACE KIT RESULT HERE"), all inside the card and not overlapping markers.
- Card is printed at 100% scale on A4 landscape, matte paper.

## 2. Colour engine — `backend/app/services/colour_engine.py` (pure Python + OpenCV + numpy, no FastAPI)

```python
def srgb_to_lab(rgb: list[float]) -> list[float]          # sRGB 0-255 -> CIELAB (D65), [L, a, b]
def delta_e2000(lab1, lab2) -> float                       # CIEDE2000
def measure(image_bytes: bytes) -> dict                    # quality + corrected window colour (used by classify + calibration)
def classify(image_bytes: bytes, profile: dict) -> dict    # full decision
```
`profile` = kit profile dict (section 3). `classify` returns EXACTLY:
```json
{
  "result": "POSITIVE | NEGATIVE | INCONCLUSIVE",
  "outcome_label": "string or null",
  "confidence": 0,
  "reason": "simple English string or null",
  "measured_lab": [0,0,0],
  "measured_rgb": [0,0,0],
  "delta_e_by_outcome": {"<outcome label>": 0.0},
  "quality": {"card_found": true, "markers_found": 4, "blur_score": 0.0, "glare_pct": 0.0, "ccm_fit_de": 0.0}
}
```
Pipeline: decode → detect ArUco (need all 4 IDs, else INCONCLUSIVE "Colour card not found — keep all 4 corner squares in the photo") → homography card-mm→pixels, warp → blur check (variance of Laplacian on warped card; too low → "Photo is blurry — hold the phone steady and retake") → glare check (% near-white saturated pixels in window/patches; too high → "Shine/glare on the card — tilt the phone a little and retake") → measure 24 patch medians (inner 60%) → fit 3×3 (or 3×4 affine) colour-correction matrix, least squares, in linear RGB → fit error (mean ΔE2000 of corrected patches vs known) too high → "Colour card could not be read properly — retake in even light" → correct the window (inner 40%, median) → Lab → ΔE2000 to each outcome → `d1` best, `d2` second:
- `d1 > max_delta_e` → INCONCLUSIVE "Colour does not match any result of this kit"
- `d2 - d1 < min_margin` → INCONCLUSIVE "Colour is in between two results — not sure"
- else result = best outcome's `category`, `outcome_label` = its label, confidence 0–99 (e.g. `100*(d2-d1)/(d2+d1)` scaled down as d1 approaches max_delta_e).
**Never guess.** Missing values → null. `measured_rgb` = corrected window colour in sRGB 0–255 (for UI chips).

## 3. Kit profile (DB table `kit_profiles`, admin-editable)

```json
{
  "id": 1, "code": "DEMO-MARQUIS-SIM", "name": "Marquis test (simulated swatches)",
  "reagent": "Printed swatch stand-in for Marquis reagent (demo only)",
  "read_time_s": 15,
  "outcomes": [
    {"label": "Opium-type drug (purple)",        "category": "POSITIVE", "srgb": [98, 45, 120],  "lab": [..]},
    {"label": "Amphetamine-type drug (orange)",  "category": "POSITIVE", "srgb": [178, 94, 40],  "lab": [..]},
    {"label": "No reaction (no colour change)",  "category": "NEGATIVE", "srgb": [236, 232, 214], "lab": [..]}
  ],
  "max_delta_e": 14, "min_margin": 4, "is_active": true, "version": 1, "updated_at": "ISO"
}
```
Seed 2 profiles:
1. `DEMO-MARQUIS-SIM` exactly as above.
2. `DEMO-IODINE`, "Iodine–Starch screen (live demo)", reagent "Betadine (povidone-iodine) diluted 1:5", read_time_s 10, outcomes: `"Starch found (blue-black)"` POSITIVE srgb `[40, 35, 60]`; `"No starch (amber)"` NEGATIVE srgb `[200, 130, 40]`; max_delta_e 18, min_margin 5.

`lab` is computed server-side from `srgb` (via `colour_engine.srgb_to_lab`) whenever a profile is saved without lab. Editing a profile bumps `version`.

**Demo swatch colours** (printed by `demo/make_card.py` into the kit window of pre-filled cards, file `demo/fake_kit_swatches.pdf`): the 3 Marquis outcome colours above, plus `AMBIGUOUS` = sRGB midpoint of purple and orange `[138, 70, 80]` (→ INCONCLUSIVE between two), plus `NO-MATCH` green `[60, 160, 80]` (→ INCONCLUSIVE no match). Each swatch card is the full reference card with the window filled and a small caption "SIMULATED — demo only".

## 4. Backend API (FastAPI, port 8000)

Auth (unchanged from old code): `POST /auth/login` body `{"username_or_email","password"}` → `{"access_token","token_type","role","user_id","username","full_name"}`; `GET /auth/me`.

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/health` | public | |
| GET | `/kits` | any logged in | active kit profiles |
| GET | `/kits/all` | supervisor, admin | incl. inactive |
| POST | `/kits` | admin | create |
| PUT | `/kits/{id}` | admin | update, version+1 |
| PATCH | `/kits/{id}/active` | admin | body `{"is_active": bool}` |
| POST | `/tests` | any logged in | multipart: `image` (file) + `context` (JSON string, below) → TestRecord |
| GET | `/tests` | any logged in | query: `date_from, date_to, officer_id, kit_id, result, q, mine`; field_officer sees only own; newest first |
| GET | `/tests/export.csv` | supervisor, admin | same filters |
| GET | `/tests/{id}` | owner, supervisor, admin | TestRecord |
| GET | `/tests/{id}/image` | owner, supervisor, admin | original bytes; header `X-Evidence-Sha256-Match: true/false` (exposed via CORS) |
| GET | `/tests/{id}/pdf` | owner, supervisor, admin | PDF with QR → verify_url |
| POST | `/tests/{id}/review` | supervisor, admin | body `{"decision": "CONFIRMED" or "RETEST", "note": str}` (append-only `reviews` table) |
| GET | `/reviews/pending` | supervisor, admin | INCONCLUSIVE tests without a review |
| GET | `/verify/{id}` | **public** | JSON verify result |
| GET | `/v/{id}` | **public** | simple mobile-friendly HTML verify page (green "Record is genuine" / red "TAMPERED") |
| GET | `/verify/pubkey` | public | `{"key_id","public_key_pem"}` |

`context` JSON for POST /tests:
```json
{"kit_id": 1, "latitude": 12.97, "longitude": 77.59, "gps_accuracy_m": 8.0, "gps_is_mock": false,
 "device_id": "android-uuid", "device_time": "2026-09-28T11:40:00+05:30",
 "client_sha256": "hex or null", "lab_sample_id": null, "notes": null}
```

TestRecord JSON:
```json
{"id": 1, "test_uid": "uuid4", "created_at": "ISO", "ntp_time": "ISO or null", "time_source": "ntp | server_clock",
 "device_time": "ISO", "clock_drift_s": 0.4, "latitude": 0, "longitude": 0, "gps_accuracy_m": 0, "gps_is_mock": false,
 "officer_id": 1, "officer_name": "…", "device_id": "…", "kit_id": 1, "kit_code": "…", "kit_name": "…", "kit_version": 1,
 "kit_outcomes": [{"label","category","srgb"}],
 "image_sha256": "hex", "client_sha256": "hex|null", "client_hash_match": true,
 "result": "…", "outcome_label": "…", "confidence": 91, "reason": null,
 "measured_lab": [..], "measured_rgb": [..], "delta_e_by_outcome": {..}, "quality": {..},
 "lab_sample_id": null, "prev_record_hash": "hex | GENESIS", "record_hash": "hex", "signature": "base64", "key_id": "ed25519-1",
 "review_status": "NOT_NEEDED | PENDING | CONFIRMED | RETEST", "verify_url": "http://<host>:8000/v/1"}
```
- Server time: try `ntplib` (pool.ntp.org, 2 s timeout) → `time_source="ntp"`; else server clock → `"server_clock"`.
- `verify_url` built from the incoming request's base URL (so a phone on LAN gets a LAN URL), overridable by env `PUBLIC_BASE_URL`.
- Image stored as original upload bytes at `backend/uploads/tests/<test_uid>.<ext>`; `image_sha256` = SHA-256 of those exact bytes.

**Signing:** `signed_payload` = canonical JSON (`json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`) of: `test_uid, created_at, ntp_time, time_source, device_time, latitude, longitude, gps_accuracy_m, gps_is_mock, officer_id, device_id, kit_id, kit_code, kit_version, image_sha256, result, outcome_label, confidence, reason, measured_lab, lab_sample_id, prev_record_hash`. Store the exact string in column `signed_payload`. `record_hash` = SHA-256 hex of it; `signature` = base64 Ed25519 signature of it (`cryptography` lib). Private key `backend/keys/ed25519_private.pem` (auto-created on first start, gitignored). `prev_record_hash` = previous test's `record_hash` (by id) or `"GENESIS"`. Tests table is append-only (no update/delete endpoints).

**/verify/{id} response:**
```json
{"test_id": 1, "ok": true,
 "checks": {"image_hash": true, "record_hash": true, "signature": true, "chain": true, "fields_match": true},
 "message": "Record is genuine — photo and details were not changed.",
 "record": {"test_uid","created_at","time_source","latitude","longitude","officer_name","kit_name","kit_version","result","outcome_label","confidence","image_sha256","record_hash"}}
```
`image_hash` = re-hash stored file == payload.image_sha256; `record_hash` = sha256(signed_payload) == stored; `signature` = Ed25519 verify; `chain` = prev_record_hash equals previous record's record_hash; `fields_match` = key DB columns (result, image_sha256, officer_id, kit_id) equal the payload.

Demo users (seed script `python -m app.scripts.seed_demo`): `officer1` (field_officer), `supervisor1` (supervisor), `admin1` (admin); password = env `DEMO_PASSWORD` from `backend/.env` (never printed, never committed).

## 5. Flutter app screens (mobile/)
Login (demo chips fill username; password from `--dart-define=DEMO_PASSWORD` if given) → Home ("New Test", "My Tests", Settings) → Pick Kit (GET /kits) → Capture (camera preview + landscape card-shaped guide box "Keep the colour card inside the box", countdown = kit `read_time_s`, then capture; "Capture now" button too; in-app camera only) → Uploading (GPS, device id, SHA-256 of photo, POST /tests) → **Result** (big colour banner: POSITIVE red / NEGATIVE green / INCONCLUSIVE purple "NOT SURE"; outcome label; "% sure"; reason if any; measured colour chip next to the kit's outcome colour chips; record box: test id, time + source, GPS, officer, short hash, "Sealed & signed ✅"; button "Open verify page" → verify_url; line **"Presumptive field result — not a substitute for laboratory confirmatory testing."**) → My Tests (GET /tests?mine=true; tap → Result).
Server URL: existing SettingsService (`LABELGUARD_API_BASE` dart-define / Settings screen). Drop ML Kit.

## 6. Dashboard (dashboard/, React + Vite)
Login (any role) → Test Log (filters date/officer/kit/result/text, table, detail panel with photo + hash-match badge + record fields + PDF + "Verify" link, CSV via `/tests/export.csv`) · Map (pins coloured by result, popup) · Kits (list, active toggle, edit name/reagent/read time/thresholds/outcomes with colour preview) · Review (pending INCONCLUSIVE, Confirm / Order retest + note) · public route `/verify/:id` (calls `GET /verify/{id}`, big green/red result). Colours: POSITIVE red, NEGATIVE green, INCONCLUSIVE purple.
