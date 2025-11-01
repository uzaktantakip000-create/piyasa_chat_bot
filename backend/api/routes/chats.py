"""
Chat routes - Telegram chat/group management.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from database import get_db, Chat
from schemas import ChatCreate, ChatUpdate, ChatResponse
from backend.api.dependencies import viewer_dependencies, operator_dependencies
from backend.api.routes.control import get_redis, publish_config_update

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["Chats"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED, dependencies=operator_dependencies)
def create_chat(chat: ChatCreate, db: Session = Depends(get_db)):
    """
    Create a new chat/group.
    Requires operator role.
    """
    db_chat = Chat(
        chat_id=chat.chat_id,
        title=chat.title,
        is_enabled=chat.is_enabled,
        topics=chat.topics
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)

    publish_config_update(get_redis(), {"type": "chat_added", "chat_id": db_chat.id})

    return db_chat


@router.get("", response_model=List[ChatResponse], dependencies=viewer_dependencies)
def list_chats(db: Session = Depends(get_db)):
    """Get all chats."""
    chats = db.query(Chat).order_by(Chat.id.asc()).all()
    return chats


@router.patch("/{chat_id}", response_model=ChatResponse, dependencies=operator_dependencies)
def update_chat(chat_id: int, patch: ChatUpdate, db: Session = Depends(get_db)):
    """
    Update chat properties.
    Requires operator role.
    """
    db_chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    for field, value in patch.dict(exclude_unset=True).items():
        setattr(db_chat, field, value)

    db.commit()
    db.refresh(db_chat)

    publish_config_update(get_redis(), {"type": "chat_updated", "chat_id": chat_id})

    return db_chat


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=operator_dependencies)
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    """
    Delete a chat.
    Requires operator role.
    """
    db_chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not db_chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    db.delete(db_chat)
    db.commit()

    publish_config_update(get_redis(), {"type": "chat_deleted", "chat_id": chat_id})

    return Response(status_code=status.HTTP_204_NO_CONTENT)
