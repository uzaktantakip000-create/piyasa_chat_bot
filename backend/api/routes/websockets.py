"""
WebSocket routes - real-time dashboard updates.
"""
import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from database import SystemCheck, SessionLocal, get_user_by_session_token, get_user_by_api_key
from backend.api.dependencies import SESSION_COOKIE_NAME, _parse_session_cookie, _role_allows
from backend.api.routes.metrics import _calculate_metrics, _system_check_to_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


def _build_dashboard_snapshot() -> Dict[str, Any]:
    """Build a snapshot of current dashboard state (metrics + latest check)."""
    db = SessionLocal()
    try:
        metrics_model = _calculate_metrics(db)
        latest_check = db.query(SystemCheck).order_by(SystemCheck.created_at.desc()).first()
        latest_payload = (
            json.loads(_system_check_to_response(latest_check).json()) if latest_check else None
        )
        return {
            "type": "dashboard_snapshot",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": json.loads(metrics_model.json()),
            "latest_check": latest_payload,
        }
    finally:
        db.close()


@router.websocket("/ws/dashboard")
async def dashboard_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.

    Sends periodic snapshots of system metrics and latest system check.
    Requires authentication (session cookie or API key).
    """
    interval = float(os.getenv("DASHBOARD_STREAM_INTERVAL", "5"))
    max_messages = int(os.getenv("DASHBOARD_STREAM_MAX_MESSAGES", "0"))
    sent = 0

    # Authenticate
    cookie_header = websocket.headers.get("cookie")
    session_token = _parse_session_cookie(cookie_header)
    api_key = websocket.headers.get("X-API-Key") or websocket.query_params.get("api_key")

    db = SessionLocal()
    try:
        user = None
        if session_token:
            user = get_user_by_session_token(db, session_token)
        if not user:
            user = get_user_by_api_key(db, api_key or "")
    finally:
        db.close()

    if not user:
        await websocket.close(code=4401)
        return
    if not _role_allows(user.role, "viewer"):
        await websocket.close(code=4403)
        return

    await websocket.accept()
    logger.info("Dashboard websocket connected for user %s", user.username)

    try:
        while True:
            payload = _build_dashboard_snapshot()
            await websocket.send_json(payload)
            sent += 1

            # For testing: limit number of messages if configured
            if max_messages and sent >= max_messages:
                break

            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        logger.info("Dashboard websocket disconnected for user %s", user.username)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Dashboard websocket error for user %s: %s", user.username, exc)
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
