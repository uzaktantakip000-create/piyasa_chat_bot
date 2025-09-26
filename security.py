"""Security utilities for API auth and token handling."""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from functools import lru_cache
from typing import Callable

_FALLBACK_B64_PREFIX = "ZGV2O"

try:
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
    _FERNET_AVAILABLE = True
except Exception:  # pragma: no cover - used in constrained environments
    _FERNET_AVAILABLE = False

    class InvalidToken(Exception):
        """Fallback InvalidToken exception when cryptography is missing."""

    class Fernet:  # type: ignore
        """Development-only fallback cipher.

        Bu sınıf, `cryptography` modülü mevcut değilse devreye girer ve temel bir
        base64 + HMAC kombinasyonu kullanır. Üretilen tokenlar `dev:` öneki ile
        başlar; üretim ortamında mutlaka gerçek `cryptography` paketini kurun.
        """

        def __init__(self, key: bytes) -> None:
            digest = hashlib.sha256(key).digest()
            self._key = digest

        def encrypt(self, value: bytes) -> bytes:
            if not isinstance(value, (bytes, bytearray)):
                raise TypeError("value must be bytes")
            body = bytes(value)[::-1]
            mac = hashlib.sha256(self._key + body).digest()[:8]
            token = base64.urlsafe_b64encode(b"dev:" + body + mac)
            return token

        def decrypt(self, token: bytes) -> bytes:
            if not isinstance(token, (bytes, bytearray)):
                raise TypeError("token must be bytes")
            try:
                raw = base64.urlsafe_b64decode(bytes(token))
            except Exception as exc:  # pragma: no cover - defensive branch
                raise InvalidToken("Invalid base64 token") from exc
            if not raw.startswith(b"dev:"):
                raise InvalidToken("Unsupported token prefix")
            payload = raw[4:]
            if len(payload) < 8:
                raise InvalidToken("Token too short")
            body, mac = payload[:-8], payload[-8:]
            expected = hashlib.sha256(self._key + body).digest()[:8]
            if mac != expected:
                raise InvalidToken("Token signature mismatch")
            return body[::-1]

from fastapi import Depends, Header, HTTPException, status

logger = logging.getLogger("security")


class SecurityConfigError(RuntimeError):
    """Raised when mandatory security configuration is missing."""


@lru_cache(maxsize=1)
def _get_cipher() -> Fernet:
    """Return a configured Fernet cipher using TOKEN_ENCRYPTION_KEY."""
    key = os.getenv("TOKEN_ENCRYPTION_KEY")
    if not key:
        raise SecurityConfigError(
            "TOKEN_ENCRYPTION_KEY is not set. Generate one with `python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"`"
        )

    # Accept both raw Fernet keys and arbitrary passphrases
    if len(key) == 44:
        try:
            Fernet(key.encode())
            cipher = Fernet(key.encode())
            if not _FERNET_AVAILABLE:
                logger.warning("cryptography modülü eksik; geliştirme amaçlı fallback şifreleyici kullanılıyor.")
            return cipher
        except Exception as exc:  # pragma: no cover - defensive branch
            raise SecurityConfigError("Invalid TOKEN_ENCRYPTION_KEY provided") from exc

    # Derive a Fernet key from arbitrary string using SHA-256
    digest = hashlib.sha256(key.encode()).digest()
    derived_key = base64.urlsafe_b64encode(digest)
    cipher = Fernet(derived_key)
    if not _FERNET_AVAILABLE:
        logger.warning("cryptography modülü eksik; geliştirme amaçlı fallback şifreleyici kullanılıyor.")
    return cipher


def encrypt_token(token: str) -> str:
    """Encrypt a Telegram bot token for persistence."""
    if not token:
        raise ValueError("Token cannot be empty")

    # Avoid double encryption by checking known prefixes
    if token.startswith("gAAAA") or _looks_like_fallback_token(token):
        return token

    cipher = _get_cipher()
    return cipher.encrypt(token.encode()).decode()


def decrypt_token(stored_value: str) -> str:
    """Decrypt stored token (backwards compatible with plaintext)."""
    if not stored_value:
        return ""

    if stored_value.startswith("gAAAA") or _looks_like_fallback_token(stored_value):
        cipher = _get_cipher()
        try:
            return cipher.decrypt(stored_value.encode()).decode()
        except InvalidToken:
            logger.error("Failed to decrypt stored bot token; ensure TOKEN_ENCRYPTION_KEY is correct")
            raise SecurityConfigError("Could not decrypt bot token; invalid TOKEN_ENCRYPTION_KEY")

    # Plaintext token from legacy installs
    return stored_value


def _looks_like_fallback_token(value: str) -> bool:
    if not value or not value.startswith(_FALLBACK_B64_PREFIX):
        return False
    try:
        raw = base64.urlsafe_b64decode(value.encode())
    except Exception:
        return False
    return raw.startswith(b"dev:")


def mask_token(token: str) -> str:
    """Return a user-facing masked representation of the token."""
    if not token:
        return ""
    token = token.strip()
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


async def require_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> None:
    """FastAPI dependency enforcing X-API-Key header."""
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key is not configured on the server",
        )
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


def with_api_key_dependency() -> Callable:
    """Convenience helper for adding API key dependency to routes."""
    return Depends(require_api_key)
