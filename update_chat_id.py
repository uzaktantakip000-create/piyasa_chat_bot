"""
Update Chat ID - Telegram grup entegrasyonu için chat ID güncelleme

Usage:
    python update_chat_id.py --chat-id="-1001234567890"
    python update_chat_id.py --chat-id="-1001234567890" --verify
"""

import argparse
import sys
from database import SessionLocal, Chat

def update_chat_id(chat_id: str, verify: bool = False):
    """Update chat ID in database"""

    db = SessionLocal()

    try:
        # Get existing chat
        chat = db.query(Chat).filter(Chat.id == 1).first()

        if not chat:
            print("[ERROR] Chat ID=1 not found in database!")
            print("Run 'python load_demo_bots.py' first to create demo chat.")
            return False

        print(f"\n[Current] Chat: {chat.title}")
        print(f"  Old chat_id: {chat.chat_id}")

        # Update chat_id
        chat.chat_id = chat_id
        db.commit()

        print(f"  New chat_id: {chat.chat_id}")
        print("\n[SUCCESS] Chat ID updated!")

        if verify:
            print("\n[Verify] Testing Telegram API connection...")
            # TODO: Add Telegram API verification
            print("  (Verification will be done when worker starts)")

        print("\n[Next Steps]")
        print("1. Start worker: python worker.py")
        print("2. Wait 5-10 minutes")
        print("3. Check messages: python check_messages.py")

        return True

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Update Telegram Chat ID")
    parser.add_argument(
        "--chat-id",
        type=str,
        required=True,
        help='Telegram chat ID (e.g., "-1001234567890")'
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify connection after update"
    )

    args = parser.parse_args()

    # Validate chat_id format
    if not args.chat_id.startswith("-"):
        print("[WARNING] Chat ID usually starts with '-' for groups")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            sys.exit(1)

    print("=" * 60)
    print("UPDATE TELEGRAM CHAT ID")
    print("=" * 60)

    success = update_chat_id(args.chat_id, args.verify)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
