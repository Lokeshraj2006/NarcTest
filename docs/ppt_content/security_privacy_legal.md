# FieldProof: Data security, privacy and legal fit

This answers the SIH review comment: *"no discussion of data privacy, security compliance, or legal admissibility of the digital records in court".*

Everything under "What we already do" was checked in the code on 28 Sep 2026, and the tests were run. Anything not in the code is written as **Next step** or **Planned**.

---

## 0. What we checked in the code (proof)

| Area | What the code really does | Where |
|---|---|---|
| Passwords | bcrypt with a new random salt for each password. Minimum length is only 6. | `backend/app/core/security.py`, `schemas/user.py` |
| Login token | JWT (HS256), valid for 480 min (8 h). Secret key comes from `.env`: it is set and is not the default `CHANGE_ME` (we checked this without printing it). On every request the user is loaded again from the DB, and blocked (inactive) users are refused. | `core/security.py`, `core/dependencies.py`, `config.py` |
| Roles | 3 roles: officer / supervisor / admin. Only admin can create users or edit kits. Supervisor/admin can do reviews and CSV export. An officer gets **403** if they open someone else's test. | `core/dependencies.py`, `routers/tests.py` (`_load`), `routers/kits.py`, `routers/reviews.py` |
| Sign-up | **Closed.** `POST /auth/register` always returns 403. Only admin can use `POST /auth/users`. | `routers/auth.py` |
| Photo fingerprint | The server takes the SHA-256 of the exact bytes it received, then saves them unchanged. The phone also makes its own SHA-256 (`client_sha256`), and the server stores whether the two match (`client_hash_match`). | `routers/tests.py`, `mobile/lib/screens/sealing_screen.dart` |
| Digital seal | Ed25519 signature on a **canonical JSON** of 22 fields (sorted keys, no spaces). `record_hash` = SHA-256 of that JSON. | `services/signing.py`, `services/record_service.py` (`SIGNED_FIELDS`) |
| Hash chain | Each record stores the `record_hash` of the record before it (the first one stores `GENESIS`). A lock makes sure two records never point to the same parent. | `routers/tests.py` (`_chain_lock`) |
| Append-only | There is **no update or delete endpoint** for tests. Reviews can only be added, never edited. (Kits can be edited by admin, but each edit raises `kit_version`, and that version number is signed into the record.) | `routers/tests.py`, `routers/reviews.py`, `routers/kits.py` |
| Verify | `/verify/{id}` (JSON) and `/v/{id}` (web page) run 5 checks: photo hash, record hash, signature, chain link, and whether the shown fields match the signed ones. Public key at `/verify/pubkey`. | `routers/verify.py`, `record_service.verify_record` |
| Time | NTP (pool.ntp.org, 2 s timeout), else the HTTPS `Date` header from google / cloudflare / microsoft, else the server clock. The source used is saved and signed (`time_source`), and so is the phone time (`device_time`). | `services/time_service.py` |
| Location | Phone GPS plus accuracy. The `gps_is_mock` flag (from geolocator `isMocked`) is signed into the record. It is **only flagged, not blocked**. | `mobile/lib/screens/sealing_screen.dart` |
| Camera | Photos come from the in-app camera only (`camera` plugin, `takePicture`), with a card-shaped guide box. `image_picker` is in `pubspec.yaml` but is **not used anywhere** in `lib/`. | `mobile/lib/screens/capture_screen.dart` |
| Token on devices | Phone: `flutter_secure_storage`. Dashboard: `sessionStorage` (cleared when the tab closes). | `mobile/lib/services/auth_service.dart`, `dashboard/src/api.js` |
| Photo storage | Plain files at `backend/uploads/tests/<random-uuid>.jpg` (gitignored). The photo is **only** shown after login (`/tests/{id}/image`), and every download re-checks its hash. | `config.py`, `routers/tests.py` |
| Signing key | `backend/keys/ed25519_private.pem`, auto-created, gitignored. On Linux the file is set to chmod 600. It is stored **unencrypted** (`NoEncryption`). | `services/signing.py` |
| Database | PostgreSQL (from `.env`). Not encrypted by the app. | `.env` (only the URL scheme was checked) |
| CORS | Only `http://localhost:5173` and `http://localhost:3000`. | `.env`, `main.py` |
| TLS / HTTPS | **None on the API.** It runs as plain `http` on `0.0.0.0:8000`, and Android allows cleartext (`usesCleartextTraffic="true"`). The only HTTPS part is the demo public link (Pinggy tunnel). | `start_fieldproof.bat`, `AndroidManifest.xml`, `scripts/public_link.py` |
| Public link | `scripts/public_link.py` is a **verify-only gateway**. It passes on ONLY `GET /v/<id>`, `/verify/<id>` and `/verify/pubkey`. Login, tests, photos and the dashboard cannot be reached through it. | `backend/scripts/public_link.py` |
| Rate limiting | **None.** | (searched the whole backend) |
| Audit log | No separate audit table. The records themselves (append-only, signed, chained) and reviews (who and when) act as the log. Other activity only goes to the console log. | `utils/logger.py` |
| PDF report | Has a block called "Hash details (SHA-256) for a BSA 2023 Sec 63 certificate" (photo SHA-256, record hash, previous hash, signature) and the presumptive-result line. | `services/report_service.py` |

