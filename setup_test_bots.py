"""
Create test bots for load testing.

Usage:
    python setup_test_bots.py --count 50
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from database import SessionLocal, Bot, Chat
from security import encrypt_token


def create_test_bots(count: int, db):
    """Create test bots with dummy tokens."""
    print(f"Creating {count} test bots...")

    # Ensure at least one chat exists
    chat = db.query(Chat).filter(Chat.is_enabled.is_(True)).first()
    if not chat:
        print("Creating test chat...")
        chat = Chat(
            chat_id=-1001234567890,
            title="Test Chat",
            topics=["BIST", "FX", "Kripto"],
            is_enabled=True
        )
        db.add(chat)
        db.commit()
        print(f"[OK] Created test chat: {chat.title}")

    created = 0
    skipped = 0

    for i in range(1, count + 1):
        bot_name = f"LoadTestBot{i:03d}"

        # Check if bot already exists
        existing = db.query(Bot).filter(Bot.name == bot_name).first()
        if existing:
            skipped += 1
            continue

        # Create bot with dummy encrypted token
        dummy_token = f"8{i:09d}:AAFakeToken{i:020d}"
        encrypted_token = encrypt_token(dummy_token)

        bot = Bot(
            name=bot_name,
            token=encrypted_token,
            username=f"loadtest_bot_{i}",
            is_enabled=True,
            speed_profile={
                "base_delay_seconds": 2.0,
                "typing_delay_multiplier": 1.0
            },
            active_hours=["00:00-23:59"],  # Always active
            persona_hint=f"Test bot {i} for load testing",
            persona_profile={
                "tone": "neutral",
                "risk_profile": "moderate",
                "watchlist": ["BIST", "USD/TRY"],
                "never_do": [],
                "style": {"length": "concise", "emojis": False}
            },
            emotion_profile={
                "tone": "neutral",
                "empathy": 0.5,
                "signature_emoji": "📊",
                "signature_phrases": [],
                "anecdotes": [],
                "energy": 0.5
            }
        )

        db.add(bot)
        created += 1

        if created % 10 == 0:
            db.commit()
            print(f"  Created {created}/{count} bots...")

    db.commit()

    print(f"\n[OK] Bot creation complete!")
    print(f"   Created: {created}")
    print(f"   Skipped (already exist): {skipped}")
    print(f"   Total enabled bots: {db.query(Bot).filter(Bot.is_enabled.is_(True)).count()}")


def main():
    parser = argparse.ArgumentParser(description="Create test bots for load testing")
    parser.add_argument("--count", type=int, default=50, help="Number of test bots to create")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        create_test_bots(args.count, db)
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
