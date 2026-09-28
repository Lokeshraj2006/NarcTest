# "Our Goals for the Prototype" - checked with real numbers

Checked on 28 Sep 2026, team laptop (AMD CPU, Python 3.11). Every number below was measured, nothing guessed.
Sources: `validation_results.json` / `validation.md` (accuracy, honesty), `goals_timing.json` from `goals_timing_run.py` (speed), `pytest tests/test_verify.py` (tamper).

---

## a) Verification table

| # | Team's claim | What we measured | Status |
|---|---|---|---|
| 1 | Accuracy: 90%+ correct on our demo colour samples in 4 types of light | Synthetic demo photos: **25 / 25 right (100%) in 5 kinds of light** (daylight, tungsten, cool white, dim, sodium lamp), right drug type every time. Real phone photos (card shown on a phone/laptop screen): **6 photos -> 5 right, 1 NOT SURE, 0 wrong** (live app). | **Partly** - true for the demo set (and it is 5 lights, not 4), but the rules were tuned on that same set, and real photos are only 5/6 right (83%), n = 6. So "90%+" should not be the headline. |
| 2 | Speed: result + sealed record in 10 s or less | Full `POST /tests` on the server (save photo + real colour check + trusted time + SHA-256 + Ed25519 sign + hash chain + DB save), 6 real photos x 3 runs = 18 runs: **median 2.5 s, max 5.0 s**. Of this, colour check = 0.16 s median, trusted time = 2.3 s median (NTP is blocked here, so 2 s NTP wait + HTTPS time), everything else = 0.04 s. `GET /verify/{id}`: **16 ms median, 28 ms max**. Live phone records (over USB): phone "send" time to server timestamp was **2.6 to 4.7 s** for all 6 real tests. | **Met** - well under 10 s on the server and in the real USB demo. Not tested on mobile data / field network, and GPS wait on the phone is not included. |
| 3 | Tamper check: change even 1 byte -> check fails | `pytest tests/test_verify.py`: **4 passed, 0 failed** (1-byte photo change caught, DB result edit caught, signed record edit caught, untouched records pass). Full backend suite: **34 passed, 0 failed**. After the 18 timing runs above, all 18 records still verified OK. | **Met** |
| 4 | Honesty: never guesses - unclear means NOT SURE | Bad synthetic photos (blur, glare, card missing, marker covered, mixed colour, unknown colour): **12 / 12 said NOT SURE**. Real photos: **0 wrong**, 1 honest NOT SURE (asked for retake). Confusion matrix: 0 false positive, 0 false negative. | **Met on our test photos** - "never" is only proven for these 12 + 6 photos, so say "in all our tests". |

### Speed details (from `goals_timing.json`)

| Part of POST /tests | Median | Min | Max |
|---|---|---|---|
| Whole request (server side) | 2535 ms | 2367 ms | 4951 ms |
| Trusted time (NTP try + HTTPS fallback) | 2337 ms | 2201 ms | 4749 ms |
| Colour check (real engine, 1080 x 1920 photos) | 161 ms | 122 ms | 235 ms |
| Save + hash + sign + chain + DB + HTTP layer | 42 ms | 37 ms | 56 ms |
| GET /verify/{id} (re-hash photo + check signature + chain) | 16 ms | 14 ms | 28 ms |

Setup: FastAPI TestClient, temporary in-memory SQLite, temp keys/uploads folders. Real colour engine and real `time_service` (every run got time from HTTPS because NTP is blocked on this network). Live server, live Postgres DB and live keys were not touched. First warm-up request (2.5 s) not counted.

Notes:
- 3 of 18 runs took about 4.7 to 5.0 s. The extra time was all in the HTTPS time lookup (internet), not in our code.
- Worst case was not forced: if NTP and all 3 HTTPS time sites fail, the code tries each with a 2 s timeout, so it could take longer before falling back to the server clock. We did not measure that case.
- Upload time of the ~0.8 MB photo over USB was **not measured on its own**, so we do not claim "under 1 s". The live phone records (send -> server timestamp 2.6 to 4.7 s) already include the upload. These use two different clocks (phone and server/internet) and the phone time is cut to whole seconds, so treat them as roughly +/- 1 s.

---

## b) Final slide content (paste this)

**Our Goals for the Prototype - and what we measured**

- **Accuracy** - 25/25 right in 5 kinds of light; 0 wrong on 6 real photos
- **Speed** - result + sealed record in 2.5 s typical, 5 s max (goal: 10 s)
- **Tamper check** - change even 1 byte, verify fails; 4/4 tamper tests pass
- **Honesty** - 12/12 bad photos said NOT SURE; no wrong guess in any test

## c) Footnote (one line, small text)

*Demo colour cards (synthetic photos + card on a screen), not real reagents; real set small (n = 6); time measured on server, not field network. 90%+ on real kits is the FSL trial goal.*

---

### What changed from the old claims
- "4 types of light" -> **5** (we tested sodium street lamp too).
- "90%+" -> replaced with the real count (25/25 demo, 0 wrong real). 90%+ on **real kits** is kept only as the next goal, because we have not tested real reagents yet.
- "10 seconds or less" -> kept as the goal, with the measured 2.5 s / 5 s.
- "Never guesses" -> "no wrong guess in any test", because we can only prove it for the photos we tested.
