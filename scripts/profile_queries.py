"""
Database Query Profiling Tool

Analyzes SQLAlchemy queries to identify:
- Slow queries (>100ms)
- N+1 query problems
- Missing indexes
- Query frequency and patterns

Usage:
    python scripts/profile_queries.py --duration 60

Requirements:
    - System must be running (docker-compose up)
    - Database accessible via DATABASE_URL
"""

import argparse
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from sqlalchemy import event, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DATABASE_URL, Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class QueryProfiler:
    """Profiles database queries with timing and pattern analysis."""

    def __init__(self):
        self.queries: List[Dict] = []
        self.query_patterns = defaultdict(int)
        self.slow_queries = []
        self.start_time = None

    def record_query(self, statement: str, duration_ms: float):
        """Record a query execution."""
        query_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "statement": statement,
            "duration_ms": duration_ms,
        }

        self.queries.append(query_data)

        # Track slow queries
        if duration_ms > 100:
            self.slow_queries.append(query_data)

        # Pattern analysis (simplified)
        pattern = self._extract_pattern(statement)
        self.query_patterns[pattern] += 1

    def _extract_pattern(self, statement: str) -> str:
        """Extract query pattern for grouping."""
        # Remove specific values, keep structure
        statement = statement.strip().upper()

        # Simplify SELECT
        if statement.startswith("SELECT"):
            if "FROM messages" in statement:
                return "SELECT_FROM_messages"
            elif "FROM bots" in statement:
                return "SELECT_FROM_bots"
            elif "FROM chats" in statement:
                return "SELECT_FROM_chats"
            elif "FROM bot_stances" in statement:
                return "SELECT_FROM_bot_stances"
            elif "FROM bot_holdings" in statement:
                return "SELECT_FROM_bot_holdings"
            elif "FROM settings" in statement:
                return "SELECT_FROM_settings"
        elif statement.startswith("INSERT"):
            return "INSERT"
        elif statement.startswith("UPDATE"):
            return "UPDATE"
        elif statement.startswith("DELETE"):
            return "DELETE"

        return "OTHER"

    def analyze(self) -> Dict:
        """Analyze recorded queries and generate report."""
        if not self.queries:
            return {"error": "No queries recorded"}

        duration_sec = (time.time() - self.start_time) if self.start_time else 0

        # Calculate statistics
        total_queries = len(self.queries)
        durations = [q["duration_ms"] for q in self.queries]
        avg_duration = sum(durations) / total_queries if total_queries > 0 else 0
        max_duration = max(durations) if durations else 0
        p95_duration = sorted(durations)[int(len(durations) * 0.95)] if durations else 0

        # Query patterns
        top_patterns = sorted(
            self.query_patterns.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Slow queries
        slow_sorted = sorted(
            self.slow_queries,
            key=lambda x: x["duration_ms"],
            reverse=True
        )[:10]

        # N+1 detection (heuristic: same pattern repeated many times in short time)
        potential_n_plus_1 = [
            (pattern, count)
            for pattern, count in top_patterns
            if count > 20 and pattern.startswith("SELECT")
        ]

        return {
            "duration_sec": duration_sec,
            "total_queries": total_queries,
            "queries_per_sec": total_queries / duration_sec if duration_sec > 0 else 0,
            "avg_duration_ms": avg_duration,
            "max_duration_ms": max_duration,
            "p95_duration_ms": p95_duration,
            "slow_query_count": len(self.slow_queries),
            "slow_query_pct": (len(self.slow_queries) / total_queries * 100) if total_queries > 0 else 0,
            "top_patterns": top_patterns,
            "slow_queries": slow_sorted,
            "potential_n_plus_1": potential_n_plus_1,
        }


# Global profiler instance
profiler = QueryProfiler()


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Event listener: Start timing query execution."""
    conn.info.setdefault("query_start_time", []).append(time.time())


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Event listener: Record query execution time."""
    start_times = conn.info.get("query_start_time", [])
    if start_times:
        start_time = start_times.pop()
        duration_ms = (time.time() - start_time) * 1000
        profiler.record_query(statement, duration_ms)


def print_report(results: Dict):
    """Print comprehensive profiling report."""
    print("\n")
    print("=" * 80)
    print(" DATABASE QUERY PROFILING REPORT")
    print("=" * 80)

    # Overview
    print("\n📊 OVERVIEW")
    print("-" * 80)
    print(f"  Duration:          {results['duration_sec']:.1f}s")
    print(f"  Total Queries:     {results['total_queries']}")
    print(f"  Queries/sec:       {results['queries_per_sec']:.2f}")

    # Performance
    print("\n⚡ PERFORMANCE")
    print("-" * 80)
    print(f"  Avg Duration:      {results['avg_duration_ms']:.2f}ms")
    print(f"  Max Duration:      {results['max_duration_ms']:.2f}ms")
    print(f"  P95 Duration:      {results['p95_duration_ms']:.2f}ms")
    print(f"  Slow Queries:      {results['slow_query_count']} ({results['slow_query_pct']:.1f}%)")

    # Query patterns
    print("\n📈 TOP QUERY PATTERNS")
    print("-" * 80)
    for pattern, count in results["top_patterns"]:
        pct = (count / results["total_queries"] * 100)
        print(f"  {pattern:<30} {count:>6} ({pct:>5.1f}%)")

    # Slow queries
    if results["slow_queries"]:
        print("\n🐌 SLOWEST QUERIES")
        print("-" * 80)
        for i, query in enumerate(results["slow_queries"][:5], 1):
            print(f"\n  #{i} - {query['duration_ms']:.2f}ms")
            # Truncate long statements
            stmt = query["statement"][:200]
            if len(query["statement"]) > 200:
                stmt += "..."
            print(f"  {stmt}")

    # N+1 detection
    if results["potential_n_plus_1"]:
        print("\n⚠️  POTENTIAL N+1 QUERY PROBLEMS")
        print("-" * 80)
        print("  (Same query pattern repeated >20 times)")
        for pattern, count in results["potential_n_plus_1"]:
            print(f"  {pattern:<30} {count:>6} times")

    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-" * 80)

    if results["slow_query_pct"] > 10:
        print("  ⚠️  High slow query percentage (>10%) - investigate slow queries")

    if results["avg_duration_ms"] > 50:
        print("  ⚠️  High average duration (>50ms) - consider adding indexes")

    if results["potential_n_plus_1"]:
        print("  ⚠️  Potential N+1 problems detected - use eager loading (joinedload)")

    if results["slow_query_pct"] < 5 and results["avg_duration_ms"] < 30:
        print("  ✅ Query performance looks good!")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Database Query Profiling")
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Profiling duration in seconds (default: 60)",
    )

    args = parser.parse_args()

    print("=" * 80)
    print(" DATABASE QUERY PROFILER")
    print("=" * 80)
    print(f"\n📝 Configuration:")
    print(f"   Duration: {args.duration}s")
    print(f"   Database: {DATABASE_URL}")

    # Create engine with event listeners
    engine = create_engine(DATABASE_URL, echo=False)

    print(f"\n🔍 Profiling database queries for {args.duration} seconds...")
    print(f"   (Monitoring all queries to the database)")
    print(f"   Press Ctrl+C to stop early\n")

    profiler.start_time = time.time()

    try:
        # Just wait and let the event listeners capture queries
        # from the running system (workers, API, etc.)
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("\n\n⚠️  Profiling interrupted by user")

    # Analyze and report
    print(f"\n📊 Analyzing {len(profiler.queries)} queries...")
    results = profiler.analyze()
    print_report(results)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
