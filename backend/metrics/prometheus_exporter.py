"""
Prometheus metrics exporter.

Bu modül Prometheus için metrikleri toplar ve dışa aktarır.

Basit Açıklama:
- Counter: Sayaç (hep artar, örn: toplam mesaj sayısı)
- Gauge: Anlık değer (artıp azalır, örn: aktif bot sayısı)
- Histogram: Dağılım (örn: mesaj üretme süresi - ortalama, p95, p99)
"""
import time
import logging
from typing import Optional

from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ============================================================================
# MESAJ ÜRETİMİ METRİKLERİ
# ============================================================================

message_generation_total = Counter(
    "message_generation_total",
    "Toplam üretilen mesaj sayısı",
    ["bot_id", "status"]  # status: success | failed
)
"""
Basit Açıklama: Kaç mesaj üretildi? (başarılı/başarısız ayrı ayrı)
Örnek: message_generation_total{bot_id="123", status="success"} = 450
"""

message_generation_duration_seconds = Histogram(
    "message_generation_duration_seconds",
    "Mesaj üretme süresi (saniye)",
    buckets=[0.5, 1, 2, 5, 10, 30, 60]  # 0.5s, 1s, 2s, 5s, 10s, 30s, 60s
)
"""
Basit Açıklama: Mesaj üretmek ne kadar sürdü?
- Ortalama: 3 saniye
- %95'i: 5 saniye altında
- %99'u: 10 saniye altında
"""

# ============================================================================
# BOT METRİKLERİ
# ============================================================================

active_bots_gauge = Gauge(
    "active_bots_total",
    "Aktif bot sayısı (is_enabled=True)"
)
"""
Basit Açıklama: Şu an kaç bot çalışıyor?
Örnek: active_bots_total = 25
"""

# ============================================================================
# VERİTABANI METRİKLERİ
# ============================================================================

database_query_duration_seconds = Histogram(
    "database_query_duration_seconds",
    "Veritabanı sorgu süresi (saniye)",
    ["query_type"],  # query_type: select | insert | update | delete
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5]  # 10ms, 50ms, 100ms, 500ms, 1s, 2s, 5s
)
"""
Basit Açıklama: Veritabanı sorguları ne kadar sürüyor?
Örnek: SELECT sorguları ortalama 50ms
"""

database_connections_gauge = Gauge(
    "database_connections_active",
    "Aktif veritabanı bağlantı sayısı"
)
"""
Basit Açıklama: Veritabanına kaç bağlantı açık?
Örnek: database_connections_active = 12 / 20 (pool size)
"""

# ============================================================================
# TELEGRAM API METRİKLERİ
# ============================================================================

telegram_api_calls_total = Counter(
    "telegram_api_calls_total",
    "Telegram API çağrı sayısı",
    ["method", "status"]  # method: sendMessage | setReaction, status: 200 | 429 | 500
)
"""
Basit Açıklama: Telegram'a kaç istek attık? Kaçı başarılı?
Örnek:
- sendMessage, 200 (başarılı): 1000
- sendMessage, 429 (rate limit): 5
"""

# ============================================================================
# LLM (Yapay Zeka) METRİKLERİ
# ============================================================================

llm_api_calls_total = Counter(
    "llm_api_calls_total",
    "LLM API çağrı sayısı",
    ["provider", "model", "status"]  # provider: openai | gemini | groq
)
"""
Basit Açıklama: Yapay zekaya kaç soru sorduk?
Örnek: openai, gpt-4o-mini, success: 500
"""

llm_token_usage_total = Counter(
    "llm_token_usage_total",
    "LLM token kullanımı (maliyet hesabı için)",
    ["provider", "model", "type"]  # type: prompt | completion
)
"""
Basit Açıklama: Kaç token harcadık? (maliyet = token * birim fiyat)
Örnek: openai, gpt-4o-mini, prompt: 100000 token
"""

# ============================================================================
# HTTP API METRİKLERİ
# ============================================================================

