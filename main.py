from __future__ import annotations

import os
import sys
import json
import logging
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
load_dotenv()  # .env dosyasını yükler

import redis
from fastapi import Body, Depends, HTTPException, Query, Response, status
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, AnyHttpUrl, ValidationError, parse_obj_as
from sqlalchemy.orm import Session

from database import (
    Bot, Chat, Setting, Message, SystemCheck, get_db, create_tables, init_default_settings,
    BotStance, BotHolding, migrate_plain_tokens,
)
from schemas import (
    BotCreate, BotUpdate, BotResponse,
    ChatCreate, ChatUpdate, ChatResponse,
    SettingResponse, MetricsResponse,
    PersonaProfile,
    StanceCreate, StanceUpdate, StanceResponse,
    HoldingCreate, HoldingUpdate, HoldingResponse,
    HealthCheckStatus,
    SystemCheckCreate,
    SystemCheckResponse,
)
from security import mask_token, require_api_key, SecurityConfigError
from settings_utils import normalize_message_length_profile

logger = logging.getLogger("api")
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))

APP_ROOT = Path(__file__).resolve().parent

app = FastAPI(title="Telegram Market Simulation API", version="1.5.0")

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
# Redis util (optional)
# ----------------------
def get_redis() -> Optional[redis.Redis]:
    url = os.getenv("REDIS_URL")
    if not url:
        return None
    try:
        return redis.from_url(url, decode_responses=True)
    except Exception as e:
        logger.warning("Redis bağlantısı kurulamadı: %s", e)
        return None

def publish_config_update(r: Optional[redis.Redis], payload: Dict[str, Any]):
    if not r:
        return
    try:
        r.publish("config_updates", json.dumps(payload))
    except Exception as e:
        logger.warning("Redis publish hatası: %s", e)

# ----------------------
# Startup
# ----------------------
@app.on_event("startup")
def _startup():
    create_tables()
    init_default_settings()
    migrate_plain_tokens()
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
        created_at=db_bot.created_at,
    )

# ----------------------
# Basic endpoints
# ----------------------
@app.get("/healthz")
def healthz():
    return {"ok": True, "ts": datetime.utcnow().isoformat()}

# ----- Bots -----
api_dependencies = [Depends(require_api_key)]


@app.post("/bots", response_model=BotResponse, status_code=status.HTTP_201_CREATED, dependencies=api_dependencies)
def create_bot(bot: BotCreate, db: Session = Depends(get_db)):
    db_bot = Bot(
        name=bot.name,
        token=bot.token,
        username=bot.username,
        is_enabled=bot.is_enabled,
        speed_profile=bot.speed_profile,
        active_hours=bot.active_hours,
        persona_hint=bot.persona_hint,
    )
    db.add(db_bot)
    db.commit()
    db.refresh(db_bot)
    publish_config_update(get_redis(), {"type": "bot_added", "bot_id": db_bot.id})
    return _bot_to_response(db_bot)

@app.get("/bots", response_model=List[BotResponse], dependencies=api_dependencies)
def list_bots(db: Session = Depends(get_db)):
    bots = db.query(Bot).order_by(Bot.id.asc()).all()
    return [_bot_to_response(bot) for bot in bots]

@app.patch("/bots/{bot_id}", response_model=BotResponse, dependencies=api_dependencies)
def update_bot(bot_id: int, patch: BotUpdate, db: Session = Depends(get_db)):
    db_bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not db_bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    for field, value in patch.dict(exclude_unset=True).items():
        setattr(db_bot, field, value)

    db.commit()
    db.refresh(db_bot)
    publish_config_update(get_redis(), {"type": "bot_updated", "bot_id": db_bot.id})
    return _bot_to_response(db_bot)

