"""
Async database module for SQLAlchemy 2.0+

Provides async engine, session factory, and helper functions for high-concurrency scenarios.
Backward compatible with existing sync database.py.

Usage:
    from database_async import get_async_session

    async def my_func():
        async with get_async_session() as session:
            result = await session.execute(select(Bot).where(Bot.is_enabled == True))
            bots = result.scalars().all()
"""

from __future__ import annotations

import logging
import os
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import selectinload
from sqlalchemy import select

# Import models from sync database (they're compatible with async)
from database import (
    Base,
    Bot,
    Chat,
    Message,
    Setting,
    BotStance,
    BotHolding,
    SystemCheck,
    ApiUser,
    ApiSession,
)

logger = logging.getLogger("database_async")

# --------------------------------------------------------------------
# Async Engine & Session Factory
# --------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# Convert sync URL to async URL
if DATABASE_URL.startswith("sqlite"):
    # SQLite: sqlite:///./app.db -> sqlite+aiosqlite:///./app.db
    ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
elif DATABASE_URL.startswith("postgresql"):
    # PostgreSQL: postgresql+psycopg://... -> postgresql+asyncpg://...
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    # Also handle plain postgresql://
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    logger.warning(f"Unknown DATABASE_URL scheme: {DATABASE_URL}, using as-is")
    ASYNC_DATABASE_URL = DATABASE_URL

logger.info(f"Async database URL: {ASYNC_DATABASE_URL.split('@')[0]}...")  # Hide credentials

# Create async engine
async_engine: AsyncEngine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",  # Enable SQL logging if needed
    pool_size=int(os.getenv("ASYNC_DB_POOL_SIZE", "20")),
    max_overflow=int(os.getenv("ASYNC_DB_MAX_OVERFLOW", "40")),
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=int(os.getenv("ASYNC_DB_POOL_RECYCLE", "3600")),  # Recycle connections after 1 hour
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Allow using objects after commit
    autoflush=False,
    autocommit=False,
)


# --------------------------------------------------------------------
# Session Context Manager
# --------------------------------------------------------------------

@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.

    Usage:
        async with get_async_session() as session:
            result = await session.execute(select(Bot))
            bots = result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


# --------------------------------------------------------------------
# Helper Functions (Async versions of common queries)
# --------------------------------------------------------------------

async def fetch_recent_messages_async(
    session: AsyncSession,
    chat_id: int,
    limit: int = 10,
    include_bot: bool = True
) -> list[Message]:
    """
    Fetch recent messages from a chat (async version).

    Args:
        session: Async database session
        chat_id: Chat ID
        limit: Maximum number of messages
        include_bot: Include bot relationship in query

    Returns:
        List of Message objects
    """
    query = select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.desc()).limit(limit)

    if include_bot:
        query = query.options(selectinload(Message.bot))

    result = await session.execute(query)
    messages = result.scalars().all()

    # Reverse to chronological order
    return list(reversed(messages))


async def fetch_bot_by_id_async(session: AsyncSession, bot_id: int) -> Bot | None:
    """Fetch bot by ID with all relationships (async version)."""
    query = (
        select(Bot)
        .where(Bot.id == bot_id)
        .options(
            selectinload(Bot.stances),
            selectinload(Bot.holdings)
        )
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def fetch_enabled_bots_async(session: AsyncSession) -> list[Bot]:
    """Fetch all enabled bots (async version)."""
    query = select(Bot).where(Bot.is_enabled == True)
    result = await session.execute(query)
    return list(result.scalars().all())


async def fetch_enabled_chats_async(session: AsyncSession) -> list[Chat]:
    """Fetch all enabled chats (async version)."""
    query = select(Chat).where(Chat.is_enabled == True)
    result = await session.execute(query)
    return list(result.scalars().all())


async def fetch_setting_async(session: AsyncSession, key: str) -> Setting | None:
    """Fetch setting by key (async version)."""
    query = select(Setting).where(Setting.key == key)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def fetch_all_settings_async(session: AsyncSession) -> dict[str, str]:
    """Fetch all settings as dictionary (async version)."""
    query = select(Setting)
    result = await session.execute(query)
    settings = result.scalars().all()
    return {s.key: s.value for s in settings}


async def create_message_async(
    session: AsyncSession,
    bot_id: int,
    chat_id: int,
    text: str,
    telegram_message_id: int | None = None,
    reply_to_message_id: int | None = None,
) -> Message:
    """
    Create a new message (async version).

    Args:
        session: Async database session
        bot_id: Bot ID
        chat_id: Chat ID
        text: Message text
        telegram_message_id: Telegram message ID
        reply_to_message_id: ID of message being replied to

    Returns:
        Created Message object
    """
    message = Message(
        bot_id=bot_id,
        chat_id=chat_id,
        text=text,
        telegram_message_id=telegram_message_id,
        reply_to_message_id=reply_to_message_id,
    )
    session.add(message)
    await session.flush()  # Get ID without committing
    await session.refresh(message)  # Refresh to get defaults
    return message


# --------------------------------------------------------------------
# Database Initialization
# --------------------------------------------------------------------

async def init_async_db():
    """
    Initialize async database (create tables if needed).

    Note: This uses the sync Base metadata, so tables must exist.
    For initial setup, use sync database.py init_db().
    """
    async with async_engine.begin() as conn:
        # Note: Base.metadata.create_all() is sync, so we run it in executor
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Async database initialized")


async def close_async_db():
    """Close async database engine (for graceful shutdown)."""
    await async_engine.dispose()
    logger.info("Async database engine disposed")


# --------------------------------------------------------------------
# Export commonly used items
# --------------------------------------------------------------------

__all__ = [
    "async_engine",
    "AsyncSessionLocal",
    "get_async_session",
    "fetch_recent_messages_async",
    "fetch_bot_by_id_async",
    "fetch_enabled_bots_async",
    "fetch_enabled_chats_async",
    "fetch_setting_async",
    "fetch_all_settings_async",
    "create_message_async",
    "init_async_db",
    "close_async_db",
    # Re-export models
    "Bot",
    "Chat",
    "Message",
    "Setting",
    "BotStance",
    "BotHolding",
    "SystemCheck",
    "ApiUser",
    "ApiSession",
]
