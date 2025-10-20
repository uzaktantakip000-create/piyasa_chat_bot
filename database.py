from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Generator, Any, Dict, Optional, Tuple

from sqlalchemy import (
    create_engine, Column, Integer, BigInteger, String, Boolean, Text, DateTime,
    JSON, ForeignKey, Float, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

from auth_utils import (
    hash_secret,
    verify_secret,
    generate_api_key,
    generate_session_token,
    generate_totp_secret,
    verify_totp,
)
from security import decrypt_token, encrypt_token, SecurityConfigError
from settings_utils import DEFAULT_MESSAGE_LENGTH_PROFILE
from news_client import DEFAULT_FEEDS

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
    pool_size=20,  # Increased from default 5 for concurrent load
    max_overflow=40,  # Increased from default 10
    pool_pre_ping=True,  # Verify connections before using
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
    # Yeni: duygusal ton, anekdot havuzu ve imza ifadeleri
    emotion_profile = Column(JSON, default=dict)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

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

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    messages = relationship("Message", back_populates="chat", cascade="all,delete-orphan")


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(64), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True, index=True)
    # Not: Chat tablosunun 'id' alanına (INT) referans veriyoruz. Telegram chat_id ile
    # karışmaması için kolon adını 'chat_db_id' tuttuk.
    chat_db_id = Column(Integer, ForeignKey("chats.id", ondelete="SET NULL"), nullable=True, index=True)

    # Telegram message_id (int). Bazı istemciler BIGINT olarak işlemek isteyebilir.
    telegram_message_id = Column(BigInteger, nullable=True, index=True)
    text = Column(Text, nullable=True)
    reply_to_message_id = Column(BigInteger, nullable=True, index=True)

    # Performans için index
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Mesaj metadata - bağlam hatırlama için
    # Örnek: {"topic": "BIST", "symbols": ["AKBNK", "GARAN"], "sentiment": "positive", "references": [123, 456]}
    msg_metadata = Column(JSON, default=dict, nullable=True)

    bot = relationship("Bot", back_populates="messages")
    chat = relationship("Chat", back_populates="messages")

    __table_args__ = (
        # Composite indexes for common queries
        Index("ix_messages_bot_created_at", "bot_id", "created_at"),
        Index("ix_messages_chat_created_at", "chat_db_id", "created_at"),
        Index("ix_messages_chat_telegram_msg", "chat_db_id", "telegram_message_id"),
        # Index for reply lookups
        Index("ix_messages_reply_lookup", "chat_db_id", "bot_id", "telegram_message_id"),
        # Index for incoming message processing (bot_id NULL check + created_at)
        Index("ix_messages_incoming", "bot_id", "created_at", "chat_db_id"),
    )


# Yeni: Bot’un konu bazlı tutumları (tutarlılık için)
class BotStance(Base):
    __tablename__ = "bot_stances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    topic = Column(String(64), nullable=False)           # örn: "Bankacılık", "Kripto", "Makro"
    stance_text = Column(Text, nullable=False)           # kısa tutum metni / kanaat özeti
    confidence = Column(Float, nullable=True)            # 0.0–1.0 arası güven
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
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
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    bot = relationship("Bot", back_populates="holdings")

    __table_args__ = (
        UniqueConstraint("bot_id", "symbol", name="uq_bot_holdings_bot_symbol"),
        Index("ix_holdings_bot_updated", "bot_id", "updated_at"),
    )


