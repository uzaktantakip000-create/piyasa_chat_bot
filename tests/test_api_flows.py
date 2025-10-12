from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


def test_create_and_toggle_bot(authenticated_client):
    client = authenticated_client
    payload = {
        "name": "Test Bot",
        "token": "12345:ABCDEF",
        "username": "test_bot",
        "is_enabled": True,
        "speed_profile": {"mode": "normal"},
        "active_hours": ["09:00-18:00"],
        "persona_hint": "temkinli",
    }

    response = client.post("/bots", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Bot"
    assert data["is_enabled"] is True
    assert data["token_masked"].startswith("1234")

    response = client.patch(
        f"/bots/{data['id']}",
        json={"is_enabled": False},
    )
    assert response.status_code == 200
    assert response.json()["is_enabled"] is False

    response = client.patch(
        f"/bots/{data['id']}",
        json={"is_enabled": True},
    )
    assert response.status_code == 200
    assert response.json()["is_enabled"] is True


def test_create_chat_and_metrics_flow(authenticated_client):
    client = authenticated_client
    chat_payload = {
        "chat_id": "-100123",
        "title": "Test Chat",
        "is_enabled": True,
        "topics": ["BIST", "Kripto"],
    }

    response = client.post("/chats", json=chat_payload)
    assert response.status_code == 201

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    payload = metrics.json()
    assert payload["total_chats"] == 1


def test_control_endpoints_update_settings(authenticated_client):
    client = authenticated_client

    start_resp = client.post("/control/start")
    assert start_resp.status_code == 200

    stop_resp = client.post("/control/stop")
    assert stop_resp.status_code == 200

    scale_resp = client.post("/control/scale", json={"factor": 1.5})
    assert scale_resp.status_code == 200
    assert scale_resp.json()["factor"] == pytest.approx(1.5)


def test_message_length_profile_normalization(authenticated_client):
    client = authenticated_client
    payload = {
        "value": {
            "short": 0.9,
            "medium": 0.9,
            "long": 0.2,
        }
    }

    response = client.patch("/settings/message_length_profile", json=payload)
    assert response.status_code == 200
    body = response.json()
    profile = body["value"]["value"]
    assert profile["short"] == pytest.approx(0.45)
    assert profile["medium"] == pytest.approx(0.45)
    assert profile["long"] == pytest.approx(0.10, abs=1e-6)
    assert profile["short"] + profile["medium"] + profile["long"] == pytest.approx(1.0)

    settings = client.get("/settings")
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


def _create_bot(client):
    payload = {
        "name": "Stance Bot",
        "token": "98765:ABCDE",
        "username": "stance_bot",
        "is_enabled": True,
    }
    response = client.post("/bots", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def test_stance_updated_at_refreshes(authenticated_client):
    client = authenticated_client
    bot_id = _create_bot(client)
    payload = {
        "topic": "Kripto",
        "stance_text": "Pozitif",
        "confidence": 0.7,
    }

    create_resp = client.post(f"/bots/{bot_id}/stances", json=payload)
    assert create_resp.status_code == 201
    stance_first = create_resp.json()
    first_updated_at = datetime.fromisoformat(stance_first["updated_at"])

    update_payload = {
        "topic": "Kripto",
        "stance_text": "Daha temkinli",
        "confidence": 0.5,
    }

    update_resp = client.post(f"/bots/{bot_id}/stances", json=update_payload)
    assert update_resp.status_code == 201
    stance_updated = update_resp.json()
    second_updated_at = datetime.fromisoformat(stance_updated["updated_at"])

    assert second_updated_at > first_updated_at


def test_system_check_flow(authenticated_client):
    client = authenticated_client
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

    create_resp = client.post("/system/checks", json=payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["status"] == "passed"
    assert created["total_steps"] == 3
    assert len(created["steps"]) == 3
    assert created["health_checks"][0]["name"] == "api"

    latest = client.get("/system/checks/latest")
    assert latest.status_code == 200
    latest_body = latest.json()
    assert latest_body["id"] == created["id"]
    assert latest_body["steps"][0]["name"] == "preflight"
    assert latest_body["health_checks"][0]["name"] == "api"


def test_system_check_summary(authenticated_client):
    client = authenticated_client
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

    first = client.post("/system/checks", json=payload)
    assert first.status_code == 201
    first_id = first.json()["id"]

    second_payload = dict(payload)
    second_payload.update({"status": "failed", "failed_steps": 1, "passed_steps": 2, "duration": 6.0})
    second = client.post("/system/checks", json=second_payload)
    assert second.status_code == 201
    second_id = second.json()["id"]

    old_payload = dict(payload)
    old_payload.update({"duration": 8.0})
    old = client.post("/system/checks", json=old_payload)
    assert old.status_code == 201
    old_id = old.json()["id"]

    from database import SessionLocal, SystemCheck

    session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
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

    summary_resp = client.get("/system/checks/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()

    assert summary["total_runs"] == 2
    assert summary["passed_runs"] == 1
    assert summary["failed_runs"] == 1
    assert summary["success_rate"] == pytest.approx(0.5)
    assert summary["average_duration"] == pytest.approx(8.0)
    assert summary["last_run_at"] is not None
    assert len(summary["daily_breakdown"]) == 2
    assert summary["overall_status"] == "critical"
    assert summary["overall_message"] == "Testlerin önemli bir kısmı başarısız; aksiyon alınmalı."
    assert summary["insights"], "insights boş olmamalı"
    failure_insight = next((item for item in summary["insights"] if "başarısız" in item["message"].lower()), None)
    assert failure_insight is not None
    assert summary["recommended_actions"], "recommended_actions boş olmamalı"
    assert any("loglarını" in action for action in summary["recommended_actions"])

    assert summary["recent_runs"], "recent_runs boş olmamalı"
    assert len(summary["recent_runs"]) == 2
    latest_run = summary["recent_runs"][0]
    assert latest_run["id"] == second_id
    assert latest_run["status"] == "failed"
    assert latest_run["created_at"] is not None
    assert latest_run["total_steps"] == payload["total_steps"]

    dates = [bucket["date"] for bucket in summary["daily_breakdown"]]
    assert dates == sorted(dates)
    totals = [bucket["total"] for bucket in summary["daily_breakdown"]]
    assert totals == [1, 1]


def test_run_system_checks_endpoint(authenticated_client, monkeypatch):
    import main

    client = authenticated_client
    dummy_result = SimpleNamespace(returncode=0, stdout="ok", stderr="")

    def fake_run(cmd, cwd=None, env=None, capture_output=None, text=None):
        return dummy_result

    monkeypatch.setattr(main, "subprocess", SimpleNamespace(run=fake_run))

    resp = client.post("/system/checks/run")
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "passed"
    assert data["total_steps"] == 3


def test_holding_updated_at_refreshes(authenticated_client):
    client = authenticated_client
    bot_id = _create_bot(client)
    payload = {
        "symbol": "BIST:AKBNK",
        "avg_price": 12.5,
        "size": 100,
        "note": "Uzun vade",
    }

    create_resp = client.post(f"/bots/{bot_id}/holdings", json=payload)
    assert create_resp.status_code == 201
    holding_first = create_resp.json()
    first_updated_at = datetime.fromisoformat(holding_first["updated_at"])

    update_payload = {
        "symbol": "BIST:AKBNK",
        "avg_price": 13.0,
        "size": 120,
        "note": "Pozisyon artırıldı",
    }

    update_resp = client.post(f"/bots/{bot_id}/holdings", json=update_payload)
    assert update_resp.status_code == 201
    holding_updated = update_resp.json()
    second_updated_at = datetime.fromisoformat(holding_updated["updated_at"])

    assert second_updated_at > first_updated_at
