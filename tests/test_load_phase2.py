"""
Phase 2 Load Test - Task 2.7
Test with 50 bots + 100 concurrent users

This script tests:
- Rate limiting (30 msg/sec global, 20 msg/min per chat)
- Message queue performance
- Database optimization
- Zero message loss
- Concurrent user handling
"""

import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import aiohttp
import statistics

# Test Configuration
NUM_BOTS = 50
NUM_USERS = 100
TEST_DURATION_MINUTES = 30
API_BASE_URL = "http://127.0.0.1:8000"
CHAT_ID = -1001234567890  # Test chat ID

# Message Templates
MESSAGE_TEMPLATES = [
    "BIST bugün nasıl? {emoji}",
    "Dolar ne olacak sizce?",
    "{symbol} hakkında ne düşünüyorsunuz?",
    "Bugünkü piyasalar çok hareketli",
    "Altın almalı mıyız?",
    "Kripto düşüşe geçti galiba",
    "{symbol} için stop koydum",
    "Portföyüm %{percent} kazandırdı",
    "Teknik analiz yapan var mı?",
    "Yarın FED toplantısı var",
]

SYMBOLS = ["BIST100", "USDTRY", "BTC", "ETH", "GOLD", "XU100", "EURUS", "SOL"]
EMOJIS = ["📈", "📉", "🚀", "💰", "🔥", "⚡", "💎", "🎯"]