http_requests_total = Counter(
    "http_requests_total",
    "HTTP istek sayısı",
    ["method", "endpoint", "status"]  # method: GET | POST, endpoint: /bots, status: 200
)
"""
Basit Açıklama: API'ye kaç istek geldi?
Örnek: GET /bots 200: 150 istek
"""

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP istek süresi (saniye)",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10]
)
"""
Basit Açıklama: API istekleri ne kadar sürdü?
Örnek: GET /bots ortalama 100ms
"""

# ============================================================================
# MIDDLEWARE - Otomatik HTTP Metrik Toplama
# ============================================================================

class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware: Her HTTP isteğini otomatik ölçer.

    Basit Açıklama:
    Bu kod her API isteğinde otomatik çalışır:
    1. İstek geldi → Kronometre başlat
    2. İstek işlendi
    3. Kronometre durdur → Süreyi kaydet
    """

    async def dispatch(self, request: Request, call_next):
        # Kronometre başlat
        start_time = time.time()

        # İsteği işle
        response = await call_next(request)

        # Kronometre durdur
        duration = time.time() - start_time

        # Endpoint'i temizle (parametre değil, sadece yol)
        # Örnek: /bots/123 → /bots/{id}
        endpoint = self._clean_endpoint(request.url.path)

        # Metrikleri kaydet
        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=endpoint
        ).observe(duration)

        return response

    def _clean_endpoint(self, path: str) -> str:
        """
        URL path'i temizle (ID'leri kaldır).

        Örnek:
        - /bots/123 → /bots/{id}
        - /chats/456/messages → /chats/{id}/messages
        """
        # Basit temizleme (sayıları {id} ile değiştir)
        import re
        # /bots/123 → /bots/{id}
        cleaned = re.sub(r'/\d+', '/{id}', path)
        return cleaned

# ============================================================================
# SETUP FUNCTION
# ============================================================================

def setup_metrics(app):
    """
    Prometheus metrics'i FastAPI app'e entegre et.

    Basit Açıklama:
    Bu fonksiyon app başlarken bir kere çalışır:
    1. Middleware ekler (otomatik HTTP ölçümü)
    2. /metrics endpoint'i ekler (Prometheus buradan okur)

    Kullanım:
    ```python
    from fastapi import FastAPI
    from backend.metrics import setup_metrics

    app = FastAPI()
    setup_metrics(app)
    ```
    """
    from fastapi import Response

    # Middleware ekle (otomatik HTTP metrik toplama)
    app.add_middleware(PrometheusMiddleware)
    logger.info("Prometheus middleware eklendi (HTTP metrikleri otomatik toplanacak)")

    # /metrics endpoint ekle (Prometheus buradan okur)
    @app.get("/metrics", include_in_schema=False)
    def metrics():
        """
        Prometheus metrics endpoint.

        Basit Açıklama:
        Prometheus bu endpoint'e her 15 saniyede bir gelir, metrikleri okur.
        """
        return Response(content=generate_latest(REGISTRY), media_type="text/plain")

    logger.info("Prometheus metrics endpoint eklendi: /metrics")
    logger.info("Prometheus şu URL'den metrikleri okuyabilir: http://localhost:8000/metrics")

    return app

# ============================================================================
# HELPER FUNCTIONS - Metrikleri Kolayca Kullanmak İçin
# ============================================================================

class MetricTimer:
    """
    Context manager: Kod bloğunun süresini ölç.

    Basit Açıklama:
    Kullanımı çok kolay:
    ```python
    with MetricTimer(message_generation_duration_seconds):
        # Bu kod bloğu ne kadar sürer?
        message = generate_message()
    # Otomatik olarak süre kaydedildi!
    ```
    """

    def __init__(self, histogram: Histogram):
        self.histogram = histogram
        self.start_time: Optional[float] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.histogram.observe(duration)

# Kullanım örneği:
# with MetricTimer(message_generation_duration_seconds):
#     message = generate_message()
