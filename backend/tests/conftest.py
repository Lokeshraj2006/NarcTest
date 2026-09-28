"""
Shared test setup: in-memory SQLite, temp key/upload folders, fake colour engine.
"""

from __future__ import annotations

import sys
import tempfile
import types
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings

_TMP = tempfile.mkdtemp(prefix="fieldproof_test_")
settings.keys_dir = f"{_TMP}/keys"
settings.uploads_dir = f"{_TMP}/uploads"
settings.public_base_url = None

import app.models  # noqa: E402,F401
from app.core.security import get_password_hash  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:",
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

PASSWORD = "Password123!"


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    s = TestingSessionLocal()
    try:
        yield s
    finally:
        s.close()


def make_user(username: str, role: str, password: str = PASSWORD) -> int:
    s = TestingSessionLocal()
    try:
        u = User(
            email=f"{username}@example.com", username=username, full_name=f"User {username}",
            hashed_password=get_password_hash(password), role=role,
        )
        s.add(u)
        s.commit()
        return u.id
    finally:
        s.close()


def auth(client: TestClient, username: str, password: str = PASSWORD) -> dict:
    res = client.post("/auth/login", json={"username_or_email": username, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


FAKE_RESULT = {
    "result": "POSITIVE",
    "outcome_label": "Opium-type drug (purple)",
    "confidence": 91,
    "reason": None,
    "measured_lab": [30.1, 35.2, -30.3],
    "measured_rgb": [98, 45, 120],
    "delta_e_by_outcome": {"Opium-type drug (purple)": 2.1},
    "quality": {"card_found": True, "markers_found": 4, "blur_score": 300.0,
                "glare_pct": 0.1, "ccm_fit_de": 1.2},
}


@pytest.fixture
def fake_engine(monkeypatch):
    """Replace the real colour engine + NTP so tests are fast and independent."""
    state = {"result": dict(FAKE_RESULT)}
    fake = types.ModuleType("app.services.colour_engine")
    fake.classify = lambda image_bytes, profile: dict(state["result"])
    fake.srgb_to_lab = lambda rgb: [50.0, 0.0, 0.0]
    import app.services as services_pkg

    monkeypatch.setitem(sys.modules, "app.services.colour_engine", fake)
    monkeypatch.setattr(services_pkg, "colour_engine", fake, raising=False)

    from app.services import time_service

    monkeypatch.setattr(
        time_service, "get_trusted_time",
        lambda timeout=2.0: (datetime.now(timezone.utc), None, "server_clock"),
    )
    return state


@pytest.fixture
def kit_id(db):
    from app.services.kit_service import seed_demo_kits
    from app.models.kit_profile import KitProfile

    seed_demo_kits(db)
    return db.query(KitProfile).filter(KitProfile.code == "DEMO-MARQUIS-SIM").one().id
