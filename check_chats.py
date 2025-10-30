"""Check all chats in database"""

from database import SessionLocal, Chat

db = SessionLocal()
chats = db.query(Chat).all()

print(f'Total chats in DB: {len(chats)}\n')

for i, c in enumerate(chats):
    print(f'Chat {i+1}:')
    print(f'  ID: {c.id}')
    print(f'  Title: {c.title}')
    print(f'  chat_id: {c.chat_id}')
    print(f'  Enabled: {c.is_enabled}')
    print(f'  Topics: {c.topics}')
    print()

db.close()