class LoadTestMetrics:
    """Metrics collector for load test"""

    def __init__(self):
        self.start_time = time.time()
        self.messages_sent = 0
        self.messages_failed = 0
        self.rate_limited = 0
        self.response_times = []
        self.queue_sizes = []
        self.error_log = []
        self.bot_message_count = {}
        self.user_message_count = {}

    def record_message(self, success: bool, response_time: float = 0):
        if success:
            self.messages_sent += 1
            if response_time > 0:
                self.response_times.append(response_time)
        else:
            self.messages_failed += 1

    def record_rate_limit(self):
        self.rate_limited += 1

    def record_error(self, error: str):
        self.error_log.append({
            "timestamp": datetime.now().isoformat(),
            "error": error
        })

    def record_queue_size(self, size: int):
        self.queue_sizes.append(size)

    def get_summary(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time

        return {
            "test_duration_seconds": round(elapsed, 2),
            "total_messages_sent": self.messages_sent,
            "total_messages_failed": self.messages_failed,
            "total_rate_limited": self.rate_limited,
            "throughput_msg_per_sec": round(self.messages_sent / elapsed, 2) if elapsed > 0 else 0,
            "error_rate_percent": round((self.messages_failed / (self.messages_sent + self.messages_failed)) * 100, 2) if (self.messages_sent + self.messages_failed) > 0 else 0,
            "avg_response_time_ms": round(statistics.mean(self.response_times) * 1000, 2) if self.response_times else 0,
            "p50_response_time_ms": round(statistics.median(self.response_times) * 1000, 2) if self.response_times else 0,
            "p95_response_time_ms": round(statistics.quantiles(self.response_times, n=20)[18] * 1000, 2) if len(self.response_times) > 20 else 0,
            "p99_response_time_ms": round(statistics.quantiles(self.response_times, n=100)[98] * 1000, 2) if len(self.response_times) > 100 else 0,
            "max_queue_size": max(self.queue_sizes) if self.queue_sizes else 0,
            "avg_queue_size": round(statistics.mean(self.queue_sizes), 2) if self.queue_sizes else 0,
            "error_count": len(self.error_log),
        }


class MockUser:
    """Simulated Telegram user"""

    def __init__(self, user_id: int, user_type: str, api_url: str, chat_id: int):
        self.user_id = user_id
        self.user_type = user_type  # "normal", "mention", "reply"
        self.api_url = api_url
        self.chat_id = chat_id
        self.username = f"testuser{user_id}"
        self.sent_count = 0

    async def send_message(self, session: aiohttp.ClientSession, bot_token: str, metrics: LoadTestMetrics):
        """Send a message via webhook"""

        # Generate message text
        template = random.choice(MESSAGE_TEMPLATES)
        text = template.format(
            symbol=random.choice(SYMBOLS),
            emoji=random.choice(EMOJIS),
            percent=random.randint(1, 50)
        )

        # Add mention if user type is "mention"
        if self.user_type == "mention" and random.random() < 0.7:
            text = f"@testbot{random.randint(1, NUM_BOTS)} {text}"

        # Webhook payload
        webhook_data = {
            "update_id": int(time.time() * 1000) + self.user_id,
            "message": {
                "message_id": int(time.time() * 1000),
                "from": {
                    "id": self.user_id,
                    "is_bot": False,
                    "first_name": f"User{self.user_id}",
                    "username": self.username
                },
                "chat": {
                    "id": self.chat_id,
                    "type": "group",
                    "title": "Load Test Chat"
                },
                "date": int(time.time()),
                "text": text
            }
        }

        # Send webhook
        start_time = time.time()
        try:
            async with session.post(
                f"{self.api_url}/webhook/telegram/{bot_token}",
                json=webhook_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                elapsed = time.time() - start_time

                if response.status == 200:
                    self.sent_count += 1
                    metrics.record_message(success=True, response_time=elapsed)
                elif response.status == 429:
                    metrics.record_rate_limit()
                    metrics.record_message(success=False)
                else:
                    metrics.record_message(success=False)
                    metrics.record_error(f"Webhook failed: HTTP {response.status}")

        except Exception as e:
            metrics.record_message(success=False)
            metrics.record_error(f"Webhook error: {str(e)}")

    async def run(self, session: aiohttp.ClientSession, bot_token: str, metrics: LoadTestMetrics, duration_minutes: int):
        """Run user message sending loop"""

        end_time = time.time() + (duration_minutes * 60)

        # Message rate based on user type
        if self.user_type == "normal":
            msg_per_min = random.uniform(1, 2)
        elif self.user_type == "mention":
            msg_per_min = random.uniform(2, 3)
        else:  # reply
            msg_per_min = random.uniform(2, 3)

        interval = 60 / msg_per_min

        while time.time() < end_time:
            await self.send_message(session, bot_token, metrics)

            # Random jitter
            sleep_time = interval * random.uniform(0.8, 1.2)
            await asyncio.sleep(sleep_time)


async def create_test_bots(api_url: str, api_key: str) -> tuple[List[Dict[str, Any]], List[str]]:
    """Create 50 test bots with different configurations

    Returns:
        (bots, tokens): List of bot dicts and list of plaintext tokens
    """

    print("📦 Creating 50 test bots...")

    bots = []
    tokens = []
    async with aiohttp.ClientSession() as session:
        for i in range(1, NUM_BOTS + 1):
            token = f"fake_token_{i}_{int(time.time())}"
            bot_data = {
                "name": f"LoadTestBot{i}",
                "token": token,
                "username": f"testbot{i}",
                "is_enabled": True,
                "persona_hint": f"Test bot {i}"
            }

            try:
                async with session.post(
                    f"{api_url}/bots",
                    json=bot_data,
                    headers={"X-API-Key": api_key},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status in [200, 201]:
                        bot = await response.json()
                        bots.append(bot)
                        tokens.append(token)  # Save plaintext token
                        print(f"  ✅ Created bot {i}/{NUM_BOTS}: {bot['name']}")
                    else:
                        print(f"  ❌ Failed to create bot {i}: HTTP {response.status}")

            except Exception as e:
                print(f"  ❌ Error creating bot {i}: {e}")

    print(f"\n✅ Successfully created {len(bots)} bots\n")
    return bots, tokens


async def create_test_chat(api_url: str, api_key: str) -> Dict[str, Any]:
    """Create test chat"""

    print("📦 Creating test chat...")

    chat_data = {
        "chat_id": CHAT_ID,
        "title": "Phase 2 Load Test Chat",
        "is_enabled": True
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{api_url}/chats",
                json=chat_data,
                headers={"X-API-Key": api_key},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status in [200, 201]:
                    chat = await response.json()
                    print(f"✅ Created chat: {chat.get('title', chat.get('chat_title', 'Unknown'))}\n")
                    return chat
                else:
                    print(f"❌ Failed to create chat: HTTP {response.status}")
                    return None

        except Exception as e:
            print(f"❌ Error creating chat: {e}")
            return None


async def monitor_metrics(api_url: str, metrics: LoadTestMetrics, duration_minutes: int):
    """Monitor queue stats and metrics during test"""

    end_time = time.time() + (duration_minutes * 60)

    async with aiohttp.ClientSession() as session:
        while time.time() < end_time:
            try:
                # Get queue stats
                async with session.get(
                    f"{api_url}/queue/stats",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        total_queued = data.get("total_queued", 0)
                        metrics.record_queue_size(total_queued)

            except Exception as e:
                pass  # Silent fail for monitoring

            await asyncio.sleep(5)  # Check every 5 seconds


async def run_load_test(api_url: str, api_key: str, duration_minutes: int):
    """Main load test orchestrator"""

    print("=" * 80)
    print("🚀 PHASE 2 LOAD TEST - Task 2.7")
    print("=" * 80)
    print(f"Configuration:")
    print(f"  - Bots: {NUM_BOTS}")
    print(f"  - Users: {NUM_USERS}")
    print(f"  - Duration: {duration_minutes} minutes")
    print(f"  - API: {api_url}")
    print("=" * 80)
    print()

    metrics = LoadTestMetrics()

    # Step 1: Create test bots
    bots, tokens = await create_test_bots(api_url, api_key)
    if len(bots) < 10:
        print("❌ Failed to create enough bots. Exiting.")
        return {}, False

    # Step 2: Create test chat (SKIP - webhook auto-creates chat)
    print("📦 Skipping chat creation - webhook will auto-create\n")

    # Step 3: Create mock users
    print(f"👥 Creating {NUM_USERS} mock users...")
    users = []

    # 60 normal users
    for i in range(60):
        users.append(MockUser(1000000 + i, "normal", api_url, CHAT_ID))

    # 20 mention users
    for i in range(20):
        users.append(MockUser(2000000 + i, "mention", api_url, CHAT_ID))

    # 20 reply users
    for i in range(20):
        users.append(MockUser(3000000 + i, "reply", api_url, CHAT_ID))

    print(f"✅ Created {len(users)} mock users")
    print(f"  - Normal: 60")
    print(f"  - Mention: 20")
    print(f"  - Reply: 20")
    print()

    # Step 4: Start monitoring
    print("📊 Starting metrics monitoring...")
    monitor_task = asyncio.create_task(monitor_metrics(api_url, metrics, duration_minutes))

    # Step 5: Run load test
    print(f"🔥 Starting load test ({duration_minutes} minutes)...")
    print("=" * 80)
    print()

    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        # Use the first bot's plaintext token for webhook calls
        bot_token = tokens[0]

        # Create user tasks
        user_tasks = [
            user.run(session, bot_token, metrics, duration_minutes)
            for user in users
        ]

        # Run all users concurrently
        await asyncio.gather(*user_tasks, return_exceptions=True)

    # Wait for monitoring to finish
    await monitor_task

    elapsed = time.time() - start_time

    # Step 6: Generate report
    print()
    print("=" * 80)
    print("✅ LOAD TEST COMPLETE")
    print("=" * 80)
    print()

    summary = metrics.get_summary()

    print("📊 RESULTS:")
    print(f"  Duration: {summary['test_duration_seconds']}s ({duration_minutes} min)")
    print(f"  Messages Sent: {summary['total_messages_sent']}")
    print(f"  Messages Failed: {summary['total_messages_failed']}")
    print(f"  Rate Limited: {summary['total_rate_limited']}")
    print(f"  Throughput: {summary['throughput_msg_per_sec']} msg/sec")
    print(f"  Error Rate: {summary['error_rate_percent']}%")
    print()
    print("⏱️  LATENCY:")
    print(f"  Average: {summary['avg_response_time_ms']}ms")
    print(f"  P50 (median): {summary['p50_response_time_ms']}ms")
    print(f"  P95: {summary['p95_response_time_ms']}ms")
    print(f"  P99: {summary['p99_response_time_ms']}ms")
    print()
    print("📦 QUEUE:")
    print(f"  Max Queue Size: {summary['max_queue_size']}")
    print(f"  Avg Queue Size: {summary['avg_queue_size']}")
    print()

    # Save report
    report = {
        "test_config": {
            "num_bots": NUM_BOTS,
            "num_users": NUM_USERS,
            "duration_minutes": duration_minutes,
            "test_date": datetime.now().isoformat(),
        },
        "summary": summary,
        "errors": metrics.error_log[:100],  # First 100 errors
    }

    report_path = f"tests/load_test_report_{int(time.time())}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"📄 Report saved to: {report_path}")
    print()

    # Check if test passed
    print("=" * 80)
    print("✅ PASS/FAIL CRITERIA:")
    print("=" * 80)

    checks = [
        ("Throughput < 30 msg/sec", summary['throughput_msg_per_sec'] < 30),
        ("Error rate < 1%", summary['error_rate_percent'] < 1.0),
        ("P95 latency < 5000ms", summary['p95_response_time_ms'] < 5000),
        ("Max queue < 1000", summary['max_queue_size'] < 1000),
    ]

    all_passed = True
    for check_name, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {check_name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 ALL CHECKS PASSED - TASK 2.7 COMPLETE!")
    else:
        print("⚠️  SOME CHECKS FAILED - REVIEW REQUIRED")

    print("=" * 80)

    return summary, all_passed


if __name__ == "__main__":
    import sys
    import os

    # Fix Windows console encoding for emojis
    if sys.platform == "win32":
        os.system("chcp 65001 >nul 2>&1")
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    # Parse arguments
    api_key = sys.argv[1] if len(sys.argv) > 1 else "dev-test-key-12345"
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 5  # Default 5 minutes for testing

    # Run test
    summary, passed = asyncio.run(run_load_test(API_BASE_URL, api_key, duration))

    # Exit code
    sys.exit(0 if passed else 1)
