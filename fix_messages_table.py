"""Fix messages table - add AUTOINCREMENT to id column"""
import sqlite3
from database import SessionLocal

def fix_messages_table():
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    print("Backing up messages table...")

    # 1. Backup existing messages
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages_backup AS
        SELECT * FROM messages
    """)

    backup_count = cursor.execute("SELECT COUNT(*) FROM messages_backup").fetchone()[0]
    print(f"Backed up {backup_count} messages")

    # 2. Drop old table and indexes
    print("Dropping old messages table...")
    cursor.execute("DROP TABLE IF EXISTS messages")

    # 3. Recreate with AUTOINCREMENT
    print("Creating new messages table with AUTOINCREMENT...")
    cursor.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER,
            chat_db_id INTEGER,
            telegram_message_id BIGINT,
            text TEXT,
            reply_to_message_id BIGINT,
            created_at DATETIME NOT NULL,
            msg_metadata TEXT,
            FOREIGN KEY(bot_id) REFERENCES bots (id) ON DELETE SET NULL,
            FOREIGN KEY(chat_db_id) REFERENCES chats (id) ON DELETE SET NULL
        )
    """)

    # 4. Recreate indexes
    print("Recreating indexes...")
    indexes = [
        "CREATE INDEX ix_messages_bot_id ON messages (bot_id)",
        "CREATE INDEX ix_messages_chat_db_id ON messages (chat_db_id)",
        "CREATE INDEX ix_messages_telegram_message_id ON messages (telegram_message_id)",
        "CREATE INDEX ix_messages_reply_to_message_id ON messages (reply_to_message_id)",
        "CREATE INDEX ix_messages_created_at ON messages (created_at)",
        "CREATE INDEX ix_messages_bot_created_at ON messages (bot_id, created_at)",
        "CREATE INDEX ix_messages_chat_created_at ON messages (chat_db_id, created_at)",
        "CREATE INDEX ix_messages_chat_telegram_msg ON messages (chat_db_id, telegram_message_id)",
        "CREATE INDEX ix_messages_reply_lookup ON messages (chat_db_id, bot_id, telegram_message_id)",
        "CREATE INDEX ix_messages_incoming ON messages (bot_id, created_at, chat_db_id)",
    ]

    for idx_sql in indexes:
        cursor.execute(idx_sql)

    # 5. Restore messages if any
    if backup_count > 0:
        print(f"Restoring {backup_count} messages...")
        cursor.execute("""
            INSERT INTO messages (bot_id, chat_db_id, telegram_message_id, text, reply_to_message_id, created_at, msg_metadata)
            SELECT bot_id, chat_db_id, telegram_message_id, text, reply_to_message_id, created_at, msg_metadata
            FROM messages_backup
        """)

        restored_count = cursor.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        print(f"Restored {restored_count} messages")

    # 6. Drop backup
    cursor.execute("DROP TABLE messages_backup")

    conn.commit()
    conn.close()

    print("\n✓ Messages table fixed with AUTOINCREMENT!")
    print("\nVerifying...")

    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='messages'")
    create_stmt = cursor.fetchone()[0]
    print(f"\nNew CREATE statement:\n{create_stmt}")
    conn.close()

if __name__ == "__main__":
    # Stop worker first!
    print("IMPORTANT: Make sure worker.py is stopped before running this script!")
    input("Press ENTER to continue or CTRL+C to abort...")
    fix_messages_table()
