"""
Tests for Authentication & RBAC — Deliverable 3

Tests password hashing, JWT creation/verification, user registration,
login flows, and Role-Based Access Control (RBAC) dependencies.
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import (
    get_current_active_user,
    require_admin,
    require_inspector,
    require_inspector_or_admin,
)
from app.core.security import (
    compute_sha256,
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from app.database import Base, get_db
from app.main import app
from app.models.user import User, UserRole

# ── Test Database Setup with Dependency Override ─────────────────
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def _make_user(username: str, role: str, password: str = "Password123!") -> None:
    """Officer accounts can't come from public sign-up, so tests seed them."""
    db = TestingSessionLocal()
    try:
        db.add(User(
            email=f"{username}@example.com", username=username, full_name=f"User {username}",
            hashed_password=get_password_hash(password), role=role,
        ))
        db.commit()
    finally:
        db.close()


def _token(username: str, password: str = "Password123!") -> str:
    return client.post(
        "/auth/login", json={"username_or_email": username, "password": password}
    ).json()["access_token"]


# ── 1. Security Utilities Tests ─────────────────────────────────

def test_password_hashing():
    """Verify bcrypt hashes passwords and checks validity correctly."""
    pwd = "LegalMetrology2026!#"
    hashed = get_password_hash(pwd)
    assert hashed != pwd
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_issuance_and_decoding():
    """Verify token encoding and claims payload."""
    token = create_access_token(subject=42, role="inspector")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "inspector"
    assert "exp" in payload


def test_sha256_computation():
    """Verify standard SHA-256 evidence hashing."""
    import hashlib

    test_bytes = b"FieldProof Evidence Payload"
    expected = hashlib.sha256(test_bytes).hexdigest()
    assert compute_sha256(test_bytes) == expected
    assert len(compute_sha256(test_bytes)) == 64


# ── 2. Registration & Login API Tests ───────────────────────────

INSPECTOR_PAYLOAD = {
    "email": "inspector.kumar@lm.gov.in",
    "username": "inspector_kumar",
    "full_name": "Suresh Kumar",
    "password": "SecurePassword123!",
    "role": "inspector",
    "badge_number": "INSP-HR-9081",
    "phone_number": "+919876543210",
}


@pytest.mark.parametrize("role", ["inspector", "admin"])
def test_public_sign_up_cannot_create_officers(role):
    """A stranger must not be able to give themselves enforcement powers."""
    res = client.post("/auth/register", json={**INSPECTOR_PAYLOAD, "role": role})
    assert res.status_code == 403
    assert "consumer accounts only" in res.json()["detail"]


