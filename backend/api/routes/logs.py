"""
Logs routes - message history and logging.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db, Message
from backend.api.dependencies import viewer_dependencies

router = APIRouter(prefix="/logs", tags=["Logs"])


def _serialize_log(message: Message) -> Dict[str, Any]:
    """Serialize message to log format."""
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


@router.get("", dependencies=viewer_dependencies)
def list_logs(limit: int = 100, db: Session = Depends(get_db)):
    """Get recent message logs with configurable limit (max 1000)."""
    limit = min(max(limit, 1), 1000)
    rows = db.query(Message).order_by(Message.created_at.desc()).limit(limit).all()
    return [_serialize_log(row) for row in rows]


@router.get("/recent", dependencies=viewer_dependencies)
def recent_logs(limit: int = 20, db: Session = Depends(get_db)):
    """Get recent message logs (shortcut for list_logs with smaller default)."""
    return list_logs(limit=limit, db=db)
