"""
Bot selection utility functions for the behavior engine.

This module provides time-range parsing and active hours checking logic
used to determine when bots should be active in conversations.
"""

from datetime import datetime
from typing import List, Optional


def parse_ranges(ranges: List[str]) -> List[tuple]:
    """
    Parse time range strings into minute-of-day tuples.

    Converts "HH:MM-HH:MM" strings to (start_minutes, end_minutes) tuples.
    Minutes are calculated from midnight (00:00).

    Examples:
        >>> parse_ranges(["09:30-12:00", "14:00-18:00"])
        [(570, 720), (840, 1080)]

    Args:
        ranges: List of time range strings in "HH:MM-HH:MM" format

    Returns:
        List of (start_minutes, end_minutes) tuples
    """
    out = []
    for r in ranges or []:
        try:
            a, b = r.split("-")
            sh, sm = [int(x) for x in a.split(":")]
            eh, em = [int(x) for x in b.split(":")]
            out.append((sh * 60 + sm, eh * 60 + em))
        except Exception:
            continue
    return out


def _time_matches_ranges(ranges: List[str], minute_of_day: int) -> bool:
    """
    Check if a minute-of-day falls within any time range.

    Handles ranges that cross midnight (e.g., "22:00-02:00").

    Args:
        ranges: List of time range strings
        minute_of_day: Minutes since midnight (0-1439)

    Returns:
        True if minute_of_day is within any range
    """
    for (s, e) in parse_ranges(ranges):
        if s <= e:
            # Normal range (e.g., 09:00-18:00)
            if s <= minute_of_day <= e:
                return True
        else:
            # Midnight-crossing range (e.g., 22:00-02:00)
            if minute_of_day >= s or minute_of_day <= e:
                return True
    return False


def is_prime_hours(ranges: List[str]) -> bool:
    """
    Check if current time is within prime hours (market hours).

    Prime hours are typically high-activity periods (e.g., market trading hours).
    Used for boosting message generation rate during active periods.

    Args:
        ranges: List of prime hour time ranges (e.g., ["09:30-12:00", "14:00-18:00"])

    Returns:
        True if current local time is within prime hours, False otherwise
    """
    local = datetime.now()  # Local system time
    hm = local.hour * 60 + local.minute
    if not ranges:
        return False
    return _time_matches_ranges(ranges, hm)


def is_within_active_hours(ranges: Optional[List[str]], *, moment: Optional[datetime] = None) -> bool:
    """
    Check if a bot should be active based on active_hours configuration.

    Bots can be configured with active_hours (time ranges when they participate).
    If no ranges provided, bot is always active.

    Examples:
        >>> is_within_active_hours(["09:00-18:00"])  # During business hours
        True  # (if current time is 14:30)

        >>> is_within_active_hours(None)  # No restrictions
        True  # (always active)

    Args:
        ranges: List of active hour time ranges, or None for always active
        moment: Specific datetime to check (default: current local time)

    Returns:
        True if bot should be active at the given moment
    """
    if not ranges:
        return True  # No restrictions = always active

    local = moment or datetime.now()
    hm = local.hour * 60 + local.minute
    return _time_matches_ranges(list(ranges), hm)
