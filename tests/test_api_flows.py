import base64  # Required so _generate_key can use base64.urlsafe_b64encode
import os
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from .conftest import auth_headers


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


def _create_bot(api_client):
    payload = {
        "name": "Stance Bot",
        "token": "98765:ABCDE",
        "username": "stance_bot",
        "is_enabled": True,
    }
    response = api_client.post("/bots", json=payload, headers=auth_headers())
    assert response.status_code == 201
    return response.json()["id"]


def test_stance_updated_at_refreshes(api_client):
    bot_id = _create_bot(api_client)
    payload = {
        "topic": "Kripto",
        "stance_text": "Pozitif",
        "confidence": 0.7,
    }

    create_resp = api_client.post(
        f"/bots/{bot_id}/stances", json=payload, headers=auth_headers()
    )
    assert create_resp.status_code == 201
    stance_first = create_resp.json()
    first_updated_at = datetime.fromisoformat(stance_first["updated_at"])

    update_payload = {
        "topic": "Kripto",
        "stance_text": "Daha temkinli",  # triggers upsert update
        "confidence": 0.5,
    }

    update_resp = api_client.post(
        f"/bots/{bot_id}/stances", json=update_payload, headers=auth_headers()
    )
    assert update_resp.status_code == 201
    stance_updated = update_resp.json()
    second_updated_at = datetime.fromisoformat(stance_updated["updated_at"])

    assert second_updated_at > first_updated_at


def test_system_check_flow(api_client):
    payload = {
        "status": "passed",
        "total_steps": 3,
        "passed_steps": 3,
        "failed_steps": 0,
        "duration": 12.5,
        "triggered_by": "unit-test",
        "steps": [
            {"name": "preflight", "success": True, "duration": 3.2, "stdout": "ok", "stderr": ""},
            {"name": "pytest", "success": True, "duration": 4.1, "stdout": "", "stderr": ""},
            {"name": "stress-test", "success": True, "duration": 5.2, "stdout": "stress ok", "stderr": ""},
        ],
        "health_checks": [
            {"name": "api", "status": "healthy", "detail": "200 OK"},
            {"name": "redis", "status": "skipped", "detail": "ci"},
        ],
    }

    create_resp = api_client.post("/system/checks", json=payload, headers=auth_headers())
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["status"] == "passed"
    assert created["total_steps"] == 3
    assert len(created["steps"]) == 3
    assert created["health_checks"][0]["name"] == "api"

    latest = api_client.get("/system/checks/latest", headers=auth_headers())
    assert latest.status_code == 200
    latest_body = latest.json()
    assert latest_body["id"] == created["id"]
    assert latest_body["steps"][0]["name"] == "preflight"
    assert latest_body["health_checks"][0]["name"] == "api"


def test_system_check_summary(api_client):
    payload = {
        "status": "passed",
        "total_steps": 3,
        "passed_steps": 3,
        "failed_steps": 0,
        "duration": 10.0,
        "triggered_by": "unit-test",
        "steps": [
            {"name": "preflight", "success": True, "duration": 3.0, "stdout": "", "stderr": ""},
            {"name": "pytest", "success": True, "duration": 4.0, "stdout": "", "stderr": ""},
            {"name": "stress-test", "success": True, "duration": 3.0, "stdout": "", "stderr": ""},
        ],
        "health_checks": [],
    }

    first = api_client.post("/system/checks", json=payload, headers=auth_headers())
    assert first.status_code == 201
    first_id = first.json()["id"]

    second_payload = dict(payload)
    second_payload.update({"status": "failed", "failed_steps": 1, "passed_steps": 2, "duration": 6.0})
    second = api_client.post("/system/checks", json=second_payload, headers=auth_headers())
    assert second.status_code == 201
    second_id = second.json()["id"]

    old_payload = dict(payload)
    old_payload.update({"duration": 8.0})
    old = api_client.post("/system/checks", json=old_payload, headers=auth_headers())
    assert old.status_code == 201
    old_id = old.json()["id"]

    from database import SessionLocal, SystemCheck

    session = SessionLocal()
    try:
        now = datetime.utcnow()
        adjustments = [
            (first_id, timedelta(days=2), "passed"),
            (second_id, timedelta(hours=6), "failed"),
            (old_id, timedelta(days=9), "passed"),
        ]

        for record_id, delta, status in adjustments:
            obj = session.query(SystemCheck).filter(SystemCheck.id == record_id).one()
            obj.created_at = now - delta
            obj.status = status
        session.commit()
    finally:
        session.close()

    summary_resp = api_client.get("/system/checks/summary", headers=auth_headers())
    assert summary_resp.status_code == 200
    summary = summary_resp.json()

    assert summary["total_runs"] == 2
    assert summary["passed_runs"] == 1
    assert summary["failed_runs"] == 1
    assert summary["success_rate"] == pytest.approx(0.5)
    assert summary["average_duration"] == pytest.approx(8.0)
    assert summary["last_run_at"] is not None
    assert len(summary["daily_breakdown"]) == 2

    dates = [bucket["date"] for bucket in summary["daily_breakdown"]]
    assert dates == sorted(dates)
    totals = [bucket["total"] for bucket in summary["daily_breakdown"]]
    assert totals == [1, 1]


def test_run_system_checks_endpoint(api_client, monkeypatch):
    import main

    dummy_result = SimpleNamespace(returncode=0, stdout="ok", stderr="")

    def fake_run(cmd, cwd=None, env=None, capture_output=None, text=None):
        return dummy_result

    monkeypatch.setattr(main, "subprocess", SimpleNamespace(run=fake_run))

    resp = api_client.post("/system/checks/run", headers=auth_headers())
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "passed"
    assert data["total_steps"] == 3


def test_holding_updated_at_refreshes(api_client):
    bot_id = _create_bot(api_client)
    payload = {
        "symbol": "BIST:AKBNK",
        "avg_price": 12.5,
        "size": 100,
        "note": "Uzun vade",
    }

    create_resp = api_client.post(
        f"/bots/{bot_id}/holdings", json=payload, headers=auth_headers()
    )
    assert create_resp.status_code == 201
    holding_first = create_resp.json()
    first_updated_at = datetime.fromisoformat(holding_first["updated_at"])

    update_payload = {
        "symbol": "BIST:AKBNK",
        "avg_price": 13.0,
        "size": 120,
        "note": "Pozisyon artırıldı",
    }

    update_resp = api_client.post(
        f"/bots/{bot_id}/holdings", json=update_payload, headers=auth_headers()
    )
    assert update_resp.status_code == 201
    holding_updated = update_resp.json()
    second_updated_at = datetime.fromisoformat(holding_updated["updated_at"])

    assert second_updated_at > first_updated_at
