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

from behavior_engine import run_engine_forever

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


async def _amain():
    logger.info("Worker starting… (LOG_LEVEL=%s)", LOG_LEVEL)
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
