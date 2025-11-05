"""
Baseline Load Test - ROADMAP Task 0.2

Tests system performance under different bot counts (10, 25, 50 bots).
Collects metrics: throughput, latency, resource usage.

Usage:
    python scripts/baseline_load_test.py --scenario low     # 10 bots, 5 min
    python scripts/baseline_load_test.py --scenario medium  # 25 bots, 5 min
    python scripts/baseline_load_test.py --scenario high    # 50 bots, 5 min
    python scripts/baseline_load_test.py --all              # Run all scenarios
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from database import get_db, Bot, Chat, Message, Setting
from sqlalchemy import func

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Test scenarios
SCENARIOS = {
    'low': {'bot_count': 10, 'duration_minutes': 5, 'description': 'Low scale (10 bots)'},
    'medium': {'bot_count': 25, 'duration_minutes': 5, 'description': 'Medium scale (25 bots)'},
    'high': {'bot_count': 50, 'duration_minutes': 5, 'description': 'High scale (50 bots)'},
}

# API configuration
API_BASE = os.getenv('API_BASE', 'http://localhost:8000')
API_KEY = os.getenv('DEFAULT_ADMIN_API_KEY', '')


def create_test_bots(db, count: int, chat_id: str) -> List[int]:
    """Create test bots for load testing."""
    bot_ids = []

    for i in range(count):
        bot = Bot(
            name=f"LoadTest_Bot_{i+1}",
            token=f"TEST_TOKEN_{i+1}_{int(time.time())}",  # Fake token for testing
            username=f"@loadtest_bot_{i+1}",
            is_enabled=True,
            speed_profile={
                "base_delay_seconds": 5,
                "typing_multiplier": 0.5,
                "reaction_delay_seconds": 1
            },
            active_hours=["00:00-23:59"],  # Always active
            persona_hint=f"Test bot #{i+1} for load testing",
            persona_profile={
                "tone": "analytical",
                "risk_profile": "moderate",
                "watchlist": ["BIST:THYAO", "XAUUSD"],
                "style": {"length": "short", "emojis": False}
            },
            emotion_profile={
                "tone": "neutral",
                "energy": "medium"
            }
        )
        db.add(bot)
        db.commit()
        db.refresh(bot)
        bot_ids.append(bot.id)

    logger.info(f"Created {count} test bots: {bot_ids}")
    return bot_ids


def ensure_test_chat(db, chat_id: str) -> Chat:
    """Ensure test chat exists."""
    chat = db.query(Chat).filter(Chat.chat_id == chat_id).first()

    if not chat:
        chat = Chat(
            chat_id=chat_id,
            title="Load Test Chat",
            is_enabled=True,
            topics=["BIST", "FX", "Kripto", "Makro"]
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)
        logger.info(f"Created test chat: {chat_id}")
    else:
        chat.is_enabled = True
        db.commit()
        logger.info(f"Using existing test chat: {chat_id}")

    return chat


def get_baseline_metrics(db) -> Dict[str, Any]:
    """Get baseline metrics before test."""
    total_messages = db.query(func.count(Message.id)).scalar()

    return {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'total_messages': total_messages,
    }


def get_api_metrics() -> Dict[str, Any]:
    """Fetch metrics from API."""
    try:
        headers = {'X-API-Key': API_KEY} if API_KEY else {}
        response = requests.get(f'{API_BASE}/metrics', headers=headers, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.warning(f"Failed to fetch API metrics: {e}")
        return {}


def enable_simulation(db, enabled: bool):
    """Enable/disable simulation."""
    setting = db.query(Setting).filter(Setting.key == 'simulation_active').first()
    if setting:
        setting.value = json.dumps(enabled)
        db.commit()
        logger.info(f"Simulation {'enabled' if enabled else 'disabled'}")


def run_scenario(scenario_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single load test scenario."""
    logger.info("=" * 80)
    logger.info(f"SCENARIO: {config['description']}")
    logger.info("=" * 80)

    db = next(get_db())

    try:
        # Setup
        logger.info("Step 1: Setup test environment...")
        test_chat_id = "-1001234567890_LOADTEST"
        ensure_test_chat(db, test_chat_id)

        baseline_metrics = get_baseline_metrics(db)
        logger.info(f"Baseline: {baseline_metrics['total_messages']} total messages")

        # Create test bots
        logger.info(f"Step 2: Creating {config['bot_count']} test bots...")
        bot_ids = create_test_bots(db, config['bot_count'], test_chat_id)

        # Enable simulation
        logger.info("Step 3: Enabling simulation...")
        enable_simulation(db, True)

        # Wait for startup
        logger.info("Waiting 10 seconds for workers to pick up config...")
        time.sleep(10)

        # Run test
        duration_seconds = config['duration_minutes'] * 60
        logger.info(f"Step 4: Running test for {config['duration_minutes']} minutes ({duration_seconds}s)...")
        logger.info("Collecting metrics every 30 seconds...")

        start_time = time.time()
        metrics_snapshots = []

        while time.time() - start_time < duration_seconds:
            elapsed = int(time.time() - start_time)
            remaining = duration_seconds - elapsed

            # Get current metrics
            current_messages = db.query(func.count(Message.id)).scalar()
            api_metrics = get_api_metrics()

            snapshot = {
                'elapsed_seconds': elapsed,
                'total_messages': current_messages,
                'messages_delta': current_messages - baseline_metrics['total_messages'],
                'api_metrics': api_metrics
            }
            metrics_snapshots.append(snapshot)

            logger.info(f"[{elapsed}s / {duration_seconds}s] Messages: {snapshot['messages_delta']} (+{snapshot['messages_delta'] - (metrics_snapshots[-2]['messages_delta'] if len(metrics_snapshots) > 1 else 0)} in last 30s)")

            if remaining < 30:
                time.sleep(remaining)
                break
            else:
                time.sleep(30)

        # Final metrics
        logger.info("Step 5: Collecting final metrics...")
        final_metrics = get_baseline_metrics(db)
        final_api_metrics = get_api_metrics()

        # Calculate results
        total_messages_generated = final_metrics['total_messages'] - baseline_metrics['total_messages']
        throughput_msgs_per_min = (total_messages_generated / config['duration_minutes']) if config['duration_minutes'] > 0 else 0

        results = {
            'scenario': scenario_name,
            'config': config,
            'start_time': datetime.fromtimestamp(start_time, tz=timezone.utc).isoformat(),
            'end_time': datetime.now(timezone.utc).isoformat(),
            'duration_minutes': config['duration_minutes'],
            'bot_count': config['bot_count'],
            'baseline_messages': baseline_metrics['total_messages'],
            'final_messages': final_metrics['total_messages'],
            'messages_generated': total_messages_generated,
            'throughput_msgs_per_min': round(throughput_msgs_per_min, 2),
            'metrics_snapshots': metrics_snapshots,
            'final_api_metrics': final_api_metrics
        }

        # Cleanup
        logger.info("Step 6: Cleaning up test bots...")
        for bot_id in bot_ids:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if bot:
                db.delete(bot)
        db.commit()

        # Disable simulation
        enable_simulation(db, False)

        logger.info("=" * 80)
        logger.info("RESULTS:")
        logger.info(f"  Messages generated: {total_messages_generated}")
        logger.info(f"  Throughput: {throughput_msgs_per_min:.2f} msgs/min")
        logger.info(f"  Duration: {config['duration_minutes']} minutes")
        logger.info("=" * 80)

        return results

    except Exception as e:
        logger.exception(f"Error during scenario: {e}")
        # Cleanup on error
        enable_simulation(db, False)
        raise
    finally:
        db.close()


