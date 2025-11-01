"""
Multi-layer caching system for piyasa_chat_bot.

Provides L1 (in-memory) and L2 (Redis) caching with automatic fallback.
"""

from backend.caching.cache_manager import CacheManager
from backend.caching.bot_cache_helpers import (
    get_bot_profile_cached,
    get_bot_persona_cached,
    get_bot_emotion_cached,
    get_bot_stances_cached,
    get_bot_holdings_cached,
    invalidate_bot_cache,
    invalidate_all_bot_caches,
)
from backend.caching.message_cache_helpers import (
    get_recent_messages_cached,
    get_bot_recent_messages_cached,
    invalidate_chat_message_cache,
    invalidate_bot_message_cache,
    invalidate_all_message_caches,
)

__all__ = [
    'CacheManager',
    # Bot caching
    'get_bot_profile_cached',
    'get_bot_persona_cached',
    'get_bot_emotion_cached',
    'get_bot_stances_cached',
    'get_bot_holdings_cached',
    'invalidate_bot_cache',
    'invalidate_all_bot_caches',
    # Message caching
    'get_recent_messages_cached',
    'get_bot_recent_messages_cached',
    'invalidate_chat_message_cache',
    'invalidate_bot_message_cache',
    'invalidate_all_message_caches',
]
