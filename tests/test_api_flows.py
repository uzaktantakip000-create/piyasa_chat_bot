import base64
import importlib
import os

import pytest
from fastapi.testclient import TestClient


def _generate_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", _generate_key())
    monkeypatch.setenv("API_KEY", "test-key")

    # Reload modules so they pick up the temporary configuration.
    import security
    import database
    import main

    importlib.reload(security)
    importlib.reload(database)
    importlib.reload(main)

    from main import app

    with TestClient(app) as client:
        yield client


def auth_headers():
    return {"X-API-Key": "test-key"}


def test_create_and_toggle_bot(api_client):
    payload = {
        "name": "Test Bot",
        "token": "12345:ABCDEF",
        "username": "test_bot",
        "is_enabled": True,
        "speed_profile": {"mode": "normal"},
        "active_hours": ["09:00-18:00"],
        "persona_hint": "temkinli"
    }

    response = api_client.post("/bots", json=payload, headers=auth_headers())
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Bot"
    assert data["is_enabled"] is True
    assert data["token_masked"].startswith("1234")

    # Disable bot
    response = api_client.patch(
        f"/bots/{data['id']}",
        json={"is_enabled": False},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    patched = response.json()
    assert patched["is_enabled"] is False

    # Re-enable bot to complete the toggle scenario
    response = api_client.patch(
        f"/bots/{data['id']}",
        json={"is_enabled": True},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.json()["is_enabled"] is True


def test_create_chat_and_metrics_flow(api_client):
    chat_payload = {
        "chat_id": "-100123",
        "title": "Test Chat",
        "is_enabled": True,
        "topics": ["BIST", "Kripto"],
    }

    response = api_client.post("/chats", json=chat_payload, headers=auth_headers())
    assert response.status_code == 201

    metrics = api_client.get("/metrics", headers=auth_headers())
    assert metrics.status_code == 200
    payload = metrics.json()
    assert payload["total_chats"] == 1


def test_control_endpoints_update_settings(api_client):
    # Ensure simulation starts and stops cleanly
    start_resp = api_client.post("/control/start", headers=auth_headers())
    assert start_resp.status_code == 200

    stop_resp = api_client.post("/control/stop", headers=auth_headers())
    assert stop_resp.status_code == 200

    scale_resp = api_client.post(
        "/control/scale",
        json={"factor": 1.5},
        headers=auth_headers(),
    )
    assert scale_resp.status_code == 200
    assert scale_resp.json()["factor"] == pytest.approx(1.5)


def test_message_length_profile_normalization(api_client):
    payload = {
        "value": {
            "short": 0.9,
            "medium": 0.9,
            "long": 0.2,
        }
    }

    response = api_client.patch(
        "/settings/message_length_profile",
        json=payload,
        headers=auth_headers(),
    )
    assert response.status_code == 200
    body = response.json()
    profile = body["value"]["value"]
    assert profile["short"] == pytest.approx(0.45)
    assert profile["medium"] == pytest.approx(0.45)
    assert profile["long"] == pytest.approx(0.10, abs=1e-6)
    assert profile["short"] + profile["medium"] + profile["long"] == pytest.approx(1.0)

    settings = api_client.get("/settings", headers=auth_headers())
    assert settings.status_code == 200
    stored = None
    for item in settings.json():
        if item["key"] == "message_length_profile":
            stored = item["value"]["value"]
            break
    assert stored is not None
    assert stored["short"] == pytest.approx(profile["short"])
    assert stored["medium"] == pytest.approx(profile["medium"])
    assert stored["long"] == pytest.approx(profile["long"])
