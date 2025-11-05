# API routes package
"""
Export all route modules for easy importing in main.py
"""

from . import (
    auth,
    bots,
    chats,
    control,
    logs,
    metrics,
    settings,
    system,
    users,
    websockets,
    wizard,
)

__all__ = [
    "auth",
    "bots",
    "chats",
    "control",
    "logs",
    "metrics",
    "settings",
    "system",
    "users",
    "websockets",
    "wizard",
]