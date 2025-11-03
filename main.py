from __future__ import annotations

import os
import sys
import json
import logging
import subprocess
import time
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from pathlib import Path
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
load_dotenv()  # .env dosyasını yükler

import redis
from fastapi import Body, Depends, HTTPException, Query, Response, status
from fastapi import Depends, FastAPI, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
from pydantic import BaseModel, Field, AnyHttpUrl, ValidationError, parse_obj_as
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import (
    Bot,
    Chat,
    Setting,
    Message,
    SystemCheck,
    get_db,
    SessionLocal,
    create_tables,
    init_default_settings,
    BotStance,
    BotHolding,
    migrate_plain_tokens,
    ensure_default_admin_user,
    get_user_by_api_key,
    get_user_by_session_token,
    authenticate_user,
    rotate_user_api_key,
    create_user_session,
    invalidate_session,
    purge_expired_sessions,
)
from schemas import (
    BotCreate, BotUpdate, BotResponse,
    ChatCreate, ChatUpdate, ChatResponse,
    SettingResponse, MetricsResponse,
    PersonaProfile,
    EmotionProfile,
    StanceCreate, StanceUpdate, StanceResponse,
    HoldingCreate, HoldingUpdate, HoldingResponse,
    HealthCheckStatus,
    SystemCheckCreate,
    SystemCheckResponse,
    SystemCheckSummaryBucket,
    SystemCheckSummaryResponse,
    SystemCheckSummaryInsight,
    SystemCheckSummaryRun,
    LoginRequest,
    LoginResponse,
    RotateApiKeyRequest,
    UserInfoResponse,
)
from security import mask_token, SecurityConfigError
from settings_utils import normalize_message_length_profile, unwrap_setting_value

# Cache invalidation helpers
try:
    from backend.caching.bot_cache_helpers import invalidate_bot_cache
    from backend.caching.message_cache_helpers import invalidate_chat_message_cache
    CACHE_AVAILABLE = True
except ImportError:
    logger.warning("Cache modules not available - cache invalidation disabled")
    CACHE_AVAILABLE = False
    # Define no-op functions
    def invalidate_bot_cache(bot_id: int) -> None:
        pass
    def invalidate_chat_message_cache(chat_id: int) -> None:
        pass

logger = logging.getLogger("api")
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))

APP_ROOT = Path(__file__).resolve().parent

app = FastAPI(title="Telegram Market Simulation API", version="1.5.0")

SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "piyasa.session")
SESSION_TTL_HOURS = int(os.getenv("DASHBOARD_SESSION_TTL_HOURS", "12"))
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "lax")
SESSION_COOKIE_PATH = os.getenv("SESSION_COOKIE_PATH", "/")
SESSION_MAX_AGE = SESSION_TTL_HOURS * 3600

# ----------------------
# CORS
# ----------------------
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if allowed_origins_env:
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
else:
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------
# PROMETHEUS METRICS
# ----------------------
# Prometheus monitoring setup - Her HTTP isteği otomatik ölçülecek
try:
    from backend.metrics import setup_metrics
    setup_metrics(app)
    logger.info("✅ Prometheus metrics aktif: /metrics endpoint hazır")
except ImportError as e:
    logger.warning(f"⚠️ Prometheus metrics yüklenemedi: {e}")
except Exception as e:
    logger.error(f"❌ Prometheus metrics setup hatası: {e}")


class AuthenticatedUser(BaseModel):
    username: str
    role: str


_ROLE_PRIORITY = {
    "viewer": 1,
    "operator": 2,
    "admin": 3,
}


def _role_allows(user_role: str, required_role: str) -> bool:
    user_score = _ROLE_PRIORITY.get(user_role, 0)
    required_score = _ROLE_PRIORITY.get(required_role, 0)
    return user_score >= required_score


def _parse_session_cookie(raw_cookie: Optional[str]) -> Optional[str]:
    if not raw_cookie:
        return None
    cookie = SimpleCookie()
    try:
        cookie.load(raw_cookie)
    except Exception:
        return None
    morsel = cookie.get(SESSION_COOKIE_NAME)
    if not morsel:
        return None
    return morsel.value


