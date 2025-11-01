"""
Simple Load Monitor - Sessions 9-13 Performance Testing

Monitors worker performance and collects cache metrics for 10 minutes.
No external dependencies needed - just monitors log output.

Usage:
    python simple_load_monitor.py --duration 10
"""

import subprocess
import time
import json
import re
import argparse
from datetime import datetime
from collections import defaultdict

class SimpleLoadMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.metrics = {
            "messages_sent": 0,
            "errors": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "llm_calls": 0,
            "telegram_calls": 0,
            "circuit_breaker_events": [],
            "timestamps": []
        }
        self.last_sample_time = self.start_time

    def parse_log_line(self, line: str):
        """Parse worker log line and extract metrics"""
        timestamp = time.time()

        # Message sent
        if "sendMessage" in line and "200 OK" in line:
            self.metrics["messages_sent"] += 1
            self.metrics["timestamps"].append({
                "event": "message_sent",
                "time": timestamp - self.start_time
            })

        # Errors
        if "ERROR:" in line:
            self.metrics["errors"] += 1
            self.metrics["timestamps"].append({
                "event": "error",
                "time": timestamp - self.start_time,
                "message": line.strip()
            })

        # Cache hits/misses
        if "Cache hit:" in line:
            self.metrics["cache_hits"] += 1
        if "Cache miss:" in line:
            self.metrics["cache_misses"] += 1

        # LLM calls
        if "api.groq.com" in line or "api.openai.com" in line:
            self.metrics["llm_calls"] += 1

        # Telegram API calls
        if "api.telegram.org" in line and "POST" in line:
            self.metrics["telegram_calls"] += 1

        # Circuit breaker events
        if "Circuit breaker" in line and ("OPEN" in line or "HALF_OPEN" in line or "CLOSED" in line):
            self.metrics["circuit_breaker_events"].append({
                "time": timestamp - self.start_time,
                "message": line.strip()
            })

    def print_live_stats(self, elapsed: int, remaining: int):
        """Print current statistics"""
        cache_hit_rate = 0
        if (self.metrics["cache_hits"] + self.metrics["cache_misses"]) > 0:
            cache_hit_rate = self.metrics["cache_hits"] / (self.metrics["cache_hits"] + self.metrics["cache_misses"]) * 100

        messages_per_min = (self.metrics["messages_sent"] / elapsed * 60) if elapsed > 0 else 0

        print(f"\n[{elapsed}s elapsed, {remaining}s remaining]")
        print(f"  Messages sent: {self.metrics['messages_sent']} ({messages_per_min:.2f}/min)")
        print(f"  Errors: {self.metrics['errors']}")
        print(f"  Cache: {self.metrics['cache_hits']} hits, {self.metrics['cache_misses']} misses ({cache_hit_rate:.1f}% hit rate)")
        print(f"  LLM calls: {self.metrics['llm_calls']}")
        print(f"  Telegram calls: {self.metrics['telegram_calls']}")
        if self.metrics["circuit_breaker_events"]:
            print(f"  Circuit breaker events: {len(self.metrics['circuit_breaker_events'])}")

    def generate_report(self, duration_minutes: int):
        """Generate final report"""
        total_time = time.time() - self.start_time

        cache_hit_rate = 0
        if (self.metrics["cache_hits"] + self.metrics["cache_misses"]) > 0:
            cache_hit_rate = self.metrics["cache_hits"] / (self.metrics["cache_hits"] + self.metrics["cache_misses"]) * 100

        messages_per_min = self.metrics["messages_sent"] / total_time * 60

        report = {
            "test_info": {
                "duration_minutes": duration_minutes,
                "actual_duration_seconds": total_time,
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "end_time": datetime.now().isoformat()
            },
            "performance": {
                "messages_sent": self.metrics["messages_sent"],
                "messages_per_minute": round(messages_per_min, 2),
                "errors": self.metrics["errors"],
                "error_rate_percent": round(self.metrics["errors"] / max(self.metrics["messages_sent"], 1) * 100, 2)
            },
            "cache": {
                "hits": self.metrics["cache_hits"],
                "misses": self.metrics["cache_misses"],
                "hit_rate_percent": round(cache_hit_rate, 2),
                "total_operations": self.metrics["cache_hits"] + self.metrics["cache_misses"]
            },
            "api_calls": {
                "llm_calls": self.metrics["llm_calls"],
                "telegram_calls": self.metrics["telegram_calls"]
            },
            "circuit_breaker": {
                "events": self.metrics["circuit_breaker_events"]
            }
        }

        return report

    def monitor(self, duration_minutes: int):
        """Monitor worker for specified duration"""
        print("=" * 80)
        print("SIMPLE LOAD MONITOR - Sessions 9-13 Performance Test")
        print("=" * 80)
        print(f"Duration: {duration_minutes} minutes")
        print(f"Start time: {datetime.now().isoformat()}")
        print("=" * 80)
        print("\nStarting worker monitoring...")

        # Start worker process
        process = subprocess.Popen(
            ["python", "worker.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        end_time = self.start_time + (duration_minutes * 60)
        last_print = self.start_time

        try:
            while time.time() < end_time:
                # Read log lines
                line = process.stdout.readline()
                if line:
                    self.parse_log_line(line)

                # Print stats every 30 seconds
                now = time.time()
                if now - last_print >= 30:
                    elapsed = int(now - self.start_time)
                    remaining = int(end_time - now)
                    self.print_live_stats(elapsed, remaining)
                    last_print = now

                # Small delay to avoid CPU spinning
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\n[!] Monitoring interrupted by user")

        finally:
            # Stop worker
            print("\n\nStopping worker...")
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

        print("\n[OK] Monitoring completed!")

        # Generate and save report
        report = self.generate_report(duration_minutes)

        # Print report
        print("\n" + "=" * 80)
        print("PERFORMANCE REPORT")
        print("=" * 80)
        print(f"\n[Test Info]")
        print(f"  Duration: {report['test_info']['duration_minutes']} minutes ({report['test_info']['actual_duration_seconds']:.1f}s)")
        print(f"  Start: {report['test_info']['start_time']}")

        print(f"\n[Performance]")
        print(f"  Messages sent: {report['performance']['messages_sent']}")
        print(f"  Messages/minute: {report['performance']['messages_per_minute']:.2f}")
        print(f"  Errors: {report['performance']['errors']} ({report['performance']['error_rate_percent']:.2f}%)")

        print(f"\n[Cache Performance] * Sessions 9-13")
        print(f"  Cache hits: {report['cache']['hits']}")
        print(f"  Cache misses: {report['cache']['misses']}")
        print(f"  Hit rate: {report['cache']['hit_rate_percent']:.2f}%")
        print(f"  Total cache operations: {report['cache']['total_operations']}")

        print(f"\n[API Calls]")
        print(f"  LLM API calls: {report['api_calls']['llm_calls']}")
        print(f"  Telegram API calls: {report['api_calls']['telegram_calls']}")

        if report['circuit_breaker']['events']:
            print(f"\n[Circuit Breaker]")
            print(f"  Events: {len(report['circuit_breaker']['events'])}")

        print("\n" + "=" * 80)

        # Save to file
        filename = f"load_test_sessions9-13_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n[Save] Report saved to: {filename}")

        return report


def main():
    parser = argparse.ArgumentParser(description="Simple Load Monitor")
    parser.add_argument("--duration", type=int, default=10, help="Test duration in minutes (default: 10)")
    args = parser.parse_args()

    monitor = SimpleLoadMonitor()
    monitor.monitor(args.duration)


if __name__ == "__main__":
    main()
