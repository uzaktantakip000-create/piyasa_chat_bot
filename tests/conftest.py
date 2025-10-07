import base64
import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from .patched_testclient import PatchedTestClient


def _generate_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


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


def auth_headers():
    return {"X-API-Key": "bootstrap-key"}
