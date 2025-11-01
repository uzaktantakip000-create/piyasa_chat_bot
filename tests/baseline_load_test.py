"""
Baseline Load Test - Task 0.2
Measure current system performance before optimization

This script:
1. Creates N bots and chats
2. Enables simulation
3. Collects metrics from Prometheus for 15 minutes
4. Reports baseline performance (latency, throughput, resource usage)

Usage:
    python tests/baseline_load_test.py --bots 10 --duration 15
    python tests/baseline_load_test.py --bots 25 --duration 10
    python tests/baseline_load_test.py --bots 50 --duration 10
"""

import asyncio
import json
import time
import argparse
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import httpx

# Configuration
API_BASE_URL = "http://localhost:8000"
PROMETHEUS_URL = "http://localhost:9090"
API_KEY = "test-api-key-12345"  # Default from .env


class BaselineMetricsCollector:
    """Collects metrics from Prometheus during load test"""

    def __init__(self):
        self.metrics_history = []
        self.start_time = None
        self.end_time = None

    async def collect_prometheus_metrics(self) -> Dict[str, Any]:
        """Fetch current metrics from Prometheus"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            metrics = {}

            # 1. Message generation rate (success)
            query = 'rate(message_generation_total{status="success"}[1m])'
            try:
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json()
                if data["status"] == "success" and data["data"]["result"]:
                    metrics["message_rate_success"] = float(data["data"]["result"][0]["value"][1])
                else:
                    metrics["message_rate_success"] = 0.0
            except Exception as e:
                print(f"Error fetching message_rate_success: {e}")
                metrics["message_rate_success"] = 0.0

            # 2. Message generation rate (failed)
            query = 'rate(message_generation_total{status="failed"}[1m])'
            try:
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json()
                if data["status"] == "success" and data["data"]["result"]:
                    metrics["message_rate_failed"] = float(data["data"]["result"][0]["value"][1])
                else:
                    metrics["message_rate_failed"] = 0.0
            except Exception as e:
                print(f"Error fetching message_rate_failed: {e}")
                metrics["message_rate_failed"] = 0.0

            # 3. Message generation duration (p50)
            query = 'histogram_quantile(0.50, rate(message_generation_duration_seconds_bucket[5m]))'
            try:
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json()
                if data["status"] == "success" and data["data"]["result"]:
                    metrics["message_duration_p50"] = float(data["data"]["result"][0]["value"][1])
                else:
                    metrics["message_duration_p50"] = 0.0
            except Exception as e:
                print(f"Error fetching message_duration_p50: {e}")
                metrics["message_duration_p50"] = 0.0

            # 4. Message generation duration (p95)
            query = 'histogram_quantile(0.95, rate(message_generation_duration_seconds_bucket[5m]))'
            try:
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json()
                if data["status"] == "success" and data["data"]["result"]:
                    metrics["message_duration_p95"] = float(data["data"]["result"][0]["value"][1])
                else:
                    metrics["message_duration_p95"] = 0.0
            except Exception as e:
                print(f"Error fetching message_duration_p95: {e}")
                metrics["message_duration_p95"] = 0.0

            # 5. Message generation duration (p99)
            query = 'histogram_quantile(0.99, rate(message_generation_duration_seconds_bucket[5m]))'
            try:
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json()
                if data["status"] == "success" and data["data"]["result"]:
                    metrics["message_duration_p99"] = float(data["data"]["result"][0]["value"][1])
                else:
                    metrics["message_duration_p99"] = 0.0
            except Exception as e:
                print(f"Error fetching message_duration_p99: {e}")
                metrics["message_duration_p99"] = 0.0

            # 6. Database query duration (p95)
            query = 'histogram_quantile(0.95, rate(database_query_duration_seconds_bucket[5m]))'
            try:
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json()
                if data["status"] == "success" and data["data"]["result"]:
                    metrics["db_query_duration_p95"] = float(data["data"]["result"][0]["value"][1])
                else:
                    metrics["db_query_duration_p95"] = 0.0
            except Exception as e:
                print(f"Error fetching db_query_duration_p95: {e}")
                metrics["db_query_duration_p95"] = 0.0

            # 7. Active bots gauge
            query = 'active_bots_gauge'
            try:
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json()
                if data["status"] == "success" and data["data"]["result"]:
                    metrics["active_bots"] = float(data["data"]["result"][0]["value"][1])
                else:
                    metrics["active_bots"] = 0.0
            except Exception as e:
                print(f"Error fetching active_bots: {e}")
                metrics["active_bots"] = 0.0

            # 8. Database connections
            query = 'database_connections_gauge'
            try:
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json()
                if data["status"] == "success" and data["data"]["result"]:
                    metrics["db_connections"] = float(data["data"]["result"][0]["value"][1])
                else:
                    metrics["db_connections"] = 0.0
            except Exception as e:
                print(f"Error fetching db_connections: {e}")
                metrics["db_connections"] = 0.0

            # 9. API request rate
            query = 'rate(http_requests_total[1m])'
            try:
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json()
                if data["status"] == "success" and data["data"]["result"]:
                    # Sum all endpoints
                    total_rate = sum(float(r["value"][1]) for r in data["data"]["result"])
                    metrics["api_request_rate"] = total_rate
                else:
                    metrics["api_request_rate"] = 0.0
            except Exception as e:
                print(f"Error fetching api_request_rate: {e}")
                metrics["api_request_rate"] = 0.0

            # 10. API request duration (p95)
            query = 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))'
            try:
                resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
                data = resp.json()
                if data["status"] == "success" and data["data"]["result"]:
                    # Average across all endpoints
                    durations = [float(r["value"][1]) for r in data["data"]["result"]]
                    metrics["api_duration_p95"] = statistics.mean(durations) if durations else 0.0
                else:
                    metrics["api_duration_p95"] = 0.0
            except Exception as e:
                print(f"Error fetching api_duration_p95: {e}")
                metrics["api_duration_p95"] = 0.0

            metrics["timestamp"] = time.time()
            return metrics

    async def collect_metrics_loop(self, duration_minutes: int, interval_seconds: int = 30):
        """Collect metrics periodically"""
        self.start_time = time.time()
        end_time = self.start_time + (duration_minutes * 60)

        print(f"\nStarting metric collection for {duration_minutes} minutes...")
        print(f"Collecting metrics every {interval_seconds} seconds\n")

        while time.time() < end_time:
            elapsed = int(time.time() - self.start_time)
            remaining = int(end_time - time.time())

            metrics = await self.collect_prometheus_metrics()
            self.metrics_history.append(metrics)

            # Print current metrics
            print(f"[{elapsed}s elapsed, {remaining}s remaining]")
            print(f"  Messages/sec: {metrics['message_rate_success']:.3f} (success), {metrics['message_rate_failed']:.3f} (failed)")
            print(f"  Message duration: p50={metrics['message_duration_p50']:.2f}s, p95={metrics['message_duration_p95']:.2f}s, p99={metrics['message_duration_p99']:.2f}s")
            print(f"  DB query p95: {metrics['db_query_duration_p95']*1000:.2f}ms")
            print(f"  Active bots: {metrics['active_bots']:.0f}")
            print(f"  DB connections: {metrics['db_connections']:.0f}")
            print()

            await asyncio.sleep(interval_seconds)

        self.end_time = time.time()
        print(f"[OK] Metric collection completed!")

    def generate_report(self, num_bots: int) -> Dict[str, Any]:
        """Generate summary report from collected metrics"""
        if not self.metrics_history:
            return {"error": "No metrics collected"}

        # Extract all values for aggregation
        message_rates_success = [m["message_rate_success"] for m in self.metrics_history if m["message_rate_success"] > 0]
        message_rates_failed = [m["message_rate_failed"] for m in self.metrics_history if m["message_rate_failed"] > 0]
        msg_duration_p50 = [m["message_duration_p50"] for m in self.metrics_history if m["message_duration_p50"] > 0]
        msg_duration_p95 = [m["message_duration_p95"] for m in self.metrics_history if m["message_duration_p95"] > 0]
        msg_duration_p99 = [m["message_duration_p99"] for m in self.metrics_history if m["message_duration_p99"] > 0]
        db_query_p95 = [m["db_query_duration_p95"] for m in self.metrics_history if m["db_query_duration_p95"] > 0]
        db_connections = [m["db_connections"] for m in self.metrics_history if m["db_connections"] > 0]

        report = {
            "test_info": {
                "num_bots": num_bots,
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "end_time": datetime.fromtimestamp(self.end_time).isoformat(),
                "duration_minutes": (self.end_time - self.start_time) / 60,
                "samples_collected": len(self.metrics_history),
            },
            "message_generation": {
                "success_rate_avg": statistics.mean(message_rates_success) if message_rates_success else 0,
                "success_rate_max": max(message_rates_success) if message_rates_success else 0,
                "failed_rate_avg": statistics.mean(message_rates_failed) if message_rates_failed else 0,
                "failed_rate_max": max(message_rates_failed) if message_rates_failed else 0,
                "error_rate_percent": (statistics.mean(message_rates_failed) / (statistics.mean(message_rates_success) + statistics.mean(message_rates_failed)) * 100) if (message_rates_success and message_rates_failed) else 0,
            },
            "latency": {
                "message_duration_p50_avg": statistics.mean(msg_duration_p50) if msg_duration_p50 else 0,
                "message_duration_p50_max": max(msg_duration_p50) if msg_duration_p50 else 0,
                "message_duration_p95_avg": statistics.mean(msg_duration_p95) if msg_duration_p95 else 0,
                "message_duration_p95_max": max(msg_duration_p95) if msg_duration_p95 else 0,
                "message_duration_p99_avg": statistics.mean(msg_duration_p99) if msg_duration_p99 else 0,
                "message_duration_p99_max": max(msg_duration_p99) if msg_duration_p99 else 0,
            },
            "database": {
                "query_duration_p95_avg_ms": statistics.mean(db_query_p95) * 1000 if db_query_p95 else 0,
                "query_duration_p95_max_ms": max(db_query_p95) * 1000 if db_query_p95 else 0,
                "connections_avg": statistics.mean(db_connections) if db_connections else 0,
                "connections_max": max(db_connections) if db_connections else 0,
            },
            "raw_samples": self.metrics_history,
        }

        return report


async def setup_test_environment(num_bots: int, api_key: str) -> Dict[str, Any]:
    """Create test bots and chats, enable simulation"""
    print(f"\n[Setup] Setting up test environment with {num_bots} bots...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"X-API-Key": api_key}

        # 1. Check current bots
        resp = await client.get(f"{API_BASE_URL}/bots", headers=headers)
        existing_bots = resp.json()
        print(f"   Existing bots: {len(existing_bots)}")

        # 2. Check current chats
        resp = await client.get(f"{API_BASE_URL}/chats", headers=headers)
        existing_chats = resp.json()
        print(f"   Existing chats: {len(existing_chats)}")

        # 3. Enable simulation
        resp = await client.patch(
            f"{API_BASE_URL}/settings/simulation_active",
            headers=headers,
            json={"value": True}
        )
        print(f"   Simulation enabled: {resp.status_code == 200}")

        # 4. Set scale factor to 1.0 (normal speed)
        resp = await client.patch(
            f"{API_BASE_URL}/settings/scale_factor",
            headers=headers,
            json={"value": 1.0}
        )
        print(f"   Scale factor set to 1.0: {resp.status_code == 200}")

        return {
            "num_bots": len(existing_bots),
            "num_chats": len(existing_chats),
            "simulation_active": True,
        }


async def cleanup_test_environment(api_key: str):
    """Optional: Disable simulation after test"""
    print(f"\n[Cleanup] Cleaning up test environment...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"X-API-Key": api_key}

        # Disable simulation
        resp = await client.patch(
            f"{API_BASE_URL}/settings/simulation_active",
            headers=headers,
            json={"value": False}
        )
        print(f"   Simulation disabled: {resp.status_code == 200}")


def print_report(report: Dict[str, Any]):
    """Print human-readable report"""
    print("\n" + "=" * 80)
    print("BASELINE LOAD TEST REPORT")
    print("=" * 80)

    test_info = report["test_info"]
    print(f"\n[Config] Test Configuration:")
    print(f"   Number of bots: {test_info['num_bots']}")
    print(f"   Start time: {test_info['start_time']}")
    print(f"   Duration: {test_info['duration_minutes']:.1f} minutes")
    print(f"   Samples collected: {test_info['samples_collected']}")

    msg_gen = report["message_generation"]
    print(f"\n[Messages] Message Generation:")
    print(f"   Success rate (avg): {msg_gen['success_rate_avg']:.3f} msg/sec")
    print(f"   Success rate (max): {msg_gen['success_rate_max']:.3f} msg/sec")
    print(f"   Failed rate (avg): {msg_gen['failed_rate_avg']:.3f} msg/sec")
    print(f"   Error rate: {msg_gen['error_rate_percent']:.2f}%")

    latency = report["latency"]
    print(f"\n[Latency] Message Generation Latency:")
    print(f"   p50 (avg): {latency['message_duration_p50_avg']:.2f}s")
    print(f"   p95 (avg): {latency['message_duration_p95_avg']:.2f}s")
    print(f"   p99 (avg): {latency['message_duration_p99_avg']:.2f}s")
    print(f"   p99 (max): {latency['message_duration_p99_max']:.2f}s")

    db = report["database"]
    print(f"\n[DB] Database Performance:")
    print(f"   Query duration p95 (avg): {db['query_duration_p95_avg_ms']:.2f}ms")
    print(f"   Query duration p95 (max): {db['query_duration_p95_max_ms']:.2f}ms")
    print(f"   Connections (avg): {db['connections_avg']:.1f}")
    print(f"   Connections (max): {db['connections_max']:.0f}")

    print("\n" + "=" * 80)


def save_report_to_file(report: Dict[str, Any], num_bots: int):
    """Save report to JSON file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"baseline_test_{num_bots}bots_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n[Save] Report saved to: {filename}")


