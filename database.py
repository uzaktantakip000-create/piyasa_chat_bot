from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Generator, Any, Dict

from sqlalchemy import (
    create_engine, Column, Integer, BigInteger, String, Boolean, Text, DateTime,
    JSON, ForeignKey, Float, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

from security import decrypt_token, encrypt_token, SecurityConfigError
from settings_utils import DEFAULT_MESSAGE_LENGTH_PROFILE

logger = logging.getLogger("database")

# --------------------------------------------------------------------
# Engine & Session
# --------------------------------------------------------------------
# Not: Varsayılan olarak SQLite kullanır. Postgres kullanacaksanız
# DATABASE_URL'i örneğin:
# postgresql+psycopg://user:password@localhost:5432/app
# şeklinde verin.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)

Base = declarative_base()

# --------------------------------------------------------------------
# Models
# --------------------------------------------------------------------
class Bot(Base):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    token_encrypted = Column("token", String(255), nullable=False)
    username = Column(String(100), nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)

    # Davranış ayarları / kişilik
    speed_profile = Column(JSON, default=dict)
    active_hours = Column(JSON, default=list)
    persona_hint = Column(Text, default="")
    # Yeni: kalıcı persona profili (örn. üslup, risk profili, ilgi alanları, yasaklar vb.)
    persona_profile = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    messages = relationship("Message", back_populates="bot", cascade="all,delete-orphan")
    # Yeni ilişkiler
    stances = relationship("BotStance", back_populates="bot", cascade="all,delete-orphan")
    holdings = relationship("BotHolding", back_populates="bot", cascade="all,delete-orphan")

    @property
    def token(self) -> str:
        return decrypt_token(self.token_encrypted)

    @token.setter
    def token(self, raw_token: str) -> None:
        self.token_encrypted = encrypt_token(raw_token)


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    # Telegram chat_id (örn. -1001234567890)
    chat_id = Column(String(64), nullable=False, unique=True)
    title = Column(String(200), nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    # Örn: ["BIST","FX","Kripto","Makro"]
    topics = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    messages = relationship("Message", back_populates="chat", cascade="all,delete-orphan")


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(64), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True, index=True)
    # Not: Chat tablosunun 'id' alanına (INT) referans veriyoruz. Telegram chat_id ile
    # karışmaması için kolon adını 'chat_db_id' tuttuk.
    chat_db_id = Column(Integer, ForeignKey("chats.id", ondelete="SET NULL"), nullable=True, index=True)

    # Telegram message_id (int). Bazı istemciler BIGINT olarak işlemek isteyebilir.
    telegram_message_id = Column(BigInteger, nullable=True)
    text = Column(Text, nullable=True)
    reply_to_message_id = Column(BigInteger, nullable=True)

    # Performans için index
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    bot = relationship("Bot", back_populates="messages")
    chat = relationship("Chat", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_bot_created_at", "bot_id", "created_at"),
        Index("ix_messages_chat_created_at", "chat_db_id", "created_at"),
    )


# Yeni: Bot’un konu bazlı tutumları (tutarlılık için)
class BotStance(Base):
    __tablename__ = "bot_stances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    topic = Column(String(64), nullable=False)           # örn: "Bankacılık", "Kripto", "Makro"
    stance_text = Column(Text, nullable=False)           # kısa tutum metni / kanaat özeti
    confidence = Column(Float, nullable=True)            # 0.0–1.0 arası güven
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    cooldown_until = Column(DateTime, nullable=True)     # bu tarihe kadar keskin fikir değişikliği yapma

    bot = relationship("Bot", back_populates="stances")

    __table_args__ = (
        UniqueConstraint("bot_id", "topic", name="uq_bot_stances_bot_topic"),
        Index("ix_stances_bot_updated", "bot_id", "updated_at"),
    )


# Yeni: Bot’un örnek portföy/pozisyon kayıtları (hikâye sürdürülebilirliği)
class BotHolding(Base):
    __tablename__ = "bot_holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(32), nullable=False)          # örn: "BIST:AKBNK", "XAUUSD", "BTCUSDT"
    avg_price = Column(Float, nullable=True)             # ortalama maliyet
    size = Column(Float, nullable=True)                  # adet/lot (sadece hikâye için)
    note = Column(Text, nullable=True)                   # açıklama (örn. "uzun vade", "kısa vade deneme")
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    bot = relationship("Bot", back_populates="holdings")

    __table_args__ = (
        UniqueConstraint("bot_id", "symbol", name="uq_bot_holdings_bot_symbol"),
        Index("ix_holdings_bot_updated", "bot_id", "updated_at"),
    )


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency - yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create database tables."""
    Base.metadata.create_all(bind=engine)


def migrate_plain_tokens() -> None:
    """Encrypt legacy plaintext bot tokens in place."""
    db = SessionLocal()
    try:
        bots = db.query(Bot).all()
        migrated = 0
        for bot in bots:
            raw_value = bot.token_encrypted
            if raw_value and not raw_value.startswith("gAAAA"):
                bot.token = raw_value  # setter encrypts
                migrated += 1
        if migrated:
            db.commit()
            logger.info("Encrypted %d legacy bot tokens", migrated)
    except SecurityConfigError as exc:
        logger.warning("Skipping token migration: %s", exc)
        db.rollback()
    finally:
        db.close()


def init_default_settings() -> None:
    """
    Varsayılan ayarları (yoksa) ekler.
    Değerler JSON primitive/objeleri olarak saklanır ({"value": ...} gibi sarmal kullanılmaz).
    """
    db = SessionLocal()
    try:
        defaults: Dict[str, Any] = {
            # Akış & gerçekçilik
            "max_msgs_per_min": 6,
            "typing_enabled": True,
            "prime_hours_boost": True,
            "prime_hours": ["09:30-12:00", "14:00-18:00"],

            # Olasılıklar
            "reply_probability": 0.65,
            "mention_probability": 0.35,
            "short_reaction_probability": 0.12,
            "new_message_probability": 0.35,

            # Uzunluk dağılımı
            "message_length_profile": DEFAULT_MESSAGE_LENGTH_PROFILE.copy(),

            # Yazma hızı (WPM)
            "typing_speed_wpm": {"min": 2.5, "max": 4.5},

            # Bot başına oranlar
            "bot_hourly_msg_limit": {"min": 6, "max": 12},

            # Kontrol & metrikler
            "simulation_active": False,
            "scale_factor": 1.0,

            # Metrikler
            "rate_limit_hits": 0,        # (deprecated) geriye dönük uyumluluk
            "telegram_429_count": 0,
            "telegram_5xx_count": 0,
        }

        for k, v in defaults.items():
            row = db.query(Setting).filter(Setting.key == k).first()
            if row is None:
                db.add(Setting(key=k, value=v))

        db.commit()
    finally:
        db.close()
