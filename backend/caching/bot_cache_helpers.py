"""
Bot Profile Caching Helpers

Provides caching wrappers for bot profiles, personas, emotions, stances, and holdings.
Reduces database queries for frequently accessed bot data.
"""

from typing import Optional, Any, Dict, List
from sqlalchemy.orm import Session
import logging

from backend.caching.cache_manager import CacheManager

logger = logging.getLogger(__name__)

# Default TTLs (in seconds)
BOT_PROFILE_TTL = 300  # 5 minutes
BOT_PERSONA_TTL = 600  # 10 minutes
BOT_STANCES_TTL = 180  # 3 minutes
BOT_HOLDINGS_TTL = 300  # 5 minutes


def get_bot_profile_cached(
    bot_id: int,
    db: Session,
    ttl: Optional[int] = BOT_PROFILE_TTL
) -> Optional[Any]:
    """
    Get bot profile with caching.

    Args:
        bot_id: Bot ID
        db: Database session
        ttl: Cache TTL in seconds

    Returns:
        Bot object or None
    """
    cache = CacheManager.get_instance()
    key = f"bot:{bot_id}:profile"

    def loader():
        from database import Bot
        return db.query(Bot).filter_by(id=bot_id).first()

    return cache.get(key, loader=loader, ttl=ttl)


def get_bot_persona_cached(
    bot_id: int,
    db: Session,
    ttl: Optional[int] = BOT_PERSONA_TTL
) -> Optional[Dict[str, Any]]:
    """
    Get bot persona_profile with caching.

    Args:
        bot_id: Bot ID
        db: Database session
        ttl: Cache TTL in seconds

    Returns:
        Persona profile dict or None
    """
    cache = CacheManager.get_instance()
    key = f"bot:{bot_id}:persona"

    def loader():
        from database import Bot
        bot = db.query(Bot).filter_by(id=bot_id).first()
        return bot.persona_profile if bot else None

    return cache.get(key, loader=loader, ttl=ttl)


def get_bot_emotion_cached(
    bot_id: int,
    db: Session,
    ttl: Optional[int] = BOT_PERSONA_TTL
) -> Optional[Dict[str, Any]]:
    """
    Get bot emotion_profile with caching.

    Args:
        bot_id: Bot ID
        db: Database session
        ttl: Cache TTL in seconds

    Returns:
        Emotion profile dict or None
    """
    cache = CacheManager.get_instance()
    key = f"bot:{bot_id}:emotion"

    def loader():
        from database import Bot
        bot = db.query(Bot).filter_by(id=bot_id).first()
        return bot.emotion_profile if bot else None

    return cache.get(key, loader=loader, ttl=ttl)


def get_bot_stances_cached(
    bot_id: int,
    db: Session,
    ttl: Optional[int] = BOT_STANCES_TTL
) -> List[Any]:
    """
    Get bot stances (CACHING DISABLED - ORM session issues).

    Args:
        bot_id: Bot ID
        db: Database session
        ttl: Cache TTL in seconds

    Returns:
        List of BotStance objects
    """
    # NOTE: Caching disabled - ORM objects become detached from session
    # The behavior_engine.fetch_psh() converts these to dicts anyway
    from database import BotStance
    return db.query(BotStance).filter_by(bot_id=bot_id).all()


def get_bot_holdings_cached(
    bot_id: int,
    db: Session,
    ttl: Optional[int] = BOT_HOLDINGS_TTL
) -> List[Any]:
    """
    Get bot holdings (CACHING DISABLED - ORM session issues).

    Args:
        bot_id: Bot ID
        db: Database session
        ttl: Cache TTL in seconds

    Returns:
        List of BotHolding objects
    """
    # NOTE: Caching disabled - ORM objects become detached from session
    # The behavior_engine.fetch_psh() converts these to dicts anyway
    from database import BotHolding
    return db.query(BotHolding).filter_by(bot_id=bot_id).all()


def invalidate_bot_cache(bot_id: int) -> None:
    """
    Invalidate all cache entries for a specific bot.

    Call this when bot profile is updated.

    Args:
        bot_id: Bot ID to invalidate
    """
    cache = CacheManager.get_instance()
    count = cache.invalidate_pattern(f"bot:{bot_id}:*")
    logger.info("Invalidated %d cache entries for bot %d", count, bot_id)


def invalidate_all_bot_caches() -> None:
    """
    Invalidate all bot-related cache entries.

    Call this on global configuration changes.
    """
    cache = CacheManager.get_instance()
    count = cache.invalidate_pattern("bot:*")
    logger.info("Invalidated %d bot cache entries", count)