def test_only_an_admin_can_create_an_officer_account():
    _make_user("chief", "admin")
    _make_user("field_officer", "inspector")

    denied = client.post(
        "/auth/users", json=INSPECTOR_PAYLOAD,
        headers={"Authorization": f"Bearer {_token('field_officer')}"},
    )
    assert denied.status_code == 403

    res = client.post(
        "/auth/users", json=INSPECTOR_PAYLOAD,
        headers={"Authorization": f"Bearer {_token('chief')}"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "inspector.kumar@lm.gov.in"
    assert data["role"] == "inspector"
    assert data["badge_number"] == "INSP-HR-9081"
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_duplicate_prevention():
    """Prevent duplicate email or username registration."""
    payload = {
        "email": "dup@lm.gov.in",
        "username": "dup_user",
        "full_name": "Dup Tester",
        "password": "password123",
        "role": "consumer",
    }
    res1 = client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    # Same email
    res2 = client.post("/auth/register", json=payload)
    assert res2.status_code == 400
    assert "email address already exists" in res2.json()["detail"]

    # Same username, different email
    payload2 = {**payload, "email": "other@lm.gov.in"}
    res3 = client.post("/auth/register", json=payload2)
    assert res3.status_code == 400
    assert "username already exists" in res3.json()["detail"]


def test_login_success_and_failure():
    """Test login authentication and token retrieval."""
    _make_user("admin_chief", "admin", "AdminPassword2026!")

    # Valid login via username
    login_res = client.post(
        "/auth/login",
        json={"username_or_email": "admin_chief", "password": "AdminPassword2026!"},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["role"] == "admin"

    # Valid login via email
    login_res2 = client.post(
        "/auth/login",
        json={"username_or_email": "admin_chief@example.com", "password": "AdminPassword2026!"},
    )
    assert login_res2.status_code == 200

    # Invalid password
    bad_pwd = client.post(
        "/auth/login",
        json={"username_or_email": "admin_chief", "password": "WrongPassword!"},
    )
    assert bad_pwd.status_code == 401


def test_get_me_profile():
    """Verify /auth/me returns the profile for authenticated requests."""
    client.post(
        "/auth/register",
        json={
            "email": "citizen@test.com",
            "username": "citizen_amit",
            "full_name": "Amit Patel",
            "password": "CitizenPassword123!",
            "role": "consumer",
        },
    )
    login_res = client.post(
        "/auth/login",
        json={"username_or_email": "citizen_amit", "password": "CitizenPassword123!"},
    )
    token = login_res.json()["access_token"]

    # Authenticated call
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "citizen_amit"

    # Unauthenticated call
    no_auth = client.get("/auth/me")
    assert no_auth.status_code == 401


# ── 3. RBAC Guards Test Endpoint ────────────────────────────────

# Mount temporary test routes on the app to verify RBAC dependencies
@app.get("/test-rbac/admin-only", tags=["test"])
def admin_only_endpoint(user: User = Depends(require_admin)):
    return {"message": f"Welcome Admin {user.username}"}


@app.get("/test-rbac/inspector-only", tags=["test"])
def inspector_only_endpoint(user: User = Depends(require_inspector)):
    return {"message": f"Welcome Inspector {user.username}"}


@app.get("/test-rbac/enforcement-staff", tags=["test"])
def enforcement_staff_endpoint(user: User = Depends(require_inspector_or_admin)):
    return {"message": f"Welcome Officer {user.username}"}


def test_rbac_authorization():
    """Test RBAC enforcement across Admin, Inspector, and Consumer roles."""
    # 1. Create one user of each role (officers can't come from public sign-up)
    _make_user("test_admin", "admin")
    _make_user("test_inspector", "inspector")
    client.post(
        "/auth/register",
        json={
            "email": "test_consumer@example.com",
            "username": "test_consumer",
            "full_name": "User test_consumer",
            "password": "Password123!",
            "role": "consumer",
        },
    )

    # 2. Get tokens for each
    admin_token = client.post(
        "/auth/login",
        json={"username_or_email": "test_admin", "password": "Password123!"},
    ).json()["access_token"]

    inspector_token = client.post(
        "/auth/login",
        json={"username_or_email": "test_inspector", "password": "Password123!"},
    ).json()["access_token"]

    consumer_token = client.post(
        "/auth/login",
        json={"username_or_email": "test_consumer", "password": "Password123!"},
    ).json()["access_token"]

    # 3. Test /test-rbac/admin-only
    res_admin = client.get(
        "/test-rbac/admin-only", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200

    res_insp_on_admin = client.get(
        "/test-rbac/admin-only", headers={"Authorization": f"Bearer {inspector_token}"}
    )
    assert res_insp_on_admin.status_code == 403
    assert "Operation not permitted" in res_insp_on_admin.json()["detail"]

    res_cons_on_admin = client.get(
        "/test-rbac/admin-only", headers={"Authorization": f"Bearer {consumer_token}"}
    )
    assert res_cons_on_admin.status_code == 403

    # 4. Test /test-rbac/inspector-only
    res_insp = client.get(
        "/test-rbac/inspector-only", headers={"Authorization": f"Bearer {inspector_token}"}
    )
    assert res_insp.status_code == 200

    res_cons_on_insp = client.get(
        "/test-rbac/inspector-only", headers={"Authorization": f"Bearer {consumer_token}"}
    )
    assert res_cons_on_insp.status_code == 403

    # 5. Test /test-rbac/enforcement-staff (Admin + Inspector allowed)
    assert (
        client.get(
            "/test-rbac/enforcement-staff",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/test-rbac/enforcement-staff",
            headers={"Authorization": f"Bearer {inspector_token}"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/test-rbac/enforcement-staff",
            headers={"Authorization": f"Bearer {consumer_token}"},
        ).status_code
        == 403
    )
