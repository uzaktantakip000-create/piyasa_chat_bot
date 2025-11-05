"""
Bot routes - Bot management, persona, emotion, stances, and holdings.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db, Bot, BotStance, BotHolding, BotMemory
from schemas import (
    BotCreate, BotUpdate, BotResponse,
    PersonaProfile, EmotionProfile,
    StanceCreate, StanceUpdate, StanceResponse,
    HoldingCreate, HoldingUpdate, HoldingResponse,
    MemoryCreate, MemoryUpdate, MemoryResponse,
)
from security import mask_token, SecurityConfigError
from backend.api.dependencies import viewer_dependencies, operator_dependencies, admin_dependencies
from backend.api.routes.control import get_redis, publish_config_update
from backend.api.utils.memory_generator import auto_generate_bot_memories

# Cache invalidation helpers
try:
    from backend.caching.bot_cache_helpers import invalidate_bot_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    def invalidate_bot_cache(bot_id: int) -> None:
        pass

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bots", tags=["Bots"])


def _bot_to_response(db_bot: Bot) -> BotResponse:
    """Convert Bot model to BotResponse schema."""
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


# ============================================================================
# Bot CRUD
# ============================================================================

@router.post("", response_model=BotResponse, status_code=status.HTTP_201_CREATED, dependencies=operator_dependencies)
def create_bot(bot: BotCreate, db: Session = Depends(get_db)):
    """
    Create a new bot.
    Requires operator role.
    """
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

    # Auto-generate default memories from persona
    try:
        memory_count = auto_generate_bot_memories(db, db_bot)
        if memory_count > 0:
            logger.info(f"Auto-generated {memory_count} memories for bot {db_bot.id}")
    except Exception as e:
        logger.warning(f"Failed to auto-generate memories for bot {db_bot.id}: {e}")

    publish_config_update(get_redis(), {"type": "bot_added", "bot_id": db_bot.id})
    return _bot_to_response(db_bot)


@router.get("", response_model=List[BotResponse], dependencies=viewer_dependencies)
def list_bots(db: Session = Depends(get_db)):
    """Get all bots."""
    bots = db.query(Bot).order_by(Bot.id.asc()).all()
    return [_bot_to_response(bot) for bot in bots]


@router.patch("/{bot_id}", response_model=BotResponse, dependencies=operator_dependencies)
def update_bot(bot_id: int, patch: BotUpdate, db: Session = Depends(get_db)):
    """
    Update bot properties.
    Requires operator role.
    """
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


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=admin_dependencies)
def delete_bot(bot_id: int, db: Session = Depends(get_db)):
    """
    Delete a bot.
    Requires admin role.
    """
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
    return None


# ============================================================================
# Persona Profile
# ============================================================================

@router.get("/{bot_id}/persona", dependencies=viewer_dependencies)
def get_persona(bot_id: int, db: Session = Depends(get_db)):
    """Get bot's persona profile."""
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")
    return bot.persona_profile or {}


@router.put("/{bot_id}/persona", dependencies=operator_dependencies)
def put_persona(bot_id: int, profile: PersonaProfile, db: Session = Depends(get_db)):
    """
    Update bot's persona profile.
    Requires operator role.
    """
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


# ============================================================================
# Emotion Profile
# ============================================================================

@router.get("/{bot_id}/emotion", dependencies=viewer_dependencies)
def get_emotion_profile(bot_id: int, db: Session = Depends(get_db)):
    """Get bot's emotion profile."""
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")
    return bot.emotion_profile or {}


@router.put("/{bot_id}/emotion", dependencies=operator_dependencies)
def put_emotion_profile(bot_id: int, profile: EmotionProfile, db: Session = Depends(get_db)):
    """
    Update bot's emotion profile.
    Requires operator role.
    """
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


# ============================================================================
# Stances Management
# ============================================================================

@router.get("/{bot_id}/stances", response_model=List[StanceResponse], dependencies=viewer_dependencies)
def list_stances(bot_id: int, db: Session = Depends(get_db)):
    """Get all stances for a bot."""
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


@router.post("/{bot_id}/stances", response_model=StanceResponse, status_code=201, dependencies=operator_dependencies)
def upsert_stance(bot_id: int, body: StanceCreate, db: Session = Depends(get_db)):
    """
    Create or update a stance (upsert by bot_id + topic).
    Requires operator role.
    """
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