**Real measured numbers**
- Backend tests: **17 of 17 passed** (`test_verify`, `test_auth`, `test_tests_api`, run on an in-memory database). They include 3 tamper tests:
  1. flipping **1 byte** of a saved photo shows "TAMPERED" on `/v/<id>`;
  2. changing the `result` column from POSITIVE to NEGATIVE is caught by the `fields_match` check;
  3. editing the signed JSON breaks both the record hash and the signature.

  They also check that sign-up is closed and that roles are enforced.
- Real phone tests today (records 7 to 12, card shown on a second phone's screen):
  - **6 of 6** records pass all verify checks;
  - **6 of 6** phone SHA-256 values match the server's SHA-256.
- Time source in those 6 records: HTTPS internet time 4, server clock 2 (records 7 and 8), NTP 0. College Wi-Fi blocks NTP; this is exactly why we added the HTTPS fallback.
- Photo metadata (EXIF) check on `test_8.jpg`: it has **no GPS tag inside the photo**. GPS is kept as a separate, signed field.

---

## 1. What we already do (prototype) vs next step (production)

| Topic | What we already do (prototype) | Next step (production) |
|---|---|---|
| **Access control** | Login needed for everything except the verify page. 3 roles (officer / supervisor / admin). An officer sees only their own tests. Sign-up is closed; only admin creates accounts. Blocked users are refused. | Link to police ID / SSO. Second factor (OTP). Bind each officer to their device. Lock the account after many wrong passwords. |
| **Passwords** | bcrypt with salt. Never stored as plain text. | Stronger rule (min 10+ characters), password expiry for admins, lockout. Min length today is only 6. |
| **Login token** | JWT, 8 h expiry, secret from `.env`. Phone keeps it in secure storage; dashboard in sessionStorage. | Shorter tokens + refresh tokens. Way to cancel (revoke) a token. Asymmetric JWT (RS256/EdDSA). |
| **Tamper evidence** | SHA-256 of the photo. Ed25519 seal on canonical JSON of 22 fields. Hash chain to the previous record. No edit/delete API. 5-check public verify page. 1-byte photo change is caught (tested). | Publish the latest chain hash every day to an outside place (for example an RFC 3161 time-stamp server), so deleting the newest records is also caught. Also seal and chain the supervisor reviews (today they are append-only but not signed). Add DB rules that block UPDATE/DELETE. |
| **Time** | NTP, else HTTPS internet time, else server clock. The source used is saved in the record and signed, along with the phone's own clock. | Trusted time-stamp authority (RFC 3161). Warn when phone and server clocks differ a lot. |
| **Location trust** | Phone GPS + accuracy + mock-GPS flag, all signed. | Block or send to review when mock GPS is on or accuracy is poor. Add network location as a cross-check. GPS from a phone can still be faked; we can only *flag* it. |
| **Photo capture** | In-app camera only (no gallery). The phone and the server both take SHA-256, and 6/6 real tests matched. | Sign on the phone with a hardware key (Android Keystore / StrongBox) plus app attestation, so the photo is sealed before it leaves the phone. |
| **Storage / encryption** | Photos stored as files with random names, not in git. Photo shown only after login, and its hash is re-checked. PostgreSQL database. **No encryption at rest yet.** | Encrypt disk / DB / photo store (AES-256). Government cloud (MeitY-empanelled) inside India. Backups kept for the NDPS case period. |
| **Network (TLS)** | **No TLS on the API yet** (plain HTTP on local Wi-Fi for the demo). CORS allows only the 2 dashboard addresses. Only the verify-only public link uses HTTPS (Pinggy tunnel). | HTTPS everywhere (TLS 1.2+), with Android cleartext turned off and certificate pinning in the app. Rate limiting and a firewall (WAF). |
| **Privacy / data minimisation** | We collect only what the case needs: the card + kit photo, GPS, time, officer ID, a random device ID (not IMEI) and an optional lab sample ID. There is no field for the accused person's name or Aadhaar (only a free-text notes box). No GPS inside the photo file. | Auto-blur any face or ID card that gets into the frame. Hide officer name and exact GPS on the public page (see gap 1). Retention and deletion rules as per law. |
| **Audit** | Records are append-only and chained. Reviews store who reviewed and when. The CSV export is only for supervisor/admin. | A proper audit log for who viewed, downloaded or exported what, and for admin actions, chained the same way. Sent to a separate log server. |
| **Key management** | One Ed25519 server key, made on first start, kept outside git. Public key is published at `/verify/pubkey`. Key is **not** password-protected. | Keep the key in an HSM / cloud KMS. Key rotation (the `key_id` field is already there). Swap to a CCA-licensed DSC / eSign for legal signatures. |

### Honest gaps we found (say these ourselves before judges ask)
1. **The public page shows too much.** `/v/<id>` shows the officer's name, exact GPS and the result to anyone with the link. The id is a small running number (7, 8, 9...), so other records can be guessed. Fix: use the random `test_uid` in the link and hide or round the name and GPS.
2. **No TLS, no encryption at rest, no rate limiting yet.** These are fine for a local demo but must be added before any real use.
3. **The signing key file is not encrypted**, and it sits on the same server as the data.
4. **Deleting the newest record(s) directly in the database would not show** on the chain, because nothing comes after them yet. Every other change is caught. Fix: publish the chain head outside the server (see table).
5. `client_hash_match` and supervisor reviews are **stored, but not inside the signed seal**.
6. `docs/PS_EXPLAINER_SIH26231.md` (Q&A line 12) says *"data is encrypted at rest"*. **This is not true yet.** Please don't say it in the review; say "planned".

---

## 2. Legal fit (India): what each law asks and what we do

> We do **not** claim "court-admissible". A court decides that. FieldProof is **designed to support admissibility**: it gives the hash value for the BSA Sec 63 certificate, and the record is signed, time-stamped and chained.
> The legal wording below is from our team research notes (`docs/PS_EXPLAINER_SIH26231.md`). Please check it against the official Gazette text before the final deck.

| Law | What it says (simple words) | How FieldProof fits | Status |
|---|---|---|---|
| **BNSS 2023, Sec 105** | Search and seizure (including the seizure list) must be recorded by audio-video electronic means, preferably a mobile phone, and sent to the Magistrate. | Our record is also made on a phone at the spot. The record number / QR can be written in the seizure memo and on the sample-bag seal, and shown in the Sec 105 video. We do **not** record the video ourselves. | Supports (fits alongside) |
| **BSA 2023, Sec 61–63** | Electronic records can be used as evidence. Sec 63 needs a certificate, and the certificate form in the Schedule asks for the **hash value** of the record (SHA1 / **SHA256** / MD5 options). | We compute **SHA-256** of the photo and of the record at the moment of saving. The PDF report already has a block called "Hash details (SHA-256) for a BSA 2023 Sec 63 certificate". The certificate still has to be signed by the responsible person and an expert. | Hash part done; certificate itself is signed by people |
| **IT Act 2000, Sec 3** | A digital signature = asymmetric cryptography + a hash function, checked with a public key. For *legal recognition* the signature needs a certificate from a **CCA-licensed** Certifying Authority (DSC / eSign). | Ed25519 uses the same **technique** (public/private key + hash). But our key is self-made, so it is a **technical prototype**, not a legally recognised signature. | Production path: DSC / eSign / HSM-held departmental key |
| **NDPS (Seizure, Storage, Sampling and Disposal) Rules 2022, Rule 3(1)** | Seized material is to be classified based on physical properties and the **results of the drug detection kit**. | FieldProof reads the kit result with a calibrated colour card and saves it as a sealed record (kit name + version, measured colour, ΔE, result). If it is not sure, it says INCONCLUSIVE and does not guess. | Supports the kit-result step |
| **DPDP Act 2023** | Personal data: use it only for the stated purpose, collect as little as possible, and keep it safe with reasonable security safeguards. | Purpose is only the drug-test record. The photo is framed on the card + kit (no faces needed; no GPS inside the photo). We use a random device ID, not IMEI. Access is role-based. Security safeguards are partly done (see table: TLS and encryption are still to do). | Partly done; gaps listed above |
| **Presumptive-only disclaimer** | A field colour test is only a first (presumptive) test. The FSL lab test confirms it. | "Presumptive field result — not a substitute for laboratory confirmatory testing" is printed on the app result, the verify page and the PDF. There is a lab sample ID field that links to the FSL report. | Done |

---

## 3. Slide-ready bullets

- **Only the right people get in.** Sign-up is closed and only the admin makes accounts. Passwords are stored with bcrypt, and an officer can only see their own tests.
- **Every photo gets a fingerprint.** We take its SHA-256 at the moment it is saved. Change even 1 byte and our check says "TAMPERED" (we tested this).
- **Every record gets a digital seal.** It is signed with Ed25519 and linked to the record before it, like a chain. You cannot edit one record quietly.
- **Anyone can check it.** Scan the QR and the public page runs 5 checks (photo, record, seal, chain, fields). In today's 6 real phone tests, all 6 passed, and the phone's hash matched the server's in all 6.
- **Trusted time and place.** Time comes from the internet (NTP, else HTTPS), and the record shows which one was used. GPS is saved, and fake-GPS apps are flagged.
- **We keep less data.** Only the card + kit photo, time, GPS, officer and a random device ID. No field for the accused person's details.
- **Built to fit Indian law:** BNSS Sec 105 (seizure on phone), BSA Sec 63 (the certificate asks for the hash; we give SHA-256), IT Act Sec 3 (same method as a digital signature), NDPS Rules 2022 (kit result is used to classify), DPDP 2023.
- **Honest next steps:** HTTPS, encryption at rest, a CCA-licensed DSC / eSign in an HSM, rate limiting and an audit log. The result is presumptive; the FSL lab confirms it.

**Judges' Q&A: "Is this legally valid evidence?"**
> "Not by itself. A court decides that. FieldProof is built to *support* admissibility: it gives the SHA-256 hash the BSA Sec 63 certificate asks for, and every record is signed, time-stamped and chained. The signature uses the same method as IT Act Sec 3, and in production we will switch it to a CCA-licensed DSC / eSign. The result is presumptive, and the FSL lab report confirms it."

---

## 4. Picture for the slide

`docs/ppt_content/security_legal.png` (1920 × 1080, white). Left side: the 5 protection steps. Right side: the 5 laws, one line each. The footer shows the production path and the presumptive-result warning. It was drawn with `docs/ppt_content/make_security_legal_png.py` (Pillow only).
