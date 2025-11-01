"""
Persona and emotion management module for the behavior engine.

This module handles persona refresh logic, emotion-driven reaction planning,
and persona note composition for LLM prompts.
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from system_prompt import summarize_persona

UTC = timezone.utc


@dataclass
class ReactionPlan:
    """
    Emotion-driven reaction plan for message generation.

    Contains instructions for LLM on how to react to market news/triggers,
    incorporating bot's emotion profile (tone, empathy, energy).
    """
    instructions: str
    signature_phrase: Optional[str] = None
    anecdote: Optional[str] = None
    emoji: Optional[str] = None


def _choose_text_item(values: Optional[Sequence[Any]]) -> Optional[str]:
    """
    Randomly select a text item from a sequence.

    Args:
        values: Sequence of values (strings)

    Returns:
        Randomly chosen string, or None if empty/invalid
    """
    if not values:
        return None
    cleaned = [str(v).strip() for v in values if isinstance(v, str) and str(v).strip()]
    if not cleaned:
        return None
    return random.choice(cleaned)


def synthesize_reaction_plan(
    *, emotion_profile: Optional[Dict[str, Any]], market_trigger: str
) -> ReactionPlan:
    """
    Synthesize reaction instructions based on emotion profile and market trigger.

    Builds a ReactionPlan with:
    - Tone/empathy/energy directives
    - Signature phrase (if available)
    - Personal anecdote (if available)
    - Signature emoji (if available)

    Args:
        emotion_profile: Bot's emotion profile dict (tone, empathy, energy, signature_phrases, anecdotes, signature_emoji)
        market_trigger: Market news/trigger text to react to

    Returns:
        ReactionPlan with instructions for LLM
    """
    if not market_trigger:
        return ReactionPlan(instructions="")

    profile = emotion_profile or {}
    tone = profile.get("tone")
    empathy = profile.get("empathy")
    energy = profile.get("energy")
    emoji = (profile.get("signature_emoji") or "").strip() or None
    signature_phrase = _choose_text_item(profile.get("signature_phrases"))
    anecdote = _choose_text_item(profile.get("anecdotes"))

    directives: List[str] = [
        "Haberi kısaca yankıla ve okuyucunun duygusunu paylaş.",
        "Panikten kaçın, sakinleştirici bir ton tuttur.",
    ]

    if empathy:
        directives.append(f"Empati seviyesi: {empathy}.")
    if tone:
        directives.append(f"Genel ton: {tone}.")
    if energy:
        directives.append(f"Tempo ipucu: {energy}.")
    if signature_phrase:
        directives.append(f"Uygun bir cümlede şu imza ifadeyi doğal biçimde kullan: \"{signature_phrase}\".")
    if anecdote:
        directives.append(f"Yer uygunsa kısa bir kişisel not paylaş: \"{anecdote}\".")
    if emoji:
        directives.append(f"Duyguyu pekiştirmek için {emoji} emojisini aşırıya kaçmadan ekleyebilirsin.")

    instructions = " ".join(directives)
    return ReactionPlan(
        instructions=instructions,
        signature_phrase=signature_phrase,
        anecdote=anecdote,
        emoji=emoji,
    )


def derive_tempo_multiplier(
    emotion_profile: Optional[Dict[str, Any]], plan: ReactionPlan
) -> float:
    """
    Derive typing speed multiplier based on emotion profile and reaction plan.

    Analyzes energy/tone keywords to adjust typing simulation speed:
    - High energy (yüksek, canlı, hızlı) → 0.85x (faster typing)
    - Low energy (sakin, yavaş, dingin) → 1.15x (slower typing)
    - Default → 1.0x

    Args:
        emotion_profile: Bot's emotion profile
        plan: Reaction plan with instructions

    Returns:
        Multiplier for typing simulation (0.85 = fast, 1.15 = slow)
    """
    profile = emotion_profile or {}
    energy_bits = " ".join(
        filter(
            None,
            [
                str(profile.get("energy") or ""),
                str(profile.get("tone") or ""),
                plan.instructions,
            ],
        )
    ).lower()

    if any(keyword in energy_bits for keyword in ["yüksek", "canlı", "enerjik", "hızlı"]):
        return 0.85
    if any(keyword in energy_bits for keyword in ["sakin", "yumuşak", "yavaş", "dingin"]):
        return 1.15
    return 1.0


def compose_persona_refresh_note(
    persona_profile: Dict[str, Any],
    persona_hint: str,
    emotion_profile: Dict[str, Any],
) -> str:
    """
    Compose persona refresh note for LLM prompt.

    Combines:
    - Summarized persona profile
    - Persona hint (freeform description)
    - Top 2 signature phrases from emotion profile

    Args:
        persona_profile: Bot's persona profile dict
        persona_hint: Freeform persona description
        emotion_profile: Bot's emotion profile dict

    Returns:
        Pipe-separated string of persona notes
    """
    parts: List[str] = []
    summary = summarize_persona(persona_profile)
    if summary and summary != "—":
        parts.append(summary)

    hint = (persona_hint or "").strip()
    if hint:
        parts.append(f"Tarz ipucu: {hint}")

    phrases = emotion_profile.get("signature_phrases") if isinstance(emotion_profile, dict) else None
    if isinstance(phrases, list) and phrases:
        parts.append("İmza ifadeler: " + ", ".join(map(str, phrases[:2])))

    return " | ".join(parts)


def _normalize_refresh_state(state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize persona refresh state to valid dict.

    Ensures:
    - messages_since is an integer >= 0
    - last is a datetime (defaults to datetime.min)

    Args:
        state: Refresh state dict (may be None or malformed)

    Returns:
        Normalized state dict
    """
    data = dict(state or {})
    messages_since = data.get("messages_since", 0)
    try:
        messages_since = int(messages_since)
    except Exception:
        messages_since = 0

    last = data.get("last")
    if not isinstance(last, datetime):
        last = datetime.min.replace(tzinfo=UTC)

    return {"messages_since": max(0, messages_since), "last": last}


