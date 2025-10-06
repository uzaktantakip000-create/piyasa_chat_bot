from __future__ import annotations

from typing import Any, Dict, List, Optional
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
