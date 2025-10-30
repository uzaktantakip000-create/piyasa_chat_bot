"""
Setup Test Data - Create test bots and chats for baseline testing

This script creates:
- 4 test bots with minimal configuration
- 1 test chat
- All bots assigned to the chat
"""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

from database import SessionLocal, Bot, Chat, BotStance, BotHolding, Setting
from security import mask_token
import json

def create_test_bots_and_chats():
    db = SessionLocal()

    try:
        # Check existing
        existing_bots = db.query(Bot).count()
        existing_chats = db.query(Chat).count()

        print(f"Existing bots: {existing_bots}")
        print(f"Existing chats: {existing_chats}")

        # Create 4 test bots
        bots = []
        for i in range(1, 5):
            bot = Bot(
                name=f"TestBot{i}",
                token=f"123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ-TEST-{i}",
                username=f"@testbot{i}",
                is_enabled=True,
                speed_profile=json.dumps({
                    "base_delay_seconds": 30,
                    "jitter_factor": 0.3,
                    "typing_delay_multiplier": 1.0
                }),
                active_hours=json.dumps(["00:00-23:59"]),  # Always active
                persona_hint=f"Test bot {i} - neutral trader",
                persona_profile=json.dumps({
                    "tone": "neutral",
                    "risk_profile": "moderate",
                    "watchlist": ["BIST", "USD/TRY"],
                    "never_do": ["panic", "spam"],
                    "style": "casual"
                }),
                emotion_profile=json.dumps({
                    "tone": "neutral",
                    "empathy": 0.5,
                    "signature_emoji": "📊",
                    "signature_phrases": ["Bakalım", "İlginç"],
                    "anecdotes": [],
                    "energy": 0.5
                })
            )
            db.add(bot)
            bots.append(bot)

        db.flush()  # Get IDs
        print(f"\nCreated {len(bots)} bots:")
        for bot in bots:
            print(f"  - {bot.name} (ID: {bot.id}, @{bot.username})")

        # Create 1 test chat
        chat = Chat(
            chat_id="-1001234567890",
            title="Test Chat - Piyasa Sohbet",
            is_enabled=True,
            topics=["BIST", "FX", "Kripto", "Makro"]  # JSON column, accepts list
        )
        db.add(chat)
        db.flush()

        print(f"\nCreated chat:")
        print(f"  - {chat.title} (ID: {chat.id}, {len(bots)} bots assigned)")

        # Add sample stances for each bot
        topics = ["BIST", "USD/TRY", "Kripto"]
        stances_text = {
            "BIST": ["yükselişte", "düşüşte", "yatay seyrediyor"],
            "USD/TRY": ["artacak", "düşecek", "stabil kalacak"],
            "Kripto": ["boğa piyasası", "ayı piyasası", "konsolidasyon"]
        }

        for bot in bots:
            for topic in topics:
                stance = BotStance(
                    bot_id=bot.id,
                    topic=topic,
                    stance_text=f"{topic} {stances_text[topic][(bot.id-1) % len(stances_text[topic])]}",
                    confidence=0.7,
                    cooldown_until=None
                )
                db.add(stance)

        print(f"\nAdded {len(topics) * len(bots)} stances")

        # Add sample holdings
        holdings_data = [
            ("THYAO", 85.50, 100),
            ("GARAN", 120.00, 50),
            ("BTC/USDT", 67000, 0.01),
        ]

        for bot in bots:
            # Each bot gets 1-2 holdings
            for j, (symbol, price, size) in enumerate(holdings_data[:2]):
                holding = BotHolding(
                    bot_id=bot.id,
                    symbol=symbol,
                    avg_price=price,
                    size=size,
                    note=f"Test holding {j+1}"
                )
                db.add(holding)

        print(f"Added {2 * len(bots)} holdings")

        # Update settings for testing
        print("\nUpdating settings for baseline test...")

        settings_updates = {
            "simulation_active": True,
            "bot_hourly_msg_limit": json.dumps({"min": 10, "max": 20}),  # Increased from 6-12
            "max_msgs_per_min": 20,  # Increased from 6
            "scale_factor": 1.0,
            "prime_hours_boost": False,  # Disable for consistent baseline
            "typing_enabled": True,
            "reply_probability": 0.65,
        }

        for key, value in settings_updates.items():
            setting = db.query(Setting).filter(Setting.key == key).first()
            if setting:
                setting.value = value if isinstance(value, str) else json.dumps(value)
                print(f"  Updated: {key} = {value}")
            else:
                setting = Setting(key=key, value=value if isinstance(value, str) else json.dumps(value))
                db.add(setting)
                print(f"  Created: {key} = {value}")

        db.commit()

        print("\n✅ Test data setup completed!")
        print(f"   - {len(bots)} bots created (all enabled)")
        print(f"   - 1 chat created (enabled)")
        print(f"   - simulation_active = True")
        print(f"   - bot_hourly_msg_limit increased to 10-20")
        print(f"   - max_msgs_per_min increased to 20")
        print(f"\nReady for baseline test!")

        return True

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("SETUP TEST DATA - Baseline Load Test")
    print("=" * 60)
    create_test_bots_and_chats()
