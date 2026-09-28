"""
FieldProof — Ed25519 signing of test records.

The private key lives at <keys_dir>/ed25519_private.pem and is created on
first use. That folder is gitignored; never commit it.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.config import settings

key_id = "ed25519-1"
KEY_FILENAME = "ed25519_private.pem"

_private_key: Ed25519PrivateKey | None = None


def canonical_json(obj: Any) -> str:
    """The exact string that gets hashed and signed."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text_or_bytes: str | bytes) -> str:
    data = text_or_bytes.encode("utf-8") if isinstance(text_or_bytes, str) else text_or_bytes
    return hashlib.sha256(data).hexdigest()


def _key_path() -> Path:
    return Path(settings.keys_dir) / KEY_FILENAME


def get_private_key() -> Ed25519PrivateKey:
    """Load the signing key, creating it the first time."""
    global _private_key
    if _private_key is not None:
        return _private_key
    path = _key_path()
    if path.exists():
        _private_key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        path.write_bytes(pem)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        _private_key = key
    return _private_key


def get_public_key() -> Ed25519PublicKey:
    return get_private_key().public_key()


def public_key_pem() -> str:
    return get_public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def sign(payload: str) -> str:
    """Base64 Ed25519 signature of the payload string."""
    return base64.b64encode(get_private_key().sign(payload.encode("utf-8"))).decode("ascii")


def verify(payload: str, signature_b64: str) -> bool:
    try:
        get_public_key().verify(base64.b64decode(signature_b64), payload.encode("utf-8"))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