@app.delete("/bots/{bot_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=api_dependencies)
def delete_bot(bot_id: int, db: Session = Depends(get_db)):
    db_bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not db_bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    db.delete(db_bot)
    db.commit()
    publish_config_update(get_redis(), {"type": "bot_deleted", "bot_id": bot_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# ----- Chats -----
@app.post("/chats", response_model=ChatResponse, status_code=status.HTTP_201_CREATED, dependencies=api_dependencies)
def create_chat(chat: ChatCreate, db: Session = Depends(get_db)):
    db_chat = Chat(chat_id=chat.chat_id, title=chat.title, is_enabled=chat.is_enabled, topics=chat.topics)
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    publish_config_update(get_redis(), {"type": "chat_added", "chat_id": db_chat.id})
    return db_chat

@app.get("/chats", response_model=List[ChatResponse], dependencies=api_dependencies)
def list_chats(db: Session = Depends(get_db)):
    chats = db.query(Chat).order_by(Chat.id.asc()).all()
    return chats


@app.patch("/chats/{chat_id}", response_model=ChatResponse, dependencies=api_dependencies)
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


@app.delete("/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=api_dependencies)
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    db_chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    db.delete(db_chat)
    db.commit()
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


@app.post("/system/checks", response_model=SystemCheckResponse, status_code=status.HTTP_201_CREATED, dependencies=api_dependencies)
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


@app.get("/system/checks/latest", response_model=Optional[SystemCheckResponse], dependencies=api_dependencies)
def get_latest_system_check(db: Session = Depends(get_db)):
    obj = (
        db.query(SystemCheck)
        .order_by(SystemCheck.created_at.desc())
        .first()
    )
    if not obj:
        return None
    return _system_check_to_response(obj)


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


@app.post("/system/checks/run", response_model=SystemCheckResponse, status_code=status.HTTP_202_ACCEPTED, dependencies=api_dependencies)
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


@app.get("/settings", response_model=List[SettingResponse], dependencies=api_dependencies)
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

@app.put("/settings/bulk", response_model=List[SettingResponse], dependencies=api_dependencies)
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


@app.patch("/settings/{key}", response_model=SettingResponse, dependencies=api_dependencies)
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
@app.post("/control/start", dependencies=api_dependencies)
def control_start(db: Session = Depends(get_db)):
    _set_setting(db, "simulation_active", True)
    publish_config_update(get_redis(), {"type": "control", "simulation_active": True})
    return {"ok": True}

@app.post("/control/stop", dependencies=api_dependencies)
def control_stop(db: Session = Depends(get_db)):
    _set_setting(db, "simulation_active", False)
    publish_config_update(get_redis(), {"type": "control", "simulation_active": False})
    return {"ok": True}

class ScalePayload(BaseModel):
    factor: float = Field(1.0, gt=0)


@app.post("/control/scale", dependencies=api_dependencies)
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
@app.get("/metrics", response_model=MetricsResponse, dependencies=api_dependencies)
def metrics(db: Session = Depends(get_db)):
    total_bots = db.query(Bot).count()
    active_bots = db.query(Bot).filter(Bot.is_enabled.is_(True)).count()
    total_chats = db.query(Chat).count()

    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    last_hour_msgs = db.query(Message).filter(Message.created_at >= one_hour_ago).count()
    per_min = round(last_hour_msgs / 60.0, 3)

    sim_active_row = db.query(Setting).filter(Setting.key == "simulation_active").first()
    scale_row = db.query(Setting).filter(Setting.key == "scale_factor").first()
    rl_row = db.query(Setting).filter(Setting.key == "rate_limit_hits").first()
    tg429_row = db.query(Setting).filter(Setting.key == "telegram_429_count").first()
    tg5xx_row = db.query(Setting).filter(Setting.key == "telegram_5xx_count").first()

    # Geri uyumluluk: rate_limit_hits yoksa telegram_5xx_count değerini göster
    rate_limit_hits = int(rl_row.value) if rl_row else (int(tg5xx_row.value) if tg5xx_row else 0)
    telegram_429_count = int(tg429_row.value) if tg429_row else 0
    telegram_5xx_count = int(tg5xx_row.value) if tg5xx_row else 0

    return MetricsResponse(
        total_bots=total_bots,
        active_bots=active_bots,
        total_chats=total_chats,
        messages_last_hour=last_hour_msgs,
        messages_per_minute=per_min,
        simulation_active=bool(sim_active_row.value) if sim_active_row else False,
        scale_factor=float(scale_row.value) if scale_row else 1.0,
        rate_limit_hits=rate_limit_hits,
        telegram_429_count=telegram_429_count,
        telegram_5xx_count=telegram_5xx_count,
    )

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


@app.get("/logs", dependencies=api_dependencies)
def list_logs(limit: int = 100, db: Session = Depends(get_db)):
    limit = min(max(limit, 1), 1000)
    rows = db.query(Message).order_by(Message.created_at.desc()).limit(limit).all()
    return [_serialize_log(row) for row in rows]


@app.get("/logs/recent", dependencies=api_dependencies)
def recent_logs(limit: int = 20, db: Session = Depends(get_db)):
    return list_logs(limit=limit, db=db)

# ==========================================================
# Persona / Stances / Holdings (Mevcut Uçlar)
# ==========================================================

# ----- Persona -----
@app.get("/bots/{bot_id}/persona", dependencies=api_dependencies)
def get_persona(bot_id: int, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")
    return bot.persona_profile or {}

@app.put("/bots/{bot_id}/persona", dependencies=api_dependencies)
def put_persona(bot_id: int, profile: PersonaProfile, db: Session = Depends(get_db)):
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")
    bot.persona_profile = profile.dict(exclude_unset=True)
    db.commit()
    publish_config_update(get_redis(), {"type": "persona_updated", "bot_id": bot_id})
    return {"ok": True, "bot_id": bot_id, "persona_profile": bot.persona_profile}

# ----- Stances -----
@app.get("/bots/{bot_id}/stances", response_model=List[StanceResponse], dependencies=api_dependencies)
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

@app.post("/bots/{bot_id}/stances", response_model=StanceResponse, status_code=201, dependencies=api_dependencies)
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
    publish_config_update(get_redis(), {"type": "stance_upserted", "bot_id": bot_id, "stance_id": row.id})
    return row

@app.patch("/stances/{stance_id}", response_model=StanceResponse, dependencies=api_dependencies)
def update_stance(stance_id: int, patch: StanceUpdate, db: Session = Depends(get_db)):
    row = db.query(BotStance).filter(BotStance.id == stance_id).first()
    if not row:
        raise HTTPException(404, "Stance not found")

    for k, v in patch.dict(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    publish_config_update(get_redis(), {"type": "stance_updated", "bot_id": row.bot_id, "stance_id": row.id})
    return row

@app.delete("/stances/{stance_id}", status_code=204, dependencies=api_dependencies)
def delete_stance(stance_id: int, db: Session = Depends(get_db)):
    row = db.query(BotStance).filter(BotStance.id == stance_id).first()
    if not row:
        raise HTTPException(404, "Stance not found")
    bot_id = row.bot_id
    db.delete(row)
    db.commit()
    publish_config_update(get_redis(), {"type": "stance_deleted", "bot_id": bot_id, "stance_id": stance_id})
    return {"ok": True}

# ----- Holdings -----
@app.get("/bots/{bot_id}/holdings", response_model=List[HoldingResponse], dependencies=api_dependencies)
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

@app.post("/bots/{bot_id}/holdings", response_model=HoldingResponse, status_code=201, dependencies=api_dependencies)
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
    publish_config_update(get_redis(), {"type": "holding_upserted", "bot_id": bot_id, "holding_id": row.id})
    return row

@app.patch("/holdings/{holding_id}", response_model=HoldingResponse, dependencies=api_dependencies)
def update_holding(holding_id: int, patch: HoldingUpdate, db: Session = Depends(get_db)):
    row = db.query(BotHolding).filter(BotHolding.id == holding_id).first()
    if not row:
        raise HTTPException(404, "Holding not found")

    for k, v in patch.dict(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    publish_config_update(get_redis(), {"type": "holding_updated", "bot_id": row.bot_id, "holding_id": row.id})
    return row

@app.delete("/holdings/{holding_id}", status_code=204, dependencies=api_dependencies)
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    row = db.query(BotHolding).filter(BotHolding.id == holding_id).first()
    if not row:
        raise HTTPException(404, "Holding not found")
    bot_id = row.bot_id
    db.delete(row)
    db.commit()
    publish_config_update(get_redis(), {"type": "holding_deleted", "bot_id": bot_id, "holding_id": holding_id})
    return {"ok": True}

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
    stances: Optional[List[StanceCreate]] = None
    holdings: Optional[List[HoldingCreate]] = None
    start_simulation: bool = True

@app.get("/wizard/example", dependencies=api_dependencies)
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

@app.post("/wizard/setup", dependencies=api_dependencies)
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

# ----------------------
# Entrypoint
# ----------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
