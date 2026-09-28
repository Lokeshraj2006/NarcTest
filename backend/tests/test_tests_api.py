"""POST /tests, list, detail, image, PDF, CSV, kits and reviews (fake colour engine)."""

import hashlib
import json

import cv2
import numpy as np

from tests.conftest import auth, make_user


def _jpeg() -> bytes:
    img = np.full((120, 200, 3), (120, 45, 98), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def submit(client, headers, kit_id, image=None, **extra):
    image = image or _jpeg()
    ctx = {
        "kit_id": kit_id, "latitude": 12.97, "longitude": 77.59, "gps_accuracy_m": 8.0,
        "gps_is_mock": False, "device_id": "android-uuid",
        "device_time": "2026-09-28T11:40:00+05:30",
        "client_sha256": hashlib.sha256(image).hexdigest(), "lab_sample_id": None, "notes": None,
        **extra,
    }
    return client.post(
        "/tests", headers=headers,
        files={"image": ("photo.jpg", image, "image/jpeg")},
        data={"context": json.dumps(ctx)},
    )


def test_submit_list_detail_pdf_csv(client, fake_engine, kit_id):
    make_user("officer1", "field_officer")
    make_user("officer2", "field_officer")
    make_user("supervisor1", "supervisor")
    ho, ho2, hs = auth(client, "officer1"), auth(client, "officer2"), auth(client, "supervisor1")

    # kits
    kits = client.get("/kits", headers=ho).json()
    assert {k["code"] for k in kits} == {"DEMO-MARQUIS-SIM", "DEMO-IODINE"}
    assert all(len(o["lab"]) == 3 for k in kits for o in k["outcomes"])

    image = _jpeg()
    res = submit(client, ho, kit_id, image=image)
    assert res.status_code == 201, res.text
    rec = res.json()
    assert rec["result"] == "POSITIVE"
    assert rec["confidence"] == 91
    assert rec["image_sha256"] == hashlib.sha256(image).hexdigest()
    assert rec["client_hash_match"] is True
    assert rec["prev_record_hash"] == "GENESIS"
    assert len(rec["record_hash"]) == 64 and rec["signature"]
    assert rec["key_id"] == "ed25519-1"
    assert rec["time_source"] == "server_clock"
    assert rec["review_status"] == "NOT_NEEDED"
    assert rec["verify_url"].endswith(f"/v/{rec['id']}")
    assert rec["officer_name"] == "User officer1"
    assert rec["kit_outcomes"][0]["label"] == "Opium-type drug (purple)"

    # second test from another officer, inconclusive
    fake_engine["result"] = {"result": "INCONCLUSIVE", "outcome_label": None, "confidence": None,
                             "reason": "Colour card not found", "measured_lab": None,
                             "measured_rgb": None, "delta_e_by_outcome": {}, "quality": {}}
    rec2 = submit(client, ho2, kit_id).json()
    assert rec2["prev_record_hash"] == rec["record_hash"]
    assert rec2["review_status"] == "PENDING"

    # list: officer sees only own; supervisor sees all, newest first
    assert [t["id"] for t in client.get("/tests", headers=ho).json()] == [rec["id"]]
    assert [t["id"] for t in client.get("/tests", headers=hs).json()] == [rec2["id"], rec["id"]]
    assert [t["id"] for t in client.get("/tests?result=POSITIVE", headers=hs).json()] == [rec["id"]]
    assert [t["id"] for t in client.get("/tests?q=officer2", headers=hs).json()] == [rec2["id"]]

    # detail + access control
    assert client.get(f"/tests/{rec['id']}", headers=ho).status_code == 200
    assert client.get(f"/tests/{rec['id']}", headers=ho2).status_code == 403
    assert client.get("/tests/999", headers=hs).status_code == 404

    # image
    img = client.get(f"/tests/{rec['id']}/image", headers=ho)
    assert img.status_code == 200
    assert img.content == image
    assert img.headers["x-evidence-sha256-match"] == "true"

    # pdf
    pdf = client.get(f"/tests/{rec['id']}/pdf", headers=ho)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    # csv (staff only)
    assert client.get("/tests/export.csv", headers=ho).status_code == 403
    csv_res = client.get("/tests/export.csv", headers=hs)
    assert csv_res.status_code == 200
    text = csv_res.content.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("id,test_uid")
    assert len(text.strip().splitlines()) == 3

    # review flow
    pending = client.get("/reviews/pending", headers=hs).json()
    assert [t["id"] for t in pending] == [rec2["id"]]
    assert client.post(f"/tests/{rec2['id']}/review", headers=ho,
                       json={"decision": "RETEST", "note": "x"}).status_code == 403
    r = client.post(f"/tests/{rec2['id']}/review", headers=hs,
                    json={"decision": "RETEST", "note": "Card was not in photo"})
    assert r.status_code == 201 and r.json()["review_status"] == "RETEST"
    assert client.get("/reviews/pending", headers=hs).json() == []
    assert client.get(f"/tests/{rec2['id']}", headers=hs).json()["review_status"] == "RETEST"


def test_engine_crash_gives_inconclusive(client, fake_engine, kit_id, monkeypatch):
    import app.services as services_pkg

    def boom(image_bytes, profile):
        raise RuntimeError("bad image")

    monkeypatch.setattr(services_pkg.colour_engine, "classify", boom)
    make_user("officer1", "field_officer")
    rec = submit(client, auth(client, "officer1"), kit_id).json()
    assert rec["result"] == "INCONCLUSIVE"
    assert rec["reason"]


def test_kit_admin_endpoints(client, fake_engine, kit_id):
    make_user("admin1", "admin")
    make_user("officer1", "field_officer")
    ha, ho = auth(client, "admin1"), auth(client, "officer1")
    body = {"code": "NEW-KIT", "name": "New kit", "reagent": "x", "read_time_s": 5,
            "outcomes": [{"label": "Blue", "category": "POSITIVE", "srgb": [0, 0, 255]},
                         {"label": "Clear", "category": "NEGATIVE", "srgb": [250, 250, 250]}],
            "max_delta_e": 12, "min_margin": 3}
    assert client.post("/kits", json=body, headers=ho).status_code == 403
    created = client.post("/kits", json=body, headers=ha)
    assert created.status_code == 201
    k = created.json()
    assert k["version"] == 1 and len(k["outcomes"][0]["lab"]) == 3
    upd = client.put(f"/kits/{k['id']}", json={"name": "Renamed"}, headers=ha).json()
    assert upd["name"] == "Renamed" and upd["version"] == 2
    off = client.patch(f"/kits/{k['id']}/active", json={"is_active": False}, headers=ha).json()
    assert off["is_active"] is False
    assert k["id"] not in [x["id"] for x in client.get("/kits", headers=ho).json()]
    assert k["id"] in [x["id"] for x in client.get("/kits/all", headers=ha).json()]
    assert client.get("/kits/all", headers=ho).status_code == 403
    # inactive kit cannot be used
    assert submit(client, ho, k["id"]).status_code == 404
