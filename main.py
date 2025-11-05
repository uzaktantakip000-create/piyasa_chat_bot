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
    DemoBotsCreate,
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

# ----------------------
# API ROUTERS
# ----------------------
# Include modular routers for clean separation of concerns
try:
    from backend.api.routes import auth, bots, chats, control, logs, metrics, settings, system, users, websockets, wizard

    app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
    app.include_router(bots.router, tags=["Bots"])
    app.include_router(chats.router, prefix="/chats", tags=["Chats"])
    app.include_router(control.router, prefix="/control", tags=["Control"])
    app.include_router(logs.router, prefix="/logs", tags=["Logs"])
    app.include_router(metrics.router, tags=["Metrics"])
    app.include_router(settings.router, prefix="/settings", tags=["Settings"])
    app.include_router(system.router, tags=["System"])
    app.include_router(users.router, tags=["User Management"])
    app.include_router(websockets.router, prefix="/ws", tags=["WebSocket"])
    app.include_router(wizard.router, tags=["Wizard"])

    logger.info("✅ API routers loaded: auth, bots, chats, control, logs, metrics, settings, system, users, websockets, wizard")
except ImportError as e:
    logger.warning(f"⚠️ Some API routers could not be loaded: {e}")
except Exception as e:
    logger.error(f"❌ API router setup error: {e}")


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

# ============================================================================
# NOTE: /auth/* endpoints moved to backend/api/routes/auth.py
# ============================================================================

# ============================================================================
# NOTE: /bots/* endpoints will be moved to backend/api/routes/bots.py (Session 33)
# NOTE: Includes: CRUD, persona, emotion, stances, holdings (~300-400 lines)
# ============================================================================

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


# ============================================================================
# NOTE: /settings/* endpoints moved to backend/api/routes/settings.py
# NOTE: /control/* endpoints moved to backend/api/routes/control.py
# NOTE: /metrics, /cache/stats, /queue/stats moved to backend/api/routes/metrics.py
# ============================================================================

# ============================================================================
# NOTE: /ws/dashboard moved to backend/api/routes/websockets.py
# NOTE: /logs/* endpoints moved to backend/api/routes/logs.py
# NOTE: _build_dashboard_snapshot, _calculate_metrics moved to respective routers
# ============================================================================

# ============================================================================
# NOTE: /bots/{bot_id}/persona, /bots/{bot_id}/emotion endpoints (Session 33)
# NOTE: /bots/{bot_id}/stances, /stances/{stance_id} endpoints (Session 33)
# NOTE: /bots/{bot_id}/holdings, /holdings/{holding_id} endpoints (Session 33)
# NOTE: Total ~240 lines to be moved to backend/api/routes/bots.py
# ============================================================================

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
