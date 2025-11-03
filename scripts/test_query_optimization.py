"""
Test Query Optimization

Compares old vs new pick_bot implementation to measure query reduction.

Usage:
    python scripts/test_query_optimization.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import event, Engine
from database import SessionLocal, Bot, Message

# Query counter
query_count = 0


@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    global query_count
    query_count += 1


def test_old_approach(db, bots):
    """Simulate old N+1 approach."""
    global query_count
    query_count = 0

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    eligible_count = 0
    for b in bots:
        # This is the old approach - one query per bot
        sent_last_hour = (
            db.query(Message)
            .filter(Message.bot_id == b.id, Message.created_at >= one_hour_ago)
            .count()
        )
        if sent_last_hour < 12:
            eligible_count += 1

    return query_count, eligible_count


def test_new_approach(db, bots):
    """Test new optimized approach."""
    from sqlalchemy import func
    global query_count
    query_count = 0

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

    # New approach - single query with GROUP BY
    bot_ids = [b.id for b in bots]
    hourly_counts = (
        db.query(Message.bot_id, func.count(Message.id))
        .filter(
            Message.bot_id.in_(bot_ids),
            Message.created_at >= one_hour_ago
        )
        .group_by(Message.bot_id)
        .all()
    )

    bot_message_counts = {bot_id: count for bot_id, count in hourly_counts}

    eligible_count = 0
    for b in bots:
        sent_last_hour = bot_message_counts.get(b.id, 0)
        if sent_last_hour < 12:
            eligible_count += 1

    return query_count, eligible_count


def main():
    print("=" * 80)
    print(" QUERY OPTIMIZATION TEST")
    print("=" * 80)

    db = SessionLocal()
    try:
        # Get all enabled bots
        bots = db.query(Bot).filter(Bot.is_enabled.is_(True)).all()
        bot_count = len(bots)

        print(f"\nTEST CONFIGURATION:")
        print(f"   Enabled Bots: {bot_count}")

        if bot_count == 0:
            print("\nWARNING: No enabled bots found. Cannot run test.")
            return

        # Test old approach
        print(f"\nOLD APPROACH (N+1 Problem):")
        old_queries, old_eligible = test_old_approach(db, bots)
        print(f"   Queries Executed: {old_queries}")
        print(f"   Eligible Bots: {old_eligible}")

        # Test new approach
        print(f"\nNEW APPROACH (Optimized):")
        new_queries, new_eligible = test_new_approach(db, bots)
        print(f"   Queries Executed: {new_queries}")
        print(f"   Eligible Bots: {new_eligible}")

        # Comparison
        print(f"\nIMPROVEMENT:")
        print(f"   Query Reduction: {old_queries} -> {new_queries} (-{old_queries - new_queries} queries)")
        if old_queries > 0:
            pct_reduction = ((old_queries - new_queries) / old_queries * 100)
            print(f"   Percentage: {pct_reduction:.1f}% reduction")
            print(f"   Speedup: ~{old_queries / max(new_queries, 1):.1f}x faster")

        if old_eligible == new_eligible:
            print(f"\nSUCCESS: Results match! Both approaches found {old_eligible} eligible bots")
        else:
            print(f"\nWARNING: Results differ - Old={old_eligible}, New={new_eligible}")

    finally:
        db.close()

    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
