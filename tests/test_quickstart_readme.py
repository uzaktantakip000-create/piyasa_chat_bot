from datetime import datetime

import pytest

from .conftest import auth_headers


def _create_bot(api_client, name="Quick Bot"):
    payload = {
        "name": name,
        "token": "12345:ABCDE",
        "username": "quick_bot",
        "is_enabled": True,
        "speed_profile": {"mode": "normal"},
        "active_hours": ["09:00-18:00"],
        "persona_hint": "dengeli"
    }
    resp = api_client.post("/bots", json=payload, headers=auth_headers())
    assert resp.status_code == 201
    return resp.json()


def _create_chat(api_client, title="Quick Chat"):
    payload = {
        "chat_id": "-100987654",
        "title": title,
        "is_enabled": True,
        "topics": ["BIST", "Kripto"]
    }
    resp = api_client.post("/chats", json=payload, headers=auth_headers())
    assert resp.status_code == 201
    return resp.json()


def test_quickstart_onboarding_flow(api_client):
    metrics_initial = api_client.get("/metrics", headers=auth_headers())
    assert metrics_initial.status_code == 200
    data_initial = metrics_initial.json()
    assert data_initial["total_bots"] == 0
    assert data_initial["total_chats"] == 0
    assert data_initial["simulation_active"] is False

    bot = _create_bot(api_client)
    chat = _create_chat(api_client)
    assert bot["id"] > 0
    assert chat["id"] > 0

    start_resp = api_client.post("/control/start", headers=auth_headers())
    assert start_resp.status_code == 200

    scale_resp = api_client.post(
        "/control/scale",
        json={"factor": 1.3},
        headers=auth_headers(),
    )
    assert scale_resp.status_code == 200
    assert scale_resp.json()["factor"] == pytest.approx(1.3)

    metrics_after = api_client.get("/metrics", headers=auth_headers())
    assert metrics_after.status_code == 200
    data_after = metrics_after.json()
    assert data_after["total_bots"] == 1
    assert data_after["total_chats"] == 1
    assert data_after["simulation_active"] is True

    stop_resp = api_client.post("/control/stop", headers=auth_headers())
    assert stop_resp.status_code == 200

    metrics_final = api_client.get("/metrics", headers=auth_headers())
    assert metrics_final.status_code == 200
    data_final = metrics_final.json()
    assert data_final["simulation_active"] is False


def test_readme_health_endpoints(api_client):
    # README'deki curl örnekleriyle aynı uçlar
    health = api_client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["ok"] is True

    logs = api_client.get("/logs/recent", headers=auth_headers())
    assert logs.status_code == 200
    assert isinstance(logs.json(), list)

    checks = api_client.get("/system/checks/latest", headers=auth_headers())
    assert checks.status_code == 200
    assert checks.json() is None

    # Tarih alanı örneği - README hızlı başlangıç zaman damgalarını kullanıyor
    now = datetime.utcnow().isoformat()
    assert isinstance(now, str)
