"""
Performance benchmark: Sync vs Async Database Queries

Compares query performance for common operations.
"""

import asyncio
import time
from database import SessionLocal, Bot, Chat, Setting
from database_async import get_async_session, fetch_enabled_bots_async, fetch_enabled_chats_async, fetch_all_settings_async
from sqlalchemy import select


def benchmark_sync():
    """Benchmark sync database queries"""
    start = time.time()

    db = SessionLocal()
    try:
        # Fetch bots (10 times)
        for _ in range(10):
            bots = db.query(Bot).filter(Bot.is_enabled == True).all()

        # Fetch chats (10 times)
        for _ in range(10):
            chats = db.query(Chat).filter(Chat.is_enabled == True).all()

        # Fetch settings (10 times)
        for _ in range(10):
            settings = db.query(Setting).all()

    finally:
        db.close()

    elapsed = time.time() - start
    return elapsed


async def benchmark_async():
    """Benchmark async database queries"""
    start = time.time()

    async with get_async_session() as session:
        # Fetch bots (10 times)
        for _ in range(10):
            bots = await fetch_enabled_bots_async(session)

        # Fetch chats (10 times)
        for _ in range(10):
            chats = await fetch_enabled_chats_async(session)

        # Fetch settings (10 times)
        for _ in range(10):
            settings = await fetch_all_settings_async(session)

    elapsed = time.time() - start
    return elapsed


async def benchmark_concurrent_async():
    """Benchmark concurrent async queries (the real benefit)"""
    start = time.time()

    tasks = []
    for _ in range(10):
        async def query_all():
            async with get_async_session() as session:
                bots = await fetch_enabled_bots_async(session)
                chats = await fetch_enabled_chats_async(session)
                settings = await fetch_all_settings_async(session)
                return len(bots), len(chats), len(settings)

        tasks.append(query_all())

    results = await asyncio.gather(*tasks)

    elapsed = time.time() - start
    return elapsed, results


def main():
    print("=" * 60)
    print("Database Performance Benchmark: Sync vs Async")
    print("=" * 60)
    print("Test: 10x (Fetch bots + Fetch chats + Fetch settings)\n")

    # Benchmark 1: Sync
    print("Benchmark 1: Synchronous Queries")
    sync_time = benchmark_sync()
    print(f"  Total time: {sync_time:.3f}s")
    print(f"  Avg per query: {sync_time/30:.4f}s\n")

    # Benchmark 2: Async (sequential)
    print("Benchmark 2: Async Queries (Sequential)")
    async_time = asyncio.run(benchmark_async())
    print(f"  Total time: {async_time:.3f}s")
    print(f"  Avg per query: {async_time/30:.4f}s")
    improvement = ((sync_time - async_time) / sync_time) * 100
    print(f"  Improvement: {improvement:+.1f}%\n")

    # Benchmark 3: Async (concurrent) - the real advantage
    print("Benchmark 3: Async Queries (10 Concurrent Sessions)")
    concurrent_time, results = asyncio.run(benchmark_concurrent_async())
    print(f"  Total time: {concurrent_time:.3f}s")
    print(f"  Queries completed: {len(results)}")
    print(f"  Avg per session: {concurrent_time/10:.4f}s")
    speedup = sync_time / concurrent_time
    print(f"  Speedup vs sync: {speedup:.2f}x\n")

    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Sync (baseline):      {sync_time:.3f}s (1.00x)")
    print(f"Async (sequential):   {async_time:.3f}s ({sync_time/async_time:.2f}x)")
    print(f"Async (concurrent):   {concurrent_time:.3f}s ({sync_time/concurrent_time:.2f}x) ← TARGET")
    print("\nConclusion:")
    if speedup >= 3.0:
        print(f"  SUCCESS: {speedup:.1f}x speedup achieved (target: 3x)")
    elif speedup >= 2.0:
        print(f"  GOOD: {speedup:.1f}x speedup (approaching target)")
    else:
        print(f"  PARTIAL: {speedup:.1f}x speedup (further optimization needed)")


if __name__ == "__main__":
    main()
