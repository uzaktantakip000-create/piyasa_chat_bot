"""Security utilities for API auth and token handling."""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from functools import lru_cache
from typing import Callable

from cryptography.fernet import Fernet, InvalidToken
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
            return Fernet(key.encode())
        except Exception as exc:  # pragma: no cover - defensive branch
            raise SecurityConfigError("Invalid TOKEN_ENCRYPTION_KEY provided") from exc

    # Derive a Fernet key from arbitrary string using SHA-256
    digest = hashlib.sha256(key.encode()).digest()
    derived_key = base64.urlsafe_b64encode(digest)
    return Fernet(derived_key)


def encrypt_token(token: str) -> str:
    """Encrypt a Telegram bot token for persistence."""
    if not token:
        raise ValueError("Token cannot be empty")

    # Avoid double encryption by checking Fernet prefix
    if token.startswith("gAAAA"):
        return token

    cipher = _get_cipher()
    return cipher.encrypt(token.encode()).decode()


def decrypt_token(stored_value: str) -> str:
    """Decrypt stored token (backwards compatible with plaintext)."""
    if not stored_value:
        return ""

    if not stored_value.startswith("gAAAA"):
        # Plaintext token from legacy installs
        return stored_value

    cipher = _get_cipher()
    try:
        return cipher.decrypt(stored_value.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt stored bot token; ensure TOKEN_ENCRYPTION_KEY is correct")
        raise SecurityConfigError("Could not decrypt bot token; invalid TOKEN_ENCRYPTION_KEY")


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