def require_role(required_role: str = "viewer"):
    async def dependency(
        request: Request,
        x_api_key: str = Header(None, alias="X-API-Key"),
        db: Session = Depends(get_db),
    ) -> AuthenticatedUser:
        if request.method == "OPTIONS":
            viewer = AuthenticatedUser(username="cors", role="viewer")
            request.state.user = viewer
            return viewer

        session_token = request.cookies.get(SESSION_COOKIE_NAME)
        if session_token:
            session_user = get_user_by_session_token(db, session_token)
            if session_user:
                if not _role_allows(session_user.role, required_role):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
                request.state.user = session_user
                return AuthenticatedUser(username=session_user.username, role=session_user.role)

        expected = os.getenv("API_KEY")
        if expected and x_api_key == expected:
            env_user = AuthenticatedUser(username="env-admin", role="admin")
            request.state.user = env_user
            return env_user

        user = get_user_by_api_key(db, x_api_key or "")
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
        if not _role_allows(user.role, required_role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        request.state.user = user
        return AuthenticatedUser(username=user.username, role=user.role)

    return dependency


viewer_dependencies = [Depends(require_role("viewer"))]
operator_dependencies = [Depends(require_role("operator"))]
admin_dependencies = [Depends(require_role("admin"))]

# ----------------------
# Redis util (optional)
# ----------------------
_redis_connection_pool: Optional[redis.ConnectionPool] = None
_redis_available = False

def _init_redis_pool() -> None:
    """Initialize Redis connection pool with health check."""
    global _redis_connection_pool, _redis_available

    url = os.getenv("REDIS_URL")
    if not url:
        logger.info("REDIS_URL not set; Redis features disabled (config sync, caching)")
        _redis_available = False
        return

    try:
        # Create connection pool with reasonable timeouts
        _redis_connection_pool = redis.ConnectionPool.from_url(
            url,
            decode_responses=True,
            max_connections=10,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
        )

        # Test connection
        client = redis.Redis(connection_pool=_redis_connection_pool)
        client.ping()
        _redis_available = True
        logger.info("Redis connection established: %s", url.split("@")[-1] if "@" in url else url)
    except Exception as e:
        logger.warning(
            "Redis unavailable: %s. System will continue without Redis features (config sync, caching).",
            e
        )
        _redis_available = False
        _redis_connection_pool = None


def get_redis() -> Optional[redis.Redis]:
    """Get Redis client from pool if available."""
    if not _redis_available or not _redis_connection_pool:
        return None
    try:
        return redis.Redis(connection_pool=_redis_connection_pool)
    except Exception as e:
        logger.debug("Redis client creation failed: %s", e)
        return None


def publish_config_update(r: Optional[redis.Redis], payload: Dict[str, Any]):
    """Publish configuration update to Redis channel with fallback."""
    if not r:
        logger.debug("Redis unavailable; config update not published: %s", payload.get("type"))
        return
    try:
        r.publish("config_updates", json.dumps(payload))
        logger.debug("Config update published to Redis: %s", payload.get("type"))
    except Exception as e:
        logger.warning("Redis publish failed: %s. Config update skipped (not critical).", e)

# ----------------------
# Startup
# ----------------------
@app.on_event("startup")
def _startup():
    create_tables()
    init_default_settings()
    migrate_plain_tokens()
    _init_redis_pool()  # Initialize Redis connection pool with health check
    admin_info = ensure_default_admin_user()
    if admin_info:
        masked_api = mask_token(admin_info["api_key"])
        masked_mfa = mask_token(admin_info["mfa_secret"])
        logger.warning(
            "Default admin user '%s' created. Store the credentials securely. API Key: %s (masked), MFA Secret: %s (masked)",
            admin_info["username"],
            masked_api,
            masked_mfa,
        )
    try:
        purged = purge_expired_sessions()
        if purged:
            logger.info("Purged %d expired API sessions during startup", purged)
    except Exception as exc:
        logger.warning("Failed to purge expired sessions: %s", exc)

    logger.info("API started. Tables ensured; default settings loaded.")


def _bot_to_response(db_bot: Bot) -> BotResponse:
    try:
        plain_token = db_bot.token
    except SecurityConfigError:
        logger.error("Bot token decrypt failed for bot_id=%s. Check TOKEN_ENCRYPTION_KEY.", db_bot.id)
        plain_token = ""

    masked = mask_token(plain_token)
    return BotResponse(
        id=db_bot.id,
        name=db_bot.name,
        token_masked=masked,
        has_token=bool(db_bot.token_encrypted),
        username=db_bot.username,
        is_enabled=db_bot.is_enabled,
        speed_profile=db_bot.speed_profile or {},
        active_hours=db_bot.active_hours or [],
        persona_hint=db_bot.persona_hint,
        emotion_profile=db_bot.emotion_profile or {},
        created_at=db_bot.created_at,
    )

# ----------------------
# Basic endpoints
# ----------------------
@app.get("/healthz")
def healthz(db: Session = Depends(get_db)):
    """
    Comprehensive health check endpoint for production readiness.

    Checks:
    - API availability (implicit - endpoint responds)
    - Database connectivity
    - Redis connectivity
    - Basic system status

    Returns HTTP 200 if healthy, HTTP 503 if degraded/unhealthy.
    """
    health_data = {
        "ok": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "healthy",
        "checks": {}
    }

    # Check 1: Database connectivity
    try:
        # Simple DB query to verify connection
        db.execute(text("SELECT 1"))
        health_data["checks"]["database"] = {"status": "healthy", "message": "Connected"}
    except Exception as e:
        health_data["ok"] = False
        health_data["status"] = "unhealthy"
        health_data["checks"]["database"] = {"status": "unhealthy", "message": str(e)[:100]}

    # Check 2: Redis connectivity
    redis_status = "connected" if _redis_available else "unavailable"
    if _redis_available:
        try:
            # Test Redis with a ping
            redis_pool = get_redis()
            if redis_pool:
                redis_pool.ping()
                health_data["checks"]["redis"] = {"status": "healthy", "message": "Connected"}
            else:
                health_data["checks"]["redis"] = {"status": "degraded", "message": "Pool unavailable"}
        except Exception as e:
            health_data["checks"]["redis"] = {"status": "degraded", "message": str(e)[:100]}
    else:
        health_data["checks"]["redis"] = {"status": "unavailable", "message": "Not configured"}

    # Check 3: Worker metrics (optional - if workers are reporting)
    try:
        # Check if we have recent worker activity (last 5 minutes)
        from database import Message
        five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        recent_count = db.query(Message).filter(Message.created_at >= five_min_ago).count()

        if recent_count > 0:
            health_data["checks"]["workers"] = {
                "status": "healthy",
                "message": f"{recent_count} messages in last 5 min"
            }
        else:
            health_data["checks"]["workers"] = {
                "status": "warning",
                "message": "No recent activity (may be intentional)"
            }
    except Exception as e:
        health_data["checks"]["workers"] = {"status": "unknown", "message": str(e)[:100]}

    # Determine overall status
    if not health_data["ok"]:
        # Critical failure (database down)
        health_data["status"] = "unhealthy"
        return JSONResponse(status_code=503, content=health_data)

    # Check for degraded state (redis issues, no worker activity)
    degraded_checks = [
        check for check in health_data["checks"].values()
        if check["status"] in ["degraded", "warning", "unavailable"]
    ]

    if degraded_checks:
        health_data["status"] = "degraded"

    return health_data


@app.post("/auth/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    logger.info("Login attempt for username: %s (totp: %s)", payload.username, bool(payload.totp))
    user = authenticate_user(db, payload.username, payload.password, payload.totp)
    if not user:
        logger.warning("Login failed for username: %s", payload.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials or MFA code")
    api_key = rotate_user_api_key(db, user)
    logger.info("User %s performed login and API key rotation", user.username)
    session_token, session = create_user_session(
        db,
        user,
        ttl_hours=SESSION_TTL_HOURS,
        user_agent=request.headers.get("user-agent"),
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite=SESSION_COOKIE_SAMESITE,
        path=SESSION_COOKIE_PATH,
    )
    response.headers["X-Session-Expires"] = session.expires_at.replace(microsecond=0).isoformat() + "Z"
    return LoginResponse(api_key=api_key, role=user.role, session_expires_at=session.expires_at)


@app.post("/auth/rotate-api-key", response_model=LoginResponse)
def rotate_api_key(payload: RotateApiKeyRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password, payload.totp)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials or MFA code")
    api_key = rotate_user_api_key(db, user)
    logger.info("User %s manually rotated API key", user.username)
    return LoginResponse(api_key=api_key, role=user.role)


@app.post("/auth/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        invalidate_session(db, token)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path=SESSION_COOKIE_PATH,
        samesite=SESSION_COOKIE_SAMESITE,
    )
    return {"ok": True}


@app.get("/auth/me", response_model=UserInfoResponse, dependencies=viewer_dependencies)
def me(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing user context")
    return UserInfoResponse(
        username=user.username,
        role=user.role,
        api_key_last_rotated=user.api_key_last_rotated,
    )

# ----- Bots -----


@app.post("/bots", response_model=BotResponse, status_code=status.HTTP_201_CREATED, dependencies=operator_dependencies)
def create_bot(bot: BotCreate, db: Session = Depends(get_db)):
    db_bot = Bot(
        name=bot.name,
        token=bot.token,
        username=bot.username,
        is_enabled=bot.is_enabled,
        speed_profile=bot.speed_profile,
        active_hours=bot.active_hours,
        persona_hint=bot.persona_hint,
        emotion_profile=bot.emotion_profile or {},
    )
    db.add(db_bot)
    db.commit()
    db.refresh(db_bot)
    publish_config_update(get_redis(), {"type": "bot_added", "bot_id": db_bot.id})
    return _bot_to_response(db_bot)

@app.get("/bots", response_model=List[BotResponse], dependencies=viewer_dependencies)
def list_bots(db: Session = Depends(get_db)):
    bots = db.query(Bot).order_by(Bot.id.asc()).all()
    return [_bot_to_response(bot) for bot in bots]

@app.patch("/bots/{bot_id}", response_model=BotResponse, dependencies=operator_dependencies)
def update_bot(bot_id: int, patch: BotUpdate, db: Session = Depends(get_db)):
    db_bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not db_bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    for field, value in patch.dict(exclude_unset=True).items():
        setattr(db_bot, field, value)

    db.commit()
    db.refresh(db_bot)

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(db_bot.id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {db_bot.id}: {e}")

    publish_config_update(get_redis(), {"type": "bot_updated", "bot_id": db_bot.id})
    return _bot_to_response(db_bot)

@app.delete("/bots/{bot_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=admin_dependencies)
def delete_bot(bot_id: int, db: Session = Depends(get_db)):
    db_bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not db_bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    db.delete(db_bot)
    db.commit()

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(bot_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {bot_id}: {e}")

    publish_config_update(get_redis(), {"type": "bot_deleted", "bot_id": bot_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# ----- Chats -----
@app.post("/chats", response_model=ChatResponse, status_code=status.HTTP_201_CREATED, dependencies=operator_dependencies)
def create_chat(chat: ChatCreate, db: Session = Depends(get_db)):
    db_chat = Chat(chat_id=chat.chat_id, title=chat.title, is_enabled=chat.is_enabled, topics=chat.topics)
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    publish_config_update(get_redis(), {"type": "chat_added", "chat_id": db_chat.id})
    return db_chat

@app.get("/chats", response_model=List[ChatResponse], dependencies=viewer_dependencies)
def list_chats(db: Session = Depends(get_db)):
    chats = db.query(Chat).order_by(Chat.id.asc()).all()
    return chats


@app.patch("/chats/{chat_id}", response_model=ChatResponse, dependencies=operator_dependencies)
def update_chat(chat_id: int, patch: ChatUpdate, db: Session = Depends(get_db)):
    db_chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    for field, value in patch.dict(exclude_unset=True).items():
        setattr(db_chat, field, value)

    db.commit()
    db.refresh(db_chat)
    publish_config_update(get_redis(), {"type": "chat_updated", "chat_id": chat_id})
    return db_chat


@app.delete("/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=operator_dependencies)
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    db_chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Store chat_id before deletion
    deleted_chat_id = db_chat.chat_id

    db.delete(db_chat)
    db.commit()

    # Invalidate message cache for this chat
    try:
        invalidate_chat_message_cache(deleted_chat_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for chat {deleted_chat_id}: {e}")

    publish_config_update(get_redis(), {"type": "chat_deleted", "chat_id": chat_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----- System Checks -----
def _system_check_to_response(db_obj: SystemCheck) -> SystemCheckResponse:
    details = db_obj.details or {}
    steps = details.get("steps", [])
    health_checks = details.get("health_checks", [])
    return SystemCheckResponse(
        id=db_obj.id,
        status=db_obj.status,
        total_steps=db_obj.total_steps,
        passed_steps=db_obj.passed_steps,
        failed_steps=db_obj.failed_steps,
        duration=db_obj.duration,
        triggered_by=db_obj.triggered_by,
        steps=steps,
        health_checks=health_checks,
        created_at=db_obj.created_at,
    )


@app.post("/system/checks", response_model=SystemCheckResponse, status_code=status.HTTP_201_CREATED, dependencies=operator_dependencies)
def create_system_check(payload: SystemCheckCreate, db: Session = Depends(get_db)):
    db_obj = SystemCheck(
        status=payload.status,
        total_steps=payload.total_steps,
        passed_steps=payload.passed_steps,
        failed_steps=payload.failed_steps,
        duration=payload.duration,
        triggered_by=payload.triggered_by,
        details={
            "steps": [step.dict() for step in payload.steps],
            "health_checks": [hc.dict() for hc in payload.health_checks],
        },
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return _system_check_to_response(db_obj)


@app.get("/system/checks/latest", response_model=Optional[SystemCheckResponse], dependencies=viewer_dependencies)
def get_latest_system_check(db: Session = Depends(get_db)):
    obj = (
        db.query(SystemCheck)
        .order_by(SystemCheck.created_at.desc())
        .first()
    )
    if not obj:
        return None
    return _system_check_to_response(obj)


@app.get(
    "/system/checks/summary",
    response_model=SystemCheckSummaryResponse,
    dependencies=viewer_dependencies,
)
def get_system_check_summary(
    window_days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(days=window_days)

    checks = (
        db.query(SystemCheck)
        .filter(SystemCheck.created_at >= window_start)
        .order_by(SystemCheck.created_at.asc())
        .all()
    )

    total_runs = len(checks)
    passed_runs = sum(1 for check in checks if check.status.lower() == "passed")
    failed_runs = total_runs - passed_runs
    durations = [check.duration for check in checks if check.duration is not None]
    average_duration = round(sum(durations) / len(durations), 2) if durations else None
    last_run_at = checks[-1].created_at if checks else None

    per_day = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
    for check in checks:
        bucket = per_day[check.created_at.date()]
        bucket["total"] += 1
        if check.status.lower() == "passed":
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1

    daily_breakdown = [
        SystemCheckSummaryBucket(
            date=day,
            total=data["total"],
            passed=data["passed"],
            failed=data["failed"],
        )
        for day, data in sorted(per_day.items())
    ]

    recent_runs = [
        SystemCheckSummaryRun(
            id=check.id,
            status=check.status,
            created_at=check.created_at,
            duration=check.duration,
            triggered_by=check.triggered_by,
            total_steps=check.total_steps,
            passed_steps=check.passed_steps,
            failed_steps=check.failed_steps,
        )
        for check in sorted(checks, key=lambda record: record.created_at, reverse=True)[:5]
    ]

    success_rate = round(passed_runs / total_runs, 4) if total_runs else 0.0

    insight_messages = set()
    insights: List[SystemCheckSummaryInsight] = []
    recommended_actions: List[str] = []

    def add_insight(level: str, message: str) -> None:
        if not message or message in insight_messages:
            return
        insights.append(SystemCheckSummaryInsight(level=level, message=message))
        insight_messages.add(message)

    def add_action(text: str) -> None:
        if not text:
            return
        if text not in recommended_actions:
            recommended_actions.append(text)

    overall_status: str = "empty" if total_runs == 0 else "healthy"
    overall_message = (
        f"Son {window_days} gün içinde otomasyon testi kaydı bulunmuyor."
        if total_runs == 0
        else "Otomasyon koşuları sağlıklı görünüyor."
    )

    def update_status(level: str, message: Optional[str] = None) -> None:
        nonlocal overall_status, overall_message
        priority = {"empty": 0, "healthy": 1, "warning": 2, "critical": 3}
        if priority.get(level, 0) > priority.get(overall_status, 0):
            overall_status = level
            if message:
                overall_message = message
        elif level == overall_status and message:
            overall_message = message

    now = datetime.now(timezone.utc)
    hours_since_last_run: Optional[float] = None
    if last_run_at is not None:
        # Ensure last_run_at is timezone-aware for comparison
        if last_run_at.tzinfo is None:
            last_run_at = last_run_at.replace(tzinfo=timezone.utc)
        hours_since_last_run = (now - last_run_at).total_seconds() / 3600.0

    if total_runs == 0:
        add_insight("info", "Henüz otomasyon raporu oluşmamış. İlk testi çalıştırın.")
        add_action("Panelden \"Testleri çalıştır\" butonunu kullanarak ilk kontrolü başlatın.")
    else:
        if failed_runs > 0:
            failure_ratio = failed_runs / total_runs
            severity = "critical" if failure_ratio >= 0.3 or success_rate < 0.7 else "warning"
            message = (
                "Testlerin önemli bir kısmı başarısız; aksiyon alınmalı."
                if severity == "critical"
                else "Bazı otomasyon adımları başarısız sonuçlandı."
            )
            update_status(severity, message)
            add_insight(
                severity,
                f"Son {total_runs} koşunun {failed_runs} tanesi başarısız oldu (başarı oranı %{round(success_rate * 100, 1)}).",
            )
            add_action("Hata veren adımların loglarını inceleyip testleri yeniden çalıştırın.")
        else:
            add_insight("success", "Son otomasyon koşularının tamamı başarılı tamamlandı.")

        if failed_runs == 0 and success_rate >= 0.95:
            add_insight("success", "Başarı oranı %{:.1f} ile hedef seviyede.".format(success_rate * 100))
        elif failed_runs == 0:
            add_insight("info", "Başarı oranı %{:.1f} seviyesinde.".format(success_rate * 100))

        if average_duration is not None:
            if average_duration > 20:
                update_status("warning", "Test süreleri uzamış görünüyor; altyapıyı kontrol edin.")
                add_insight(
                    "warning",
                    f"Ortalama test süresi {average_duration:.1f} sn; bu değer önceki günlerden yüksek olabilir.",
                )
                add_action("Uzun süren adımların loglarını inceleyin ve gerekli optimizasyonları planlayın.")
            elif failed_runs == 0:
                add_insight("success", f"Ortalama test süresi {average_duration:.1f} sn ile sağlıklı görünüyor.")

        if hours_since_last_run is not None:
            if hours_since_last_run > 24:
                update_status("critical", "Son otomasyon koşusu 24 saatten eski; yeni bir koşu başlatın.")
                add_insight("critical", "Son otomasyon koşusu 24 saatten daha eski.")
                add_action("Güncel sonuç almak için otomasyon testlerini yeniden başlatın.")
            elif hours_since_last_run > 12:
                update_status("warning", "Son otomasyon koşusu 12 saatten eski; yeni koşu planlayın.")
                add_insight("warning", "Son otomasyon koşusu 12 saatten daha eski.")
                add_action("Testleri manuel olarak tetikleyin veya zamanlayıcıyı gözden geçirin.")
            elif failed_runs == 0:
                add_insight("success", "Son otomasyon koşusu son 12 saat içinde tamamlandı.")

    if overall_status == "healthy" and not insights:
        add_insight("success", "Otomasyon koşuları stabil şekilde çalışıyor.")

    return SystemCheckSummaryResponse(
        window_start=window_start,
        window_end=window_end,
        total_runs=total_runs,
        passed_runs=passed_runs,
        failed_runs=failed_runs,
        success_rate=success_rate,
        average_duration=average_duration,
        last_run_at=last_run_at,
        daily_breakdown=daily_breakdown,
        overall_status=overall_status,
        overall_message=overall_message,
        insights=insights,
        recommended_actions=recommended_actions,
        recent_runs=recent_runs,
    )


def _run_step(name: str, cmd: List[str], env: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(APP_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    duration = time.time() - started
    return {
        "name": name,
        "success": proc.returncode == 0,
        "duration": duration,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


@app.post("/system/checks/run", response_model=SystemCheckResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=operator_dependencies)
def run_system_checks(db: Session = Depends(get_db)):
    env = os.environ.copy()
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    env.setdefault("API_BASE", os.getenv("API_BASE", "http://localhost:8000"))

    steps = [
        _run_step("preflight", [sys.executable, "preflight.py"], env=env),
        _run_step(
            "pytest",
            [sys.executable, "-m", "pytest", "-q", "tests/test_api_flows.py", "tests/test_content_filters.py"],
            env=env,
        ),
        _run_step(
            "stress-test",
            [
                sys.executable,
                "scripts/stress_test.py",
                "--duration",
                os.getenv("SYSTEM_CHECK_STRESS_DURATION", "15"),
                "--concurrency",
                os.getenv("SYSTEM_CHECK_STRESS_CONCURRENCY", "2"),
            ],
            env=env,
        ),
    ]

    total = len(steps)
    passed = sum(1 for step in steps if step["success"])
    failed = total - passed
    total_duration = sum(step["duration"] for step in steps)
    status_value = "passed" if failed == 0 else "failed"

    db_obj = SystemCheck(
        status=status_value,
        total_steps=total,
        passed_steps=passed,
        failed_steps=failed,
        duration=total_duration,
        triggered_by="dashboard",
        details={"steps": steps, "health_checks": []},
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    return _system_check_to_response(db_obj)

# ----- Settings -----
def _unwrap_or_default(row: Optional[Setting], default: Any) -> Any:
    if row is None:
        return default
    value = unwrap_setting_value(row.value)
    return default if value is None else value


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off", ""}:
            return False
    if value is None:
        return default
    return bool(value)


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def _normalize_setting_value(key: str, raw: Any) -> Dict[str, Any]:
    if key == "message_length_profile":
        normalized = normalize_message_length_profile(raw)
        return {"value": normalized}
    if isinstance(raw, dict) and "value" in raw and len(raw) == 1:
        return raw
    return {"value": raw}


def _setting_to_response(row: Setting) -> SettingResponse:
    return SettingResponse(
        key=row.key,
        value=_normalize_setting_value(row.key, row.value),
        updated_at=row.updated_at,
    )


def _normalize_news_feed_urls(value: Any) -> List[str]:
    if isinstance(value, dict) and "value" in value and len(value) == 1:
        value = value["value"]

    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        raise HTTPException(status_code=400, detail="news_feed_urls değeri liste olmalıdır.")

    normalized: List[str] = []
    for item in candidates:
        item_str = str(item or "").strip()
        if not item_str:
            continue
        try:
            parsed = parse_obj_as(AnyHttpUrl, item_str)
        except ValidationError:
            raise HTTPException(status_code=400, detail=f"Geçersiz RSS adresi: {item_str}")
        parsed_str = str(parsed)
        if parsed_str not in normalized:
            normalized.append(parsed_str)

    return normalized


# ----- Cache Stats -----
@app.get("/cache/stats", dependencies=viewer_dependencies)
def get_cache_stats():
    """
    Get cache statistics for monitoring.

    Returns L1 and L2 cache statistics including hit rates, sizes, and availability.
    """
    try:
        from backend.caching.cache_manager import CacheManager
        cache = CacheManager.get_instance()
        stats = cache.get_stats()
        return {
            "ok": True,
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("Cache stats error")
        return {
            "ok": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ----- Settings -----
@app.get("/settings", response_model=List[SettingResponse], dependencies=viewer_dependencies)
def list_settings(db: Session = Depends(get_db)):
    rows = db.query(Setting).order_by(Setting.key.asc()).all()
    return [_setting_to_response(row) for row in rows]


def _set_setting(db: Session, key: str, value: Any):
    row = db.query(Setting).filter(Setting.key == key).first()
    if not row:
        row = Setting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()
    db.refresh(row)
    return row

# >>> NEW: bulk settings update <<<
class SettingsBulkUpdate(BaseModel):
    updates: Dict[str, Any] = Field(default_factory=dict)

@app.put("/settings/bulk", response_model=List[SettingResponse], dependencies=admin_dependencies)
def update_settings_bulk(body: SettingsBulkUpdate, db: Session = Depends(get_db)):
    if not body.updates:
        raise HTTPException(400, "No updates provided")
    changed: List[str] = []
    out: List[Setting] = []
    for k, v in body.updates.items():
        if k == "message_length_profile":
            v = normalize_message_length_profile(v)
        if k == "news_feed_urls":
            v = _normalize_news_feed_urls(v)
        row = db.query(Setting).filter(Setting.key == k).first()
        if not row:
            row = Setting(key=k, value=v)
            db.add(row)
        else:
            row.value = v
        changed.append(k)
        out.append(row)
    db.commit()
    for row in out:
        db.refresh(row)
    publish_config_update(get_redis(), {"type": "settings_updated", "keys": changed})
    return [_setting_to_response(row) for row in out]


class SettingUpdate(BaseModel):
    value: Any


@app.patch("/settings/{key}", response_model=SettingResponse, dependencies=admin_dependencies)
def update_setting(key: str, payload: SettingUpdate, db: Session = Depends(get_db)):
    value = payload.value
    if key == "message_length_profile":
        value = normalize_message_length_profile(value)
    if key == "news_feed_urls":
        value = _normalize_news_feed_urls(value)
    row = db.query(Setting).filter(Setting.key == key).first()
    if not row:
        row = Setting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()
    db.refresh(row)
    publish_config_update(get_redis(), {"type": "settings_updated", "keys": [key]})
    return _setting_to_response(row)

# Control: start/stop/scale
@app.post("/control/start", dependencies=operator_dependencies)
def control_start(db: Session = Depends(get_db)):
    _set_setting(db, "simulation_active", True)
    publish_config_update(get_redis(), {"type": "control", "simulation_active": True})
    return {"ok": True}

@app.post("/control/stop", dependencies=operator_dependencies)
def control_stop(db: Session = Depends(get_db)):
    _set_setting(db, "simulation_active", False)
    publish_config_update(get_redis(), {"type": "control", "simulation_active": False})
    return {"ok": True}

class ScalePayload(BaseModel):
    factor: float = Field(1.0, gt=0)


@app.post("/control/scale", dependencies=operator_dependencies)
def control_scale(
    factor: Optional[float] = Query(default=None, gt=0),
    body: Optional[ScalePayload] = Body(default=None),
    db: Session = Depends(get_db),
):
    resolved = factor
    if resolved is None and body is not None:
        resolved = body.factor
    if resolved is None:
        resolved = 1.0
    factor_value = float(resolved)
    if factor_value <= 0:
        raise HTTPException(400, "factor must be > 0")
    _set_setting(db, "scale_factor", factor_value)
    publish_config_update(get_redis(), {"type": "scale", "factor": factor_value})
    return {"ok": True, "factor": factor_value}

# ----- Metrics -----
def _calculate_metrics(db: Session) -> MetricsResponse:
    total_bots = db.query(Bot).count()
    active_bots = db.query(Bot).filter(Bot.is_enabled.is_(True)).count()
    total_chats = db.query(Chat).count()

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    last_hour_msgs = db.query(Message).filter(Message.created_at >= one_hour_ago).count()
    per_min = round(last_hour_msgs / 60.0, 3)

    sim_active_row = db.query(Setting).filter(Setting.key == "simulation_active").first()
    scale_row = db.query(Setting).filter(Setting.key == "scale_factor").first()
    rl_row = db.query(Setting).filter(Setting.key == "rate_limit_hits").first()
    tg429_row = db.query(Setting).filter(Setting.key == "telegram_429_count").first()
    tg5xx_row = db.query(Setting).filter(Setting.key == "telegram_5xx_count").first()

    sim_value = _unwrap_or_default(sim_active_row, False)
    scale_value = _unwrap_or_default(scale_row, 1.0)
    rl_value = _unwrap_or_default(rl_row, None)
    tg429_value = _unwrap_or_default(tg429_row, 0)
    tg5xx_value = _unwrap_or_default(tg5xx_row, 0)

    # Geri uyumluluk: rate_limit_hits yoksa telegram_5xx_count değerini göster
    rate_limit_hits = _as_int(rl_value, 0) if rl_value is not None else _as_int(tg5xx_value, 0)
    telegram_429_count = _as_int(tg429_value, 0)
    telegram_5xx_count = _as_int(tg5xx_value, 0)

    return MetricsResponse(
        total_bots=total_bots,
        active_bots=active_bots,
        total_chats=total_chats,
        messages_last_hour=last_hour_msgs,
        messages_per_minute=per_min,
        simulation_active=_as_bool(sim_value, False),
        scale_factor=_as_float(scale_value, 1.0),
        rate_limit_hits=rate_limit_hits,
        telegram_429_count=telegram_429_count,
        telegram_5xx_count=telegram_5xx_count,
    )


@app.get("/metrics", response_model=MetricsResponse, dependencies=viewer_dependencies)
def metrics(db: Session = Depends(get_db)):
    return _calculate_metrics(db)


@app.get("/queue/stats", dependencies=viewer_dependencies)
def queue_stats():
    """
    Get message queue statistics.

    Returns current queue lengths for each priority level.
    """
    try:
        from behavior_engine import _ENGINE

        if _ENGINE is None:
            return {
                "error": "Behavior engine not running",
                "stats": None
            }

        stats = _ENGINE.msg_queue.get_stats()
        return {
            "stats": stats,
            "total_queued": sum(stats.values()) - stats.get("dlq", 0),
            "total_failed": stats.get("dlq", 0),
        }
    except Exception as e:
        logger.exception("Error getting queue stats: %s", e)
        return {
            "error": str(e),
            "stats": None
        }


def _build_dashboard_snapshot() -> Dict[str, Any]:
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


@app.websocket("/ws/dashboard")
async def dashboard_stream(websocket: WebSocket):
    interval = float(os.getenv("DASHBOARD_STREAM_INTERVAL", "5"))
    max_messages = int(os.getenv("DASHBOARD_STREAM_MAX_MESSAGES", "0"))
    sent = 0
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

# ----- Logs (recent) -----
def _serialize_log(message: Message) -> Dict[str, Any]:
    text = message.text or ""
    if len(text) > 100:
        text = text[:100] + "..."
    return {
        "id": message.id,
        "bot_name": message.bot.name if message.bot and message.bot.name else "",
        "chat_title": message.chat.title if message.chat and message.chat.title else "",
        "text": text,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "reply_to": message.reply_to_message_id,
    }


@app.get("/logs", dependencies=viewer_dependencies)
def list_logs(limit: int = 100, db: Session = Depends(get_db)):
    limit = min(max(limit, 1), 1000)
    rows = db.query(Message).order_by(Message.created_at.desc()).limit(limit).all()
    return [_serialize_log(row) for row in rows]


@app.get("/logs/recent", dependencies=viewer_dependencies)
def recent_logs(limit: int = 20, db: Session = Depends(get_db)):
    return list_logs(limit=limit, db=db)

# ==========================================================
# Persona / Stances / Holdings (Mevcut Uçlar)
# ==========================================================

# ----- Persona -----
@app.get("/bots/{bot_id}/persona", dependencies=viewer_dependencies)
def get_persona(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")
    return bot.persona_profile or {}

@app.put("/bots/{bot_id}/persona", dependencies=operator_dependencies)
def put_persona(bot_id: int, profile: PersonaProfile, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")
    bot.persona_profile = profile.dict(exclude_unset=True)
    db.commit()

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(bot_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {bot_id}: {e}")

    publish_config_update(get_redis(), {"type": "persona_updated", "bot_id": bot_id})
    return {"ok": True, "bot_id": bot_id, "persona_profile": bot.persona_profile}


@app.get("/bots/{bot_id}/emotion", dependencies=viewer_dependencies)
def get_emotion_profile(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")
    return bot.emotion_profile or {}


@app.put("/bots/{bot_id}/emotion", dependencies=operator_dependencies)
def put_emotion_profile(bot_id: int, profile: EmotionProfile, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")
    bot.emotion_profile = profile.dict(exclude_unset=True)
    db.commit()

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(bot_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {bot_id}: {e}")

    publish_config_update(get_redis(), {"type": "emotion_updated", "bot_id": bot_id})
    return {"ok": True, "bot_id": bot_id, "emotion_profile": bot.emotion_profile}

# ----- Stances -----
@app.get("/bots/{bot_id}/stances", response_model=List[StanceResponse], dependencies=viewer_dependencies)
def list_stances(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")
    rows = (
        db.query(BotStance)
        .filter(BotStance.bot_id == bot_id)
        .order_by(BotStance.updated_at.desc())
        .all()
    )
    return rows

@app.post("/bots/{bot_id}/stances", response_model=StanceResponse, status_code=201, dependencies=operator_dependencies)
def upsert_stance(bot_id: int, body: StanceCreate, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")

    # Unique: (bot_id, topic) -> upsert
    row = (
        db.query(BotStance)
        .filter(BotStance.bot_id == bot_id, BotStance.topic == body.topic)
        .first()
    )
    if row:
        row.stance_text = body.stance_text
        row.confidence = body.confidence
        row.cooldown_until = body.cooldown_until
    else:
        row = BotStance(
            bot_id=bot_id,
            topic=body.topic,
            stance_text=body.stance_text,
            confidence=body.confidence,
            cooldown_until=body.cooldown_until,
        )
        db.add(row)

    db.commit()
    db.refresh(row)

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(bot_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {bot_id}: {e}")

    publish_config_update(get_redis(), {"type": "stance_upserted", "bot_id": bot_id, "stance_id": row.id})
    return row

@app.patch("/stances/{stance_id}", response_model=StanceResponse, dependencies=operator_dependencies)
def update_stance(stance_id: int, patch: StanceUpdate, db: Session = Depends(get_db)):
    row = db.query(BotStance).filter(BotStance.id == stance_id).first()
    if not row:
        raise HTTPException(404, "Stance not found")

    for k, v in patch.dict(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(row.bot_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {row.bot_id}: {e}")

    publish_config_update(get_redis(), {"type": "stance_updated", "bot_id": row.bot_id, "stance_id": row.id})
    return row

@app.delete("/stances/{stance_id}", status_code=204, dependencies=operator_dependencies)
def delete_stance(stance_id: int, db: Session = Depends(get_db)):
    row = db.query(BotStance).filter(BotStance.id == stance_id).first()
    if not row:
        raise HTTPException(404, "Stance not found")
    bot_id = row.bot_id
    db.delete(row)
    db.commit()

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(bot_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {bot_id}: {e}")

    publish_config_update(get_redis(), {"type": "stance_deleted", "bot_id": bot_id, "stance_id": stance_id})
    return {"ok": True}

# ----- Holdings -----
@app.get("/bots/{bot_id}/holdings", response_model=List[HoldingResponse], dependencies=viewer_dependencies)
def list_holdings(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")
    rows = (
        db.query(BotHolding)
        .filter(BotHolding.bot_id == bot_id)
        .order_by(BotHolding.updated_at.desc())
        .all()
    )
    return rows

@app.post("/bots/{bot_id}/holdings", response_model=HoldingResponse, status_code=201, dependencies=operator_dependencies)
def upsert_holding(bot_id: int, body: HoldingCreate, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")

    # Unique: (bot_id, symbol) -> upsert
    row = (
        db.query(BotHolding)
        .filter(BotHolding.bot_id == bot_id, BotHolding.symbol == body.symbol)
        .first()
    )
    if row:
        if body.avg_price is not None:
            row.avg_price = body.avg_price
        if body.size is not None:
            row.size = body.size
        if body.note is not None:
            row.note = body.note
    else:
        row = BotHolding(
            bot_id=bot_id,
            symbol=body.symbol,
            avg_price=body.avg_price,
            size=body.size,
            note=body.note,
        )
        db.add(row)

    db.commit()
    db.refresh(row)

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(bot_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {bot_id}: {e}")

    publish_config_update(get_redis(), {"type": "holding_upserted", "bot_id": bot_id, "holding_id": row.id})
    return row

@app.patch("/holdings/{holding_id}", response_model=HoldingResponse, dependencies=operator_dependencies)
def update_holding(holding_id: int, patch: HoldingUpdate, db: Session = Depends(get_db)):
    row = db.query(BotHolding).filter(BotHolding.id == holding_id).first()
    if not row:
        raise HTTPException(404, "Holding not found")

    for k, v in patch.dict(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(row.bot_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {row.bot_id}: {e}")

    publish_config_update(get_redis(), {"type": "holding_updated", "bot_id": row.bot_id, "holding_id": row.id})
    return row

@app.delete("/holdings/{holding_id}", status_code=204, dependencies=operator_dependencies)
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    row = db.query(BotHolding).filter(BotHolding.id == holding_id).first()
    if not row:
        raise HTTPException(404, "Holding not found")
    bot_id = row.bot_id
    db.delete(row)
    db.commit()

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(bot_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {bot_id}: {e}")

    publish_config_update(get_redis(), {"type": "holding_deleted", "bot_id": bot_id, "holding_id": holding_id})
    return {"ok": True}

# ==========================================================
# DEMO BOTS — Optimize edilmiş demo botları oluştur
# ==========================================================
class DemoBotsCreate(BaseModel):
    count: int = Field(default=6, ge=1, le=6, description="Oluşturulacak demo bot sayısı (1-6)")

@app.post("/demo-bots/create", dependencies=admin_dependencies)
def create_demo_bots(payload: DemoBotsCreate, db: Session = Depends(get_db)):
    """
    Optimize edilmiş demo bot profillerini oluşturur.
    Token'lar boş bırakılır - kullanıcı panelden doldurur.
    """
    template_path = APP_ROOT / "demo_bots_template.json"
    if not template_path.exists():
        raise HTTPException(404, "Demo bot template bulunamadı")

    with open(template_path, encoding="utf-8") as f:
        template_data = json.load(f)

    bots_data = template_data.get("bots", [])[:payload.count]
    created_bots = []
    skipped_bots = []

    for bot_data in bots_data:
        # Check if bot already exists (by username)
        existing = db.query(Bot).filter(Bot.username == bot_data["username"]).first()
        if existing:
            skipped_bots.append({
                "username": bot_data["username"],
                "reason": "Zaten mevcut"
            })
            continue

        # Create bot with empty token
        bot = Bot(
            name=bot_data["name"],
            token="",  # Token boş - kullanıcı panelden dolduracak
            username=bot_data["username"],
            is_enabled=False,  # Başlangıçta disabled
            speed_profile=bot_data.get("speed_profile", {}),
            active_hours=bot_data.get("active_hours", []),
            persona_hint=bot_data.get("persona_hint", ""),
            persona_profile=bot_data.get("persona_profile", {}),
            emotion_profile=bot_data.get("emotion_profile", {}),
        )
        db.add(bot)
        db.flush()  # ID'yi al

        # Add stances
        for stance_data in bot_data.get("stances", []):
            stance = BotStance(
                bot_id=bot.id,
                topic=stance_data["topic"],
                stance_text=stance_data["stance_text"],
                confidence=stance_data.get("confidence", "orta"),
                cooldown_until=stance_data.get("cooldown_until"),
            )
            db.add(stance)

        # Add holdings
        for holding_data in bot_data.get("holdings", []):
            holding = BotHolding(
                bot_id=bot.id,
                symbol=holding_data["symbol"],
                avg_price=holding_data.get("avg_price"),
                size=holding_data.get("size"),
                note=holding_data.get("note", ""),
            )
            db.add(holding)

        created_bots.append({
            "id": bot.id,
            "name": bot.name,
            "username": bot.username,
        })

    db.commit()

    if created_bots:
        publish_config_update(get_redis(), {
            "type": "demo_bots_created",
            "count": len(created_bots)
        })

    return {
        "ok": True,
        "created": created_bots,
        "skipped": skipped_bots,
        "message": f"{len(created_bots)} bot oluşturuldu. Token'ları panelden doldurun ve enable edin."
    }

# ==========================================================
# WIZARD — Kullanıcı dostu tek adım kurulum
# ==========================================================
class WizardBot(BaseModel):
    name: str
    token: str
    username: Optional[str] = None
    is_enabled: bool = True

class WizardChat(BaseModel):
    chat_id: str
    title: Optional[str] = None
    topics: List[str] = Field(default_factory=lambda: ["BIST","FX","Kripto","Makro"])

class WizardSetup(BaseModel):
    bot: WizardBot
    chat: WizardChat
    persona: Optional[PersonaProfile] = None
    emotion: Optional[EmotionProfile] = None
    stances: Optional[List[StanceCreate]] = None
    holdings: Optional[List[HoldingCreate]] = None
    start_simulation: bool = True

@app.get("/wizard/example", dependencies=viewer_dependencies)
def wizard_example():
    example = {
        "bot": {
            "name": "AkıllıBot",
            "token": "REPLACE_WITH_TELEGRAM_BOT_TOKEN",
            "username": "@akillibot",
            "is_enabled": True
        },
        "chat": {
            "chat_id": "-1001234567890",
            "title": "Deneme Grup",
            "topics": ["BIST","FX","Kripto","Makro"]
        },
        "persona": {
            "tone": "samimi ama profesyonel",
            "risk_profile": "orta",
            "watchlist": ["BIST:AKBNK","XAUUSD","BTCUSDT"],
            "never_do": ["garanti kazanç vaadi","kaynak vermeden kesin rakam"],
            "style": {"emojis": True, "length": "kısa-orta", "disclaimer": "yatırım tavsiyesi değildir"}
        },
        "emotion": {
            "tone": "sıcak ve umutlu",
            "empathy": "kullanıcının duygusunu aynala, sonra umut ver",
            "signature_emoji": "😊",
            "signature_phrases": ["şahsi fikrim", "seninle aynı hissediyorum"],
            "anecdotes": [
                "Geçen ayki dalgalanmada sakin kalıp planıma sadık kaldım",
                "2008 krizinde paniğe kapılmadan portföyümü korumuştum"
            ],
            "energy": "orta"
        },
        "stances": [
            {"topic": "Bankacılık", "stance_text": "Orta vadede temkinli; geri çekilmeleri kademeli toplarım.", "confidence": 0.7},
            {"topic": "Kripto", "stance_text": "Kısa vadede volatil; uzun vadede seçici iyimser.", "confidence": 0.6}
        ],
        "holdings": [
            {"symbol": "BIST:AKBNK", "avg_price": 63.4, "size": 120, "note": "uzun vade çekirdek pozisyon"}
        ],
        "start_simulation": True
    }
    return example

@app.post("/wizard/setup", dependencies=admin_dependencies)
def wizard_setup(payload: WizardSetup, db: Session = Depends(get_db)):
    r = get_redis()

    # --- Bot: token'a göre upsert ---
    bot = None
    for candidate in db.query(Bot).all():
        try:
            if candidate.token == payload.bot.token:
                bot = candidate
                break
        except SecurityConfigError as exc:
            logger.error("Bot token decrypt failed during wizard setup: %s", exc)
            raise HTTPException(status_code=500, detail="Token decrypt failed. Check server TOKEN_ENCRYPTION_KEY.")

    if bot:
        bot.name = payload.bot.name
        bot.username = payload.bot.username
        bot.is_enabled = payload.bot.is_enabled
    else:
        bot = Bot(
            name=payload.bot.name,
            token=payload.bot.token,
            username=payload.bot.username,
            is_enabled=payload.bot.is_enabled,
            speed_profile={},
            active_hours=["09:30-12:00","14:00-18:00"],
            persona_hint="",
        )
        db.add(bot)
        db.flush()  # id üretimi için

    # --- Chat: chat_id'ye göre upsert ---
    chat = db.query(Chat).filter(Chat.chat_id == payload.chat.chat_id).first()
    if chat:
        chat.title = payload.chat.title
        chat.is_enabled = True
        chat.topics = payload.chat.topics or chat.topics
    else:
        chat = Chat(
            chat_id=payload.chat.chat_id,
            title=payload.chat.title,
            is_enabled=True,
            topics=payload.chat.topics or ["BIST","FX","Kripto","Makro"],
        )
        db.add(chat)

    db.commit()
    db.refresh(bot)
    db.refresh(chat)

    # --- Persona (opsiyonel) ---
    if payload.persona is not None:
        bot.persona_profile = payload.persona.dict(exclude_unset=True)
        db.commit()
        publish_config_update(r, {"type": "persona_updated", "bot_id": bot.id})

    if payload.emotion is not None:
        bot.emotion_profile = payload.emotion.dict(exclude_unset=True)
        db.commit()
        publish_config_update(r, {"type": "emotion_updated", "bot_id": bot.id})

    # --- Stances (opsiyonel, upsert)---
    created_stances: List[int] = []
    if payload.stances:
        for s in payload.stances:
            row = (
                db.query(BotStance)
                .filter(BotStance.bot_id == bot.id, BotStance.topic == s.topic)
                .first()
            )
            if row:
                row.stance_text = s.stance_text
                row.confidence = s.confidence
                row.cooldown_until = s.cooldown_until
            else:
                row = BotStance(
                    bot_id=bot.id,
                    topic=s.topic,
                    stance_text=s.stance_text,
                    confidence=s.confidence,
                    cooldown_until=s.cooldown_until,
                )
                db.add(row)
            db.commit()
            db.refresh(row)
            created_stances.append(row.id)
        publish_config_update(r, {"type": "stance_bulk_upsert", "bot_id": bot.id, "ids": created_stances})

    # --- Holdings (opsiyonel, upsert) ---
    created_holdings: List[int] = []
    if payload.holdings:
        for h in payload.holdings:
            row = (
                db.query(BotHolding)
                .filter(BotHolding.bot_id == bot.id, BotHolding.symbol == h.symbol)
                .first()
            )
            if row:
                if h.avg_price is not None:
                    row.avg_price = h.avg_price
                if h.size is not None:
                    row.size = h.size
                if h.note is not None:
                    row.note = h.note
            else:
                row = BotHolding(
                    bot_id=bot.id,
                    symbol=h.symbol,
                    avg_price=h.avg_price,
                    size=h.size,
                    note=h.note,
                )
                db.add(row)
            db.commit()
            db.refresh(row)
            created_holdings.append(row.id)
        publish_config_update(r, {"type": "holding_bulk_upsert", "bot_id": bot.id, "ids": created_holdings})

    # --- Simülasyonu başlat (opsiyonel) ---
    if payload.start_simulation:
        _set_setting(db, "simulation_active", True)
        publish_config_update(r, {"type": "control", "simulation_active": True})

    return {
        "ok": True,
        "bot": {"id": bot.id, "name": bot.name, "username": bot.username},
        "chat": {"id": chat.id, "chat_id": chat.chat_id, "title": chat.title},
        "stances": created_stances,
        "holdings": created_holdings,
        "simulation_active": payload.start_simulation,
    }

# ==========================================================
# TELEGRAM WEBHOOK — Incoming message handler
# ==========================================================

class TelegramUpdate(BaseModel):
    """Telegram Bot API Update object (simplified)"""
    update_id: int
    message: Optional[Dict[str, Any]] = None
    edited_message: Optional[Dict[str, Any]] = None
    channel_post: Optional[Dict[str, Any]] = None
    edited_channel_post: Optional[Dict[str, Any]] = None


@app.post("/webhook/telegram/{bot_token}")
async def telegram_webhook(
    bot_token: str,
    update: TelegramUpdate,
    db: Session = Depends(get_db),
):
    """
    Telegram webhook endpoint. Her bot için ayrı URL:
    /webhook/telegram/{bot_token}

    Gelen mesajları DB'ye kaydeder ve Redis'e priority queue'ya ekler.
    """
    try:
        # Bot token'ı verify et
        bot = None
        for candidate in db.query(Bot).filter(Bot.is_enabled.is_(True)).all():
            try:
                if candidate.token == bot_token:
                    bot = candidate
                    break
            except SecurityConfigError:
                continue

        if not bot:
            logger.warning("Webhook received for unknown/disabled bot token: %s", mask_token(bot_token))
            raise HTTPException(status_code=404, detail="Bot not found or disabled")

        # Mesaj extract et (message veya edited_message)
        msg_data = update.message or update.edited_message
        if not msg_data:
            # Channel post'ları şimdilik ignore ediyoruz
            return {"ok": True, "action": "ignored"}

        # Mesaj detaylarını parse et
        telegram_msg_id = msg_data.get("message_id")
        chat_data = msg_data.get("chat", {})
        telegram_chat_id = str(chat_data.get("id", ""))
        from_user = msg_data.get("from", {})
        user_id = from_user.get("id")
        username = from_user.get("username", "")
        text = msg_data.get("text", "")
        reply_to_msg_id = msg_data.get("reply_to_message", {}).get("message_id")

        # Bu mesaj bir bot'tan mı geliyor? (bot mesajlarını ignore et)
        if from_user.get("is_bot", False):
            return {"ok": True, "action": "ignored_bot_message"}

        # Chat'i DB'de bul
        chat = db.query(Chat).filter(Chat.chat_id == telegram_chat_id).first()
        if not chat:
            # Auto-create chat if not exists (opsiyonel)
            logger.info("Auto-creating chat for telegram_chat_id=%s", telegram_chat_id)
            chat = Chat(
                chat_id=telegram_chat_id,
                title=chat_data.get("title") or chat_data.get("first_name") or "Unknown",
                is_enabled=True,
                topics=["BIST", "FX", "Kripto", "Makro"],
            )
            db.add(chat)
            db.commit()
            db.refresh(chat)

        # Incoming mesajı DB'ye kaydet
        # Not: bot_id None olacak çünkü bu bir kullanıcı mesajı
        incoming_msg = Message(
            bot_id=None,  # Kullanıcı mesajı için None
            chat_db_id=chat.id,
            telegram_message_id=telegram_msg_id,
            text=text,
            reply_to_message_id=reply_to_msg_id,
            msg_metadata={
                "from_user_id": user_id,
                "username": username,
                "is_incoming": True,
                "update_id": update.update_id,
            },
        )
        db.add(incoming_msg)
        db.commit()
        db.refresh(incoming_msg)

        logger.info(
            "Incoming message saved: msg_id=%s, chat=%s, user=%s, text_preview=%s",
            telegram_msg_id,
            telegram_chat_id,
            username or user_id,
            text[:50] if text else "(no text)",
        )

        # Redis'e priority queue'ya ekle (mention detection için)
        r = get_redis()
        if r:
            try:
                # Bot'un mention edilip edilmediğini kontrol et
                bot_username = bot.username or ""
                is_mentioned = False
                if bot_username and f"@{bot_username.lstrip('@')}" in text:
                    is_mentioned = True

                # Mesaj bot'a reply mi?
                is_reply_to_bot = False
                if reply_to_msg_id:
                    # Reply edilen mesajın bot'a ait olup olmadığını kontrol et
                    replied_msg = db.query(Message).filter(
                        Message.telegram_message_id == reply_to_msg_id,
                        Message.chat_db_id == chat.id,
                        Message.bot_id == bot.id,
                    ).first()
                    if replied_msg:
                        is_reply_to_bot = True

                # Priority queue'ya ekle
                priority_data = {
                    "type": "incoming_message",
                    "message_id": incoming_msg.id,
                    "telegram_message_id": telegram_msg_id,
                    "chat_id": chat.id,
                    "telegram_chat_id": telegram_chat_id,
                    "bot_id": bot.id,
                    "text": text,
                    "is_mentioned": is_mentioned,
                    "is_reply_to_bot": is_reply_to_bot,
                    "priority": "high" if (is_mentioned or is_reply_to_bot) else "normal",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Redis LPUSH ile queue'ya ekle (priority'ye göre farklı queue'lar)
                queue_key = f"priority_queue:high" if priority_data["priority"] == "high" else "priority_queue:normal"
                r.lpush(queue_key, json.dumps(priority_data))
                logger.debug("Added to priority queue: %s (priority=%s)", queue_key, priority_data["priority"])
            except Exception as e:
                logger.warning("Failed to add to priority queue: %s", e)

        return {
            "ok": True,
            "action": "saved",
            "message_id": incoming_msg.id,
            "chat_id": chat.id,
            "reply_to_message_id": reply_to_msg_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Webhook processing failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal webhook processing error")


# ----------------------
# Entrypoint
# ----------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
