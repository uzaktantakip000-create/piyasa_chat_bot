import base64
import importlib
import os

import pytest

from .patched_testclient import PatchedTestClient


def _generate_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _generate_key())
    monkeypatch.setenv("API_KEY", "test-key")

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
    return {"X-API-Key": "test-key"}