# Note: PATCH/DELETE /stances/{stance_id} endpoints are not under /bots prefix
# They will be defined in this router but with different path

@router.patch("/stances/{stance_id}", response_model=StanceResponse, dependencies=operator_dependencies)
def update_stance(stance_id: int, patch: StanceUpdate, db: Session = Depends(get_db)):
    """
    Update a stance by ID.
    Requires operator role.
    """
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


@router.delete("/stances/{stance_id}", status_code=204, dependencies=operator_dependencies)
def delete_stance(stance_id: int, db: Session = Depends(get_db)):
    """
    Delete a stance by ID.
    Requires operator role.
    """
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
    return None


# ============================================================================
# Holdings Management
# ============================================================================

@router.get("/{bot_id}/holdings", response_model=List[HoldingResponse], dependencies=viewer_dependencies)
def list_holdings(bot_id: int, db: Session = Depends(get_db)):
    """Get all holdings for a bot."""
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


@router.post("/{bot_id}/holdings", response_model=HoldingResponse, status_code=201, dependencies=operator_dependencies)
def upsert_holding(bot_id: int, body: HoldingCreate, db: Session = Depends(get_db)):
    """
    Create or update a holding (upsert by bot_id + symbol).
    Requires operator role.
    """
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


# Note: PATCH/DELETE /holdings/{holding_id} endpoints are not under /bots prefix
# They will be defined in this router but with different path

@router.patch("/holdings/{holding_id}", response_model=HoldingResponse, dependencies=operator_dependencies)
def update_holding(holding_id: int, patch: HoldingUpdate, db: Session = Depends(get_db)):
    """
    Update a holding by ID.
    Requires operator role.
    """
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


@router.delete("/holdings/{holding_id}", status_code=204, dependencies=operator_dependencies)
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    """
    Delete a holding by ID.
    Requires operator role.
    """
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
    return None


# ============================================================================
# Bot Memory Management
# ============================================================================

@router.get("/{bot_id}/memories", response_model=List[MemoryResponse], dependencies=viewer_dependencies)
def list_memories(bot_id: int, db: Session = Depends(get_db)):
    """Get all memories for a bot."""
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")
    rows = (
        db.query(BotMemory)
        .filter(BotMemory.bot_id == bot_id)
        .order_by(BotMemory.relevance_score.desc(), BotMemory.last_used_at.desc())
        .all()
    )
    return rows


@router.post("/{bot_id}/memories", response_model=MemoryResponse, status_code=201, dependencies=operator_dependencies)
def create_memory(bot_id: int, body: MemoryCreate, db: Session = Depends(get_db)):
    """
    Create a new memory for a bot.
    Requires operator role.
    """
    bot = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot:
        raise HTTPException(404, "Bot not found")

    row = BotMemory(
        bot_id=bot_id,
        memory_type=body.memory_type,
        content=body.content,
        relevance_score=body.relevance_score or 1.0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(bot_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {bot_id}: {e}")

    publish_config_update(get_redis(), {"type": "memory_created", "bot_id": bot_id, "memory_id": row.id})
    return row


@router.patch("/memories/{memory_id}", response_model=MemoryResponse, dependencies=operator_dependencies)
def update_memory(memory_id: int, patch: MemoryUpdate, db: Session = Depends(get_db)):
    """
    Update a memory by ID.
    Requires operator role.
    """
    row = db.query(BotMemory).filter(BotMemory.id == memory_id).first()
    if not row:
        raise HTTPException(404, "Memory not found")

    for k, v in patch.dict(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(row.bot_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {row.bot_id}: {e}")

    publish_config_update(get_redis(), {"type": "memory_updated", "bot_id": row.bot_id, "memory_id": row.id})
    return row


@router.delete("/memories/{memory_id}", status_code=204, dependencies=operator_dependencies)
def delete_memory(memory_id: int, db: Session = Depends(get_db)):
    """
    Delete a memory by ID.
    Requires operator role.
    """
    row = db.query(BotMemory).filter(BotMemory.id == memory_id).first()
    if not row:
        raise HTTPException(404, "Memory not found")
    bot_id = row.bot_id
    db.delete(row)
    db.commit()

    # Invalidate cache and publish config update
    try:
        invalidate_bot_cache(bot_id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for bot {bot_id}: {e}")

    publish_config_update(get_redis(), {"type": "memory_deleted", "bot_id": bot_id, "memory_id": memory_id})
    return None
