from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from datetime import datetime, date

from pydantic import BaseModel, Field


# ---------------------------------------------------------
# BOT SCHEMAS
# ---------------------------------------------------------
class BotCreate(BaseModel):
    name: str = Field(..., description="Botun görünen adı")
    token: str = Field(..., description="Telegram BotFather token")
    username: Optional[str] = Field(None, description="Telegram @kullaniciadi (opsiyonel)")
    is_enabled: bool = Field(True, description="Bot aktif mi?")
    speed_profile: Dict[str, Any] = Field(default_factory=dict, description="Davranış profili")
    active_hours: List[str] = Field(default_factory=list, description="Aktif saat aralıkları")
    persona_hint: Optional[str] = Field("", description="Kişilik ipucu (örn: iyimser, kısa yazar)")
    emotion_profile: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Duygusal ton, anekdotlar ve imza ifadeler",
    )
    # Yeni alan opsiyonel olarak kabul edilir (API ile dolduracağız)
    # persona_profile JSON alanı ayrı uçtan yönetilecek


class BotUpdate(BaseModel):
    name: Optional[str] = None
    token: Optional[str] = None
    username: Optional[str] = None
    is_enabled: Optional[bool] = None
    speed_profile: Optional[Dict[str, Any]] = None
    active_hours: Optional[List[str]] = None
    persona_hint: Optional[str] = None
    emotion_profile: Optional[Dict[str, Any]] = None
    # persona_profile bu uçta güncellenmez (ayrı endpoint)


class BotResponse(BaseModel):
    id: int
    name: str
    token_masked: str
    has_token: bool
    username: Optional[str]
    is_enabled: bool
    speed_profile: Dict[str, Any]
    active_hours: List[str]
    persona_hint: Optional[str]
    emotion_profile: Dict[str, Any]
    # DB tarafında JSON; API'de ayrı uçtan alınır/güncellenir
    created_at: datetime

    class Config:
        orm_mode = True


# ---------------------------------------------------------
# CHAT SCHEMAS
# ---------------------------------------------------------
class ChatCreate(BaseModel):
    chat_id: str = Field(..., description="Telegram chat_id (örn. -1001234567890)")
    title: Optional[str] = Field(None, description="Görünen ad")
    is_enabled: bool = Field(True, description="Chat aktif mi?")
    topics: List[str] = Field(default_factory=list, description="Konu etiketleri")


class ChatUpdate(BaseModel):
    chat_id: Optional[str] = None
    title: Optional[str] = None
    is_enabled: Optional[bool] = None
    topics: Optional[List[str]] = None


class ChatResponse(BaseModel):
    id: int
    chat_id: str
    title: Optional[str]
    is_enabled: bool
    topics: List[str]
    created_at: datetime

    class Config:
        orm_mode = True


# ---------------------------------------------------------
# SETTINGS / METRICS
# ---------------------------------------------------------
class SettingResponse(BaseModel):
    key: str
    value: Any
    updated_at: datetime

    class Config:
        orm_mode = True


class MetricsResponse(BaseModel):
    total_bots: int
    active_bots: int
    total_chats: int
    messages_last_hour: int
    messages_per_minute: float
    simulation_active: bool
    scale_factor: float

    # Eski alan (geri uyumluluk)
    rate_limit_hits: int = Field(0, description="(Deprecated) 5xx sayacı için eski alan")

    # Yeni ayrıştırılmış alanlar
    telegram_429_count: int = 0
    telegram_5xx_count: int = 0


# ---------------------------------------------------------
# PERSONA / STANCE / HOLDING (Yeni)
# ---------------------------------------------------------
class PersonaStyle(BaseModel):
    emojis: Optional[bool] = Field(None, description="Emoji kullanımı (kontrollü)")
    length: Optional[str] = Field(None, description="Örn: 'kısa', 'kısa-orta', 'orta'")
    disclaimer: Optional[str] = Field(None, description="Varsayılan kısa dipnot (örn. yatırım tavsiyesi değildir)")


class PersonaProfile(BaseModel):
    tone: Optional[str] = Field(None, description="Üslup (örn. samimi ama profesyonel)")
    risk_profile: Optional[str] = Field(None, description="Örn: düşük / orta / yüksek")
    watchlist: Optional[List[str]] = Field(None, description="Örn: ['BIST:AKBNK','XAUUSD','BTCUSDT']")
    never_do: Optional[List[str]] = Field(None, description="Kaçınılacak içerikler/ifadeler")
    style: Optional[PersonaStyle] = None


class EmotionProfile(BaseModel):
    tone: Optional[str] = Field(None, description="Varsayılan duygu tonu (örn. sıcak ve umutlu)")
    empathy: Optional[str] = Field(None, description="Empati düzeyi veya yaklaşım (örn. kullanıcıyla aynı duyguyu paylaş)")
    anecdotes: Optional[List[str]] = Field(
        None,
        description="Paylaşılabilecek kısa kişisel anekdot havuzu",
    )
    signature_emoji: Optional[str] = Field(None, description="Mesajlara serpiştirilecek imza emoji")
    signature_phrases: Optional[List[str]] = Field(
        None,
        description="Tekrarlı kullanılabilecek sıcak ifadeler",
    )
    energy: Optional[str] = Field(None, description="Enerji seviyesi veya tempo ipucu")


# ---------------- Stance ----------------
class StanceCreate(BaseModel):
    topic: str = Field(..., description="Örn: Bankacılık, Kripto, Makro")
    stance_text: str = Field(..., description="Kısa tutum/kanaat özeti")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="0.0–1.0 arası güven")
    cooldown_until: Optional[datetime] = Field(None, description="Bu zamana kadar keskin görüş değişimi olmasın")


