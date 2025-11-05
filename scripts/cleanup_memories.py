"""
Periodic memory cleanup script.

Removes low-relevance, unused memories to prevent database bloat.

Usage:
    python scripts/cleanup_memories.py [--dry-run] [--aggressive]
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db, BotMemory

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Konfigürasyon
MAX_MEMORIES_PER_BOT = 50
LOW_RELEVANCE_THRESHOLD = 0.3
MIN_USAGE_COUNT = 2
UNUSED_MONTHS = 6


def cleanup_low_relevance_memories(db: Session, dry_run: bool = False) -> int:
    """
    Düşük skorlu ve az kullanılan hafızaları temizle.

    Criteria:
    - relevance_score < 0.3
    - usage_count < 2
    - last_used_at > 6 months ago
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=30 * UNUSED_MONTHS)

    query = db.query(BotMemory).filter(
        BotMemory.relevance_score < LOW_RELEVANCE_THRESHOLD,
        BotMemory.usage_count < MIN_USAGE_COUNT,
        BotMemory.last_used_at < cutoff_date
    )

    count = query.count()

    if count == 0:
        logger.info("No low-relevance memories to clean up")
        return 0

    if dry_run:
        logger.info(f"[DRY RUN] Would delete {count} low-relevance memories")
        # Show samples
        samples = query.limit(5).all()
        for mem in samples:
            logger.info(f"  - Bot {mem.bot_id}: [{mem.memory_type}] {mem.content[:60]}... "
                       f"(score={mem.relevance_score:.2f}, usage={mem.usage_count})")
        return count

    query.delete(synchronize_session=False)
    db.commit()

    logger.info(f"✅ Deleted {count} low-relevance memories")
    return count


def enforce_memory_limit(db: Session, dry_run: bool = False) -> int:
    """
    Her bot için maksimum hafıza limitini uygula.

    Eğer bot'un hafıza sayısı MAX_MEMORIES_PER_BOT'u aşarsa,
    en düşük skorlu ve az kullanılanları sil.
    """
    # Bot'ları ve hafıza sayılarını getir
    bot_memory_counts = db.query(
        BotMemory.bot_id,
        func.count(BotMemory.id).label('count')
    ).group_by(BotMemory.bot_id).having(
        func.count(BotMemory.id) > MAX_MEMORIES_PER_BOT
    ).all()

    if not bot_memory_counts:
        logger.info(f"All bots are within memory limit ({MAX_MEMORIES_PER_BOT})")
        return 0

    total_deleted = 0

    for bot_id, count in bot_memory_counts:
        excess = count - MAX_MEMORIES_PER_BOT

        logger.info(f"Bot {bot_id} has {count} memories (excess: {excess})")

        # En düşük skorlu hafızaları bul
        to_delete = db.query(BotMemory).filter(
            BotMemory.bot_id == bot_id
        ).order_by(
            BotMemory.relevance_score.asc(),
            BotMemory.usage_count.asc(),
            BotMemory.last_used_at.asc()
        ).limit(excess).all()

        if dry_run:
            logger.info(f"  [DRY RUN] Would delete {len(to_delete)} memories from bot {bot_id}")
            for mem in to_delete[:3]:  # Show first 3
                logger.info(f"    - [{mem.memory_type}] {mem.content[:50]}... "
                           f"(score={mem.relevance_score:.2f})")
        else:
            for mem in to_delete:
                db.delete(mem)
            db.commit()
            logger.info(f"  ✅ Deleted {len(to_delete)} excess memories from bot {bot_id}")

        total_deleted += len(to_delete)

    return total_deleted


