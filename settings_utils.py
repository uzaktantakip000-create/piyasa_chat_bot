"""Helper utilities for settings normalization."""
from __future__ import annotations

import math
from typing import Any, Dict

DEFAULT_MESSAGE_LENGTH_PROFILE: Dict[str, float] = {
    "short": 0.55,
    "medium": 0.35,
    "long": 0.10,
}


def _coerce_positive_number(value: Any) -> float | None:
    """Return a non-negative float if possible, otherwise None."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return max(number, 0.0)


def normalize_message_length_profile(raw: Any) -> Dict[str, float]:
    """Ensure the message length profile sums to 1.0 and is well-formed."""
    if not isinstance(raw, dict):
        values = DEFAULT_MESSAGE_LENGTH_PROFILE.copy()
    else:
        values = {}
        for key, default in DEFAULT_MESSAGE_LENGTH_PROFILE.items():
            coerced = _coerce_positive_number(raw.get(key))
            if coerced is None:
                values[key] = default
            else:
                values[key] = coerced

    total = sum(values.values())
    if total <= 0:
        values = DEFAULT_MESSAGE_LENGTH_PROFILE.copy()
        total = sum(values.values())

    normalized = {key: values[key] / total for key in DEFAULT_MESSAGE_LENGTH_PROFILE}

    # Adjust the last key with any floating point residue so the total is exactly 1.0
    residue = 1.0 - sum(normalized.values())
    last_key = next(reversed(DEFAULT_MESSAGE_LENGTH_PROFILE))
    normalized[last_key] = max(0.0, normalized[last_key] + residue)

    return normalized


def unwrap_setting_value(value: Any) -> Any:
    """
    Unwrap legacy ``{"value": ...}`` payloads stored in the database.

    Also parses JSON strings to dicts/lists if possible.
    """
    import json

    # First, try to parse JSON strings
    if isinstance(value, str):
        # Try JSON parsing
        if value.strip().startswith('{') or value.strip().startswith('['):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                pass  # Not valid JSON, keep as string

    # Then unwrap legacy {"value": ...} wrapper
    seen = set()
    current = value
    while isinstance(current, dict) and "value" in current and len(current) == 1:
        # Protect against pathological self-referential dicts
        obj_id = id(current)
        if obj_id in seen:
            break
        seen.add(obj_id)
        current = current["value"]
    return current


__all__ = [
    "DEFAULT_MESSAGE_LENGTH_PROFILE",
    "normalize_message_length_profile",
    "unwrap_setting_value",
]
