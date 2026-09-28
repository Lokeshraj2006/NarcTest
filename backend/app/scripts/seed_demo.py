"""
FieldProof — Demo seed.

    python -m app.scripts.seed_demo        (run from backend/)

* Makes sure DEMO_PASSWORD exists in backend/.env (adds a random one if not).
* Creates / updates officer1, supervisor1, admin1 with that password.
* Seeds the 2 demo kit profiles (safe to run many times).
* Writes the logins to DEMO_LOGINS.txt in the repo root (gitignored).
The password is never printed.
"""

from __future__ import annotations

import os
import secrets
import string
from pathlib import Path

from app.config import BACKEND_DIR

ENV_PATH = BACKEND_DIR / ".env"
LOGINS_PATH = BACKEND_DIR.parent / "DEMO_LOGINS.txt"

DEMO_USERS = [
    ("officer1", "field_officer", "Officer One (Demo)"),
    ("supervisor1", "supervisor", "Supervisor One (Demo)"),
    ("admin1", "admin", "Admin One (Demo)"),
]


def _read_env_password() -> str | None:
    if not ENV_PATH.exists():
        return None
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DEMO_PASSWORD="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return value or None
    return None


def ensure_demo_password() -> str:
    pw = _read_env_password() or os.environ.get("DEMO_PASSWORD") or None
    if pw:
        return pw
    alphabet = string.ascii_letters + string.digits
    pw = "".join(secrets.choice(alphabet) for _ in range(10))
    existing = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    with ENV_PATH.open("a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(f"DEMO_PASSWORD={pw}\n")
    return pw


def main() -> None:
    password = ensure_demo_password()

    import app.models  # noqa: F401
    from app.core.security import get_password_hash
    from app.database import Base, SessionLocal, engine
    from app.models.user import User
    from app.services.kit_service import seed_demo_kits

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for username, role, full_name in DEMO_USERS:
            user = db.query(User).filter(User.username == username).first()
            if user is None:
                user = User(
                    username=username,
                    email=f"{username}@fieldproof.in",
                    full_name=full_name,
                    role=role,
                    hashed_password=get_password_hash(password),
                    is_active=True,
                )
                db.add(user)
            else:
                user.role = role
                user.is_active = True
                user.hashed_password = get_password_hash(password)
        db.commit()
        seed_demo_kits(db)
    finally:
        db.close()

    lines = ["FieldProof demo logins (do not commit this file)", ""]
    lines += [f"{u:<12} ({r})" for u, r, _ in DEMO_USERS]
    lines += ["", f"Password for all: {password}", ""]
    LOGINS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("Demo users ready (see DEMO_LOGINS.txt)")


if __name__ == "__main__":
    main()
