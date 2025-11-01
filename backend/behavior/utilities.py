"""
General utility functions for the behavior engine.

This module provides simple math and string utilities used throughout the engine.
"""

from typing import Any, Optional


def safe_float(value: Any, default: float) -> float:
    """
    Safely convert value to float with fallback default.

    Args:
        value: Value to convert
        default: Default float to return if conversion fails

    Returns:
        Float value or default

    Examples:
        >>> safe_float("3.14", 0.0)
        3.14
        >>> safe_float("invalid", 1.0)
        1.0
        >>> safe_float(None, 0.0)
        0.0
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(v: float, lo: float, hi: float) -> float:
    """
    Clamp value to [lo, hi] range.

    Args:
        v: Value to clamp
        lo: Minimum value
        hi: Maximum value

    Returns:
        Clamped value

    Examples:
        >>> clamp(5.0, 0.0, 10.0)
        5.0
        >>> clamp(-5.0, 0.0, 10.0)
        0.0
        >>> clamp(15.0, 0.0, 10.0)
        10.0
    """
    return max(lo, min(hi, v))


def shorten(s: Optional[str], max_chars: int) -> str:
    """
    Shorten string to max_chars with ellipsis if needed.

    Args:
        s: Input string (or None)
        max_chars: Maximum characters (including ellipsis)

    Returns:
        Shortened string with "…" suffix if truncated

    Examples:
        >>> shorten("Hello world", 20)
        "Hello world"
        >>> shorten("This is a very long message", 10)
        "This is a…"
        >>> shorten(None, 10)
        ""
    """
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"
