# MIGRATION_PLAN — SIH26034 (LMCS / LabelGuard AI) → SIH26231 (FieldProof)

> **Status:** Step 1 of 4. Nothing is copied until you say "ok".
> Old project: `C:\Users\LOKESHRAJ M\SIH`, plus reference files in `Downloads`. These are **READ-ONLY**: copy only.
> New project: `C:\Users\LOKESHRAJ M\SIH26231`
> `Documents` and `OneDrive\Documents` were searched for SIH, 26034, LMCS, LabelGuard, Legal Metrology, HexTech and Proposal → **no matches**. All reference files are in `Downloads`.

## 1. Big picture

| Area | Old (LMCS) | New (FieldProof) | How much we reuse |
|---|---|---|---|
| Backend | FastAPI + SQLAlchemy + Alembic, PostgreSQL 18 (Windows service, port 5433) | same stack, new DB `fieldproof_db` | ~35–40 % of the code |
| Dashboard | React 18 + Vite + react-leaflet | same | ~60 % (shell, API client, auth, map, log, queue, CSV/PDF helpers) |
| Mobile | Flutter (Provider, Dio, camera, geolocator, ntp, crypto, ML Kit) | same, minus ML Kit | ~55 % (auth, server URL settings, camera, GPS, NTP, API client, map, log screens) |

**Already in the old code:**
- JWT + bcrypt login, with `require_roles` role checks
- SHA-256 of each upload, file stored under its hash, duplicate photo flag
- Phone clock checked against internet (NTP) time; a large gap → tamper flag
- Hash re-checked live when a photo is opened (`X-Evidence-Sha256-Match`)
- Rules stored as data, switched on/off from the dashboard
- Inspector → Controller confirm/reject workflow
- ReportLab PDF styles
- Searchable log, Leaflet map and CSV export (CSV is built in the dashboard)
- Server URL can be changed inside the app
- LAN demo helpers (`lan_serve.py`, `build_and_serve.py`)

