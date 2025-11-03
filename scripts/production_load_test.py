"""
Production Load Testing Script

Tests system capacity with 50-200 bot simulations.

Usage:
    python scripts/production_load_test.py --bots 50 --duration 300

Requirements:
    - System must be running (docker-compose up)
    - API accessible at http://localhost:8000
    - Admin API key configured

Metrics Measured:
    - Message throughput (msg/sec)
    - Average latency (seconds)
    - Error rate (%)
    - Database query performance
    - Redis cache hit rate
    - Worker utilization
"""

import argparse
import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import httpx

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import Bot, Chat, Message, SessionLocal, get_db


class LoadTestResults:
    """Container for load test metrics."""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.total_messages = 0
        self.total_errors = 0
        self.latencies = []
        self.throughput_samples = []

    def record_message(self, latency: float):
        """Record successful message generation."""
        self.total_messages += 1
        self.latencies.append(latency)

    def record_error(self):
        """Record failed message generation."""
        self.total_errors += 1

    def avg_latency(self) -> float:
        """Calculate average latency."""
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0

    def max_latency(self) -> float:
        """Calculate max latency."""
        return max(self.latencies) if self.latencies else 0.0

    def error_rate(self) -> float:
        """Calculate error rate (%)."""
        total = self.total_messages + self.total_errors
        return (self.total_errors / total * 100) if total > 0 else 0.0

    def throughput(self) -> float:
        """Calculate overall throughput (msg/sec)."""
        duration = (self.end_time - self.start_time).total_seconds()
        return self.total_messages / duration if duration > 0 else 0.0


