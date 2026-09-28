"""
FieldProof — Auth Service

Encapsulates user retrieval, password hashing, registration, and authentication logic.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Look up a user by email address."""
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Look up a user by username."""
    return db.query(User).filter(User.username == username.lower()).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Look up a user by numeric primary key."""
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, user_in: UserCreate) -> User:
    """Create and persist a new user with bcrypt-hashed password."""
    user = User(
        email=user_in.email.lower(),
        username=user_in.username.lower(),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        badge_number=user_in.badge_number,
        phone_number=user_in.phone_number,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(
    db: Session, username_or_email: str, password: str
) -> Optional[User]:
    """
    Authenticate user using either username or email and plaintext password.
    Returns the user instance if credentials match and account is active, else None.
    """
    identifier = username_or_email.lower().strip()
    user = (
        db.query(User)
        .filter(or_(User.email == identifier, User.username == identifier))
        .first()
    )

    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None

    return user
