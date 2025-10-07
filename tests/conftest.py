import base64
import base64
import hmac
import importlib
import os
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from .patched_testclient import PatchedTestClient


def _generate_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _generate_totp(secret: str, step: int = 30, digits: int = 6) -> str:
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded.upper())
    counter = int(time.time() // step)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, digestmod="sha1").digest()
    offset = digest[-1] & 0x0F
    code = digest[offset : offset + 4]
    number = struct.unpack(">I", code)[0] & 0x7FFFFFFF
    return str(number % (10 ** digits)).zfill(digits)

@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _generate_key())
    monkeypatch.setenv("DEFAULT_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "SuperSecure!123")
    monkeypatch.setenv("DEFAULT_ADMIN_API_KEY", "bootstrap-key")
    monkeypatch.setenv("DEFAULT_ADMIN_MFA_SECRET", "JBSWY3DPEHPK3PXP")
    monkeypatch.setenv("DASHBOARD_STREAM_INTERVAL", "0.1")
    monkeypatch.setenv("AUTH_PBKDF_ITERATIONS", "1000")
    monkeypatch.delenv("API_KEY", raising=False)

    import security
    import database
    import main

    importlib.reload(security)
    importlib.reload(database)
    importlib.reload(main)

    from main import app

    with PatchedTestClient(app) as client:
        yield client


@pytest.fixture()
def authenticated_client(api_client):
    payload = {
        "username": "admin",
        "password": "SuperSecure!123",
        "totp": _generate_totp("JBSWY3DPEHPK3PXP"),
    }
    response = api_client.post("/auth/login", json=payload)
    assert response.status_code == 200
    return api_client