async def main():
    parser = argparse.ArgumentParser(description="Baseline Load Test")
    parser.add_argument("--bots", type=int, default=10, help="Number of bots to test (default: 10)")
    parser.add_argument("--duration", type=int, default=15, help="Test duration in minutes (default: 15)")
    parser.add_argument("--interval", type=int, default=30, help="Metric collection interval in seconds (default: 30)")
    parser.add_argument("--api-key", type=str, default=API_KEY, help=f"API key (default: {API_KEY})")
    parser.add_argument("--skip-cleanup", action="store_true", help="Skip disabling simulation after test")
    args = parser.parse_args()

    print("=" * 80)
    print("BASELINE LOAD TEST - Task 0.2")
    print("=" * 80)
    print(f"Configuration:")
    print(f"  - Bots: {args.bots}")
    print(f"  - Duration: {args.duration} minutes")
    print(f"  - Collection interval: {args.interval} seconds")
    print("=" * 80)

    # Setup
    setup_result = await setup_test_environment(args.bots, args.api_key)

    # Wait a bit for metrics to stabilize
    print("\n[Wait] Waiting 30 seconds for metrics to stabilize...")
    await asyncio.sleep(30)

    # Collect metrics
    collector = BaselineMetricsCollector()
    await collector.collect_metrics_loop(args.duration, args.interval)

    # Generate and print report
    report = collector.generate_report(setup_result["num_bots"])
    print_report(report)
    save_report_to_file(report, setup_result["num_bots"])

    # Cleanup
    if not args.skip_cleanup:
        await cleanup_test_environment(args.api_key)

    print("\n[OK] Baseline load test completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
