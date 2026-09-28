"""Tamper checks for /verify/{id} and /v/{id}."""

from app.models.test_record import TestRecord
from app.services import record_service

from tests.conftest import auth, make_user
from tests.test_tests_api import submit


def _two_records(client, kit_id):
    make_user("officer1", "field_officer")
    h = auth(client, "officer1")
    r1 = submit(client, h, kit_id).json()
    r2 = submit(client, h, kit_id).json()
    return r1, r2


def test_fresh_records_verify_and_chain(client, fake_engine, kit_id):
    r1, r2 = _two_records(client, kit_id)
    for r in (r1, r2):
        v = client.get(f"/verify/{r['id']}").json()  # public, no token
        assert v["ok"] is True, v
        assert all(v["checks"].values())
        assert v["record"]["record_hash"] == r["record_hash"]
    assert r2["prev_record_hash"] == r1["record_hash"]
    page = client.get(f"/v/{r1['id']}")
    assert page.status_code == 200
    assert "Record is genuine" in page.text
    assert client.get("/verify/999").status_code == 404
    key = client.get("/verify/pubkey").json()
    assert key["key_id"] == "ed25519-1" and "BEGIN PUBLIC KEY" in key["public_key_pem"]


def test_changed_photo_byte_is_caught(client, fake_engine, kit_id, db):
    r1, _ = _two_records(client, kit_id)
    test = db.get(TestRecord, r1["id"])
    path = record_service.image_file(test)
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0x01
    path.write_bytes(bytes(data))

    v = client.get(f"/verify/{r1['id']}").json()
    assert v["checks"]["image_hash"] is False
    assert v["ok"] is False
    assert client.get(f"/tests/{r1['id']}/image",
                      headers=auth(client, "officer1")).headers["x-evidence-sha256-match"] == "false"
    page = client.get(f"/v/{r1['id']}")
    assert "TAMPERED" in page.text


def test_changed_result_column_is_caught(client, fake_engine, kit_id, db):
    r1, r2 = _two_records(client, kit_id)
    test = db.get(TestRecord, r1["id"])
    test.result = "NEGATIVE"
    db.commit()

    v = client.get(f"/verify/{r1['id']}").json()
    assert v["checks"]["fields_match"] is False
    assert v["checks"]["signature"] is True  # payload itself untouched
    assert v["ok"] is False
    # the other record is still fine and its chain link still holds
    v2 = client.get(f"/verify/{r2['id']}").json()
    assert v2["ok"] is True and v2["checks"]["chain"] is True


def test_changed_signed_payload_breaks_hash_and_signature(client, fake_engine, kit_id, db):
    r1, _ = _two_records(client, kit_id)
    test = db.get(TestRecord, r1["id"])
    test.signed_payload = test.signed_payload.replace('"POSITIVE"', '"NEGATIVE"')
    db.commit()
    v = client.get(f"/verify/{r1['id']}").json()
    assert v["checks"]["record_hash"] is False
    assert v["checks"]["signature"] is False
    assert v["ok"] is False
