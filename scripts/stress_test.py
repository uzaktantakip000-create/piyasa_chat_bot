"""Simple stress testing utility for the FastAPI application.

The script spins up an in-process TestClient and issues concurrent
requests against the API endpoints that the dashboard exercises most
frequently (metrics fetch, bot CRUD operations and control toggles).

Usage:
    python scripts/stress_test.py --duration 60 --concurrency 4
"""

from __future__ import annotations

import argparse
import base64
import importlib
import os
import random
import secrets
import string
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient


def random_token() -> str:
    prefix = ''.join(random.choices(string.digits, k=5))
    suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
    return f"{prefix}:{suffix}"


def _generate_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def configure_environment(database_url: str, api_key: str) -> None:
    os.environ['DATABASE_URL'] = database_url
    os.environ['API_KEY'] = api_key
    os.environ.setdefault('TOKEN_ENCRYPTION_KEY', _generate_key())

    # Reload modules so they pick up the ephemeral configuration.
    import security
    import database
    import main

    importlib.reload(security)
    importlib.reload(database)
    importlib.reload(main)


def worker_thread(app, api_key: str, duration: float, results: List[Tuple[float, str]], lock: threading.Lock) -> int:
    completed = 0
    headers = {'X-API-Key': api_key}
    started_at = time.time()

    with TestClient(app) as client:
        created_bot_ids: List[int] = []
        while time.time() - started_at < duration:
            action = random.choice(['metrics', 'bots', 'toggle', 'control'])
            try:
                if action == 'metrics':
                    response = client.get('/metrics', headers=headers)
                    response.raise_for_status()
                elif action == 'bots':
                    if not created_bot_ids or random.random() < 0.3:
                        payload = {
                            'name': f'StressBot-{random.randint(1, 9999)}',
                            'token': random_token(),
                            'username': f'stress_bot_{random.randint(1, 9999)}',
                            'is_enabled': True,
                            'speed_profile': {'mode': 'stress'},
                            'active_hours': ['09:00-18:00'],
                            'persona_hint': 'otomatik test'
                        }
                        response = client.post('/bots', json=payload, headers=headers)
                        response.raise_for_status()
                        created_bot_ids.append(response.json()['id'])
                    else:
                        target_id = random.choice(created_bot_ids)
                        desired_state = random.choice([True, False])
                        response = client.patch(
                            f'/bots/{target_id}',
                            json={'is_enabled': desired_state},
                            headers=headers,
                        )
                        response.raise_for_status()
                elif action == 'toggle':
                    endpoint = random.choice(['/control/start', '/control/stop'])
                    response = client.post(endpoint, headers=headers)
                    response.raise_for_status()
                else:
                    factor = round(random.uniform(0.5, 2.0), 2)
                    response = client.post('/control/scale', json={'factor': factor}, headers=headers)
                    response.raise_for_status()
                completed += 1
            except Exception as exc:  # noqa: BLE001 - collect any error for the summary
                with lock:
                    results.append((time.time(), str(exc)))
            finally:
                time.sleep(0.05)
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description='In-process stress test runner')
    parser.add_argument('--duration', type=int, default=120, help='Test süresi (saniye cinsinden)')
    parser.add_argument('--concurrency', type=int, default=4, help='Eşzamanlı iş parçacığı sayısı')
    parser.add_argument('--database-url', default='sqlite:///./stress_test.db', help='Geçici veritabanı bağlantısı')
    parser.add_argument('--api-key', default='stress-key', help='Testte kullanılacak API anahtarı')
    args = parser.parse_args()

    configure_environment(args.database_url, args.api_key)
    from main import app  # reloaded in configure_environment

    errors: List[Tuple[float, str]] = []
    lock = threading.Lock()

    # Warm up once to create tables and defaults before starting concurrent clients.
    with TestClient(app) as warm_client:
        warm_client.get('/healthz', headers={'X-API-Key': args.api_key})

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(worker_thread, app, args.api_key, args.duration, errors, lock)
            for _ in range(args.concurrency)
        ]
        total_requests = sum(future.result() for future in as_completed(futures))

    print('=' * 60)
    print('Stress Test Özeti')
    print(f'Süre: {args.duration} sn | Eşzamanlılık: {args.concurrency} | Toplam istek: {total_requests}')
    if errors:
        print(f'Hata sayısı: {len(errors)}')
        for ts, message in errors[:10]:
            formatted = time.strftime('%H:%M:%S', time.localtime(ts))
            print(f'- [{formatted}] {message}')
        if len(errors) > 10:
            print(f'  ... {len(errors) - 10} ek hata daha')
    else:
        print('Hata gözlenmedi.')
    print('=' * 60)


if __name__ == '__main__':
    main()
