"""
FieldProof — Security Utilities

Handles password hashing (bcrypt), JWT token issuance/verification (python-jose),
and SHA-256 evidence hashing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any, Optional

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    subject: str | int,
    role: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """Generate a signed JWT access token containing subject and user role."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT token."""
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
    )


def compute_sha256(data: bytes) -> str:
    """Compute standard SHA-256 hexadecimal hash for evidence/file integrity."""
    return hashlib.sha256(data).hexdigest()
