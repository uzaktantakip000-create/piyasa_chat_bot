"""
Behavior Engine Modules

Modularized behavior engine for improved maintainability and testability.

Architecture:
- engine.py: Main BehaviorEngine orchestrator
- bot_selector.py: Bot selection logic (pick_bot)
- message_generator.py: LLM prompt building and message generation
- topic_manager.py: Topic scoring and selection
- persona_manager.py: Persona refresh and emotion handling
- stance_manager.py: Stance consistency and cooldown management
- reply_handler.py: Reply target selection and @mentions
- micro_behaviors.py: Ellipsis, emoji placement, deduplication

Status: Foundation created (Session 9)
Next: Extract functions from behavior_engine.py (Session 10+)
"""

__version__ = "0.1.0"
__status__ = "Extraction in Progress (Session 10)"

# Extracted modules
from backend.behavior.topic_manager import (
    TOPIC_KEYWORDS,
    choose_topic_from_messages,
    score_topics_from_messages,
)
from backend.behavior.persona_manager import (
    ReactionPlan,
    compose_persona_refresh_note,
    derive_tempo_multiplier,
    now_utc,
    should_refresh_persona,
    synthesize_reaction_plan,
    update_persona_refresh_state,
)
from backend.behavior.bot_selector import (
    is_prime_hours,
    is_within_active_hours,
    parse_ranges,
)
from backend.behavior.reply_handler import (
    detect_sentiment,
    detect_topics,
    extract_symbols,
)
from backend.behavior.deduplication import (
    normalize_text,
)
from backend.behavior.message_utils import (
    choose_message_length_category,
    compose_length_hint,
)
from backend.behavior.utilities import (
    clamp,
    safe_float,
    shorten,
)
from backend.behavior.message_processor import (
    anonymize_example_text,
    build_contextual_examples,
    build_history_transcript,
    resolve_message_speaker,
)
from backend.behavior.micro_behaviors import (
    generate_time_context,
)

__all__ = [
    "TOPIC_KEYWORDS",
    "choose_topic_from_messages",
    "score_topics_from_messages",
    "ReactionPlan",
    "compose_persona_refresh_note",
    "derive_tempo_multiplier",
    "now_utc",
    "should_refresh_persona",
    "synthesize_reaction_plan",
    "update_persona_refresh_state",
    "is_prime_hours",
    "is_within_active_hours",
    "parse_ranges",
    "detect_sentiment",
    "detect_topics",
    "extract_symbols",
    "normalize_text",
    "choose_message_length_category",
    "compose_length_hint",
    "generate_time_context",
    "clamp",
    "safe_float",
    "shorten",
    "anonymize_example_text",
    "build_contextual_examples",
    "build_history_transcript",
    "resolve_message_speaker",
]