class BotMemory(Base):
    """
    Kişisel hafıza sistemi: Bot'un tutarlı geçmiş hikayesi, anıları ve ilişkileri.

    memory_type örnekleri:
    - 'personal_fact': Kişisel bilgi (örn: "İstanbul'da yaşıyorum", "Yazılımcıyım")
    - 'past_event': Geçmiş olay/anı (örn: "2023'te BIST'ten 30% kâr ettim", "Kripto'da yanmıştım")
    - 'relationship': İlişki bilgisi (örn: "@AliTrader arkadaşımdır", "@MehmetYatırımcı ile her zaman tartışırız")
    - 'preference': Tercihler (örn: "Teknik analize inanmam", "Altın sevmem")
    - 'routine': Rutin davranışlar (örn: "Sabahları ilk işim BIST'e bakmaktır")
    """
    __tablename__ = "bot_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    memory_type = Column(String(32), nullable=False)  # personal_fact, past_event, relationship, preference, routine
    content = Column(Text, nullable=False)  # Hafıza içeriği (Türkçe doğal dil)
    relevance_score = Column(Float, default=1.0, nullable=False)  # 0.0-1.0, düşük skorlular zaman içinde unutulabilir
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_used_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)  # Son kullanım zamanı
    usage_count = Column(Integer, default=0, nullable=False)  # Kaç kez konuşmalarda kullanıldı

    bot = relationship("Bot", backref="memories")

    __table_args__ = (
        Index("ix_memories_bot_type", "bot_id", "memory_type"),
        Index("ix_memories_bot_relevance", "bot_id", "relevance_score"),
    )


class SystemCheck(Base):
    __tablename__ = "system_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(32), nullable=False)
    total_steps = Column(Integer, nullable=False)
    passed_steps = Column(Integer, nullable=False)
    failed_steps = Column(Integer, nullable=False)
    duration = Column(Float, nullable=True)
    triggered_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    details = Column(JSON, default=dict)

    __table_args__ = (
        Index("ix_system_checks_created", "created_at"),
    )


class ApiUser(Base):
    """RBAC destekli panel/API kullanıcı modeli."""

    __tablename__ = "api_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), nullable=False, unique=True, index=True)
    role = Column(String(32), nullable=False, default="viewer")
    password_hash = Column(String(256), nullable=False)
    password_salt = Column(String(32), nullable=False)
    mfa_secret = Column(String(32), nullable=True)
    api_key_hash = Column(String(128), nullable=False)
    api_key_salt = Column(String(32), nullable=False)
    api_key_last_rotated = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ApiSession(Base):
    __tablename__ = "api_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("api_users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_id = Column(String(32), nullable=False, index=True)
    session_hash = Column(String(128), nullable=False)
    session_salt = Column(String(32), nullable=False)
    user_agent = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    user = relationship("ApiUser", backref="sessions")

    __table_args__ = (
        # Index for session validation (token lookup + active + not expired)
        Index("ix_sessions_token_active_expires", "token_id", "is_active", "expires_at"),
        # Index for session cleanup (expired sessions)
        Index("ix_sessions_expires_active", "expires_at", "is_active"),
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
            "reply_probability": 0.65,  # Genel reply ihtimali
            "reply_to_bots_probability": 0.5,  # Bot mesajlarına özel reply ihtimali (Week 2 Day 4-5)
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

            # Persona yenileme
            "persona_refresh_interval": 8,
            "persona_refresh_minutes": 30,

            # Metrikler
            "rate_limit_hits": 0,        # (deprecated) geriye dönük uyumluluk
            "telegram_429_count": 0,
            "telegram_5xx_count": 0,
            # Haber akışı RSS adresleri
            "news_feed_urls": list(DEFAULT_FEEDS),

            # PHASE 2 Week 3: Semantic Deduplication
            "semantic_dedup_enabled": True,  # Anlamsal benzerlik kontrolü

            # PHASE 2 Week 4 Day 1-3: Rich News Integration
            "news_trigger_enabled": True,     # Haber tetikleyici aktif mi?
            "news_trigger_probability": 0.5,  # %50 olasılıkla haber kullan (was 0.75)
        }

        for k, v in defaults.items():
            row = db.query(Setting).filter(Setting.key == k).first()
            if row is None:
                db.add(Setting(key=k, value=v))

        db.commit()
    finally:
        db.close()


def init_demo_bots() -> None:
    """
    İlk kurulumda demo bot'ları otomatik yükle.
    Bu fonksiyon startup'ta çağrılır, bot yoksa 6 demo bot'u oluşturur.
    """
    try:
        from init_demo_bots import init_demo_bots as load_demo_bots
        load_demo_bots()
    except Exception as exc:
        logger.warning("Demo bot'ları yüklenemedi: %s", exc)


