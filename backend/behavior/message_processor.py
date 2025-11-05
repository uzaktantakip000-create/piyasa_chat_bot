"""
Message processing utilities for the behavior engine.

This module provides message history transcript building, speaker resolution,
and contextual example generation for LLM prompts.
"""

import re
from typing import Any, List, Optional, Sequence

from backend.behavior.utilities import shorten

# Regex for anonymizing mentions in example text
_ANON_HANDLE_RE = re.compile(r"@\w+")


def resolve_message_speaker(message: Any) -> str:
    """
    Best-effort speaker label extraction from message object.

    Attempts to extract speaker name from:
    1. Bot username/name/id
    2. Sender metadata (sender_name, author_name, display_name)
    3. Message meta dict
    4. Chat title

    Args:
        message: Message object with potential speaker attributes

    Returns:
        Speaker label string (e.g., "username", "Bot#123", "Kullanıcı")

    Examples:
        >>> msg = Message(bot=Bot(username="trader_bot"))
        >>> resolve_message_speaker(msg)
        "trader_bot"

        >>> msg = Message(sender_name="Ali")
        >>> resolve_message_speaker(msg)
        "Ali"
    """
    # SESSION 41: Try to access bot relationship, but catch DetachedInstanceError
    try:
        bot = getattr(message, "bot", None)
        if bot is not None:
            username = getattr(bot, "username", None)
            if isinstance(username, str) and username.strip():
                return username.lstrip("@")
            name = getattr(bot, "name", None)
            if isinstance(name, str) and name.strip():
                return name.strip()
            bot_id = getattr(message, "bot_id", None)
            if bot_id is not None:
                return f"Bot#{bot_id}"
            return "Bot"
    except Exception:
        # Detached or lazy-load error - fallback to bot_id
        bot_id = getattr(message, "bot_id", None)
        if bot_id is not None:
            return f"Bot#{bot_id}"

    # Human participants - check common name attributes
    for attr in ("sender_name", "author_name", "display_name"):
        candidate = getattr(message, attr, None)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    # Check meta dict for name fields
    meta = getattr(message, "meta", None)
    if isinstance(meta, dict):
        for key in ("sender_name", "username", "author", "display_name"):
            candidate = meta.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

    # Fallback: chat title if available
    try:
        chat = getattr(message, "chat", None)
        if chat is not None:
            title = getattr(chat, "title", None)
            if isinstance(title, str) and title.strip():
                return title.strip()
    except Exception:
        # Detached or lazy-load error - continue to fallback
        pass

    return "Kullanıcı"


def build_history_transcript(messages: Sequence[Any]) -> str:
    """
    Create multi-line dialog transcript from chronological messages.

    Formats messages as:
    ```
    [Speaker1]: message text
    [Speaker2]: message text
    ...
    ```

    Args:
        messages: Chronological sequence of message objects

    Returns:
        Newline-separated transcript string

    Examples:
        >>> msgs = [Message(text="Merhaba", bot=Bot(username="ali"))]
        >>> build_history_transcript(msgs)
        "[ali]: Merhaba"
    """
    lines: List[str] = []
    for msg in messages:
        if msg is None:
            continue
        text = getattr(msg, "text", "") or ""
        text = re.sub(r"\s+", " ", str(text)).strip()
        if not text:
            text = "(boş)"
        snippet = shorten(text, 180)
        speaker = resolve_message_speaker(msg)
        lines.append(f"[{speaker}]: {snippet}")

    return "\n".join(lines)


def anonymize_example_text(text: str) -> str:
    """
    Anonymize message text for use in contextual examples.

    Replaces @mentions with generic "@kullanici" to prevent persona leakage.
    Also normalizes whitespace and truncates to 140 characters.

    Args:
        text: Message text to anonymize

    Returns:
        Anonymized text string

    Examples:
        >>> anonymize_example_text("Hey @john, how are you?")
        "Hey @kullanici, how are you?"

        >>> anonymize_example_text("Very long message " * 20)
        "Very long message Very long message Very long message..."  # Truncated to 140 chars
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    cleaned = _ANON_HANDLE_RE.sub("@kullanici", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return shorten(cleaned, 140)


def build_contextual_examples(
    messages: Sequence[Any], *, bot_id: int, max_pairs: int = 3
) -> str:
    """
    Build contextual turn-taking examples for LLM prompt.

    Extracts user-bot message pairs to demonstrate bot's conversational style.
    Examples are anonymized to prevent persona leakage.

    Format:
    ```
    - Kullanıcı: "user message" -> Bot: "bot response"
    - Kullanıcı: "user message" -> Bot: "bot response"
    ```

    Args:
        messages: Chronological message sequence
        bot_id: Bot ID to extract examples for
        max_pairs: Maximum number of user-bot pairs to extract (default: 3)

    Returns:
        Newline-separated examples string

    Examples:
        >>> msgs = [
        ...     Message(text="Merhaba", bot_id=None),
        ...     Message(text="Selam!", bot_id=1)
        ... ]
        >>> build_contextual_examples(msgs, bot_id=1, max_pairs=3)
        "- Kullanıcı: \\"Merhaba\\" -> Bot: \\"Selam!\\""
    """
    pairs: List[str] = []
    pending_user: Optional[str] = None

    for msg in messages:
        if msg is None:
            continue

        msg_text = anonymize_example_text(getattr(msg, "text", ""))
        if not msg_text:
            continue

        if getattr(msg, "bot_id", None) == bot_id:
            if pending_user:
                pairs.append(f"- Kullanıcı: \"{pending_user}\" -> Bot: \"{msg_text}\"")
                if len(pairs) >= max_pairs:
                    break
            pending_user = None
        else:
            pending_user = msg_text

    return "\n".join(pairs)
