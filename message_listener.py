"""
Message Listener Service

Long polling modu için Telegram mesajlarını dinleyen ve DB'ye kaydeden servis.
Webhook modu tercih edildiğinde bu servis kullanılmaz.
"""

from __future__ import annotations

import asyncio
import logging
import os
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import redis

from database import SessionLocal, Bot, Chat, Message
from telegram_client import TelegramClient
from security import SecurityConfigError, mask_token

logger = logging.getLogger("message_listener")


class MessageListenerService:
    """
    Telegram'dan gelen mesajları long polling ile dinler ve DB'ye kaydeder.

    Not: Webhook kullanıyorsanız bu servisi çalıştırmanıza gerek yok.
    Long polling ve webhook aynı anda kullanılamaz.
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        polling_interval: float = 1.0,
        long_poll_timeout: int = 30,
    ):
        """
        Args:
            redis_client: Redis client (priority queue için)
            polling_interval: Update'ler arasındaki bekleme süresi (saniye)
            long_poll_timeout: Telegram long polling timeout (saniye)
        """
        self.telegram_client = TelegramClient()
        self.redis_client = redis_client
        self.polling_interval = polling_interval
        self.long_poll_timeout = long_poll_timeout
        self.running = False
        self.last_update_ids: Dict[int, int] = {}  # bot_id -> last_update_id

    async def start(self) -> None:
        """Listener'ı başlat (long polling loop)"""
        self.running = True
        logger.info("MessageListenerService started (long polling mode)")

        try:
            while self.running:
                try:
                    await self._poll_all_bots()
                    await asyncio.sleep(self.polling_interval)
                except Exception as e:
                    logger.exception("Error in listener loop: %s", e)
                    await asyncio.sleep(5.0)  # Error durumunda biraz bekle
        finally:
            await self.telegram_client.close()
            logger.info("MessageListenerService stopped")

    async def stop(self) -> None:
        """Listener'ı durdur"""
        self.running = False

    async def _poll_all_bots(self) -> None:
        """Tüm aktif bot'lar için update'leri kontrol et"""
        db = SessionLocal()
        try:
            bots = db.query(Bot).filter(Bot.is_enabled.is_(True)).all()

            for bot in bots:
                try:
                    token = bot.token
                except SecurityConfigError as e:
                    logger.warning("Bot %s token decrypt failed: %s", bot.id, e)
                    continue

                # Son işlenen update_id'yi al
                offset = self.last_update_ids.get(bot.id)
                if offset is not None:
                    offset += 1  # Telegram bir sonraki update'i bekler

                # Telegram'dan update'leri al
                updates = await self.telegram_client.get_updates(
                    token=token,
                    offset=offset,
                    limit=100,
                    timeout=self.long_poll_timeout,
                )

                if not updates:
                    continue

                # Her update'i işle
                for update in updates:
                    update_id = update.get("update_id")
                    if not update_id:
                        continue

                    # Update ID'yi kaydet
                    self.last_update_ids[bot.id] = update_id

                    # Mesajı process et
                    await self._process_update(bot, update, db)

        finally:
            db.close()

    async def _process_update(
        self,
        bot: Bot,
        update: Dict[str, Any],
        db: Any,
    ) -> None:
        """Tek bir Telegram update'ini işle"""
        try:
            update_id = update.get("update_id")

            # Mesaj tipini belirle
            msg_data = update.get("message") or update.get("edited_message")
            if not msg_data:
                # Channel post'ları ignore et
                return

            # Mesaj detaylarını parse et
            telegram_msg_id = msg_data.get("message_id")
            chat_data = msg_data.get("chat", {})
            telegram_chat_id = str(chat_data.get("id", ""))
            from_user = msg_data.get("from", {})
            user_id = from_user.get("id")
            username = from_user.get("username", "")
            text = msg_data.get("text", "")
            reply_to_msg_id = msg_data.get("reply_to_message", {}).get("message_id")

            # Bot mesajlarını ignore et
            if from_user.get("is_bot", False):
                return

            # Chat'i DB'de bul veya oluştur
            chat = db.query(Chat).filter(Chat.chat_id == telegram_chat_id).first()
            if not chat:
                logger.info("Auto-creating chat for telegram_chat_id=%s", telegram_chat_id)
                chat = Chat(
                    chat_id=telegram_chat_id,
                    title=chat_data.get("title") or chat_data.get("first_name") or "Unknown",
                    is_enabled=True,
                    topics=["BIST", "FX", "Kripto", "Makro"],
                )
                db.add(chat)
                db.commit()
                db.refresh(chat)

            # Incoming mesajı DB'ye kaydet
            incoming_msg = Message(
                bot_id=None,  # Kullanıcı mesajı
                chat_db_id=chat.id,
                telegram_message_id=telegram_msg_id,
                text=text,
                reply_to_message_id=reply_to_msg_id,
                msg_metadata={
                    "from_user_id": user_id,
                    "username": username,
                    "is_incoming": True,
                    "update_id": update_id,
                },
            )
            db.add(incoming_msg)
            db.commit()
            db.refresh(incoming_msg)

            logger.info(
                "Incoming message saved: msg_id=%s, chat=%s, user=%s, text_preview=%s",
                telegram_msg_id,
                telegram_chat_id,
                username or user_id,
                text[:50] if text else "(no text)",
            )

            # Redis priority queue'ya ekle
            if self.redis_client:
                try:
                    # Mention detection
                    bot_username = bot.username or ""
                    is_mentioned = False
                    if bot_username and f"@{bot_username.lstrip('@')}" in text:
                        is_mentioned = True

                    # Reply to bot check
                    is_reply_to_bot = False
                    if reply_to_msg_id:
                        replied_msg = db.query(Message).filter(
                            Message.telegram_message_id == reply_to_msg_id,
                            Message.chat_db_id == chat.id,
                            Message.bot_id == bot.id,
                        ).first()
                        if replied_msg:
                            is_reply_to_bot = True

                    # Priority data
                    priority_data = {
                        "type": "incoming_message",
                        "message_id": incoming_msg.id,
                        "telegram_message_id": telegram_msg_id,
                        "chat_id": chat.id,
                        "telegram_chat_id": telegram_chat_id,
                        "bot_id": bot.id,
                        "text": text,
                        "is_mentioned": is_mentioned,
                        "is_reply_to_bot": is_reply_to_bot,
                        "priority": "high" if (is_mentioned or is_reply_to_bot) else "normal",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                    # Redis queue'ya ekle
                    queue_key = (
                        "priority_queue:high"
                        if priority_data["priority"] == "high"
                        else "priority_queue:normal"
                    )
                    self.redis_client.lpush(queue_key, json.dumps(priority_data))
                    logger.debug(
                        "Added to priority queue: %s (priority=%s)",
                        queue_key,
                        priority_data["priority"],
                    )
                except Exception as e:
                    logger.warning("Failed to add to priority queue: %s", e)

        except Exception as e:
            logger.exception("Failed to process update %s: %s", update.get("update_id"), e)


async def run_listener_service(redis_client: Optional[redis.Redis] = None) -> None:
    """
    Listener service'i başlat (long polling mode).

    Not: Webhook kullanıyorsanız bu fonksiyonu çağırmayın.
    """
    polling_interval = float(os.getenv("LISTENER_POLLING_INTERVAL", "1.0"))
    long_poll_timeout = int(os.getenv("LISTENER_LONG_POLL_TIMEOUT", "30"))

    service = MessageListenerService(
        redis_client=redis_client,
        polling_interval=polling_interval,
        long_poll_timeout=long_poll_timeout,
    )

    logger.info("Starting MessageListenerService...")
    await service.start()
