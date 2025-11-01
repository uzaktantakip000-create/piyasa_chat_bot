"""Load demo bots from .env"""

import os
import json
from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal, Bot, Chat, BotStance, BotHolding

db = SessionLocal()

try:
    # Clear test bots
    db.query(Bot).delete()
    db.query(Chat).delete()
    db.commit()

    print('Creating demo bots from .env tokens...')

    # Demo bots configuration
    demo_bots = [
        {
            "name": "Mehmet Yatırımcı",
            "token_env": "DEMO_BOT_1_TOKEN",
            "username": "@mehmet_trader",
            "persona": "Orta yaşlı, deneyimli, temkinli yatırımcı",
            "tone": "neutral",
            "risk": "low"
        },
        {
            "name": "Ayşe Scalper",
            "token_env": "DEMO_BOT_2_TOKEN",
            "username": "@ayse_scalp",
            "persona": "Genç, agresif, day trader",
            "tone": "enthusiastic",
            "risk": "high"
        },
        {
            "name": "Ali Hoca",
            "token_env": "DEMO_BOT_3_TOKEN",
            "username": "@ali_ekonomist",
            "persona": "Akademisyen, makro ekonomi odaklı",
            "tone": "analytical",
            "risk": "moderate"
        },
        {
            "name": "Zeynep Yeni",
            "token_env": "DEMO_BOT_4_TOKEN",
            "username": "@zeynep_newbie",
            "persona": "Yeni başlayan, öğrenmek isteyen",
            "tone": "curious",
            "risk": "low"
        },
    ]

    created_bots = []
    for bot_config in demo_bots:
        token = os.getenv(bot_config["token_env"])
        if not token:
            print(f'  [SKIP] {bot_config["name"]}: Token not found ({bot_config["token_env"]})')
            continue

        bot = Bot(
            name=bot_config["name"],
            token=token,
            username=bot_config["username"],
            is_enabled=True,
            speed_profile=json.dumps({
                "base_delay_seconds": 30,
                "jitter_factor": 0.3,
                "typing_delay_multiplier": 1.0
            }),
            active_hours=json.dumps(["00:00-23:59"]),
            persona_hint=bot_config["persona"],
            persona_profile=json.dumps({
                "tone": bot_config["tone"],
                "risk_profile": bot_config["risk"],
                "watchlist": ["BIST", "USD/TRY", "Kripto"],
                "never_do": ["spam", "vulgar"],
                "style": "casual"
            }),
            emotion_profile=json.dumps({
                "tone": bot_config["tone"],
                "empathy": 0.5,
                "signature_emoji": "📊",
                "signature_phrases": ["Bakalım"],
                "anecdotes": [],
                "energy": 0.6
            })
        )
        db.add(bot)
        created_bots.append(bot)
        print(f'  [OK] {bot_config["name"]} ({bot_config["username"]})')

    if not created_bots:
        print('\n[ERROR] No bots created! Check .env tokens.')
        db.rollback()
        exit(1)

    db.flush()

    # Create demo chat (MUST use real Telegram chat ID!)
    # For testing, we'll use a placeholder - user needs to replace with real chat ID
    print('\nCreating demo chat...')
    print('[WARNING] Using placeholder chat_id. To test message sending, update with real Telegram chat ID!')

    chat = Chat(
        chat_id="-1001234567890",  # PLACEHOLDER - Replace with real chat ID!
        title="Demo Chat - Piyasa Sohbet",
        is_enabled=True,
        topics=["BIST", "FX", "Kripto", "Makro"]
    )
    db.add(chat)
    db.flush()

    print(f'  [OK] {chat.title} (ID: {chat.id})')

    # Skip stances for now (can be added later via API)
    print('\n[INFO] Skipping stances (add via API if needed)')

    db.commit()

    print(f'\n[SUCCESS] Demo bots loaded successfully!')
    print(f'   - {len(created_bots)} bots created')
    print(f'   - 1 chat created')
    print(f'\n[NOTE] To send messages to Telegram, you need:')
    print(f'   1. Update chat_id with real Telegram chat ID')
    print(f'   2. Add all bots to that Telegram group')
    print(f'   3. Make sure bots have permission to send messages')

except Exception as e:
    db.rollback()
    print(f'\n[ERROR] {e}')
    import traceback
    traceback.print_exc()

finally:
    db.close()
