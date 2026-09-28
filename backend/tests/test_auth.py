"""Auth + roles (field_officer / supervisor / admin)."""

import hashlib

import pytest
from fastapi import Depends

from app.core.dependencies import require_admin, require_supervisor_or_admin
from app.core.security import (
    compute_sha256,
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from app.main import app
from app.models.user import User, UserRole

from tests.conftest import auth, make_user


def test_roles_are_lowercase():
    assert {r.value for r in UserRole} == {"field_officer", "supervisor", "admin"}


def test_password_hashing():
    hashed = get_password_hash("FieldProof2026!")
    assert hashed != "FieldProof2026!"
    assert verify_password("FieldProof2026!", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_round_trip():
    payload = decode_access_token(create_access_token(subject=42, role="field_officer"))
    assert payload["sub"] == "42" and payload["role"] == "field_officer"


def test_sha256():
    assert compute_sha256(b"x") == hashlib.sha256(b"x").hexdigest()


NEW_USER = {
    "email": "officer.kumar@example.com",
    "username": "officer_kumar",
    "full_name": "Suresh Kumar",
    "password": "SecurePassword123!",
    "role": "field_officer",
}


@pytest.mark.parametrize("role", ["field_officer", "supervisor", "admin"])
def test_public_sign_up_is_closed(client, role):
    res = client.post("/auth/register", json={**NEW_USER, "role": role})
    assert res.status_code == 403


def test_only_admin_creates_accounts(client):
    make_user("chief", "admin")
    make_user("sup", "supervisor")
    denied = client.post("/auth/users", json=NEW_USER, headers=auth(client, "sup"))
    assert denied.status_code == 403
    res = client.post("/auth/users", json=NEW_USER, headers=auth(client, "chief"))
    assert res.status_code == 201
    assert res.json()["role"] == "field_officer"
    assert "hashed_password" not in res.json()
    dup = client.post("/auth/users", json=NEW_USER, headers=auth(client, "chief"))
    assert dup.status_code == 400


def test_login_and_me(client):
    make_user("officer1", "field_officer")
    res = client.post("/auth/login", json={"username_or_email": "officer1", "password": "Password123!"})
    assert res.status_code == 200
    body = res.json()
    assert body["role"] == "field_officer"
    assert {"access_token", "token_type", "user_id", "username", "full_name"} <= set(body)
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["username"] == "officer1"
    bad = client.post("/auth/login", json={"username_or_email": "officer1", "password": "nope"})
    assert bad.status_code == 401
    assert client.get("/auth/me").status_code == 401


@app.get("/test-rbac/admin-only", include_in_schema=False)
def _admin_only(user: User = Depends(require_admin)):
    return {"ok": True}


@app.get("/test-rbac/staff", include_in_schema=False)
def _staff(user: User = Depends(require_supervisor_or_admin)):
    return {"ok": True}


def test_rbac(client):
    make_user("a", "admin")
    make_user("s", "supervisor")
    make_user("o", "field_officer")
    h = {u: auth(client, u) for u in "aso"}
    assert client.get("/test-rbac/admin-only", headers=h["a"]).status_code == 200
    assert client.get("/test-rbac/admin-only", headers=h["s"]).status_code == 403
    assert client.get("/test-rbac/staff", headers=h["s"]).status_code == 200
    assert client.get("/test-rbac/staff", headers=h["o"]).status_code == 403
