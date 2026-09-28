"""
FieldProof — Create an account of any role from the command line.

Public sign-up is closed; admins create accounts through POST /auth/users.
This script bootstraps the first admin, or any account, directly in the
database. For the demo users use: python -m app.scripts.seed_demo
Roles: field_officer, supervisor, admin.

Usage (from Backend/):
    python -m app.scripts.create_user --username controller1 --email c1@lm.gov.in \
        --full-name "Controller One" --role admin --password "..."
"""

from __future__ import annotations

import argparse

from app.database import SessionLocal
from app.models.user import UserRole
from app.schemas.user import UserCreate
from app.services.auth_service import create_user, get_user_by_email, get_user_by_username


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an FieldProof account.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--role", required=True, choices=[r.value for r in UserRole])
    parser.add_argument("--password", required=True)
    parser.add_argument("--badge-number")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if get_user_by_username(db, args.username) or get_user_by_email(db, args.email):
            raise SystemExit("An account with that username or email already exists.")
        user = create_user(db, UserCreate(
            username=args.username,
            email=args.email,
            full_name=args.full_name,
            role=UserRole(args.role),
            password=args.password,
            badge_number=args.badge_number,
        ))
        print(f"Created {user.role} account '{user.username}' (id {user.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
