"""Fix bot persona_profile and emotion_profile encoding"""

import json
from database import SessionLocal, Bot

db = SessionLocal()

print("Fixing bot personas...")

bots = db.query(Bot).all()

for bot in bots:
    print(f"\n[Bot] {bot.name}")

    # Fix persona_profile if it's a string
    if isinstance(bot.persona_profile, str):
        try:
            bot.persona_profile = json.loads(bot.persona_profile)
            print(f"  Fixed persona_profile (was string)")
        except:
            bot.persona_profile = {}
            print(f"  Reset persona_profile (invalid JSON)")

    # Fix emotion_profile if it's a string
    if isinstance(bot.emotion_profile, str):
        try:
            bot.emotion_profile = json.loads(bot.emotion_profile)
            print(f"  Fixed emotion_profile (was string)")
        except:
            bot.emotion_profile = {}
            print(f"  Reset emotion_profile (invalid JSON)")

    # Fix speed_profile if it's a string
    if isinstance(bot.speed_profile, str):
        try:
            bot.speed_profile = json.loads(bot.speed_profile)
            print(f"  Fixed speed_profile (was string)")
        except:
            bot.speed_profile = {"base_delay_seconds": 30, "jitter_factor": 0.3, "typing_delay_multiplier": 1.0}
            print(f"  Reset speed_profile (invalid JSON)")

    # Fix active_hours if it's a string
    if isinstance(bot.active_hours, str):
        try:
            bot.active_hours = json.loads(bot.active_hours)
            print(f"  Fixed active_hours (was string)")
        except:
            bot.active_hours = ["00:00-23:59"]
            print(f"  Reset active_hours (invalid JSON)")

db.commit()
print("\n[SUCCESS] All bot personas fixed!")
db.close()
