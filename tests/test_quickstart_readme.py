from datetime import datetime

from datetime import datetime

import pytest


def _create_bot(client, name="Quick Bot"):
    payload = {
        "name": name,
        "token": "12345:ABCDE",
        "username": "quick_bot",
        "is_enabled": True,
        "speed_profile": {"mode": "normal"},
        "active_hours": ["09:00-18:00"],
        "persona_hint": "dengeli"
    }
    resp = client.post("/bots", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _create_chat(client, title="Quick Chat"):
    payload = {
        "chat_id": "-100987654",
        "title": title,
        "is_enabled": True,
        "topics": ["BIST", "Kripto"]
    }
    resp = client.post("/chats", json=payload)
    assert resp.status_code == 201
    return resp.json()


def test_quickstart_onboarding_flow(authenticated_client):
    client = authenticated_client
    metrics_initial = client.get("/metrics")
    assert metrics_initial.status_code == 200
    data_initial = metrics_initial.json()
    assert data_initial["total_bots"] == 0
    assert data_initial["total_chats"] == 0
    assert data_initial["simulation_active"] is False

    bot = _create_bot(client)
    chat = _create_chat(client)
    assert bot["id"] > 0
    assert chat["id"] > 0

    start_resp = client.post("/control/start")
    assert start_resp.status_code == 200

    scale_resp = client.post(
        "/control/scale",
        json={"factor": 1.3},
    )
    assert scale_resp.status_code == 200
    assert scale_resp.json()["factor"] == pytest.approx(1.3)

    metrics_after = client.get("/metrics")
    assert metrics_after.status_code == 200
    data_after = metrics_after.json()
    assert data_after["total_bots"] == 1
    assert data_after["total_chats"] == 1
    assert data_after["simulation_active"] is True

    stop_resp = client.post("/control/stop")
    assert stop_resp.status_code == 200

    metrics_final = client.get("/metrics")
    assert metrics_final.status_code == 200
    data_final = metrics_final.json()
    assert data_final["simulation_active"] is False


def test_readme_health_endpoints(authenticated_client):
    # README'deki curl örnekleriyle aynı uçlar
    client = authenticated_client
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["ok"] is True

    logs = client.get("/logs/recent")
    assert logs.status_code == 200
    assert isinstance(logs.json(), list)

    checks = client.get("/system/checks/latest")
    assert checks.status_code == 200
    assert checks.json() is None

    # Tarih alanı örneği - README hızlı başlangıç zaman damgalarını kullanıyor
    now = datetime.utcnow().isoformat()
    assert isinstance(now, str)
