"""
Database Query Performance Profiling

Measures execution time of critical queries to identify bottlenecks.
"""

import time
from datetime import datetime, timedelta, timezone
from database import SessionLocal, Message, Bot, Chat, BotStance, BotHolding, Setting
from sqlalchemy import text

def measure_query(name: str, func):
    """Measure query execution time"""
    start = time.perf_counter()
    result = func()
    duration = (time.perf_counter() - start) * 1000  # milliseconds
    return duration, result

def profile_queries():
    """Profile all critical queries"""

    db = SessionLocal()

    print("=" * 70)
    print("DATABASE QUERY PERFORMANCE PROFILING")
    print("=" * 70)

    # Check database size
    total_messages = db.query(Message).count()
    total_bots = db.query(Bot).count()
    total_chats = db.query(Chat).count()

    print(f"\n[Database Size]")
    print(f"  Messages: {total_messages}")
    print(f"  Bots: {total_bots}")
    print(f"  Chats: {total_chats}")

    if total_messages == 0:
        print("\n[WARNING] No messages in database. Some queries will return 0 results.")
        print("Run worker for a few minutes to populate data, then re-run profiling.")

    print(f"\n[Query Performance]")
    print(f"{'Query':<50} {'Time (ms)':<12} {'Results':<10}")
    print("-" * 70)

    # Query 1: Count messages in last hour (per bot)
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    if total_bots > 0:
        bot = db.query(Bot).first()
        duration, count = measure_query(
            "Messages per bot (last hour)",
            lambda: db.query(Message).filter(
                Message.bot_id == bot.id,
                Message.created_at >= one_hour_ago
            ).count()
        )
        print(f"{'1. Messages per bot (last hour)':<50} {duration:>10.2f}ms {count:>9}")
    else:
        print(f"{'1. Messages per bot (last hour)':<50} {'SKIP':<12} {'No bots':<10}")

    # Query 2: Last message in chat
    if total_chats > 0:
        chat = db.query(Chat).first()
        duration, msg = measure_query(
            "Last message in chat",
            lambda: db.query(Message).filter(
                Message.chat_db_id == chat.id
            ).order_by(Message.created_at.desc()).first()
        )
        result = "Found" if msg else "None"
        print(f"{'2. Last message in chat':<50} {duration:>10.2f}ms {result:>9}")
    else:
        print(f"{'2. Last message in chat':<50} {'SKIP':<12} {'No chats':<10}")

    # Query 3: Recent messages for dedup (bot_id filter)
    if total_bots > 0:
        bot = db.query(Bot).first()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        duration, msgs = measure_query(
            "Recent messages (dedup check)",
            lambda: db.query(Message).filter(
                Message.bot_id == bot.id,
                Message.created_at >= cutoff
            ).order_by(Message.created_at.desc()).limit(100).all()
        )
        print(f"{'3. Recent messages (dedup check)':<50} {duration:>10.2f}ms {len(msgs):>9}")
    else:
        print(f"{'3. Recent messages (dedup check)':<50} {'SKIP':<12} {'No bots':<10}")

    # Query 4: Message history (chat context)
    if total_chats > 0:
        chat = db.query(Chat).first()
        duration, msgs = measure_query(
            "Message history (last 20)",
            lambda: db.query(Message).filter(
                Message.chat_db_id == chat.id
            ).order_by(Message.created_at.desc()).limit(20).all()
        )
        print(f"{'4. Message history (last 20)':<50} {duration:>10.2f}ms {len(msgs):>9}")
    else:
        print(f"{'4. Message history (last 20)':<50} {'SKIP':<12} {'No chats':<10}")

    # Query 5: All enabled bots
    duration, bots = measure_query(
        "All enabled bots",
        lambda: db.query(Bot).filter(Bot.is_enabled.is_(True)).all()
    )
    print(f"{'5. All enabled bots':<50} {duration:>10.2f}ms {len(bots):>9}")

    # Query 6: All enabled chats
    duration, chats = measure_query(
        "All enabled chats",
        lambda: db.query(Chat).filter(Chat.is_enabled.is_(True)).all()
    )
    print(f"{'6. All enabled chats':<50} {duration:>10.2f}ms {len(chats):>9}")

    # Query 7: Bot stances
    if total_bots > 0:
        bot = db.query(Bot).first()
        duration, stances = measure_query(
            "Bot stances",
            lambda: db.query(BotStance).filter(BotStance.bot_id == bot.id).all()
        )
        print(f"{'7. Bot stances':<50} {duration:>10.2f}ms {len(stances):>9}")
    else:
        print(f"{'7. Bot stances':<50} {'SKIP':<12} {'No bots':<10}")

    # Query 8: Bot holdings
    if total_bots > 0:
        bot = db.query(Bot).first()
        duration, holdings = measure_query(
            "Bot holdings",
            lambda: db.query(BotHolding).filter(BotHolding.bot_id == bot.id).all()
        )
        print(f"{'8. Bot holdings':<50} {duration:>10.2f}ms {len(holdings):>9}")
    else:
        print(f"{'8. Bot holdings':<50} {'SKIP':<12} {'No bots':<10}")

    # Query 9: All settings
    duration, settings = measure_query(
        "All settings",
        lambda: db.query(Setting).all()
    )
    print(f"{'9. All settings':<50} {duration:>10.2f}ms {len(settings):>9}")

    # Query 10: Messages in last minute (rate limit check)
    one_min_ago = datetime.now(timezone.utc) - timedelta(minutes=1)
    duration, count = measure_query(
        "Messages in last minute",
        lambda: db.query(Message).filter(Message.created_at >= one_min_ago).count()
    )
    print(f"{'10. Messages in last minute':<50} {duration:>10.2f}ms {count:>9}")

    print("\n" + "=" * 70)
    print("[Analysis]")
    print("- Queries < 10ms: EXCELLENT")
    print("- Queries 10-50ms: GOOD")
    print("- Queries 50-100ms: ACCEPTABLE")
    print("- Queries > 100ms: NEEDS OPTIMIZATION")
    print("=" * 70)

    db.close()

if __name__ == "__main__":
    profile_queries()
