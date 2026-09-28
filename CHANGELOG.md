# CHANGELOG — FieldProof (SIH26231)

## 2026-09-28

### Step 1 — Inventory & plan
- Read-only inventory of the old SIH26034 project (`C:\Users\LOKESHRAJ M\SIH`) and `Downloads`; `Documents` had no matches.
- `MIGRATION_PLAN.md`: file-by-file REUSE / ADAPT / DROP table, copy rules, planned folder tree.

### Step 2 — Copy, rebrand, first run
- Copied `Backend → backend`, `Frontend → dashboard`, `mobile → mobile` (excluded venv, node_modules, build dirs, old uploads 50 MB, backups 20 MB, label fixtures, SQLite backup, 235 MB APK).
- Old PS reference files → `docs/old_ps_reference/` (old decks, architecture notes, diagrams, script).
- Rebranded LMCS / LabelGuard / SIH26034 → FieldProof / SIH26231 in 93 files (UI text, titles, API title, DB name, storage keys). **Not renamed (TODO):** Android `applicationId` / Kotlin package / Dart package `labelguard_mobile`.
- `.env` copied (DB name + APP_NAME changed only), gitignored with keys, uploads, venv, local DB.
- New backend venv (Python 3.11.15, OpenCV 4.10 with ArUco).
- Database: the Postgres app login cannot create databases, so `create_fieldproof_db.bat` (run once by the user with the postgres password) created **`fieldproof_db`** on PostgreSQL 18 (port 5433). `backend/.env` now points to it; SQLite is kept only as a commented offline fallback.
- `git init` + first commit. Start checks: backend `/health` ✅, dashboard `vite build` ✅, Flutter debug APK ✅ (Gradle needs a short TEMP dir + running outside the tool sandbox).
- `docs/CONTRACT.md`: shared API / record / colour-engine / screen contract for the prototype.

### Step 3 — Basic prototype (in progress)
- Colour engine + printable reference card + simulated swatch cards + synthetic test images.
- Backend: kit profiles, test records, Ed25519 signing + hash chain, `/verify`, PDF with QR, CSV, reviews. Old Legal Metrology modules removed from the new copy.
- Flutter: login → pick kit → camera with card guide + timer → result → my tests. ML Kit removed.
- Dashboard: test log, map, kit editor, review queue, public verify page.