def decay_old_memories(db: Session, dry_run: bool = False) -> int:
    """
    6 aydan eski hafızaların relevance_score'unu %10 azalt.

    Bu sayede eski hafızalar zamanla otomatik olarak önem kaybeder.
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)

    query = db.query(BotMemory).filter(
        BotMemory.created_at < cutoff_date,
        BotMemory.relevance_score > 0.1  # 0'a inmesin
    )

    count = query.count()

    if count == 0:
        logger.info("No old memories to decay")
        return 0

    if dry_run:
        logger.info(f"[DRY RUN] Would decay {count} old memories by 10%")
        return count

    # Decay işlemi
    query.update(
        {BotMemory.relevance_score: BotMemory.relevance_score * 0.9},
        synchronize_session=False
    )
    db.commit()

    logger.info(f"✅ Decayed {count} old memories (score × 0.9)")
    return count


def get_memory_statistics(db: Session):
    """Hafıza istatistiklerini göster."""
    total = db.query(func.count(BotMemory.id)).scalar()
    unique_bots = db.query(func.count(func.distinct(BotMemory.bot_id))).scalar()

    avg_per_bot = total / unique_bots if unique_bots > 0 else 0

    # En çok hafızası olan bot
    max_bot = db.query(
        BotMemory.bot_id,
        func.count(BotMemory.id).label('count')
    ).group_by(BotMemory.bot_id).order_by(
        func.count(BotMemory.id).desc()
    ).first()

    # Ortalama relevance score
    avg_score = db.query(func.avg(BotMemory.relevance_score)).scalar() or 0

    # Kullanılmayan hafızalar (6+ ay)
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    unused = db.query(func.count(BotMemory.id)).filter(
        BotMemory.last_used_at < cutoff
    ).scalar()

    logger.info("=" * 60)
    logger.info("MEMORY STATISTICS")
    logger.info("=" * 60)
    logger.info(f"Total memories: {total}")
    logger.info(f"Unique bots: {unique_bots}")
    logger.info(f"Average per bot: {avg_per_bot:.1f}")
    logger.info(f"Max per bot: {max_bot[1] if max_bot else 0} (bot_id: {max_bot[0] if max_bot else 'N/A'})")
    logger.info(f"Average relevance score: {avg_score:.2f}")
    logger.info(f"Unused (6+ months): {unused}")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Clean up bot memories')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    parser.add_argument('--aggressive', action='store_true', help='More aggressive cleanup (shorter retention)')
    parser.add_argument('--stats-only', action='store_true', help='Only show statistics')
    args = parser.parse_args()

    if args.aggressive:
        global UNUSED_MONTHS, LOW_RELEVANCE_THRESHOLD, MAX_MEMORIES_PER_BOT
        UNUSED_MONTHS = 3  # 3 ay
        LOW_RELEVANCE_THRESHOLD = 0.5  # Daha yüksek eşik
        MAX_MEMORIES_PER_BOT = 30  # Daha düşük limit
        logger.info("🔥 Aggressive mode enabled")

    logger.info("=" * 60)
    logger.info("BOT MEMORY CLEANUP")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")

    db = next(get_db())

    try:
        # İstatistikleri göster
        get_memory_statistics(db)

        if args.stats_only:
            return

        logger.info("\n" + "=" * 60)
        logger.info("CLEANUP OPERATIONS")
        logger.info("=" * 60 + "\n")

        # 1. Düşük skorlu hafızaları temizle
        logger.info("Step 1: Cleaning up low-relevance memories...")
        deleted_low = cleanup_low_relevance_memories(db, dry_run=args.dry_run)

        # 2. Hafıza limitini uygula
        logger.info("\nStep 2: Enforcing memory limit per bot...")
        deleted_excess = enforce_memory_limit(db, dry_run=args.dry_run)

        # 3. Eski hafızaları decay et
        logger.info("\nStep 3: Decaying old memories...")
        decayed = decay_old_memories(db, dry_run=args.dry_run)

        # Özet
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Low-relevance deleted: {deleted_low}")
        logger.info(f"Excess deleted: {deleted_excess}")
        logger.info(f"Old memories decayed: {decayed}")
        logger.info(f"Total cleanup actions: {deleted_low + deleted_excess + decayed}")
        logger.info("=" * 60)

        if args.dry_run:
            logger.info("\n✅ Dry run complete - No changes were made")
        else:
            logger.info("\n✅ Cleanup complete")

    except Exception as e:
        logger.exception(f"Error during cleanup: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    main()
