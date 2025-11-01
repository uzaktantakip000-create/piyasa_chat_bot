"""
Text deduplication utilities for the behavior engine.

This module provides text normalization for duplicate detection.
"""

import re


def normalize_text(s: str) -> str:
    """
    Normalize text for duplicate detection.

    Normalization steps:
    1. Convert to lowercase
    2. Strip whitespace
    3. Collapse multiple spaces to single space
    4. Remove emojis and punctuation (keep Turkish characters)
    5. Truncate to 400 characters

    Args:
        s: Input text to normalize

    Returns:
        Normalized text string (max 400 chars)

    Examples:
        >>> normalize_text("  BIST  yükseldi!!! 🚀  ")
        "bist yükseldi"

        >>> normalize_text("Çok güzel   bir    gün...")
        "çok güzel bir gün"
    """
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)          # Collapse multiple spaces
    s = re.sub(r"[^\w\sçğıöşü]", "", s) # Remove emojis/punctuation (keep Turkish chars)
    return s[:400]  # Short excerpt sufficient for comparison