def save_results(results: List[Dict[str, Any]], output_file: str):
    """Save test results to JSON file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_date': datetime.now(timezone.utc).isoformat(),
            'scenarios': results
        }, f, indent=2)

    logger.info(f"Results saved to: {output_file}")


def print_summary(results: List[Dict[str, Any]]):
    """Print summary table of all results."""
    print("\n" + "=" * 80)
    print("BASELINE LOAD TEST SUMMARY")
    print("=" * 80)
    print(f"{'Scenario':<15} {'Bots':<8} {'Duration':<10} {'Messages':<12} {'Throughput':<20}")
    print("-" * 80)

    for r in results:
        print(f"{r['scenario']:<15} {r['bot_count']:<8} {r['duration_minutes']} min{'':<5} {r['messages_generated']:<12} {r['throughput_msgs_per_min']:.2f} msgs/min")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='Baseline load testing')
    parser.add_argument('--scenario', choices=['low', 'medium', 'high'], help='Run specific scenario')
    parser.add_argument('--all', action='store_true', help='Run all scenarios')
    parser.add_argument('--duration', type=int, help='Override test duration in minutes (default: scenario default)')
    parser.add_argument('--output', default='docs/baseline_load_test_results.json', help='Output file for results')
    args = parser.parse_args()

    if not args.scenario and not args.all:
        parser.error('Must specify --scenario or --all')

    logger.info("BASELINE LOAD TEST - ROADMAP Task 0.2")
    logger.info(f"API Base: {API_BASE}")

    # Determine which scenarios to run
    scenarios_to_run = []
    if args.all:
        scenarios_to_run = list(SCENARIOS.keys())
    else:
        scenarios_to_run = [args.scenario]

    # Run scenarios
    results = []
    for scenario_name in scenarios_to_run:
        config = SCENARIOS[scenario_name].copy()
        # Override duration if specified
        if args.duration:
            config['duration_minutes'] = args.duration
            logger.info(f"Overriding duration to {args.duration} minutes")
        result = run_scenario(scenario_name, config)
        results.append(result)

        # Wait between scenarios
        if scenario_name != scenarios_to_run[-1]:
            logger.info("Waiting 60 seconds before next scenario...")
            time.sleep(60)

    # Save and summarize
    save_results(results, args.output)
    print_summary(results)

    logger.info("Load test complete!")


if __name__ == '__main__':
    main()