def migrate_news_feed_urls_setting() -> None:
    """Ensure the ``news_feed_urls`` setting exists for legacy installs."""
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == "news_feed_urls").first()
        if row is None:
            db.add(Setting(key="news_feed_urls", value=list(DEFAULT_FEEDS)))
            db.commit()
            logger.info("Added default news_feed_urls setting for legacy database.")
        elif not isinstance(row.value, list):
            row.value = list(DEFAULT_FEEDS)
            db.commit()
            logger.info("Normalized news_feed_urls setting to list value.")
    finally:
        db.close()


def _validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength for admin accounts.
    Returns: (is_valid, error_message)
    """
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"

    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`" for c in password)

    if not has_upper:
        return False, "Password must contain at least one uppercase letter"
    if not has_lower:
        return False, "Password must contain at least one lowercase letter"
    if not has_digit:
        return False, "Password must contain at least one digit"
    if not has_special:
        return False, "Password must contain at least one special character (!@#$%^&* etc.)"

    # Check for common weak passwords
    weak_passwords = {"password123!", "Admin123!", "admin123!", "Password123!"}
    if password in weak_passwords:
        return False, "Password is too common; please use a unique strong password"

    return True, ""


def ensure_default_admin_user() -> Optional[Dict[str, str]]:
    """Create the default admin user with MFA and API key if requested."""

    username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    password = os.getenv("DEFAULT_ADMIN_PASSWORD")
    role = os.getenv("DEFAULT_ADMIN_ROLE", "admin")
    mfa_secret = os.getenv("DEFAULT_ADMIN_MFA_SECRET")
    provided_api_key = os.getenv("DEFAULT_ADMIN_API_KEY")

    if not password:
        logger.warning("DEFAULT_ADMIN_PASSWORD not set; skipping default admin creation.")
        return None

    # Validate password strength
    is_valid, error_msg = _validate_password_strength(password)
    if not is_valid:
        logger.error(
            "DEFAULT_ADMIN_PASSWORD validation failed: %s. "
            "Admin user creation skipped for security. "
            "Please set a strong password in .env (min 12 chars, uppercase, lowercase, digit, special char).",
            error_msg
        )
        return None

    db = SessionLocal()
    try:
        existing = db.query(ApiUser).filter(ApiUser.username == username).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                db.commit()
            return None

        password_hash, password_salt = hash_secret(password)
        if provided_api_key:
            api_key_plain = provided_api_key
            api_key_hash, api_key_salt = hash_secret(provided_api_key)
        else:
            api_key_plain, api_key_hash, api_key_salt = generate_api_key()

        if not mfa_secret:
            mfa_secret = generate_totp_secret()

        user = ApiUser(
            username=username,
            role=role,
            password_hash=password_hash,
            password_salt=password_salt,
            mfa_secret=mfa_secret,
            api_key_hash=api_key_hash,
            api_key_salt=api_key_salt,
            api_key_last_rotated=datetime.now(timezone.utc),
            is_active=True,
        )
        db.add(user)
        db.commit()
        logger.info("Default admin user '%s' created with role '%s'.", username, role)
        return {
            "username": username,
            "api_key": api_key_plain,
            "mfa_secret": mfa_secret,
        }
    finally:
        db.close()


def get_user_by_api_key(db: Session, api_key: str) -> Optional[ApiUser]:
    if not api_key:
        return None
    candidates = db.query(ApiUser).filter(ApiUser.is_active.is_(True)).all()
    for candidate in candidates:
        if verify_secret(api_key, candidate.api_key_hash, candidate.api_key_salt):
            return candidate
    return None


def create_user_session(
    db: Session,
    user: ApiUser,
    *,
    ttl_hours: int = 12,
    user_agent: Optional[str] = None,
) -> Tuple[str, ApiSession]:
    token_id, token_secret, session_hash, session_salt = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    session = ApiSession(
        user_id=user.id,
        token_id=token_id,
        session_hash=session_hash,
        session_salt=session_salt,
        user_agent=user_agent,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return f"{token_id}.{token_secret}", session


def get_user_by_session_token(db: Session, token: str) -> Optional[ApiUser]:
    if not token or "." not in token:
        return None
    token_id, token_secret = token.split(".", 1)
    session = (
        db.query(ApiSession)
        .filter(
            ApiSession.token_id == token_id,
            ApiSession.is_active.is_(True),
            ApiSession.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if not session:
        return None
    if not verify_secret(token_secret, session.session_hash, session.session_salt):
        return None
    session.last_seen_at = datetime.now(timezone.utc)
    db.add(session)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return session.user


def invalidate_session(db: Session, token: str) -> None:
    if not token or "." not in token:
        return
    token_id, token_secret = token.split(".", 1)
    session = (
        db.query(ApiSession)
        .filter(ApiSession.token_id == token_id, ApiSession.is_active.is_(True))
        .first()
    )
    if not session:
        return
    if not verify_secret(token_secret, session.session_hash, session.session_salt):
        return
    session.is_active = False
    db.add(session)
    db.commit()


def purge_expired_sessions(db: Optional[Session] = None) -> int:
    owns_session = False
    if db is None:
        db = SessionLocal()
        owns_session = True
    try:
        now = datetime.now(timezone.utc)
        sessions = (
            db.query(ApiSession)
            .filter(ApiSession.expires_at <= now, ApiSession.is_active.is_(True))
            .all()
        )
        for session in sessions:
            session.is_active = False
            db.add(session)
        count = len(sessions)
        if count:
            db.commit()
        else:
            db.rollback()
        return count
    finally:
        if owns_session and db is not None:
            db.close()


def authenticate_user(db: Session, username: str, password: str, totp: Optional[str]) -> Optional[ApiUser]:
    user = db.query(ApiUser).filter(ApiUser.username == username, ApiUser.is_active.is_(True)).first()
    if not user:
        return None
    if not verify_secret(password, user.password_hash, user.password_salt):
        return None
    if user.mfa_secret:
        if not totp or not verify_totp(user.mfa_secret, totp):
            return None
    return user


def rotate_user_api_key(db: Session, user: ApiUser) -> str:
    api_key, api_key_hash, api_key_salt = generate_api_key()
    user.api_key_hash = api_key_hash
    user.api_key_salt = api_key_salt
    user.api_key_last_rotated = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return api_key


def update_user_password(db: Session, user: ApiUser, new_password: str) -> None:
    password_hash, password_salt = hash_secret(new_password)
    user.password_hash = password_hash
    user.password_salt = password_salt
    db.add(user)
    db.commit()


def create_api_user(
    username: str,
    password: str,
    role: str = "viewer",
    *,
    mfa_secret: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, str]:
    """Helper for provisioning API users programmatically."""

    db = SessionLocal()
    try:
        if db.query(ApiUser).filter(ApiUser.username == username).first():
            raise ValueError(f"User '{username}' already exists")

        password_hash, password_salt = hash_secret(password)
        if api_key:
            api_plain = api_key
            api_key_hash, api_key_salt = hash_secret(api_key)
        else:
            api_plain, api_key_hash, api_key_salt = generate_api_key()
        if not mfa_secret:
            mfa_secret = generate_totp_secret()

        user = ApiUser(
            username=username,
            role=role,
            password_hash=password_hash,
            password_salt=password_salt,
            mfa_secret=mfa_secret,
            api_key_hash=api_key_hash,
            api_key_salt=api_key_salt,
            api_key_last_rotated=datetime.now(timezone.utc),
            is_active=True,
        )
        db.add(user)
        db.commit()
        return {"api_key": api_plain, "mfa_secret": mfa_secret, "role": role}
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database utilities")
    parser.add_argument(
        "--migrate-news-feed-urls",
        action="store_true",
        help="Ensure news_feed_urls setting exists with default feeds.",
    )
    args = parser.parse_args()

    if args.migrate_news_feed_urls:
        migrate_news_feed_urls_setting()
