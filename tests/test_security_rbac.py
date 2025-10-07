import base64
import hashlib
import hmac
import base64
import hashlib
import hmac
import struct
import time

import pytest


@pytest.mark.parametrize("endpoint", ["/bots", "/chats", "/metrics"])
def test_requires_api_key(endpoint, api_client):
    response = api_client.get(endpoint)
    assert response.status_code == 401


def test_viewer_access_with_session_cookie(authenticated_client):
    response = authenticated_client.get("/bots")
    assert response.status_code == 200


def test_admin_only_endpoint_rejects_operator(api_client):
    from database import create_api_user

    operator_info = create_api_user(
        "operator",
        "Password!123",
        role="operator",
        api_key="operator-key",
        mfa_secret="JBSWY3DPEHPK3PZQ",
    )
    response = api_client.delete("/bots/999", headers={"X-API-Key": operator_info["api_key"]})
    assert response.status_code == 403


def test_login_with_totp_rotates_api_key(api_client):
    from database import create_api_user

    user_info = create_api_user(
        "mfauser",
        "Rotate!234",
        role="admin",
        api_key="login-key",
        mfa_secret="JBSWY3DPEHPK3P5X",
    )
    totp_code = _generate_totp(user_info["mfa_secret"])
    payload = {"username": "mfauser", "password": "Rotate!234", "totp": totp_code}
    response = api_client.post("/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"
    new_key = data["api_key"]
    assert new_key and new_key != user_info["api_key"]

    # Session cookie should allow authenticated access without header
    session_cookie = response.cookies.get("piyasa.session")
    assert session_cookie
    cookie_response = api_client.get("/bots")
    assert cookie_response.status_code == 200

    # Old key should no longer work
    api_client.cookies.clear()
    old_response = api_client.get(
        "/bots",
        headers={"X-API-Key": user_info["api_key"]},
    )
    assert old_response.status_code == 401

    # New key should succeed
    new_response = api_client.get(
        "/bots",
        headers={"X-API-Key": new_key},
    )
    assert new_response.status_code == 200


def _generate_totp(secret: str, step: int = 30, digits: int = 6) -> str:
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded.upper())
    counter = int(time.time() // step)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = digest[offset: offset + 4]
    num = struct.unpack(">I", code)[0] & 0x7FFFFFFF
    return str(num % (10 ** digits)).zfill(digits)


def test_dashboard_websocket_stream(authenticated_client):
    with authenticated_client.websocket_connect("/ws/dashboard") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "dashboard_snapshot"
        assert "metrics" in message
        websocket.close()