**Missing, to build in Step 3:**
- Reference-card colour engine (ArUco → warp → CCM → CIELAB → ΔE2000 → decision)
- Glare and blur checks on the server
- Kit profiles table and dashboard editor
- Ed25519 signing and hash chain
- `/verify/{id}` and a public verify page
- QR code in the PDF
- CSV export from the server
- Phone-side hash sent to the server (the app's `HashingService` exists but is never called)

### Old concept → new concept
| Old | New |
|---|---|
| Scan / EvidenceRecord | **Test record** (`tests` table) |
| PASS / FAIL / REVIEW / EXEMPT | **POSITIVE / NEGATIVE / INCONCLUSIVE** |
| 13 rules stored as data (toggled on the dashboard) | **Kit profiles stored as data** (outcome colours + thresholds, editable) |
| Inspector → Controller (confirm/reject a violation) | **Field Officer → Supervisor** (review INCONCLUSIVE results) |
| roles `consumer / inspector / admin` | roles `field_officer / supervisor / admin` |

## 2. How Step 2 copies (safe and fast)

1. **Never copied:**
   - `venv/`, `node_modules/`, `__pycache__/`, `build/`, `dist/`, `.dart_tool/`, `.gradle/`, `.git/`, `.idea/`, `.claude/`, `.pytest_cache/`, `.github/modernize/`
   - `Backend/uploads/` (old evidence photos, 50 MB) and `backups/` (20 MB)
   - `Backend/labelguard.db.pre-postgres-backup`
   - `Backend/tests/fixtures/` (label images) and `mobile/test/fixtures_*`
   - the 235 MB APK
   - `CLAUDE.md` (LMCS notes; its useful machine tips go into the new README instead)
2. **Copy all the code first as one working app**, including the DROP *code* modules, then rebrand it and start it once on the new DB to prove it still runs. The old models and routers link to each other (User ↔ Complaint/Inspection/Violation), so deleting them straight away would stop the app from starting.
3. **Delete the DROP code modules from the NEW copy only**, one by one as each FieldProof replacement lands in Step 3. Each deletion is logged in `CHANGELOG.md`. Nothing in the old folder is ever touched.
4. **`.env` files:**
   - Copied, but only two values change: the DB name in `DATABASE_URL` → `fieldproof_db`, and `APP_NAME`.
   - Listed in `.gitignore`; values are never printed.
   - The new Ed25519 private key goes in `backend/keys/`, which is also gitignored.
5. **Folder names:** `Backend/ → backend/`, `Frontend/ → dashboard/`, `mobile/ → mobile/`.
6. **Branding:**
   - LMCS / LabelGuard / SIH26034 → **FieldProof / SIH26231** in UI text, titles, README, API title, DB name, CSV/PDF file names and sessionStorage keys.
   - **Not renamed, left as a TODO (renaming could break the build):** the Android `applicationId`/`namespace` `gov.in.legalmetrology.labelguard_mobile`, the Kotlin package folder, and the Dart package name `labelguard_mobile`.
7. **`git init` and first commit, then check:**
   - backend `/health` and login work
   - dashboard loads with `npm run dev`
   - Flutter passes `flutter analyze` and builds a debug APK

## 3. Planned folder tree

```
SIH26231/
├── MIGRATION_PLAN.md · README.md · CHANGELOG.md · .gitignore · docker-compose.yml
├── backend/                         (from Backend/)
│   ├── .env (copied, gitignored) · .env.example · requirements.txt · Dockerfile · alembic.ini
│   ├── keys/                        NEW  Ed25519 private/public key (gitignored)
│   ├── alembic/versions/            fresh 0001_fieldproof_initial (old 0001–0008 dropped)
│   ├── app/
│   │   ├── main.py · config.py · database.py
│   │   ├── core/        security.py (+ Ed25519 sign/verify, canonical JSON) · dependencies.py
│   │   ├── models/      user.py (new roles) · test_record.py (from evidence.py) · kit_profile.py (from rule.py) · review.py (from violation.py)
│   │   ├── routers/     auth.py · tests.py (from scan.py) · log.py (from inspections.py) · kits.py (from rules.py) · reviews.py (from violations.py) · verify.py NEW
│   │   ├── services/    colour_engine.py NEW · quality.py NEW (blur/glare) · signing.py NEW · report_service.py (per-test PDF + QR) · scan_audit.py · auth_service.py
│   │   └── scripts/     create_user.py · seed_kits.py (from seed_rules.py) · seed_demo_users.py NEW
│   ├── scripts/lan_serve.py
│   └── tests/           test_auth · test_health · test_colour_engine NEW · test_signing_verify NEW
├── dashboard/                       (from Frontend/)
│   └── src/ api.js · auth.jsx · download.js · App.jsx · styles.css
│       └── pages/ Login · TestLog (SystemLog) · TestMap (MapView) · Kits (Rules) · Review (Queue) · TestDetail (ReportDetail) · Verify NEW
├── mobile/                          (Flutter; package id unchanged)
│   └── lib/ services (api, auth, settings, camera, gps, ntp, hashing) · screens (login, splash, settings, kit_picker NEW, capture, result, my_tests, map)
├── demo/                            NEW  make_card.py · reference_card.pdf · card_spec.json · fake_kit_swatches.pdf · make_test_images.py · test_images/
└── docs/
    ├── old_ps_reference/            reference copies only (see §7)
    ├── DEMO_SCRIPT.md · PPT_NOTES.md · api-contract.md · db-schema.md
    └── FieldProof_SIH26231_TEAM_BRIEF.md · PS_EXPLAINER_SIH26231.md · SIH26231_FieldProof_HexTech.pptx/.pdf (our new deck)
```

## 4. Backend — `Backend/` → `backend/`  (REUSE 18 · ADAPT 31 · DROP 48)

| File / folder | Decision | Reason |
|---|---|---|
| `Backend/alembic.ini` | ✅ REUSE | url overridden in env.py |
| `Backend/alembic/README` | ✅ REUSE | boilerplate |
| `Backend/alembic/env.py` | ✅ REUSE | reads settings.database_url, imports app.models metadata |
| `Backend/alembic/script.py.mako` | ✅ REUSE | template |
| `Backend/app/__init__.py` | ✅ REUSE | empty package marker |
| `Backend/app/core/__init__.py` | ✅ REUSE | package marker |
| `Backend/app/core/security.py` | ✅ REUSE | bcrypt hash/verify, JWT create/decode with role claim, compute_sha256; add Ed25519 sign/verify here |
| `Backend/app/database.py` | ✅ REUSE | engine/SessionLocal/Base/get_db, sqlite+pg aware |
| `Backend/app/routers/__init__.py` | ✅ REUSE | package marker |
| `Backend/app/schemas/user.py` | ✅ REUSE | Token/UserCreate/UserLogin/UserResponse (role enum follows model) |
| `Backend/app/scripts/__init__.py` | ✅ REUSE | package marker |
| `Backend/app/services/__init__.py` | ✅ REUSE | package marker |
| `Backend/app/services/auth_service.py` | ✅ REUSE | get_user_by_id/username, create_user, authenticate |
| `Backend/app/utils/__init__.py` | ✅ REUSE | package marker |
| `Backend/app/utils/logger.py` | ✅ REUSE | get_logger configured from settings |
| `Backend/scripts/lan_serve.py` | ✅ REUSE | uvicorn on 0.0.0.0 for phone on LAN + firewall hint; rename header |
| `Backend/tests/__init__.py` | ✅ REUSE | package marker |
| `Backend/tests/test_health.py` | ✅ REUSE | health probe test (check app name assertion) |
| `Backend/.env.example` | 🔧 ADAPT | rename labelguard DB/app name, add signing key vars |
| `Backend/Dockerfile` | 🔧 ADAPT | 2-stage python:3.11-slim; drop libzbar0; libgl1-mesa-glx may not exist on newer Debian |
| `Backend/app/config.py` | 🔧 ADAPT | pydantic-settings; rename defaults (DB url/name, app_name LMCS), add signing key path + public base URL for QR |
| `Backend/app/core/dependencies.py` | 🔧 ADAPT | get_current_user + require_roles factory; rename convenience guards to field_officer/supervisor/admin |
| `Backend/app/main.py` | 🔧 ADAPT | lifespan create_all, CORS w/ exposed header, /health; change title/description, router list |
| `Backend/app/models/__init__.py` | 🔧 ADAPT | model registry for Alembic; prune dropped models, add TestRecord/KitProfile |
| `Backend/app/models/evidence.py` | 🔧 ADAPT | base for TestRecord: sha256, GPS, device/NTP ts, drift, is_tampered; drop OCR/seller/complaint cols, add device_id, kit_profile+version, result, confidence, signature, prev_hash |
| `Backend/app/models/rule.py` | 🔧 ADAPT | rules-as-data pattern (is_active, config_json, timestamps) -> KitProfile with outcome colours JSON + version |
| `Backend/app/models/user.py` | 🔧 ADAPT | User table fine; UserRole -> FIELD_OFFICER/SUPERVISOR/ADMIN, drop complaint/violation relationships, badge_number keep as officer id |
| `Backend/app/models/violation.py` | 🔧 ADAPT | status-machine pattern reusable for supervisor review of INCONCLUSIVE; strip LM fields |
| `Backend/app/routers/auth.py` | 🔧 ADAPT | register/admin create user/login/me; restrict public register (no consumer role) |
| `Backend/app/routers/inspections.py` | 🔧 ADAPT | /log list with filters, detail, image with live SHA-256 re-check header, view-access guard; drop complaints_router, add filters date/officer/kit/result, /verify |
| `Backend/app/routers/legal_notice.py` | 🔧 ADAPT | PDF streaming endpoint pattern (inline/attachment); repoint to per-test PDF |
| `Backend/app/routers/rules.py` | 🔧 ADAPT | list + admin PATCH toggle/config -> kit profile CRUD |
| `Backend/app/routers/scan.py` | 🔧 ADAPT | multipart upload + context JSON, SHA-256, store-by-hash, duplicate flag, NTP drift tamper check, history; replace OCR/barcode/FSSAI/rules pipeline with colour pipeline + sign/chain |
| `Backend/app/routers/violations.py` | 🔧 ADAPT | file/confirm/reject workflow -> supervisor review queue for INCONCLUSIVE |
| `Backend/app/schemas/__init__.py` | 🔧 ADAPT | schema registry; prune |
| `Backend/app/schemas/inspection.py` | 🔧 ADAPT | log row/detail/EvidenceMeta shapes for dashboard+map; drop authenticity/FSSAI/GSTIN/complaint parts |
| `Backend/app/schemas/scan.py` | 🔧 ADAPT | ScanContext (GPS, device/ntp ts, drift, rescan_of_id) -> TestContext; drop OCR/barcode/text_blocks fields |
| `Backend/app/schemas/violation.py` | 🔧 ADAPT | review workflow schemas |
| `Backend/app/scripts/create_user.py` | 🔧 ADAPT | CLI bootstrap user of any role; update role names/examples |
| `Backend/app/scripts/seed_rules.py` | 🔧 ADAPT | idempotent seeder pattern -> seed kit profiles |
| `Backend/app/services/report_service.py` | 🔧 ADAPT | ReportLab styles, _fmt_dt, _make_image_flowable, hash/GPS/NTP blocks; rewrite body as per-test report + QR |
| `Backend/app/services/scan_audit.py` | 🔧 ADAPT | enum_value, pin_color, log_row + eager-load options; map verdicts POSITIVE/NEGATIVE/INCONCLUSIVE, drop edited_fields/OCR |
| `Backend/app/services/violation_service.py` | 🔧 ADAPT | state-guarded transitions with row lock -> supervisor review |
| `Backend/requirements.txt` | 🔧 ADAPT | keep fastapi/sqlalchemy/alembic/psycopg2/jose/bcrypt/opencv/numpy/reportlab/ntplib; drop pyzbar, asyncpg unused; add cryptography(Ed25519), qrcode, opencv-contrib for ArUco, scikit-image or colour-science for dE2000 |
| `Backend/tests/test_auth.py` | 🔧 ADAPT | in-memory SQLite + dependency_overrides fixture, hashing/JWT/sha256/RBAC tests; update roles |
| `Backend/tests/test_models.py` | 🔧 ADAPT | ORM round-trip pattern; rewrite for new models |
| `Backend/tests/test_scan_history_and_audit.py` | 🔧 ADAPT | history/log/image-hash-match tests pattern |
| `Backend/tests/test_violation_escalation.py` | 🔧 ADAPT | workflow transition tests -> supervisor review |
| `docker-compose.yml` | 🔧 ADAPT | postgres:15 + backend; rename labelguard names; build context ./backend is lowercase vs Backend folder |
| `Backend/.env` | ✅ REUSE | copied as-is except DB name → fieldproof_db and APP_NAME; gitignored; values never printed |
| `Backend/alembic/versions/0001_initial_schema.py` | ❌ DROP | LM schema; generate fresh 0001 for new models |
| `Backend/alembic/versions/0002_product_registry.py` | ❌ DROP | registry |
| `Backend/alembic/versions/0003_compliance_result.py` | ❌ DROP | LM aggregate |
| `Backend/alembic/versions/0004_evidence_seller_fields.py` | ❌ DROP | seller fields |
| `Backend/alembic/versions/0005_rules_and_escalation.py` | ❌ DROP | LM rules/violations |
| `Backend/alembic/versions/0006_one_notice_per_report.py` | ❌ DROP | notices |
| `Backend/alembic/versions/0007_additional_fssai_licences.py` | ❌ DROP | FSSAI |
| `Backend/alembic/versions/0008_scan_history_audit.py` | ❌ DROP | LM audit cols (idea reused in new model) |
| `Backend/app/models/calibration.py` | ❌ DROP | barcode-as-ruler scale table; colour-card calibration differs (could store CCM JSON on test record instead) |
| `Backend/app/models/complaint.py` | ❌ DROP | consumer complaint module |
| `Backend/app/models/compliance_result.py` | ❌ DROP | 13-rule aggregate verdict (compliant/needs_review/action_needed); verdict goes on test record |
| `Backend/app/models/font_size_rule.py` | ❌ DROP | Rule 7 font-size table |
| `Backend/app/models/inspection.py` | ❌ DROP | LM field inspection entity, unused by scan flow |
| `Backend/app/models/legal_notice.py` | ❌ DROP | legal notices |
| `Backend/app/models/penalty.py` | ❌ DROP | LM penalties |
| `Backend/app/models/product.py` | ❌ DROP | packaged commodity product |
| `Backend/app/models/product_registry.py` | ❌ DROP | product registry/DataKart |
| `Backend/app/models/rule_check.py` | ❌ DROP | per-rule 13-check outcomes; CheckStatus enum pattern only |
| `Backend/app/scripts/seed_product_registry.py` | ❌ DROP | product registry seed |
| `Backend/app/services/applicability_engine.py` | ❌ DROP | empty stub, LM specific |
| `Backend/app/services/authenticity_service.py` | ❌ DROP | product registry cross-check |
| `Backend/app/services/barcode_service.py` | ❌ DROP | pyzbar barcode decode |
| `Backend/app/services/calibration_service.py` | ❌ DROP | empty stub (barcode scale) |
| `Backend/app/services/complaint_service.py` | ❌ DROP | consumer complaint auto-notify |
| `Backend/app/services/compliance_aggregator.py` | ❌ DROP | 13-rule aggregate |
| `Backend/app/services/compliance_rules.py` | ❌ DROP | the 13 LM rules |
| `Backend/app/services/cv_service.py` | ❌ DROP | barcode ruler/font size/placement; only _relative_luminance/contrast snippet mildly useful |
| `Backend/app/services/evidence_service.py` | ❌ DROP | empty stub (docstring only); write real sealing service here fresh |
| `Backend/app/services/font_size_rules.py` | ❌ DROP | empty stub, font rules |
| `Backend/app/services/fssai_mark_service.py` | ❌ DROP | FSSAI veg mark detection |
| `Backend/app/services/ocr_service.py` | ❌ DROP | empty stub, OCR |
| `Backend/app/services/penalty_service.py` | ❌ DROP | empty stub, penalties |
| `Backend/app/utils/gstin_validator.py` | ❌ DROP | GSTIN |
| `Backend/labelguard.db.pre-postgres-backup` | ❌ DROP | old SQLite data backup |
| `Backend/tests/fixtures/barcode/pack_a_back_barcode.png` | ❌ DROP | label dataset |
| `Backend/tests/fixtures/fssai/*.png (9 files)` | ❌ DROP | FSSAI label fixtures |
| `Backend/tests/test_authenticity_service.py` | ❌ DROP | registry |
| `Backend/tests/test_barcode_service.py` | ❌ DROP | barcode |
| `Backend/tests/test_compliance_aggregator.py` | ❌ DROP | aggregate |
| `Backend/tests/test_compliance_rules.py` | ❌ DROP | 13 rules |
| `Backend/tests/test_cv_service.py` | ❌ DROP | barcode ruler CV |
| `Backend/tests/test_fssai_mark_service.py` | ❌ DROP | FSSAI |
| `Backend/tests/test_gstin_validator.py` | ❌ DROP | GSTIN |
| `Backend/tests/test_needs_review_scan.py` | ❌ DROP | LM scan pipeline |
| `Backend/tests/test_rule_switches_and_scale.py` | ❌ DROP | LM rule switches/barcode scale |
| `Backend/tests/test_scan_barcode_fallback.py` | ❌ DROP | barcode |
| `Backend/tests/test_scan_extra_photos.py` | ❌ DROP | FSSAI extra photos |

**Reusable pieces:**
- app/core/security.py: get_password_hash / verify_password (bcrypt), create_access_token(subject, role, extra_claims) / decode_access_token (python-jose HS256), compute_sha256(bytes) -- add Ed25519 sign/verify next to these
- app/core/dependencies.py: get_current_user, get_current_active_user, require_roles(*roles) RBAC factory + convenience guards (require_admin, require_inspector_or_admin -> rename)
- app/database.py: engine (sqlite/pg aware pool args), SessionLocal, Base(DeclarativeBase), get_db
- app/config.py: Settings(BaseSettings) reading .env incl. ntp_max_drift_seconds, storage path, cors_origins
- app/main.py: lifespan Base.metadata.create_all + CORS with expose_headers=[X-Evidence-Sha256-Match] + /health
- app/routers/scan.py: _resolve_upload_dir / _persist_image (content-addressed storage by sha256), duplicate_of_id lookup by sha256, NTP drift -> is_tampered/tamper_reason block, multipart image + JSON Form context parsing via pydantic model_validate_json, GET /scan/history
- app/routers/inspections.py: _photo_response(path, recorded_sha256, mime) -- live SHA-256 re-check returning X-Evidence-Sha256-Match; _require_view_access owner-or-privileged guard; /inspections/log paginated list with filters
- app/services/scan_audit.py: enum_value, pin_color (verdict->map pin colour), log_row + log_row_options (joinedload to avoid N+1)
- app/models/evidence.py: EvidenceRecord column set for sha256/GPS/accuracy/timestamp_device/timestamp_ntp/ntp_drift/is_tampered/captured_by_id, rescan_of_id/duplicate_of_id self-FKs
- app/models/rule.py + app/routers/rules.py: data-driven catalogue with is_active + config_json and admin PATCH -> KitProfile editor
- app/services/violation_service.py + routers/violations.py: guarded status transitions (file -> confirm/reject) with RBAC -> supervisor review queue
- app/services/report_service.py: ParagraphStyle set, _fmt_dt, _make_image_flowable, SimpleDocTemplate A4 layout, SHA-256/GPS/NTP chain-of-custody table rows
- app/routers/legal_notice.py: StreamingResponse PDF with ?inline=true Content-Disposition pattern
- app/scripts/create_user.py: CLI to bootstrap first admin
- app/scripts/seed_rules.py: idempotent upsert seeder pattern
- scripts/lan_serve.py: run uvicorn on 0.0.0.0 for phone testing + Windows firewall hint
- tests/test_auth.py: in-memory SQLite + app.dependency_overrides[get_db] fixture and _make_user/_token helpers

## 5. Dashboard — `Frontend/` → `dashboard/`  (REUSE 3 · ADAPT 12 · DROP 1)

| File / folder | Decision | Reason |
|---|---|---|
| `Frontend/src/download.js` | ✅ REUSE | saveBlob/saveCsv (Excel BOM)/stamp, fully generic |
| `Frontend/src/main.jsx` | ✅ REUSE | BrowserRouter + AuthProvider bootstrap, generic |
| `Frontend/vite.config.js` | ✅ REUSE | Port 5173, host:true for LAN demo; no branding |
| `Frontend/index.html` | 🔧 ADAPT | Change the <title> 'LMCS — Controller Dashboard'; keep the Leaflet CSS link from unpkg |
| `Frontend/package.json` | 🔧 ADAPT | Keep deps (react, react-router-dom, leaflet, react-leaflet, vite); rename package name/description; add qrcode lib only if the dashboard renders QR codes |
| `Frontend/src/App.jsx` | 🔧 ADAPT | Keep ErrorBoundary, Shell/Outlet layout, pending-count badge, health banner; rename nav items/routes (/tests, /map, /review, /kits, /tests/:id) and brand |
| `Frontend/src/api.js` | 🔧 ADAPT | Keep request() wrapper, token/session helpers, ApiError, hash-match header image fetch; swap endpoints (violations->tests/review, rules->kit-profiles, add verify); rename labelguard_* keys |
| `Frontend/src/auth.jsx` | 🔧 ADAPT | Keep context/RequireAuth; change the role gate from 'admin' only to SUPERVISOR/ADMIN |
| `Frontend/src/pages/Login.jsx` | 🔧 ADAPT | Generic login form; change the 'LMCS / Controller of Legal Metrology' heading and the default redirect |
| `Frontend/src/pages/MapView.jsx` | 🔧 ADAPT | Becomes the TEST MAP: CircleMarker+Popup+FitBounds; recolour pins by result, drop complaints/reports layers, change the Bengaluru default centre if needed |
| `Frontend/src/pages/Queue.jsx` | 🔧 ADAPT | Becomes the SUPERVISOR REVIEW QUEUE (INCONCLUSIVE): status filter tabs + counts + CSV; replace severity ranking and notice statuses |
| `Frontend/src/pages/ReportDetail.jsx` | 🔧 ADAPT | Becomes TEST DETAIL/REVIEW: photo with hash-match badge, confirm/reject notes, PDF download; drop the issueNotice/legal notice section and add signature/chain verify status |
| `Frontend/src/pages/Rules.jsx` | 🔧 ADAPT | Becomes the KIT PROFILE EDITOR: the load-from-DB + PATCH toggle pattern stays; replace the 13-rule categories with kit fields (outcome Lab colours, ΔE thresholds, version) |
| `Frontend/src/pages/SystemLog.jsx` | 🔧 ADAPT | Becomes the TEST LOG: list + person/query filters + detail + CSV + PDF; drop barcode/edited-field/rescan flags; add date/kit/result/place filters |
| `Frontend/src/styles.css` | 🔧 ADAPT | Keep layout; recolour/rename --compliant/--violation/--review/--exempt tokens to POSITIVE/NEGATIVE/INCONCLUSIVE; fix header comment |
| `Frontend/src/ExtraPhotos.jsx` | ❌ DROP | Multi-face pack photos + veg mark words are LMCS-specific (the zoom modal pattern could be salvaged) |

## 6. Mobile — `mobile/`  (REUSE 8 · ADAPT 34 · DROP 27)

| File / folder | Decision | Reason |
|---|---|---|
| `mobile/lib/services/auth_service.dart` | ✅ REUSE | Secure JWT/role storage |
| `mobile/lib/services/camera_service.dart` | ✅ REUSE | Generic back-camera init/capture, veryHigh JPEG |
| `mobile/lib/services/gps_service.dart` | ✅ REUSE | Permission-checked high-accuracy GPS with last-known fallback |
| `mobile/lib/services/hashing_service.dart` | ✅ REUSE | SHA-256 of a file or bytes; currently unused, so wire it into the capture flow |
| `mobile/lib/services/ntp_service.dart` | ✅ REUSE | NTP time + drift with offline fallback |
| `mobile/lib/services/settings_service.dart` | ✅ REUSE | Runtime-overridable backend URL; only rename the dart-define key |
| `mobile/lib/utils/server_time.dart` | ✅ REUSE | Offset-safe ISO parse to local time |
| `mobile/lib/widgets/custom_button.dart` | ✅ REUSE | Button with loading state |
| `mobile/android/app/build.gradle.kts` | 🔧 ADAPT | Change namespace/applicationId; drop pinned ndkVersion (only needed for ML Kit) |
| `mobile/android/app/src/main/AndroidManifest.xml` | 🔧 ADAPT | Change label LMCS; remove ML Kit DEPENDENCIES meta-data; keep camera/location/cleartext/FileProvider |
| `mobile/android/app/src/main/kotlin/gov/in/legalmetrology/labelguard_mobile/MainActivity.kt` | 🔧 ADAPT | Package path must move to match new applicationId |
| `mobile/lib/main.dart` | 🔧 ADAPT | Rename LMCSApp/title; trim provider list |
| `mobile/lib/models/evidence_model.dart` | 🔧 ADAPT | Keep EvidenceMetadata core (hash/GPS/NTP); drop BoundingBox/Barcode/OCR payload |
| `mobile/lib/models/inspection_log_models.dart` | 🔧 ADAPT | Log row/detail/EvidenceMetaModel become test record + signature/chain fields |
| `mobile/lib/models/scan_models.dart` | 🔧 ADAPT | Keep ScanContext GPS/NTP/timestamp fields; drop OCR/barcode/FSSAI/GSTIN/authenticity models; add kit profile, device id, hash |
| `mobile/lib/models/user_model.dart` | 🔧 ADAPT | Roles consumer/inspector/admin -> field_officer/supervisor/admin |
| `mobile/lib/providers/auth_provider.dart` | 🔧 ADAPT | Keep as is; update default role and add officer/device id |
| `mobile/lib/providers/inspection_log_provider.dart` | 🔧 ADAPT | Becomes the test log provider (filters, detail) |
| `mobile/lib/providers/pending_complaints_provider.dart` | 🔧 ADAPT | Pattern for the supervisor INCONCLUSIVE review queue (or drop) |
| `mobile/lib/providers/scan_provider.dart` | 🔧 ADAPT | Becomes TestProvider submitting image + context |
| `mobile/lib/screens/admin/admin_home_screen.dart` | 🔧 ADAPT | 'Use web dashboard' screen with dashboard URL derived from API host; rebrand |
| `mobile/lib/screens/auth/login_screen.dart` | 🔧 ADAPT | Login + settings link; rebrand and replace demo chips with new seeded users |
| `mobile/lib/screens/consumer/my_scans_screen.dart` | 🔧 ADAPT | Becomes the officer's 'My tests' history |
| `mobile/lib/screens/consumer/scan_capture_screen.dart` | 🔧 ADAPT | Keep camera/gallery/GPS/NTP staging; remove barcode/OCR/extractor; add hash + kit picker; submit directly |
| `mobile/lib/screens/consumer/scan_result_screen.dart` | 🔧 ADAPT | Keep verdict header/thumbnail/audit/_kv cards; replace FSSAI/GSTIN/authenticity cards with result, confidence, reason, ΔE and verify QR |
| `mobile/lib/screens/inspector/inspection_detail_screen.dart` | 🔧 ADAPT | Test detail + evidence card (hash); drop file-report/registry logic; add verify |
| `mobile/lib/screens/inspector/inspection_map_screen.dart` | 🔧 ADAPT | flutter_map OSM pins + directions; drop complaint layer; fix userAgentPackageName |
| `mobile/lib/screens/inspector/inspections_log_screen.dart` | 🔧 ADAPT | Test log list with filter bar |
| `mobile/lib/screens/inspector/inspector_home_screen.dart` | 🔧 ADAPT | Becomes Field Officer home (new test, log, map) |
| `mobile/lib/screens/inspector/pending_complaints_screen.dart` | 🔧 ADAPT | Template for the supervisor INCONCLUSIVE queue (or drop) |
| `mobile/lib/screens/settings_screen.dart` | 🔧 ADAPT | Server URL edit/test/reset; only the LMCS text changes |
| `mobile/lib/screens/splash_screen.dart` | 🔧 ADAPT | Session check + role routing; rebrand text |
| `mobile/lib/services/api_service.dart` | 🔧 ADAPT | Keep Dio+JWT interceptor, health, login; replace scan/complaint/violation endpoints with /tests, /verify, review |
| `mobile/lib/services/pdf_service.dart` | 🔧 ADAPT | Download+open PDF; repoint from legal notice to per-test report |
| `mobile/lib/utils/app_colors.dart` | 🔧 ADAPT | Palette reusable; rename verdict colours (compliant/actionNeeded to negative/positive/inconclusive) |
| `mobile/lib/utils/verdict.dart` | 🔧 ADAPT | Label/color/icon/pinGlyph switch; swap to 3 test outcomes |
| `mobile/lib/widgets/camera_overlay.dart` | 🔧 ADAPT | Vignette frame reusable; change hints to 'align card's 4 markers + kit window' |
| `mobile/lib/widgets/status_badge.dart` | 🔧 ADAPT | Pill badge; map to POSITIVE/NEGATIVE/INCONCLUSIVE |
| `mobile/pubspec.yaml` | 🔧 ADAPT | Rename package labelguard_mobile, drop google_mlkit_* packages; keep the rest |
| `mobile/scripts/build_and_serve.py` | 🔧 ADAPT | Build APK with dart-define, serve it and print a QR; rename LABELGUARD_API_BASE and labelguard.apk |
| `mobile/test/verdict_test.dart` | 🔧 ADAPT | Rewrite for new verdicts or drop |
| `mobile/test/widget_test.dart` | 🔧 ADAPT | Smoke test; update package import and brand text |
| `mobile/lib/models/complaint_model.dart` | ❌ DROP | Consumer complaints |
| `mobile/lib/models/compliance_model.dart` | ❌ DROP | 13-rule compliance report |
| `mobile/lib/models/extracted_fields.dart` | ❌ DROP | Label fields |
| `mobile/lib/models/inspection_model.dart` | ❌ DROP | Legacy inspection assignments |
| `mobile/lib/models/pending_complaint_model.dart` | ❌ DROP | Complaint queue |
| `mobile/lib/models/violation_models.dart` | ❌ DROP | Violation reports / Rule 6(3) |
| `mobile/lib/providers/compliance_provider.dart` | ❌ DROP | Legacy compliance/evidence upload |
| `mobile/lib/providers/inspection_provider.dart` | ❌ DROP | Legacy inspections/complaints |
| `mobile/lib/screens/consumer/consumer_home_screen.dart` | ❌ DROP | Consumer role; rights card text |
| `mobile/lib/screens/consumer/ocr_review_screen.dart` | ❌ DROP | OCR correction screen (only the submit pattern is worth copying) |
| `mobile/lib/screens/inspector/file_report_screen.dart` | ❌ DROP | Violation report filing |
| `mobile/lib/services/barcode_service.dart` | ❌ DROP | Barcode-as-ruler |
| `mobile/lib/services/field_extractor.dart` | ❌ DROP | Legal Metrology label field regex/fuzzy extraction |
| `mobile/lib/services/ocr_service.dart` | ❌ DROP | ML Kit OCR |
| `mobile/lib/utils/fuzzy_match.dart` | ❌ DROP | OCR keyword matching |
| `mobile/lib/utils/printed_elsewhere.dart` | ❌ DROP | Label second-photo logic |
| `mobile/lib/widgets/scan_flags.dart` | ❌ DROP | OCR-edit/complaint/rescan chips |
| `mobile/test/amul_scans_test.dart` | ❌ DROP | Label OCR fixtures |
| `mobile/test/barcode_source_test.dart` | ❌ DROP | Barcode |
| `mobile/test/field_extractor_test.dart` | ❌ DROP | Field extractor |
| `mobile/test/fixtures_amul_scan34.txt` | ❌ DROP | Label OCR fixture |
| `mobile/test/fixtures_amul_scan35.txt` | ❌ DROP | Label OCR fixture |
| `mobile/test/fixtures_obgob_side.txt` | ❌ DROP | Label OCR fixture |
| `mobile/test/fssai_mark_photo_test.dart` | ❌ DROP | FSSAI mark |
| `mobile/test/obgob_scan32_test.dart` | ❌ DROP | Label OCR |
| `mobile/test/printed_elsewhere_test.dart` | ❌ DROP | Label logic |
| `mobile/test/registry_report_test.dart` | ❌ DROP | Registry/violation |

**Reusable pieces:**
- lib/services/settings_service.dart SettingsService: the backend URL can be changed at runtime (a saved override, then a --dart-define value, then 10.0.2.2:8000); also has normalizeUrl() and validate()
- lib/services/api_service.dart ApiService constructor: Dio interceptor that picks the base URL on every request and adds a Bearer JWT; checkHealth() probes GET /health
- lib/services/api_service.dart submitScan(): pattern for a multipart image upload with a JSON 'context' field; reuse it for POST /tests
- lib/services/auth_service.dart AuthService: saves and reads the token and role in secure storage; also isLoggedIn and logout
- lib/providers/auth_provider.dart AuthProvider.login/checkSession/logout: calls POST /auth/login and expects access_token, role, user_id, username, full_name
- lib/services/camera_service.dart CameraService.initialize/takePicture: back camera, veryHigh resolution, JPEG
- lib/services/gps_service.dart GpsService.getCurrentPosition: asks for permission, takes a high-accuracy fix with a 5 s timeout, falls back to the last known position
- lib/services/ntp_service.dart NtpService.getNetworkTime + NtpTimeResult: gets NTP time from pool.ntp.org and computes the drift from the device clock
- lib/services/hashing_service.dart HashingService.computeFileSha256/computeBytesSha256
- lib/screens/consumer/scan_capture_screen.dart _runPipeline/_safeNtp: capture screen that shows each step's progress (keep the GPS and NTP steps)
- lib/models/scan_models.dart ScanContext.toJson: fields for GPS, device time, NTP time and drift
- lib/widgets/camera_overlay.dart CameraOverlay: darkened frame with hint labels
- lib/screens/settings_screen.dart SettingsScreen: edit and test the server URL, with the current values shown
- lib/screens/inspector/inspection_map_screen.dart: flutter_map OSM map with pins, legend, bottom sheet, and directions through url_launcher
- lib/screens/inspector/inspections_log_screen.dart + providers/inspection_log_provider.dart: log list with a filter bar and a detail loader
- lib/utils/verdict.dart Verdict + lib/utils/app_colors.dart AppColors: one central place for verdict labels, colours, icons and pin colours
- lib/utils/server_time.dart parseServerTime/parseServerTimeOr
- lib/services/pdf_service.dart PdfService: downloads a PDF, saves it to a temp folder and opens it with open_filex
- lib/screens/admin/admin_home_screen.dart: works out the web dashboard URL from the API host
- scripts/build_and_serve.py: builds the APK with the backend URL baked in, serves it on :8080 and prints a QR code for installing on the phone

## 7. Repo-level files  (REUSE 0 · ADAPT 6 · DROP 5)

| File / folder | Decision | Reason |
|---|---|---|
| `.gitignore` | 🔧 ADAPT | Mostly generic; remove Backend/labelguard.db.pre-postgres-backup, keep uploads/evidence_store/generated_reports/backups rules |
| `CLAUDE.md` | 🔧 ADAPT | Keep the 'machine-specific traps' and getting-running notes (Postgres :5433 service, adb reverse, token expiry); drop LMCS state/design notes |
| `README.md` | 🔧 ADAPT | Reuse the structure (parts table, mermaid flows, getting started, tests, limitations); rewrite all content, since it is entirely Legal Metrology |
| `docker-compose.yml` | 🔧 ADAPT | Postgres15 + uvicorn services usable; rename container/DB names labelguard-*; context ./backend casing differs from Backend/; hardcoded dev DB credential in DATABASE_URL |
| `docs/api-contract.md` | 🔧 ADAPT | Tiny stub; rewrite for the auth/tests/kit-profiles/verify endpoints and roles FIELD_OFFICER/SUPERVISOR/ADMIN |
| `docs/db-schema.md` | 🔧 ADAPT | Tiny stub; rewrite for users, tests, kit_profiles, audit chain; drop products/complaints/penalties/calibration/font tables |
| `.claude/` | ❌ DROP | Local Claude settings/worktrees |
| `.github/modernize/java-upgrade/` | ❌ DROP | Unrelated Java-upgrade tool hooks, not CI |
| `.idea/` | ❌ DROP | IDE files (gitignored) |
| `docs/presentation/LMCS_SIH26034.pptx` | ❌ DROP | Old deck (identical copy exists in Downloads); only as reference |
| `docs/presentation/build_deck.js` | ❌ DROP | LMCS deck builder (pptxgenjs); the teammates handle the presentation. Keep only as reference if wanted |

### Reference files → `docs/old_ps_reference/` (copy only, reference)

| File / folder | Decision | Reason |
|---|---|---|
| `Downloads/26034 PPT - latest(1).pdf` | ✅ REUSE | Newest 'latest' pdf (Sep 22 18:02): copy to docs/old_ps_reference/. 'PPT jerbin.pdf' is newer by date but byte-identical to the original '26034 PPT.pdf' |
| `Downloads/26034 PPT - latest.pptx` | ✅ REUSE | Newest pptx (Sep 23 12:25): copy to docs/old_ps_reference/ |
| `Downloads/LMCS - Presentation Script.pdf` | ✅ REUSE | Useful template for the new presentation script (27 KB) |
| `Downloads/LMCS - barcode ruler, barcode backup reader, registry check, scan to fields, five in one page, technical approach*, feasibility*, impact slide, before and after, key parts, violation path, tested on real packs (png/svg)` | ✅ REUSE | Archive only as old-PS reference (content is LMCS-specific: OCR/barcode/registry); could be DROPped if space or time is short |
| `Downloads/LMCS - system architecture.png/.svg, architecture (half slide), roles and workflow, roles flow (half slide), sha256 flow, system flow (plain)` | ✅ REUSE | Diagrams whose structure transfers to FieldProof (arch, roles, sealing); copy for reference and redraw |
| `Downloads/LMCS-workflow.html` | ✅ REUSE | archify end-to-end diagram (829 KB) for reference; a good pattern to regenerate for the FieldProof flow |
| `Downloads/LabelGuard_AI_Architecture_Workflow.md` | ✅ REUSE | Old architecture reference to archive |
| `Downloads/LabelGuard_AI_Final_Architecture(1).md` | ✅ REUSE | Newest/larger final architecture (24.6 KB, Sep 9 22:01): archive this one |
| `Downloads/LabelGuard_AI_Models_Report.pdf` | ✅ REUSE | Models report for reference (1 MB) |
| `Downloads/26034 PPT*.pptx/pdf (all other versions: revised*, latest.pdf, latest(1).pptx, PPT.pptx/pdf, jerbin.pdf)` | ❌ DROP | Superseded duplicates |
| `Downloads/LMCS app - working 2026-09-25 2203.apk` | ❌ DROP | 235 MB old build |
| `Downloads/LMCS-workflow.visual-check.*, LMCS_compliance_report_scan*.pdf, LMCS_violation_reports_*.csv, LMCS_SIH26034.pptx, SIH26034_Panel_Verdict_HexTech.pdf, SIH_26034_Detailed_Report.*, SIH26034_Technical_Architecture_Updated*` | ❌ DROP | Not in the requested set; generated outputs or duplicates (the panel verdict pdf may be worth reading for feedback) |
| `Downloads/LabelGuard_AI_Final_Architecture.md` | ❌ DROP | Older version of (1) |
| `Downloads/Problem Statement ID – 26034 … by scanning product image.pptx` | ✅ REUSE | Newest old deck (template of our new SIH26231 deck) |

## 8. Run facts found (for Step 2)
- Start: from Backend/ `uvicorn app.main:app --reload` (or `python scripts/lan_serve.py` for LAN, port 8000). Tables are auto-created in lifespan via Base.metadata.create_all; Alembic: `alembic upgrade head` (env.py overrides sqlalchemy.url with settings.database_url).
- Env var NAMES (.env / .env.example): DATABASE_URL, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, STORAGE_BACKEND, LOCAL_STORAGE_PATH, (GCS_BUCKET_NAME commented), NTP_SERVER, NTP_MAX_DRIFT_SECONDS, APP_NAME, APP_VERSION, DEBUG, LOG_LEVEL, CORS_ORIGINS (JSON list).
- DB: default/example DATABASE_URL is postgresql://labelguard:...@localhost:5432/labelguard_db (user labelguard, db labelguard_db). The local .env comments say Postgres 18 runs as a Windows service on port 5433, with a commented-out SQLite fallback. In docker-compose, db is postgres:15-alpine, container labelguard-db, POSTGRES_DB=labelguard_db, and the backend container labelguard-backend is on 8000.
- Roles: UserRole str enum in models/user.py: ADMIN='admin', INSPECTOR='inspector', CONSUMER='consumer', stored as String(20). The JWT carries sub=user id and role. Public /auth/register creates consumers only, and admins create officers via POST /auth/users. The Controller is the ADMIN role.
- Sealing: routers/scan.py submit_scan uses hashlib.sha256 on the raw upload and saves the file as uploads/evidence/<sha256><ext> under cwd. It uses LOCAL_STORAGE_PATH only through getattr(settings,'evidence_upload_dir'), which does not exist, so the path is effectively hardcoded. GPS, device_timestamp, ntp_timestamp and ntp_drift_seconds all come from the client JSON context. The server never queries NTP, even though ntplib is in requirements. Drift over NTP_MAX_DRIFT_SECONDS sets is_tampered. The hash re-check happens on GET /inspections/{id}/image via the X-Evidence-Sha256-Match header.
- Missing for FieldProof: no Ed25519 signing, no hash chain, no /verify endpoint, no QR in the PDF, no server-side CSV export (grep finds no csv in the backend, so the dashboard must build it client-side), no blur/glare check server-side, and no ArUco/colour correction/dE2000. services/evidence_service.py and calibration_service.py are empty stubs.
- PDF: report_service.generate_legal_notice_pdf / generate_go_notice_pdf (ReportLab platypus, A4) is served by routers/legal_notice.py and routers/violations.py (/violations/{id}/notice.pdf). It imports LegalNotice, ProductRegistry and ComplianceResult, so it cannot be copied without rewriting its imports.
- Copy hazards: main.py imports all routers (legal_notice, violations, complaints_router), and models/__init__.py plus the User relationships reference Complaint/Inspection/ViolationReport, so dropping models means pruning those relationships and imports together or mapper configuration fails. docker-compose build context is ./backend (lowercase) but the folder is Backend, which breaks on case-sensitive filesystems. The Dockerfile's libgl1-mesa-glx is not available in newer Debian slim images (use libgl1). For ArUco, opencv-python-headless 4.10 includes cv2.aruco in main modules since 4.7 (check this). tests/conftest.py is referenced in the .env comment but does not exist; each test builds its own SQLite engine. `from __future__ import annotations` with Mapped[...] forward refs is used throughout.
- Tests: `pytest` from Backend/ (in-memory SQLite, httpx TestClient); fixtures in tests/fixtures are LM label images.
- Dashboard: cd Frontend && npm install && npm run dev -> http://localhost:5173 (must be served; opening index.html as a file shows a blank page)
- Env var name: VITE_API_BASE (defaults to http://localhost:8000). The backend CORS_ORIGINS must include 5173
- sessionStorage keys 'labelguard_token' and 'labelguard_user' in api.js: rename them
- auth.jsx rejects any role != 'admin' (lowercase roles). The new roles FIELD_OFFICER/SUPERVISOR/ADMIN need that check and the casing updated, or supervisors cannot log in
- The Leaflet CSS is loaded from unpkg in index.html with an SRI hash; the map breaks offline
- The api.js endpoints /violations, /rules, /inspections/log, /inspections/{id}/image, /legal-notice/{id}/generate, /complaints/pending must be renamed in step with the backend
- Backend per CLAUDE.md: Backend/venv python -m uvicorn app.main:app --host 0.0.0.0 --port 8000; PostgreSQL runs as a Windows service on port 5433 (docker-compose uses 5432); for the phone, run adb reverse tcp:8000 tcp:8000; ACCESS_TOKEN_EXPIRE_MINUTES in Backend/.env
- docker-compose.yml: DB labelguard_db, user labelguard, containers labelguard-db/labelguard-backend; the build context ./backend is lowercase while the folder is Backend/ (matters on case-sensitive hosts); DATABASE_URL carries a hardcoded dev credential
- The Map default centre is Bengaluru [12.9716, 77.5946]
- No lint config is present, although package.json has an eslint script and eslint is not in devDependencies
- Android applicationId and namespace are both gov.in.legalmetrology.labelguard_mobile. MainActivity.kt sits at android/app/src/main/kotlin/gov/in/legalmetrology/labelguard_mobile/, so renaming the id means moving that folder and changing the package line.
- minSdk = flutter.minSdkVersion, and targetSdk and compileSdk also come from Flutter; none is overridden. Java/Kotlin target 17. ndkVersion is pinned to 28.2.13676358 only because ML Kit (google_mlkit_commons jni) needs it, so it can likely be removed once ML Kit is dropped.
- Release builds are signed with the debug keys. There is no android/key.properties and no .jks file.
- AndroidManifest has these permissions: INTERNET, ACCESS_NETWORK_STATE, CAMERA, FINE/COARSE LOCATION. It sets usesCleartextTraffic=true (needed for http LAN backend), label 'LMCS', ML Kit meta-data 'ocr,barcode' (remove it), a FileProvider (${applicationId}.fileprovider, @xml/file_paths), and a PDF VIEW entry in <queries>.
- Packages that are only for OCR/barcode and should be dropped: google_mlkit_text_recognition ^0.13.0 and google_mlkit_barcode_scanning ^0.12.0. Keep: provider, dio, flutter_secure_storage, camera, geolocator, path_provider, path, ntp, crypto, intl, flutter_map, latlong2, url_launcher, open_filex, image_picker, cupertino_icons.
- The pubspec package name labelguard_mobile appears in package: imports in the tests (test/widget_test.dart). Renaming the package means updating those imports. lib/ uses relative imports.
- Server URL resolution order: a user override saved under the secure-storage key 'api_base_url_override' from the Settings screen, then compile-time --dart-define=LABELGUARD_API_BASE=http://<lan-ip>:8000, then http://10.0.2.2:8000 (emulator). main() awaits SettingsService.load() before runApp.
- The client never calls HashingService; the SHA-256 is currently computed only on the server. For FieldProof, hash on the device and send it in the context so the server can compare.
- The map sets the userAgentPackageName string to the old id in inspection_map_screen.dart:114. Change it together with the applicationId.
- To build and install: from mobile/, run python scripts/build_and_serve.py [--lan-ip X --backend-port 8000 --serve-port 8080 --release]. It needs pip qrcode and flutter on PATH, and outputs labelguard.apk.

## 9. Risks / TODOs
- Android package id + Dart package name stay `labelguard_mobile` (renaming risks the build) → TODO after the hackathon.
- No phone connected right now (`adb devices` empty) → need a phone on USB (`adb reverse tcp:8000 tcp:8000`) or LAN APK via `build_and_serve.py` for the demo.
- Docker daemon is not running → we use the local PostgreSQL 18 service (port 5433), not docker-compose, for the demo.
- Old demo logins share a plaintext password → new seeded FieldProof users get fresh passwords (kept only in gitignored files, never in docs).
- Ed25519 is a technical signature; legal-grade DSC/eSign is future scope (said honestly on the PPT).
