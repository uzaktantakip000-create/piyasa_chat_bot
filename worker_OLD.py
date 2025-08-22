from __future__ import annotations

import asyncio
import logging
import os
import signal
from contextlib import suppress

from dotenv import load_dotenv
load_dotenv()  # .env ortam değişkenlerini worker için de yükle

from behavior_engine import run_engine_forever

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("worker")


class GracefulExit(SystemExit):
    pass


def _install_signal_handlers(loop: asyncio.AbstractEventLoop):
    def _handler():
        raise GracefulExit()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, _handler)


async def _amain():
    logger.info("Worker starting… (LOG_LEVEL=%s)", LOG_LEVEL)
    await run_engine_forever()


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _install_signal_handlers(loop)

    try:
        loop.run_until_complete(_amain())
    except GracefulExit:
        logger.info("Worker shutting down…")
    except Exception as e:
        logger.exception("Worker crashed: %s", e)
        raise
    finally:
        # tüm pending task'leri iptal et
        tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for t in tasks:
            t.cancel()
        with suppress(Exception):
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        loop.close()
        logger.info("Worker stopped.")


if __name__ == "__main__":
    main()
