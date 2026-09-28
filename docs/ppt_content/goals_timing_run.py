# Measures server-side time of a full POST /tests (save + real colour engine + real trusted time
# + SHA-256 + Ed25519 sign + hash chain + DB commit) and GET /verify/{id}.
# Uses a TEMPORARY in-memory SQLite DB and temp keys/uploads dirs (same idea as backend/tests/conftest.py).
# It never touches the live Postgres DB, the live keys/uploads folders, or the server on :8000.
# Run from backend/:  ./venv/Scripts/python.exe -B ../docs/ppt_content/goals_timing_run.py
import os, sys, json, time, hashlib, statistics, tempfile, platform
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"          # force: never build a Postgres engine
sys.dont_write_bytecode = True
ROOT = Path(r"C:\Users\LOKESHRAJ M\SIH26231")
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings
TMP = tempfile.mkdtemp(prefix="fieldproof_timing_")
settings.keys_dir = f"{TMP}/keys"
settings.uploads_dir = f"{TMP}/uploads"
settings.public_base_url = None

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import app.models  # noqa
from app.core.security import get_password_hash
from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.kit_profile import KitProfile
from app.services.kit_service import seed_demo_kits
from app.services import time_service, colour_engine

assert settings.database_url == "sqlite://"
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
Base.metadata.create_all(bind=engine)
s = Session()
seed_demo_kits(s)
s.add(User(email="timer@example.com", username="timer", full_name="Timer",
           hashed_password=get_password_hash("Password123!"), role="field_officer"))
s.commit()
KITS = {k.code: k.id for k in s.query(KitProfile).all()}
s.close()

# Timing wrappers around the REAL functions (behaviour unchanged, only timed).
last = {}
_real_time, _real_classify = time_service.get_trusted_time, colour_engine.classify
def timed_time(*a, **k):
    t0 = time.perf_counter(); r = _real_time(*a, **k); last["time_ms"] = (time.perf_counter() - t0) * 1000; return r
def timed_classify(*a, **k):
    t0 = time.perf_counter(); r = _real_classify(*a, **k); last["classify_ms"] = (time.perf_counter() - t0) * 1000; return r
time_service.get_trusted_time = timed_time
colour_engine.classify = timed_classify

client = TestClient(app)  # no "with": lifespan (live DB init) does NOT run
tok = client.post("/auth/login", json={"username_or_email": "timer", "password": "Password123!"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
recs = json.loads((ROOT / "docs/ppt_content/real_tests/records.json").read_text())

def post(img: bytes, kit_code: str):
    ctx = {"kit_id": KITS[kit_code], "latitude": 12.97, "longitude": 77.59, "gps_accuracy_m": 8.0,
           "gps_is_mock": False, "device_id": "timing-run", "device_time": "2026-09-28T12:00:00+05:30",
           "client_sha256": hashlib.sha256(img).hexdigest()}
    last.clear()
    t0 = time.perf_counter()
    r = client.post("/tests", headers=H, files={"image": ("photo.jpg", img, "image/jpeg")},
                    data={"context": json.dumps(ctx)})
    ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 201, r.text
    return r.json(), ms, dict(last)

# warm-up (first key creation, imports) - reported but not counted
first = recs[0]
w, w_ms, w_parts = post((ROOT / "docs/ppt_content/real_tests" / first["image_file"]).read_bytes(), first["kit_code"])

rows = []
for rec in recs:
    img = (ROOT / "docs/ppt_content/real_tests" / rec["image_file"]).read_bytes()
    for run in range(3):
        j, ms, parts = post(img, rec["kit_code"])
        v_ms = []
        for _ in range(3):
            t0 = time.perf_counter(); v = client.get(f"/verify/{j['id']}"); v_ms.append((time.perf_counter() - t0) * 1000)
            assert v.status_code == 200 and v.json()["ok"] is True, v.text
        rows.append({"photo": rec["image_file"], "bytes": len(img), "run": run + 1, "id": j["id"],
                     "result": j["result"], "confidence": j["confidence"], "time_source": j["time_source"],
                     "post_ms": round(ms, 1), "classify_ms": round(parts.get("classify_ms", 0), 1),
                     "trusted_time_ms": round(parts.get("time_ms", 0), 1),
                     "rest_ms": round(ms - parts.get("classify_ms", 0) - parts.get("time_ms", 0), 1),
                     "verify_ms_median": round(statistics.median(v_ms), 1)})

def stat(key):
    xs = [r[key] for r in rows]
    return {"median": round(statistics.median(xs), 1), "min": round(min(xs), 1), "max": round(max(xs), 1)}

chain_ok = all(client.get(f"/verify/{r['id']}").json()["ok"] for r in rows)
out = {
    "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "machine": f"{platform.processor()} / Python {platform.python_version()}",
    "setup": "FastAPI TestClient, in-memory SQLite, temp keys/uploads, REAL colour engine, REAL time_service",
    "n_posts": len(rows),
    "warmup": {"post_ms": round(w_ms, 1), **{k: round(v, 1) for k, v in w_parts.items()}, "time_source": w["time_source"]},
    "post_ms": stat("post_ms"), "classify_ms": stat("classify_ms"),
    "trusted_time_ms": stat("trusted_time_ms"), "rest_ms": stat("rest_ms"),
    "verify_ms": stat("verify_ms_median"),
    "time_sources": sorted({r["time_source"] for r in rows}),
    "all_verify_ok_after_run": chain_ok,
    "rows": rows,
}
(ROOT / "docs/ppt_content/goals_timing.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
for r in rows:
    print(r["photo"], r["run"], r["result"], r["confidence"], r["time_source"], r["post_ms"], r["classify_ms"], r["trusted_time_ms"], r["rest_ms"], r["verify_ms_median"])
