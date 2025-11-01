"""Fix database schema - add missing msg_metadata column"""

from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    db.execute(text('ALTER TABLE messages ADD COLUMN msg_metadata TEXT'))
    db.commit()
    print('[OK] Column msg_metadata added to messages table')
except Exception as e:
    print(f'[INFO] Column may already exist or error: {e}')
finally:
    db.close()
