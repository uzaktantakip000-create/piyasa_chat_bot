from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from contextlib import suppress

from dotenv import load_dotenv

# .env ortam değişkenlerini worker için de yükle
load_dotenv()

import redis

from behavior_engine import run_engine_forever
from message_listener import run_listener_service

# (Opsiyonel) Davranış motoru için kapatma kancası
try:
    from behavior_engine import shutdown as behavior_shutdown  # type: ignore
    HAVE_BEHAVIOR_SHUTDOWN = True
except Exception:
    behavior_shutdown = None
    HAVE_BEHAVIOR_SHUTDOWN = False

# ---- Konfig ----
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SHUTDOWN_TIMEOUT = float(os.getenv("SHUTDOWN_TIMEOUT", "15"))  # saniye
# Long polling veya webhook modu (varsayılan: webhook)
USE_LONG_POLLING = os.getenv("USE_LONG_POLLING", "false").lower() in {"1", "true", "yes", "on"}

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("worker")


class GracefulExit(SystemExit):
    """Nazik çıkış için özel istisna."""
    pass


def _install_signal_handlers(loop: asyncio.AbstractEventLoop):
    """SIGINT/SIGTERM geldiğinde nazikçe çıkış tetikle."""
    def _handler():
        raise GracefulExit()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _handler)


def _get_redis_client() -> redis.Redis | None:
    """Redis client oluştur (varsa)"""
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        logger.warning("REDIS_URL not set; priority queue disabled")
        return None
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()  # Test connection
        logger.info("Redis connected: %s", redis_url.split("@")[-1] if "@" in redis_url else redis_url)
        return client
    except Exception as e:
        logger.warning("Redis connection failed: %s. Priority queue disabled.", e)
        return None


async def _amain():
    # Start Prometheus metrics HTTP server for worker metrics
    try:
        from prometheus_client import start_http_server
        WORKER_METRICS_PORT = int(os.getenv("WORKER_METRICS_PORT", "8001"))
        start_http_server(WORKER_METRICS_PORT)
        logger.info(f"Worker Prometheus metrics server started on port {WORKER_METRICS_PORT}")
    except Exception as e:
        logger.warning(f"Failed to start worker metrics server: {e}")

    logger.info("Worker starting… (LOG_LEVEL=%s)", LOG_LEVEL)

    # Redis client (priority queue için)
    redis_client = _get_redis_client()

    # Long polling veya webhook mode
    if USE_LONG_POLLING:
        logger.info("Running in LONG POLLING mode (USE_LONG_POLLING=true)")
        logger.warning(
            "Long polling mode is active. Make sure webhook is disabled on Telegram. "
            "You can disable webhook with: telegram_client.delete_webhook()"
        )

        # Behavior engine ve message listener'ı paralel çalıştır
        await asyncio.gather(
            run_engine_forever(),
            run_listener_service(redis_client=redis_client),
        )
    else:
        logger.info("Running in WEBHOOK mode (USE_LONG_POLLING=false)")
        logger.info("MessageListenerService is disabled. Using webhook endpoint: /webhook/telegram/{bot_token}")

        # Sadece behavior engine'i çalıştır (mesajlar webhook'tan gelecek)
        await run_engine_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worker service runner")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Yalnızca bağımlılık ve modül kontrolünü yapıp çık",
    )
    args, _ = parser.parse_known_args(argv)

    if args.check_only:
        logger.info("Worker check-only modu: modüller yüklendi, çıkılıyor.")
        return 0

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _install_signal_handlers(loop)

    try:
        loop.run_until_complete(_amain())
    except GracefulExit:
        logger.info("Worker shutting down… (signal received)")
    except KeyboardInterrupt:
        logger.info("Worker shutting down… (keyboard interrupt)")
    except Exception as e:
        logger.exception("Worker crashed: %s", e)
        raise
    finally:
        # 1) Davranış motoru için kapatma kancası (varsa)
        if HAVE_BEHAVIOR_SHUTDOWN and behavior_shutdown is not None:
            logger.info("Calling behavior_engine.shutdown() …")
            with suppress(Exception):
                loop.run_until_complete(
                    asyncio.wait_for(behavior_shutdown(), timeout=SHUTDOWN_TIMEOUT)
                )

        # 2) Tüm pending task'leri nazikçe iptal et
        tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for t in tasks:
            t.cancel()

        with suppress(Exception):
            loop.run_until_complete(
                asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=SHUTDOWN_TIMEOUT,
                )
            )

        loop.close()
        logger.info("Worker stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
