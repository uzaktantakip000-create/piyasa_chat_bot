"""
Topic selection and scoring module for the behavior engine.

This module handles topic selection logic, scoring topics based on message history,
and keyword matching for market discussions.
"""

import random
import re
from collections import Counter
from typing import Any, Dict, Optional, Sequence

# Topic keywords for Turkish financial markets
TOPIC_KEYWORDS: Dict[str, set] = {
    "bist": {"bist", "borsa", "hisse", "hisseler", "bist100", "x100"},
    "fx": {"fx", "doviz", "döviz", "kur", "usd", "eur", "parite"},
    "kripto": {"kripto", "crypto", "bitcoin", "btc", "eth", "ethereum", "altcoin", "coin"},
    "makro": {"makro", "enflasyon", "faiz", "ekonomi", "gsyih", "büyüme", "veri"},
}


def _tokenize_messages(messages: Sequence[Any]) -> Counter:
    """
    Tokenize messages into word frequency counter.

    Args:
        messages: Sequence of message objects with 'text' attribute

    Returns:
        Counter of lowercase tokens (words) with frequencies
    """
    tokens: Counter = Counter()
    for msg in messages:
        if msg is None:
            continue
        text = getattr(msg, "text", None)
        if not isinstance(text, str):
            continue
        for raw_token in text.split():
            token = raw_token.strip().lower()
            token = token.strip("#.,;:!?()[]{}\"'`""'")
            if not token:
                continue
            tokens[token] += 1
    return tokens


def score_topics_from_messages(messages: Sequence[Any], topics: Sequence[str]) -> Dict[str, float]:
    """
    Score topics based on keyword matching in message history.

    Uses simple keyword matching with predefined topic keywords (TOPIC_KEYWORDS)
    plus tokens extracted from topic names themselves.

    Args:
        messages: Sequence of message objects to analyze
        topics: List of topic strings to score

    Returns:
        Dictionary mapping topic names to scores (higher = more relevant)
        Only topics with score > 0 are included
    """
    if not topics:
        return {}

    topic_list = [t for t in topics if isinstance(t, str) and t.strip()]
    if not topic_list:
        return {}

    token_counts = _tokenize_messages(messages)
    if not token_counts:
        return {}

    joined_text = " ".join(token_counts.elements())
    scores: Dict[str, float] = {}

    for topic in topic_list:
        topic_key = topic.strip()
        topic_lower = topic_key.lower()
        keywords = set()
        keywords.add(topic_lower)
        keywords.update(TOPIC_KEYWORDS.get(topic_lower, set()))
        keywords.update(k for k in re.split(r"[^\wçğıöşü]+", topic_lower) if k)

        score = 0.0
        for kw in keywords:
            if not kw:
                continue
            score += token_counts.get(kw, 0)
            if kw not in token_counts and kw in joined_text:
                score += 0.2

        if score > 0:
            scores[topic_key] = score

    return scores


def choose_topic_from_messages(
    messages: Sequence[Any],
    topic_candidates: Sequence[str],
    fallback_defaults: Optional[Sequence[str]] = None,
    *,
    rng: Optional[random.Random] = None,
) -> str:
    """
    Choose a topic from candidates based on message history.

    Scores all topic candidates and picks the one with highest score.
    If no scores, picks randomly from candidates. If no candidates,
    picks from fallback defaults.

    Args:
        messages: Recent message history to analyze
        topic_candidates: List of possible topics to choose from
        fallback_defaults: Default topics if no candidates (default: BIST, FX, Kripto, Makro)
        rng: Random number generator (default: global random)

    Returns:
        Selected topic string
    """
    rng = rng or random
    fallback_pool = list(fallback_defaults or ["BIST", "FX", "Kripto", "Makro"])
    candidates = [t for t in topic_candidates or [] if isinstance(t, str) and t.strip()]

    scored = score_topics_from_messages(messages, candidates)
    if scored:
        max_score = max(scored.values())
        best = [topic for topic, score in scored.items() if score == max_score]
        return rng.choice(best)

    if candidates:
        return rng.choice(candidates)

    return rng.choice(fallback_pool)
