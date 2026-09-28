# Re-runs the colour engine on demo/test_images (37) and docs/ppt_content/real_tests (6).
# Run from backend/:  ./venv/Scripts/python.exe -B ../docs/ppt_content/validation_run.py
import json, sys, time, statistics, platform
from pathlib import Path
ROOT = Path(r"C:\Users\LOKESHRAJ M\SIH26231")
sys.path.insert(0, str(ROOT / "backend"))
sys.dont_write_bytecode = True
from app.services import colour_engine as ce
from app.services.kit_service import DEMO_KITS, with_lab

profiles = {k["code"]: {**k, "outcomes": with_lab(k["outcomes"])} for k in DEMO_KITS}

def run(path, prof, reps=3):
    b = Path(path).read_bytes()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter(); r = ce.classify(b, prof); ts.append((time.perf_counter() - t0) * 1000)
    return r, statistics.median(ts)

# warm-up
man = json.loads((ROOT / "demo/test_images/manifest.json").read_text())
ce.classify((ROOT / "demo/test_images" / man[0]["file"]).read_bytes(), profiles[man[0]["kit"]])

syn = []
for e in man:
    r, ms = run(ROOT / "demo/test_images" / e["file"], profiles[e["kit"]])
    ok = r["result"] == e["expected"] and (e["expected_label"] is None or r["outcome_label"] == e["expected_label"])
    syn.append({**e, "got": r["result"], "got_label": r["outcome_label"], "confidence": r["confidence"],
                "reason": r["reason"], "ms": round(ms, 1), "correct": ok,
                "delta_e": r["delta_e_by_outcome"], "quality": r["quality"]})
    print(f'{e["file"]:34s} {e["kind"]:9s} {e["lighting"]:9s} exp={e["expected"]:12s} got={r["result"]:12s} {str(r["outcome_label"])[:22]:22s} {ms:6.1f}ms {"OK" if ok else "WRONG"}  {r["reason"] or ""}')

truth = {7: ("Opium-type drug (purple)", "phone screen (2 cards in frame)"),
         8: ("Opium-type drug (purple)", "phone screen"),
         9: ("Amphetamine-type drug (orange)", "laptop screen"),
         10: ("Amphetamine-type drug (orange)", "laptop screen"),
         11: ("Opium-type drug (purple)", "laptop screen"),
         12: ("Opium-type drug (purple)", "laptop screen")}
recs = {r["id"]: r for r in json.loads((ROOT / "docs/ppt_content/real_tests/records.json").read_text(encoding="utf-8"))}
real = []
for i, (lab, screen) in truth.items():
    r, ms = run(ROOT / f"docs/ppt_content/real_tests/test_{i}.jpg", profiles["DEMO-MARQUIS-SIM"])
    rec = recs[i]
    def verdict(res, lbl):
        if res == "INCONCLUSIVE": return "not_sure"
        return "correct" if lbl == lab else "wrong"
    real.append({"id": i, "file": f"test_{i}.jpg", "truth": lab, "shown_on": screen,
                 "live_result": rec["result"], "live_label": rec["outcome_label"], "live_conf": rec["confidence"],
                 "live_reason": rec["reason"], "live_verdict": verdict(rec["result"], rec["outcome_label"]),
                 "rerun_result": r["result"], "rerun_label": r["outcome_label"], "rerun_conf": r["confidence"],
                 "rerun_reason": r["reason"], "rerun_verdict": verdict(r["result"], r["outcome_label"]),
                 "rerun_ms": round(ms, 1), "rerun_quality": r["quality"], "rerun_delta_e": r["delta_e_by_outcome"]})
    print(i, lab, "| live:", rec["result"], rec["outcome_label"], rec["reason"], "| rerun:", r["result"], r["outcome_label"], r["confidence"], r["reason"], r["quality"], f"{ms:.0f}ms")

out = {"synthetic": syn, "real": real, "thresholds": ce.THRESHOLDS,
       "machine": platform.processor() or platform.machine(), "python": platform.python_version()}
(ROOT / "docs/ppt_content/validation_results.json").write_text(json.dumps(out, indent=1))