class StanceUpdate(BaseModel):
    topic: Optional[str] = None
    stance_text: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    cooldown_until: Optional[datetime] = None


class StanceResponse(BaseModel):
    id: int
    bot_id: int
    topic: str
    stance_text: str
    confidence: Optional[float]
    updated_at: datetime
    cooldown_until: Optional[datetime]

    class Config:
        orm_mode = True


# ---------------- Holding ----------------
class HoldingCreate(BaseModel):
    symbol: str = Field(..., description="Örn: BIST:AKBNK, XAUUSD, BTCUSDT")
    avg_price: Optional[float] = Field(None, description="Ortalama maliyet")
    size: Optional[float] = Field(None, description="Adet/lot/birim (hikâye amaçlı)")
    note: Optional[str] = Field(None, description="Kısa not (örn. uzun vade)")


class HoldingUpdate(BaseModel):
    symbol: Optional[str] = None
    avg_price: Optional[float] = None
    size: Optional[float] = None
    note: Optional[str] = None


class HoldingResponse(BaseModel):
    id: int
    bot_id: int
    symbol: str
    avg_price: Optional[float]
    size: Optional[float]
    note: Optional[str]
    updated_at: datetime

    class Config:
        orm_mode = True


# ---------------------------------------------------------
# BOT MEMORY SCHEMAS
# ---------------------------------------------------------
class MemoryCreate(BaseModel):
    memory_type: Literal["personal_fact", "past_event", "relationship", "preference", "routine"] = Field(
        ..., description="Hafıza tipi"
    )
    content: str = Field(..., description="Hafıza içeriği (Türkçe doğal dil)")
    relevance_score: Optional[float] = Field(1.0, ge=0.0, le=1.0, description="0.0-1.0 arası önem skoru")


class MemoryUpdate(BaseModel):
    memory_type: Optional[Literal["personal_fact", "past_event", "relationship", "preference", "routine"]] = None
    content: Optional[str] = None
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class MemoryResponse(BaseModel):
    id: int
    bot_id: int
    memory_type: str
    content: str
    relevance_score: float
    created_at: datetime
    last_used_at: datetime
    usage_count: int

    class Config:
        orm_mode = True


# ---------------------------------------------------------
# SYSTEM CHECKS
# ---------------------------------------------------------
class HealthCheckStatus(BaseModel):
    name: str
    status: str
    detail: Optional[str] = None


class SystemCheckStep(BaseModel):
    name: str
    success: bool
    duration: float
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class SystemCheckCreate(BaseModel):
    status: str = Field(..., description="passed/failed gibi durum")
    total_steps: int
    passed_steps: int
    failed_steps: int
    duration: Optional[float] = Field(None, description="Toplam süre (saniye)")
    triggered_by: Optional[str] = Field(None, description="Tetikleyen süreç (örn. oneclick)")
    steps: List[SystemCheckStep]
    health_checks: List[HealthCheckStatus] = Field(
        default_factory=list,
        description="Servis bazlı sağlık kontrollerinin özeti",
    )


class SystemCheckResponse(SystemCheckCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class SystemCheckSummaryBucket(BaseModel):
    date: date
    total: int
    passed: int
    failed: int


class SystemCheckSummaryInsight(BaseModel):
    level: Literal["info", "success", "warning", "critical"]
    message: str


class SystemCheckSummaryRun(BaseModel):
    id: int
    status: str
    created_at: datetime
    duration: Optional[float] = None
    triggered_by: Optional[str] = None
    total_steps: Optional[int] = None
    passed_steps: Optional[int] = None
    failed_steps: Optional[int] = None


class SystemCheckSummaryResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    total_runs: int
    passed_runs: int
    failed_runs: int
    success_rate: float
    average_duration: Optional[float]
    last_run_at: Optional[datetime]
    daily_breakdown: List[SystemCheckSummaryBucket]
    overall_status: Literal["empty", "healthy", "warning", "critical"]
    overall_message: str
    insights: List[SystemCheckSummaryInsight] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    recent_runs: List[SystemCheckSummaryRun] = Field(default_factory=list)


class LoginRequest(BaseModel):
    username: str
    password: str
    totp: Optional[str] = Field(None, description="6 haneli MFA kodu")


class LoginResponse(BaseModel):
    api_key: str
    role: str
    session_expires_at: datetime


class RotateApiKeyRequest(BaseModel):
    username: str
    password: str
    totp: Optional[str] = None


class UserInfoResponse(BaseModel):
    username: str
    role: str
    api_key_last_rotated: datetime


# ---------------------------------------------------------
# USER MANAGEMENT SCHEMAS
# ---------------------------------------------------------
class UserCreateRequest(BaseModel):
    username: str = Field(..., description="Kullanıcı adı (benzersiz)", min_length=3, max_length=64)
    password: str = Field(..., description="Şifre", min_length=6)
    role: str = Field(..., description="Rol: viewer, operator, admin")
    mfa_enabled: bool = Field(False, description="MFA aktif mi?")


class UserUpdateRequest(BaseModel):
    role: Optional[str] = Field(None, description="Yeni rol: viewer, operator, admin")
    is_active: Optional[bool] = Field(None, description="Kullanıcı aktif mi?")
    reset_password: Optional[str] = Field(None, description="Yeni şifre (sadece şifre değiştirmek için)", min_length=6)


class UserListResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    mfa_enabled: bool
    created_at: datetime
    api_key_last_rotated: datetime

    class Config:
        orm_mode = True


# ---------------------------------------------------------
# DEMO BOTS SCHEMAS
# ---------------------------------------------------------
class DemoBotsCreate(BaseModel):
    count: int = Field(..., description="Oluşturulacak demo bot sayısı", ge=1, le=50)
