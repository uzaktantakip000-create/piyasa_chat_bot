"""Authentication helper utilities (password hashing, API anahtarı üretimi, MFA)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from typing import Optional, Tuple

_PBKDF_ITERATIONS = int(os.getenv("AUTH_PBKDF_ITERATIONS", "480000"))


def _ensure_bytes(value: str) -> bytes:
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8")


def hash_secret(secret: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash a secret using PBKDF2-HMAC-SHA256.

    Returns the tuple ``(hashed, salt)``. Salt is generated randomly when not
    provided.
    """

    if salt is None:
        salt_bytes = secrets.token_bytes(16)
        salt = base64.urlsafe_b64encode(salt_bytes).decode("utf-8")
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        _ensure_bytes(secret),
        _ensure_bytes(salt),
        _PBKDF_ITERATIONS,
    )
    return base64.urlsafe_b64encode(derived).decode("utf-8"), salt


def verify_secret(secret: str, hashed: str, salt: str) -> bool:
    expected, _ = hash_secret(secret, salt)
    return hmac.compare_digest(expected, hashed)


def generate_api_key(length: int = 48) -> Tuple[str, str, str]:
    """Return a freshly generated API key and its hashed representation."""

    api_key = secrets.token_urlsafe(length)
    hashed, salt = hash_secret(api_key)
    return api_key, hashed, salt


def generate_totp_secret(length: int = 20) -> str:
    """Return a Base32-encoded TOTP secret."""

    return base64.b32encode(secrets.token_bytes(length)).decode("utf-8").rstrip("=")


def _time_counter(step: int) -> int:
    return int(time.time() // step)


def generate_totp(secret: str, *, step: int = 30, digits: int = 6, counter: Optional[int] = None) -> str:
    if counter is None:
        counter = _time_counter(step)
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded.upper())
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = digest[offset: offset + 4]
    num = struct.unpack(">I", code)[0] & 0x7FFFFFFF
    return str(num % (10 ** digits)).zfill(digits)


def verify_totp(secret: str, code: str, *, step: int = 30, digits: int = 6, window: int = 1) -> bool:
    """Check a TOTP code allowing +-``window`` steps."""

    code = (code or "").strip()
    if not code.isdigit():
        return False
    counter = _time_counter(step)
    for delta in range(-window, window + 1):
        candidate = generate_totp(secret, step=step, digits=digits, counter=counter + delta)
        if hmac.compare_digest(candidate, code):
            return True
    return False


__all__ = [
    "hash_secret",
    "verify_secret",
    "generate_api_key",
    "generate_totp_secret",
    "verify_totp",
    "generate_totp",
]
