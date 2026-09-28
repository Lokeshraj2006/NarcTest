"""
Escalation workflow: inspector files → admin confirms/rejects → admin issues GO notice.

Covers the sequences a nervous click can trigger live. Each must end in a
defined status code and leave no duplicate or half-applied state behind.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.security import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.evidence import EvidenceRecord
from app.models.legal_notice import LegalNotice
from app.models.rule import Rule
from app.models.rule_check import CheckStatus, RuleCheck
from app.models.user import User, UserRole
from app.models.violation import ViolationReport
from app.scripts.seed_rules import RULES
from app.services import violation_service as svc


def _plain(value):
    return value.value if isinstance(value, Enum) else value


def _seed(db) -> dict:
    for payload in RULES:
        db.add(Rule(**{k: _plain(v) for k, v in payload.items() if k != "config"}))

    def user(username: str, role: UserRole) -> User:
        u = User(
            email=f"{username}@lm.test",
            username=username,
            hashed_password="unused",
            full_name=username.replace("_", " ").title(),
            role=role.value,
            badge_number="INSP-TN-01" if role is UserRole.INSPECTOR else None,
        )
        db.add(u)
        return u

    admin = user("controller", UserRole.ADMIN)
    inspector = user("inspector_one", UserRole.INSPECTOR)
    other_inspector = user("inspector_two", UserRole.INSPECTOR)
    consumer = user("consumer_one", UserRole.CONSUMER)
    db.flush()

    evidence = EvidenceRecord(
        file_path="uploads/label.jpg",
        original_filename="label.jpg",
        file_size_bytes=1024,
        sha256_hash="ab" * 32,
        gps_latitude=10.9362,
        gps_longitude=76.7441,
        timestamp_device=datetime.now(timezone.utc),
        seller_name="Sri Murugan Stores",
        seller_address="12 Market Road, Coimbatore",
        captured_by_id=inspector.id,
        detected_fields_json=json.dumps(
            {"ocr": {"manufacturer_name": "Acme Foods Pvt Ltd",
                     "manufacturer_address": "Plot 4, SIDCO, Coimbatore"}}
        ),
    )
    db.add(evidence)
    db.flush()

    checks = [
        (1, "Manufacturer details", "MANUFACTURER_DETAILS", "Rule 6(1)(a)", CheckStatus.PASS, None),
        (5, "Retail sale price", "MRP_DECLARATION", "Rule 6(1)(e)", CheckStatus.FAIL, "MRP not declared"),
        (9, "Minimum font size", "FONT_SIZE", "Rule 7(2)", CheckStatus.REVIEW, "No barcode scale"),
    ]
    for number, name, code, ref, status, reason in checks:
        db.add(RuleCheck(
            evidence_id=evidence.id, rule_number=number, rule_name=name, rule_code=code,
            statutory_reference=ref, status=status.value, failure_reason=reason,
        ))
    db.commit()

    return {
        "admin_id": admin.id,
        "inspector_id": inspector.id,
        "evidence_id": evidence.id,
        "admin": create_access_token(subject=admin.id, role="admin"),
        "inspector": create_access_token(subject=inspector.id, role="inspector"),
        "other_inspector": create_access_token(subject=other_inspector.id, role="inspector"),
        "consumer": create_access_token(subject=consumer.id, role="consumer"),
    }


@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    # Restore rather than clear: other test modules install their own override.
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    with Session() as db:
        ids = _seed(db)
    try:
        yield SimpleNamespace(client=TestClient(app), Session=Session, **ids)
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
        Base.metadata.drop_all(engine)
        engine.dispose()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _file(env, token=None, rule_check_ids=None):
    payload = {"evidence_record_id": env.evidence_id}
    if rule_check_ids is not None:
        payload["rule_check_ids"] = rule_check_ids
    return env.client.post(
        "/violations",
        json=payload,
        headers=_auth(token or env.inspector),
    )


def _filed_id(env) -> int:
    r = _file(env)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _confirm(env, report_id, token=None, notes=None):
    return env.client.post(
        f"/violations/{report_id}/confirm",
        json={"admin_notes": notes},
        headers=_auth(token or env.admin),
    )


def _reject(env, report_id, token=None, notes=None):
    return env.client.post(
        f"/violations/{report_id}/reject",
        json={"admin_notes": notes},
        headers=_auth(token or env.admin),
    )


def _notice(env, report_id, token=None):
    return env.client.post(
        f"/violations/{report_id}/notice", headers=_auth(token or env.admin)
    )


def _report(env, report_id) -> ViolationReport:
    with env.Session() as db:
        return db.get(ViolationReport, report_id)


def _notice_count(env, report_id) -> int:
    with env.Session() as db:
        return (
            db.query(LegalNotice)
            .filter(LegalNotice.violation_report_id == report_id)
            .count()
        )


# ── Happy path ───────────────────────────────────────────────────────────


def test_full_chain_file_confirm_notice_pdf(env):
    r = _file(env)
    assert r.status_code == 201, r.text
    report = r.json()
    assert report["status"] == "pending_admin_confirmation"
    assert report["severity"] == "critical"
    assert report["shop_name"] == "Sri Murugan Stores"
    assert report["manufacturer_name"] == "Acme Foods Pvt Ltd"
    # REVIEW (rule 9) and PASS (rule 1) are never cited — only the FAIL.
    assert [c["rule_number"] for c in report["violated_rules"]] == [5]

    r = _confirm(env, report["id"], notes="Verified on site.")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"
    assert r.json()["confirmed_at"] is not None
    assert r.json()["admin_notes"] == "Verified on site."

    r = _notice(env, report["id"])
    assert r.status_code == 201, r.text
    notice = r.json()
    assert notice["notice_number"].startswith("GO-")
    assert notice["violation_report_id"] == report["id"]

    detail = env.client.get(f"/violations/{report['id']}", headers=_auth(env.admin)).json()
    assert detail["status"] == "notice_generated"
    assert detail["notice_generated"] is True
    assert detail["notice_id"] == notice["notice_id"]

    pdf = env.client.get(notice["download_url"], headers=_auth(env.admin))
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["x-notice-number"] == notice["notice_number"]
    assert pdf.content.startswith(b"%PDF")


# ── Authority split ──────────────────────────────────────────────────────


def test_inspector_cannot_confirm(env):
    report_id = _filed_id(env)
    assert _confirm(env, report_id, token=env.inspector).status_code == 403
    assert _report(env, report_id).status == "pending_admin_confirmation"


def test_inspector_cannot_reject(env):
    report_id = _filed_id(env)
    assert _reject(env, report_id, token=env.inspector).status_code == 403
    assert _report(env, report_id).status == "pending_admin_confirmation"


def test_inspector_cannot_issue_notice(env):
    report_id = _filed_id(env)
    assert _confirm(env, report_id).status_code == 200
    assert _notice(env, report_id, token=env.inspector).status_code == 403
    assert _notice_count(env, report_id) == 0
    assert _report(env, report_id).status == "confirmed"


def test_consumer_cannot_file_report(env):
    assert _file(env, token=env.consumer).status_code == 403
    with env.Session() as db:
        assert db.query(ViolationReport).count() == 0


def test_inspector_cannot_view_another_inspectors_report(env):
    report_id = _filed_id(env)
    r = env.client.get(f"/violations/{report_id}", headers=_auth(env.other_inspector))
    assert r.status_code == 403


# ── State machine: out-of-order and repeated clicks ─────────────────────


def test_notice_before_confirmation_returns_409(env):
    report_id = _filed_id(env)
    r = _notice(env, report_id)
    assert r.status_code == 409
    assert "not been confirmed" in r.json()["detail"]
    assert _notice_count(env, report_id) == 0
    assert _report(env, report_id).status == "pending_admin_confirmation"


def test_double_confirm_returns_409_and_leaves_record_unchanged(env):
    report_id = _filed_id(env)
    assert _confirm(env, report_id, notes="first").status_code == 200
    first = _report(env, report_id)

    r = _confirm(env, report_id, notes="second")
    assert r.status_code == 409

    after = _report(env, report_id)
    assert after.status == "confirmed"
    assert after.admin_notes == "first"
    assert after.confirmed_at == first.confirmed_at


def test_confirm_after_reject_is_blocked(env):
    report_id = _filed_id(env)
    assert _reject(env, report_id, notes="Label was compliant.").status_code == 200
    assert _confirm(env, report_id).status_code == 409
    after = _report(env, report_id)
    assert after.status == "rejected"
    assert after.confirmed_at is None


def test_reject_after_confirm_is_blocked(env):
    report_id = _filed_id(env)
    assert _confirm(env, report_id).status_code == 200
    assert _reject(env, report_id).status_code == 409
    after = _report(env, report_id)
    assert after.status == "confirmed"
    assert after.rejected_at is None


def test_reject_after_notice_generated_is_blocked(env):
    report_id = _filed_id(env)
    assert _confirm(env, report_id).status_code == 200
    assert _notice(env, report_id).status_code == 201
    assert _reject(env, report_id).status_code == 409
    after = _report(env, report_id)
    assert after.status == "notice_generated"
    assert after.rejected_at is None


def test_notice_on_rejected_report_returns_409(env):
    report_id = _filed_id(env)
    assert _reject(env, report_id).status_code == 200
    assert _notice(env, report_id).status_code == 409
    assert _notice_count(env, report_id) == 0


def test_repeated_notice_click_returns_the_same_notice(env):
    report_id = _filed_id(env)
    assert _confirm(env, report_id).status_code == 200

    first = _notice(env, report_id)
    second = _notice(env, report_id)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["notice_id"] == first.json()["notice_id"]
    assert second.json()["notice_number"] == first.json()["notice_number"]
    assert _notice_count(env, report_id) == 1


def test_second_report_on_same_scan_returns_400(env):
    assert _file(env).status_code == 201
    r = _file(env)
    assert r.status_code == 400
    assert "already open" in r.json()["detail"]
    with env.Session() as db:
        assert db.query(ViolationReport).count() == 1


def test_notice_pdf_before_notice_is_issued_returns_404(env):
    report_id = _filed_id(env)
    assert _confirm(env, report_id).status_code == 200
    r = env.client.get(f"/violations/{report_id}/notice.pdf", headers=_auth(env.admin))
    assert r.status_code == 404


# ── What a report may cite ───────────────────────────────────────────────


def _check_id(env, rule_number: int) -> int:
    with env.Session() as db:
        return (
            db.query(RuleCheck.id)
            .filter(
                RuleCheck.evidence_id == env.evidence_id,
                RuleCheck.rule_number == rule_number,
            )
            .scalar()
        )


def _add_net_quantity_fail(env, evidence_id: int) -> int:
    """A second FAIL (rule 4), on this scan or another one."""
    with env.Session() as db:
        check = RuleCheck(
            evidence_id=evidence_id, rule_number=4, rule_name="Net quantity",
            rule_code="NET_QUANTITY", statutory_reference="Rule 6(1)(c)",
            status=CheckStatus.FAIL.value, failure_reason="Net quantity not declared",
        )
        db.add(check)
        db.commit()
        return check.id


def _add_other_scan(env) -> int:
    with env.Session() as db:
        evidence = EvidenceRecord(
            file_path="uploads/other_label.jpg",
            original_filename="other_label.jpg",
            file_size_bytes=2048,
            sha256_hash="cd" * 32,
            gps_latitude=11.0168,
            gps_longitude=76.9558,
            timestamp_device=datetime.now(timezone.utc),
            seller_name="Lakshmi Traders",
            seller_address="3 Cross Cut Road, Coimbatore",
            captured_by_id=env.inspector_id,
            detected_fields_json=json.dumps({"ocr": {}}),
        )
        db.add(evidence)
        db.commit()
        return evidence.id


def _report_count(env) -> int:
    with env.Session() as db:
        return db.query(ViolationReport).count()


@pytest.mark.parametrize("rule_number,status", [(9, "REVIEW"), (1, "PASS")])
def test_citing_a_check_that_did_not_fail_is_refused(env, rule_number, status):
    not_failed = _check_id(env, rule_number)
    # Sent alongside the scan's real FAIL, so the bad id can't ride along on it.
    r = _file(env, rule_check_ids=[_check_id(env, 5), not_failed])
    assert r.status_code == 400, r.text
    assert f"#{not_failed} (rule {rule_number}) is {status}" in r.json()["detail"]
    assert _report_count(env) == 0


def test_citing_another_scans_failed_check_is_refused(env):
    foreign = _add_net_quantity_fail(env, _add_other_scan(env))
    r = _file(env, rule_check_ids=[foreign])
    assert r.status_code == 400, r.text
    assert f"#{foreign} is not a check on this scan" in r.json()["detail"]
    assert _report_count(env) == 0


def test_citing_a_subset_of_failed_checks_cites_only_that_subset(env):
    net_quantity = _add_net_quantity_fail(env, env.evidence_id)
    r = _file(env, rule_check_ids=[net_quantity])
    assert r.status_code == 201, r.text
    assert [c["rule_number"] for c in r.json()["violated_rules"]] == [4]


@pytest.mark.parametrize("rule_check_ids", [None, []], ids=["omitted", "empty-list"])
def test_no_ids_cites_every_failed_check(env, rule_check_ids):
    _add_net_quantity_fail(env, env.evidence_id)
    r = _file(env, rule_check_ids=rule_check_ids)
    assert r.status_code == 201, r.text
    assert [c["rule_number"] for c in r.json()["violated_rules"]] == [4, 5]


# ── Citing a registry mismatch (Rule 6(3)) ───────────────────────────────

_HIGHER_MRP = {"field": "mrp", "expected": "109.0", "detected": "129.0",
               "note": "Higher than the registered MRP."}


def _add_registry_scan(env, status="tampered_suspected", mismatches=(_HIGHER_MRP,),
                       with_fail=False) -> int:
    """A scan whose stored registry cross-check has the given verdict."""
    with env.Session() as db:
        evidence = EvidenceRecord(
            file_path="uploads/tampered.jpg",
            original_filename="tampered.jpg",
            file_size_bytes=4096,
            sha256_hash="ef" * 32,
            gps_latitude=10.9362,
            gps_longitude=76.7441,
            timestamp_device=datetime.now(timezone.utc),
            seller_name="Sri Murugan Stores",
            seller_address="12 Market Road, Coimbatore",
            captured_by_id=env.inspector_id,
            detected_fields_json=json.dumps({
                "ocr": {"manufacturer_name": "Acme Foods Pvt Ltd"},
                "authenticity": {"status": status, "mismatches": list(mismatches)},
            }),
        )
        db.add(evidence)
        db.flush()
        db.add(RuleCheck(
            evidence_id=evidence.id, rule_number=4, rule_name="Net quantity",
            rule_code="NET_QUANTITY", statutory_reference="Rule 6(1)(c)",
            status=(CheckStatus.FAIL if with_fail else CheckStatus.PASS).value,
            failure_reason="Net quantity not declared" if with_fail else None,
        ))
        db.commit()
        return evidence.id


def _file_registry(env, evidence_id, pack_checked=True, cite_registry=True):
    return env.client.post(
        "/violations",
        json={"evidence_record_id": evidence_id, "cite_registry": cite_registry,
              "pack_checked": pack_checked},
        headers=_auth(env.inspector),
    )


def test_registry_mismatch_needs_the_inspector_to_check_the_pack(env):
    r = _file_registry(env, _add_registry_scan(env), pack_checked=False)
    assert r.status_code == 400, r.text
    assert "checked the pack yourself" in r.json()["detail"]
    assert _report_count(env) == 0


def test_tampering_flag_alone_is_not_a_report(env):
    # Without the inspector's citation, a scan with no FAILs has nothing to report.
    r = _file_registry(env, _add_registry_scan(env), cite_registry=False)
    assert r.status_code == 400, r.text
    assert "nothing to report" in r.json()["detail"]
    assert _report_count(env) == 0


def test_higher_mrp_checked_on_the_pack_cites_rule_6_3_through_to_the_notice(env):
    r = _file_registry(env, _add_registry_scan(env))
    assert r.status_code == 201, r.text
    report = r.json()
    assert report["severity"] == "major"
    [ground] = report["violated_rules"]
    assert ground["rule_number"] is None
    assert ground["source"] == "registry"
    assert ground["statutory_reference"].startswith("Rule 6(3)")
    assert ground["detected_value"] == "129.0"
    assert ground["required_value"] == "109.0 (registered)"
    assert "Registry (MRP differs from the registered product)" in report["violation_summary"]

    # The Controller still confirms before any notice.
    assert _notice(env, report["id"]).status_code == 409
    assert _confirm(env, report["id"]).status_code == 200
    notice = _notice(env, report["id"])
    assert notice.status_code == 201, notice.text
    with env.Session() as db:
        stored = db.get(LegalNotice, notice.json()["notice_id"])
        assert "(Registry) MRP differs from the registered product" in stored.notice_body
        assert "Rule 6(3)" in stored.statutory_clauses_cited

    pdf = env.client.get(notice.json()["download_url"], headers=_auth(env.admin))
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")


def test_registry_ground_is_cited_alongside_failed_checks(env):
    r = _file_registry(env, _add_registry_scan(env, with_fail=True))
    assert r.status_code == 201, r.text
    cited = r.json()["violated_rules"]
    assert [(c["rule_number"], c["source"]) for c in cited] == [(4, "rule"), (None, "registry")]


@pytest.mark.parametrize(
    "status,mismatches",
    [
        # A lower MRP is a divergence, never tampering (Rule 6(3) allows the sticker).
        ("authentic", ()),
        ("unverified", ()),
        # Mismatches outside Legal Metrology declarations can't be cited here.
        ("tampered_suspected", ({"field": "fssai_license_number", "expected": "1" * 14,
                                 "detected": "2" * 14},)),
        # Scans stored before the MRP direction was checked (#43) still carry a
        # lower MRP as tampering; it is allowed, so it isn't citable either.
        ("tampered_suspected", ({"field": "mrp", "expected": "109.0", "detected": "9.31"},)),
    ],
    ids=["authentic", "unverified", "fssai-only", "stored-lower-mrp"],
)
def test_nothing_citable_in_the_registry_is_refused(env, status, mismatches):
    r = _file_registry(env, _add_registry_scan(env, status=status, mismatches=mismatches))
    assert r.status_code == 400, r.text
    assert "no registry mismatch that can be cited" in r.json()["detail"]
    assert _report_count(env) == 0


# ── Auth and missing records ─────────────────────────────────────────────

_REPORT_ENDPOINTS = [
    ("post", "/violations/{id}/confirm"),
    ("post", "/violations/{id}/reject"),
    ("post", "/violations/{id}/notice"),
    ("get", "/violations/{id}"),
    ("get", "/violations/{id}/notice.pdf"),
]


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer not-a-real-token"}],
    ids=["no-token", "bad-token"],
)
@pytest.mark.parametrize(
    "method,path",
    _REPORT_ENDPOINTS + [("get", "/violations"), ("post", "/violations")],
)
def test_unauthenticated_requests_return_401(env, method, path, headers):
    report_id = _filed_id(env)
    kwargs = {"headers": headers}
    if method == "post":
        kwargs["json"] = {"evidence_record_id": env.evidence_id}
    r = getattr(env.client, method)(path.format(id=report_id), **kwargs)
    assert r.status_code == 401, r.text


@pytest.mark.parametrize("method,path", _REPORT_ENDPOINTS)
def test_unknown_report_returns_404(env, method, path):
    kwargs = {"headers": _auth(env.admin)}
    if method == "post":
        kwargs["json"] = {}
    r = getattr(env.client, method)(path.format(id=99999), **kwargs)
    assert r.status_code == 404, r.text
    assert "not found" in r.json()["detail"]


# ── Real concurrency (PostgreSQL only) ───────────────────────────────────


@pytest.fixture()
def pg_sessions():
    url = settings.database_url
    if not url.startswith("postgresql"):
        pytest.skip("needs PostgreSQL — SQLite serialises writers, so it cannot race")

    schema = f"lg_pytest_{uuid.uuid4().hex[:8]}"
    admin_engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    except OperationalError as exc:
        admin_engine.dispose()
        pytest.skip(f"PostgreSQL unreachable: {exc.orig}")

    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        yield sessionmaker(bind=engine, autoflush=False)
    finally:
        engine.dispose()
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def test_simultaneous_notice_clicks_issue_exactly_one_notice(pg_sessions, monkeypatch):
    Session = pg_sessions
    with Session() as db:
        ids = _seed(db)
        report = svc.create_report(db, db.get(User, ids["inspector_id"]), ids["evidence_id"])
        svc.confirm_report(db, db.get(User, ids["admin_id"]), report)
        db.commit()
        report_id, admin_id = report.id, ids["admin_id"]

    # Widen the gap between "is there a notice yet?" and the insert so both
    # requests land inside it, as a double-click does.
    original_number = svc._notice_number

    def slow_number():
        time.sleep(0.5)
        return original_number()

    monkeypatch.setattr(svc, "_notice_number", slow_number)

    barrier = threading.Barrier(2)
    issued, errors = [], []

    def click():
        with Session() as db:
            report = db.get(ViolationReport, report_id)
            admin = db.get(User, admin_id)
            barrier.wait()
            try:
                notice = svc.issue_notice(db, admin, report)
                db.commit()
                issued.append(notice.notice_number)
            except Exception as exc:  # noqa: BLE001 — surfaced by the assert below
                db.rollback()
                errors.append(exc)

    threads = [threading.Thread(target=click) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    with Session() as db:
        stored = [
            n.notice_number
            for n in db.query(LegalNotice).filter(LegalNotice.violation_report_id == report_id)
        ]
        final_status = db.get(ViolationReport, report_id).status

    assert errors == []
    assert len(stored) == 1, f"duplicate notices issued: {stored}"
    assert issued == stored * 2
    assert final_status == "notice_generated"