def should_refresh_persona(
    state: Optional[Dict[str, Any]],
    *,
    refresh_interval: int,
    refresh_minutes: int,
    now: Optional[datetime] = None,
) -> tuple[bool, Dict[str, Any]]:
    """
    Determine if persona should be refreshed in next message.

    Refresh triggers:
    1. Message count threshold reached (messages_since >= refresh_interval)
    2. Time threshold reached (minutes since last refresh >= refresh_minutes)

    Args:
        state: Current refresh state dict
        refresh_interval: Number of messages between refreshes
        refresh_minutes: Number of minutes between refreshes
        now: Current time (default: now_utc())

    Returns:
        Tuple of (should_refresh: bool, normalized_state: dict)
    """
    normalized = _normalize_refresh_state(state)
    now = now or now_utc()

    interval = max(1, int(refresh_interval or 0))
    minutes = max(1, int(refresh_minutes or 0))

    should_refresh = normalized["messages_since"] >= interval
    if not should_refresh:
        if (now - normalized["last"]) > timedelta(minutes=minutes):
            should_refresh = True

    return should_refresh, normalized


def update_persona_refresh_state(
    state: Dict[str, Any],
    *,
    triggered: bool,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Update persona refresh state after message generation.

    If triggered (refresh happened):
    - Reset messages_since to 0
    - Update last refresh time to now

    If not triggered:
    - Increment messages_since by 1

    Args:
        state: Current refresh state
        triggered: Whether persona refresh was triggered in this message
        now: Current time (default: now_utc())

    Returns:
        Updated state dict
    """
    normalized = _normalize_refresh_state(state)
    now = now or now_utc()

    if triggered:
        normalized["messages_since"] = 0
        normalized["last"] = now
    else:
        normalized["messages_since"] += 1

    return normalized


def now_utc() -> datetime:
    """
    Get current UTC datetime.

    Returns:
        Current datetime with UTC timezone
    """
    return datetime.now(UTC)