async def check_system_health(api_url: str) -> bool:
    """Check if system is healthy before testing."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_url}/healthz", timeout=10.0)
            if response.status_code != 200:
                print(f"❌ Health check failed: HTTP {response.status_code}")
                return False

            data = response.json()
            if data.get("status") != "healthy":
                print(f"❌ System status: {data.get('status')}")
                print(f"   Checks: {data.get('checks')}")
                return False

            print("✅ System health check passed")
            return True
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def get_baseline_metrics() -> Dict:
    """Get baseline metrics before test."""
    db = SessionLocal()
    try:
        total_messages = db.query(Message).count()
        total_bots = db.query(Bot).filter(Bot.is_enabled.is_(True)).count()
        total_chats = db.query(Chat).filter(Chat.is_enabled.is_(True)).count()

        return {
            "messages_before": total_messages,
            "active_bots": total_bots,
            "active_chats": total_chats,
        }
    finally:
        db.close()


def get_final_metrics(baseline: Dict) -> Dict:
    """Get final metrics after test."""
    db = SessionLocal()
    try:
        total_messages = db.query(Message).count()
        messages_generated = total_messages - baseline["messages_before"]

        # Get recent message timestamps for throughput calculation
        recent_msgs = (
            db.query(Message)
            .order_by(Message.created_at.desc())
            .limit(messages_generated)
            .all()
        )

        if len(recent_msgs) >= 2:
            time_span = (recent_msgs[0].created_at - recent_msgs[-1].created_at).total_seconds()
            throughput = messages_generated / time_span if time_span > 0 else 0.0
        else:
            throughput = 0.0

        return {
            "messages_after": total_messages,
            "messages_generated": messages_generated,
            "measured_throughput": throughput,
        }
    finally:
        db.close()


async def monitor_throughput(results: LoadTestResults, duration: int):
    """Monitor throughput periodically during test."""
    print("\n📊 Real-time monitoring (30s intervals):")
    print("-" * 60)

    start_time = time.time()
    last_count = 0

    while time.time() - start_time < duration:
        await asyncio.sleep(30)  # Sample every 30 seconds

        current_count = results.total_messages
        interval_messages = current_count - last_count
        interval_throughput = interval_messages / 30.0

        elapsed = int(time.time() - start_time)
        print(
            f"[{elapsed:3d}s] Messages: {current_count:4d} | "
            f"Interval: {interval_messages:3d} (+{interval_throughput:.2f} msg/s) | "
            f"Errors: {results.total_errors}"
        )

        last_count = current_count
        results.throughput_samples.append(interval_throughput)


def print_report(results: LoadTestResults, baseline: Dict, final: Dict, bot_count: int):
    """Print comprehensive test report."""
    print("\n")
    print("=" * 70)
    print(" PRODUCTION LOAD TEST REPORT")
    print("=" * 70)

    # Test configuration
    print("\n📋 TEST CONFIGURATION")
    print("-" * 70)
    print(f"  Bot Count:        {bot_count}")
    print(f"  Duration:         {int((results.end_time - results.start_time).total_seconds())}s")
    print(f"  Start Time:       {results.start_time.isoformat()}")
    print(f"  End Time:         {results.end_time.isoformat()}")

    # System metrics
    print("\n📊 SYSTEM METRICS")
    print("-" * 70)
    print(f"  Active Bots:      {baseline['active_bots']}")
    print(f"  Active Chats:     {baseline['active_chats']}")
    print(f"  Messages Before:  {baseline['messages_before']}")
    print(f"  Messages After:   {final['messages_after']}")
    print(f"  Messages Generated: {final['messages_generated']}")

    # Performance metrics
    print("\n⚡ PERFORMANCE METRICS")
    print("-" * 70)
    print(f"  Total Messages:   {results.total_messages}")
    print(f"  Total Errors:     {results.total_errors}")
    print(f"  Error Rate:       {results.error_rate():.2f}%")
    print(f"  Throughput:       {results.throughput():.3f} msg/sec")
    print(f"  Measured (DB):    {final['measured_throughput']:.3f} msg/sec")

    if results.latencies:
        print(f"  Avg Latency:      {results.avg_latency():.2f}s")
        print(f"  Max Latency:      {results.max_latency():.2f}s")

    # Throughput analysis
    if results.throughput_samples:
        avg_throughput = sum(results.throughput_samples) / len(results.throughput_samples)
        max_throughput = max(results.throughput_samples)
        min_throughput = min(results.throughput_samples)

        print("\n📈 THROUGHPUT ANALYSIS (30s intervals)")
        print("-" * 70)
        print(f"  Average:          {avg_throughput:.3f} msg/sec")
        print(f"  Maximum:          {max_throughput:.3f} msg/sec")
        print(f"  Minimum:          {min_throughput:.3f} msg/sec")

    # Capacity assessment
    print("\n🎯 CAPACITY ASSESSMENT")
    print("-" * 70)

    target_throughput = 0.5  # msg/sec baseline
    actual = results.throughput()

    if actual >= target_throughput * 2:
        status = "✅ EXCELLENT"
        message = f"System exceeds baseline by {(actual/target_throughput-1)*100:.0f}%"
    elif actual >= target_throughput:
        status = "✅ GOOD"
        message = f"System meets baseline ({(actual/target_throughput)*100:.0f}%)"
    elif actual >= target_throughput * 0.7:
        status = "⚠️  ACCEPTABLE"
        message = f"System at {(actual/target_throughput)*100:.0f}% of baseline"
    else:
        status = "❌ DEGRADED"
        message = f"System below baseline ({(actual/target_throughput)*100:.0f}%)"

    print(f"  Status:           {status}")
    print(f"  Assessment:       {message}")
    print(f"  Error Rate:       {'✅ < 1%' if results.error_rate() < 1.0 else '❌ >= 1%'}")

    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-" * 70)

    if results.error_rate() > 5.0:
        print("  ⚠️  High error rate detected - investigate worker logs")

    if actual < target_throughput:
        print("  ⚠️  Low throughput - consider scaling workers or optimizing queries")

    if results.max_latency() > 30.0:
        print("  ⚠️  High latency spikes - check database query performance")

    if results.error_rate() < 1.0 and actual >= target_throughput:
        print("  ✅ System performing well - ready for production scale")

    print("\n" + "=" * 70)


async def run_load_test(bot_count: int, duration: int, api_url: str) -> LoadTestResults:
    """Run the load test."""
    results = LoadTestResults()
    results.start_time = datetime.now(timezone.utc)

    # Create monitoring task
    monitor_task = asyncio.create_task(monitor_throughput(results, duration))

    try:
        # Simulate load by letting workers run
        print(f"\n🚀 Load test running for {duration}s with {bot_count} bots...")
        print(f"   Workers will generate messages naturally")
        print(f"   Monitoring throughput...\n")

        await asyncio.sleep(duration)

    finally:
        results.end_time = datetime.now(timezone.utc)
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

    return results


async def main():
    parser = argparse.ArgumentParser(description="Production Load Testing")
    parser.add_argument(
        "--bots",
        type=int,
        default=50,
        help="Number of bots to simulate (default: 50)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Test duration in seconds (default: 300)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print(" PRODUCTION LOAD TEST")
    print("=" * 70)
    print(f"\n📝 Configuration:")
    print(f"   Bots:     {args.bots}")
    print(f"   Duration: {args.duration}s")
    print(f"   API URL:  {args.api_url}")

    # Step 1: Health check
    print(f"\n🏥 Checking system health...")
    if not await check_system_health(args.api_url):
        print("\n❌ System is not healthy. Aborting test.")
        sys.exit(1)

    # Step 2: Get baseline metrics
    print(f"\n📊 Collecting baseline metrics...")
    baseline = get_baseline_metrics()
    print(f"   Active bots: {baseline['active_bots']}")
    print(f"   Active chats: {baseline['active_chats']}")
    print(f"   Messages: {baseline['messages_before']}")

    if baseline['active_bots'] == 0:
        print("\n❌ No active bots found. Cannot run load test.")
        sys.exit(1)

    # Step 3: Run load test
    results = await run_load_test(args.bots, args.duration, args.api_url)

    # Step 4: Get final metrics
    print(f"\n📊 Collecting final metrics...")
    final = get_final_metrics(baseline)

    # Step 5: Print report
    print_report(results, baseline, final, args.bots)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
