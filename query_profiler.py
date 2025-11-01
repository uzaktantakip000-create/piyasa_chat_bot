"""
Query Profiler - Session 15
Lightweight query timing and analysis tool
"""

import time
import logging
from contextlib import contextmanager
from typing import Dict, List, Any
from collections import defaultdict
import json

logger = logging.getLogger(__name__)

class QueryProfiler:
    """Profile database queries and identify bottlenecks"""

    def __init__(self):
        self.queries: List[Dict[str, Any]] = []
        self.query_counts = defaultdict(int)
        self.query_times = defaultdict(list)

    @contextmanager
    def profile(self, query_name: str):
        """Context manager for profiling a query"""
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self.queries.append({
                "name": query_name,
                "duration": duration,
                "timestamp": start
            })
            self.query_counts[query_name] += 1
            self.query_times[query_name].append(duration)

            # Log slow queries (>100ms)
            if duration > 0.1:
                logger.warning(f"SLOW QUERY: {query_name} took {duration:.3f}s")

    def get_stats(self) -> Dict[str, Any]:
        """Get profiling statistics"""
        stats = {
            "total_queries": len(self.queries),
            "unique_queries": len(self.query_counts),
            "query_breakdown": {},
            "slowest_queries": []
        }

        # Query breakdown by name
        for name, times in self.query_times.items():
            stats["query_breakdown"][name] = {
                "count": self.query_counts[name],
                "total_time": sum(times),
                "avg_time": sum(times) / len(times),
                "min_time": min(times),
                "max_time": max(times)
            }

        # Top 10 slowest queries
        all_with_names = [(q["name"], q["duration"]) for q in self.queries]
        slowest = sorted(all_with_names, key=lambda x: x[1], reverse=True)[:10]
        stats["slowest_queries"] = [
            {"name": name, "duration": duration}
            for name, duration in slowest
        ]

        return stats

    def print_report(self):
        """Print formatted profiling report"""
        stats = self.get_stats()

        print("\n" + "=" * 80)
        print("QUERY PROFILING REPORT")
        print("=" * 80)

        print(f"\n[Summary]")
        print(f"  Total queries: {stats['total_queries']}")
        print(f"  Unique query types: {stats['unique_queries']}")

        print(f"\n[Query Breakdown]")
        for name, info in sorted(
            stats['query_breakdown'].items(),
            key=lambda x: x[1]['total_time'],
            reverse=True
        ):
            print(f"\n  {name}:")
            print(f"    Count: {info['count']}")
            print(f"    Total time: {info['total_time']:.3f}s")
            print(f"    Avg time: {info['avg_time']:.3f}s")
            print(f"    Min/Max: {info['min_time']:.3f}s / {info['max_time']:.3f}s")

        print(f"\n[Top 10 Slowest Queries]")
        for i, query in enumerate(stats['slowest_queries'], 1):
            print(f"  {i}. {query['name']}: {query['duration']:.3f}s")

        print("\n" + "=" * 80)

    def save_report(self, filename: str = "query_profile.json"):
        """Save profiling report to JSON"""
        stats = self.get_stats()
        stats["all_queries"] = self.queries

        with open(filename, "w") as f:
            json.dump(stats, f, indent=2)

        print(f"\n[Save] Report saved to: {filename}")

    def reset(self):
        """Reset profiling data"""
        self.queries.clear()
        self.query_counts.clear()
        self.query_times.clear()


# Global profiler instance
_profiler = None

def get_profiler() -> QueryProfiler:
    """Get global profiler instance"""
    global _profiler
    if _profiler is None:
        _profiler = QueryProfiler()
    return _profiler


def profile_query(name: str):
    """Decorator for profiling query functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            profiler = get_profiler()
            with profiler.profile(name):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# Example usage:
"""
from query_profiler import get_profiler

profiler = get_profiler()

# In behavior_engine.py:
with profiler.profile("fetch_recent_messages"):
    messages = db.query(Message).filter(...).all()

# At the end:
profiler.print_report()
profiler.save_report()
"""
