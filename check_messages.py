"""Check message generation results"""

from database import SessionLocal, Message, Bot
from datetime import datetime, timedelta, timezone

db = SessionLocal()

all_messages = db.query(Message).all()
recent = db.query(Message).filter(Message.created_at > datetime.now(timezone.utc) - timedelta(minutes=5)).all()
bots = db.query(Bot).all()

print('=== MESSAGE GENERATION TEST RESULTS ===')
print(f'Total messages in DB: {len(all_messages)}')
print(f'Messages in last 5 minutes: {len(recent)}')
print(f'Enabled bots: {len([b for b in bots if b.is_enabled])}')

if recent:
    print(f'\nRecent messages:')
    for m in recent[-10:]:
        print(f'  - [{m.created_at.strftime("%H:%M:%S")}] Bot {m.bot_id}: {m.text[:60]}...')
else:
    print('\n[WARNING] No messages generated in last 5 minutes!')

# Calculate throughput
if len(recent) > 0:
    duration_minutes = 5
    throughput = len(recent) / duration_minutes
    print(f'\n[THROUGHPUT] {throughput:.2f} messages/minute ({throughput*60:.1f} messages/hour)')

db.close()
