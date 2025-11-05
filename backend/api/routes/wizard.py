"""
Wizard routes - One-step bot+chat+persona setup wizard.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db, Bot, Chat, BotStance, BotHolding
from schemas import PersonaProfile, EmotionProfile, StanceCreate, HoldingCreate
from security import SecurityConfigError
from backend.api.dependencies import viewer_dependencies, admin_dependencies
from backend.api.routes.control import get_redis, publish_config_update, _set_setting
from backend.api.utils.memory_generator import auto_generate_bot_memories

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wizard", tags=["Wizard"])


# ============================================================================
# Wizard Schemas
# ============================================================================

class WizardBot(BaseModel):
    name: str
    token: str
    username: Optional[str] = None
    is_enabled: bool = True


class WizardChat(BaseModel):
    chat_id: str
    title: Optional[str] = None
    topics: List[str] = Field(default_factory=lambda: ["BIST", "FX", "Kripto", "Makro"])


class WizardSetup(BaseModel):
    bot: WizardBot
    chat: WizardChat
    persona: Optional[PersonaProfile] = None
    emotion: Optional[EmotionProfile] = None
    stances: Optional[List[StanceCreate]] = None
    holdings: Optional[List[HoldingCreate]] = None
    start_simulation: bool = True


# ============================================================================
# Wizard Endpoints
# ============================================================================

@router.get("/example", dependencies=viewer_dependencies)
def wizard_example():
    """
    Get an example payload for the wizard setup.
    Returns a complete example with bot, chat, persona, emotion, stances, and holdings.
    """
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
            "topics": ["BIST", "FX", "Kripto", "Makro"]
        },
        "persona": {
            "tone": "samimi ama profesyonel",
            "risk_profile": "orta",
            "watchlist": ["BIST:AKBNK", "XAUUSD", "BTCUSDT"],
            "never_do": ["garanti kazanç vaadi", "kaynak vermeden kesin rakam"],
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


@router.post("/setup", dependencies=admin_dependencies)
def wizard_setup(payload: WizardSetup, db: Session = Depends(get_db)):
    """
    One-step wizard to create/update bot + chat + persona + emotion + stances + holdings.
    Optionally starts simulation.
    Requires admin role.
    """
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
            active_hours=["09:30-12:00", "14:00-18:00"],
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
            topics=payload.chat.topics or ["BIST", "FX", "Kripto", "Makro"],
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

    # --- Auto-generate bot memories from persona ---
    memory_count = 0
    try:
        memory_count = auto_generate_bot_memories(db, bot)
        if memory_count > 0:
            logger.info(f"Wizard: Auto-generated {memory_count} memories for bot {bot.id}")
    except Exception as e:
        logger.warning(f"Wizard: Failed to auto-generate memories for bot {bot.id}: {e}")

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
        "memories": memory_count,
        "simulation_active": payload.start_simulation,
    }
