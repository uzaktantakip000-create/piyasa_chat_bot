"""
Message History Caching Helpers

Provides caching wrappers for chat message history.
Reduces database queries for frequently accessed message lists.
"""

from typing import List, Any, Optional
from sqlalchemy.orm import Session
import logging

from backend.caching.cache_manager import CacheManager

logger = logging.getLogger(__name__)

# Default TTL for message history (short-lived, messages change frequently)
MESSAGE_HISTORY_TTL = 60  # 1 minute


def get_recent_messages_cached(
    chat_id: int,
    db: Session,
    limit: int = 20,
    ttl: Optional[int] = MESSAGE_HISTORY_TTL
) -> List[Any]:
    """
    Get recent messages for a chat with caching.

    Args:
        chat_id: Chat ID
        db: Database session
        limit: Number of recent messages to fetch
        ttl: Cache TTL in seconds

    Returns:
        List of Message objects (newest first)
    """
    cache = CacheManager.get_instance()
    key = f"chat:{chat_id}:messages:recent:{limit}"

    def loader():
        from database import Message
        return (
            db.query(Message)
            .filter_by(chat_db_id=chat_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )

    result = cache.get(key, loader=loader, ttl=ttl)
    return result if result is not None else []


def get_bot_recent_messages_cached(
    bot_id: int,
    db: Session,
    limit: int = 10,
    ttl: Optional[int] = MESSAGE_HISTORY_TTL
) -> List[Any]:
    """
    Get recent messages sent by a specific bot with caching.

    Args:
        bot_id: Bot ID
        db: Database session
        limit: Number of recent messages to fetch
        ttl: Cache TTL in seconds

    Returns:
        List of Message objects (newest first)
    """
    cache = CacheManager.get_instance()
    key = f"bot:{bot_id}:messages:recent:{limit}"

    def loader():
        from database import Message
        return (
            db.query(Message)
            .filter_by(bot_id=bot_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )

    result = cache.get(key, loader=loader, ttl=ttl)
    return result if result is not None else []


def invalidate_chat_message_cache(chat_id: int) -> None:
    """
    Invalidate message cache for a specific chat.

    Call this after new message is sent to the chat.

    Args:
        chat_id: Chat ID to invalidate
    """
    cache = CacheManager.get_instance()
    count = cache.invalidate_pattern(f"chat:{chat_id}:messages:*")
    logger.debug("Invalidated %d message cache entries for chat %d", count, chat_id)


def invalidate_bot_message_cache(bot_id: int) -> None:
    """
    Invalidate message cache for a specific bot.

    Call this after bot sends a new message.

    Args:
        bot_id: Bot ID to invalidate
    """
    cache = CacheManager.get_instance()
    count = cache.invalidate_pattern(f"bot:{bot_id}:messages:*")
    logger.debug("Invalidated %d message cache entries for bot %d", count, bot_id)


def invalidate_all_message_caches() -> None:
    """
    Invalidate all message-related cache entries.

    Call this on global message data changes.
    """
    cache = CacheManager.get_instance()
    count_chat = cache.invalidate_pattern("chat:*:messages:*")
    count_bot = cache.invalidate_pattern("bot:*:messages:*")
    total = count_chat + count_bot
    logger.info("Invalidated %d message cache entries", total)
