"""
Message generation utility functions for the behavior engine.

This module provides message length sampling and hint composition logic.
"""

import random
from typing import Any, Dict, List, Optional

from settings_utils import DEFAULT_MESSAGE_LENGTH_PROFILE

# Message length hint templates (Turkish)
_MESSAGE_LENGTH_HINTS = {
    "short": "bu tur: kısa tut (1-2 cümle)",
    "medium": "bu tur: orta uzunluk (2-3 cümle)",
    "long": "bu tur: biraz daha detay (3-4 cümle)",
}


def choose_message_length_category(
    profile: Optional[Dict[str, float]], *, rng: Optional[random.Random] = None
) -> str:
    """
    Sample a message length category from a weighted profile.

    Uses weighted random sampling based on category probabilities.
    Categories: "short", "medium", "long"

    Args:
        profile: Message length profile dict with weights (e.g., {"short": 0.5, "medium": 0.3, "long": 0.2})
                If None or invalid, uses DEFAULT_MESSAGE_LENGTH_PROFILE
        rng: Random number generator (default: global random)

    Returns:
        Selected category string ("short", "medium", or "long")

    Examples:
        >>> profile = {"short": 0.7, "medium": 0.2, "long": 0.1}
        >>> choose_message_length_category(profile)
        "short"  # Most likely (70% probability)
    """
    if not isinstance(profile, dict):
        profile = DEFAULT_MESSAGE_LENGTH_PROFILE

    rng = rng or random
    cutoff = rng.random()

    cumulative = 0.0
    chosen = None
    for key in DEFAULT_MESSAGE_LENGTH_PROFILE:
        weight = float(profile.get(key, 0.0))
        if weight < 0:
            weight = 0.0
        cumulative += weight
        if cutoff <= cumulative:
            chosen = key
            break

    if chosen is None:
        chosen = next(iter(DEFAULT_MESSAGE_LENGTH_PROFILE))

    return chosen


def compose_length_hint(
    *, persona_profile: Optional[Dict[str, Any]], selected_category: str
) -> str:
    """
    Compose length hint for LLM prompt by combining persona style and category.

    Combines:
    1. Bot's persona style length preference (if available)
    2. Sampled category hint (short/medium/long)

    Args:
        persona_profile: Bot's persona profile dict (with "style" → "length")
        selected_category: Sampled category ("short", "medium", "long")

    Returns:
        Pipe-separated length hint string for LLM prompt

    Examples:
        >>> persona = {"style": {"length": "kısa ve öz"}}
        >>> compose_length_hint(persona_profile=persona, selected_category="short")
        "kısa ve öz | bu tur: kısa tut (1-2 cümle)"

        >>> compose_length_hint(persona_profile=None, selected_category="medium")
        "bu tur: orta uzunluk (2-3 cümle)"
    """
    parts: List[str] = []
    if persona_profile:
        style = persona_profile.get("style") or {}
        persona_length = style.get("length")
        if persona_length:
            parts.append(str(persona_length))

    parts.append(_MESSAGE_LENGTH_HINTS.get(selected_category, selected_category))

    return " | ".join(parts)
