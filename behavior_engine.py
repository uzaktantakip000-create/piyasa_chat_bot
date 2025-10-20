from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import random
import re
from dataclasses import dataclass
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Sequence

from sqlalchemy.orm import Session

from database import (
    SessionLocal, Bot, Chat, Message, Setting,
    BotStance, BotHolding, BotMemory,
)
from settings_utils import (
    DEFAULT_MESSAGE_LENGTH_PROFILE,
    normalize_message_length_profile,
    unwrap_setting_value,
)
from llm_client import LLMClient
from system_prompt import (
    generate_user_prompt,
    generate_system_prompt,  # <-- YENİ: Her bot için unique system prompt
    summarize_persona,
    summarize_stances,
)
from telegram_client import TelegramClient
from message_queue import MessageQueue, QueuedMessage, MessagePriority
from news_client import NewsClient, DEFAULT_FEEDS  # <-- HABER TETIKLEYICI
from voice_profiles import VoiceProfileGenerator  # <-- PHASE 2 Week 3 Day 4-5: Voice Profiles

logger = logging.getLogger("behavior")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

UTC = timezone.utc

# Çalışan engine'in referansı (worker.py 'shutdown' çağırabilsin diye)
_ENGINE: Optional["BehaviorEngine"] = None


# ---------------------------
# Yardımcı fonksiyonlar
# ---------------------------
TOPIC_KEYWORDS: Dict[str, set] = {
    "bist": {"bist", "borsa", "hisse", "hisseler", "bist100", "x100"},
    "fx": {"fx", "doviz", "döviz", "kur", "usd", "eur", "parite"},
    "kripto": {"kripto", "crypto", "bitcoin", "btc", "eth", "ethereum", "altcoin", "coin"},
    "makro": {"makro", "enflasyon", "faiz", "ekonomi", "gsyih", "büyüme", "veri"},
}


@dataclass
class ReactionPlan:
    instructions: str
    signature_phrase: Optional[str] = None
    anecdote: Optional[str] = None
    emoji: Optional[str] = None


def _choose_text_item(values: Optional[Sequence[Any]]) -> Optional[str]:
    if not values:
        return None
    cleaned = [str(v).strip() for v in values if isinstance(v, str) and str(v).strip()]
    if not cleaned:
        return None
    return random.choice(cleaned)


def synthesize_reaction_plan(
    *, emotion_profile: Optional[Dict[str, Any]], market_trigger: str
) -> ReactionPlan:
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
    """Return (should_refresh, normalized_state)."""

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
    normalized = _normalize_refresh_state(state)
    now = now or now_utc()

    if triggered:
        normalized["messages_since"] = 0
        normalized["last"] = now
    else:
        normalized["messages_since"] += 1

    return normalized


def now_utc() -> datetime:
    return datetime.now(UTC)


def exp_delay(mean_seconds: float) -> float:
    """Exponential (Poisson process) gecikme üreten yardımcı."""
    if mean_seconds <= 0:
        return 1.0
    return random.expovariate(1.0 / mean_seconds)


def parse_ranges(ranges: List[str]) -> List[tuple]:
    """
    "HH:MM-HH:MM" listesi -> [(start_min, end_min), ...]
    Zamanlar yerel saat varsayımıyla yorumlanır; burada sadece göreli hız için kullanıyoruz.
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


def is_prime_hours(ranges: List[str]) -> bool:
    local = datetime.now()  # sistemin yerel saati (sunucu)
    hm = local.hour * 60 + local.minute
    if not ranges:
        return False
    return _time_matches_ranges(ranges, hm)


def _time_matches_ranges(ranges: List[str], minute_of_day: int) -> bool:
    for (s, e) in parse_ranges(ranges):
        if s <= e:
            if s <= minute_of_day <= e:
                return True
        else:
            # Gece yarısı devreden aralık (örn. 22:00-02:00)
            if minute_of_day >= s or minute_of_day <= e:
                return True
    return False


def is_within_active_hours(ranges: Optional[List[str]], *, moment: Optional[datetime] = None) -> bool:
    """Yerel zamana göre active_hours aralığında mı? Liste boşsa her zaman aktif say."""

    if not ranges:
        return True

    local = moment or datetime.now()
    hm = local.hour * 60 + local.minute
    return _time_matches_ranges(list(ranges), hm)


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def shorten(s: Optional[str], max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"


def _resolve_message_speaker(message: Any) -> str:
    """Best effort speaker label for history transcripts."""

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

    # İnsan katılımcılar için potansiyel alanlar
    for attr in ("sender_name", "author_name", "display_name"):
        candidate = getattr(message, attr, None)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    meta = getattr(message, "meta", None)
    if isinstance(meta, dict):
        for key in ("sender_name", "username", "author", "display_name"):
            candidate = meta.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

    chat = getattr(message, "chat", None)
    if chat is not None:
        title = getattr(chat, "title", None)
        if isinstance(title, str) and title.strip():
            return title.strip()

    return "Kullanıcı"


def build_history_transcript(messages: Sequence[Any]) -> str:
    """Create a multi-line dialog transcript from chronological messages."""

    lines: List[str] = []
    for msg in messages:
        if msg is None:
            continue
        text = getattr(msg, "text", "") or ""
        text = re.sub(r"\s+", " ", str(text)).strip()
        if not text:
            text = "(boş)"
        snippet = shorten(text, 180)
        speaker = _resolve_message_speaker(msg)
        lines.append(f"[{speaker}]: {snippet}")

    return "\n".join(lines)


_ANON_HANDLE_RE = re.compile(r"@\w+")


def _anonymize_example_text(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    cleaned = _ANON_HANDLE_RE.sub("@kullanici", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return shorten(cleaned, 140)


def build_contextual_examples(
    messages: Sequence[Any], *, bot_id: int, max_pairs: int = 3
) -> str:
    pairs: List[str] = []
    pending_user: Optional[str] = None

    for msg in messages:
        if msg is None:
            continue

        msg_text = _anonymize_example_text(getattr(msg, "text", ""))
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


def _tokenize_messages(messages: Sequence[Any]) -> Counter:
    tokens: Counter = Counter()
    for msg in messages:
        if msg is None:
            continue
        text = getattr(msg, "text", None)
        if not isinstance(text, str):
            continue
        for raw_token in text.split():
            token = raw_token.strip().lower()
            token = token.strip("#.,;:!?()[]{}\"'`“”’")
            if not token:
                continue
            tokens[token] += 1
    return tokens


def score_topics_from_messages(messages: Sequence[Any], topics: Sequence[str]) -> Dict[str, float]:
    """Basit anahtar kelime eşleşmesiyle mesajlara göre topic skorla."""

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
    """Mesajlara bakarak topic seç; eşleşme yoksa rastgele fallback kullan."""

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


def generate_time_context() -> str:
    """Generate human-like time-of-day context for more natural conversations."""
    local = datetime.now()
    hour = local.hour

    # Sabah (06:00-09:00)
    if 6 <= hour < 9:
        contexts = [
            "Günaydın, sabah kahvesi içerken",
            "Sabah erken saatler",
            "İşe gitmeden önce hızlıca",
            "Güne başlarken",
        ]
    # Piyasa açılış (09:00-10:30)
    elif 9 <= hour < 11:
        contexts = [
            "Piyasa açılışı sırasında",
            "Sabah ilk saatler",
            "Gün başında",
            "Açılış heyecanıyla",
        ]
    # Öğlen (10:30-13:00)
    elif 11 <= hour < 13:
        contexts = [
            "Öğlen arası molada",
            "Gün ortası",
            "Öğle yemeği öncesi",
        ]
    # Öğleden sonra (13:00-17:00)
    elif 13 <= hour < 17:
        contexts = [
            "Öğleden sonra işlerin arasında",
            "Günün ikinci yarısı",
            "Piyasa kapanışına doğru",
        ]
    # Piyasa kapanış (17:00-19:00)
    elif 17 <= hour < 19:
        contexts = [
            "Piyasa kapandı, evde dinlenirken",
            "İşten yeni çıktım",
            "Akşam yaklaşırken",
            "Günü değerlendirirken",
        ]
    # Akşam (19:00-23:00)
    elif 19 <= hour < 23:
        contexts = [
            "Akşam yemeğinden sonra",
            "Akşam saatleri, rahat rahat",
            "Günü geride bırakırken",
            "Akşam dinlenirken",
        ]
    # Gece (23:00-06:00)
    else:
        contexts = [
            "Gece geç saatler",
            "Herkes uyumuşken ben hâlâ piyasalara bakıyorum",
            "Gece vakti sessizlikte",
        ]

    # Hafta sonu özel durumu
    if local.weekday() >= 5:  # Cumartesi=5, Pazar=6
        return "Hafta sonu keyifle"

    return random.choice(contexts)


def add_conversation_openings(text: str, probability: float = 0.25) -> str:
    """
    Mesajlara doğal konuşma açılışları ekler.

    Args:
        text: Düzenlenecek metin
        probability: Açılış ekleme olasılığı (varsayılan %25)

    Returns:
        Açılış ifadesiyle zenginleştirilmiş metin
    """
    if not text or random.random() > probability:
        return text

    # Türkçe konuşma dilinde yaygın açılışlar
    openings = [
        "Bak şimdi",
        "Şöyle söyleyeyim",
        "Valla dikkatimi çekti",
        "Bence şöyle",
        "Açıkçası",
        "Bakın",
        "Şimdi",
        "Dürüst olmak gerekirse",
        "Yani şey",
        "Nasıl desem",
        "Bakıyorum da",
        "Gördüm de",
        "İzliyorum da",
        "Takip ediyorum",
        "Bir de",
    ]

    opening = random.choice(openings)

    # İlk harfi büyük yap, virgül ekle
    return f"{opening}, {text[0].lower() + text[1:]}"


def add_hesitation_markers(text: str, probability: float = 0.30) -> str:
    """
    Belirsizlik ve tereddüt belirteçleri ekler (en kritik insanlaştırma özelliği).

    Args:
        text: Düzenlenecek metin
        probability: Belirsizlik ekleme olasılığı (varsayılan %30)

    Returns:
        Belirsizlik ifadeleriyle zenginleştirilmiş metin
    """
    if not text or random.random() > probability:
        return text

    # Türkçe belirsizlik ifadeleri
    hesitation_phrases = [
        "sanki",
        "gibime geliyor",
        "gibi",
        "emin değilim ama",
        "belki de",
        "olabilir",
        "muhtemelen",
        "galiba",
        "herhalde",
        "sanırım",
        "bence",
        "gibi geldi",
        "gibi düşünüyorum",
    ]

    # Cümleleri ayır
    sentences = re.split(r'([.!?])', text)
    modified = False

    for i, part in enumerate(sentences):
        if part in '.!?':
            continue

        sentence = part.strip()
        if not sentence or len(sentence.split()) < 3:
            continue

        # İlk veya ikinci cümleye ekle
        if i <= 2 and not modified and random.random() < 0.6:
            hesitation = random.choice(hesitation_phrases)
            words = sentence.split()

            # Cümlenin başına veya ortasına ekle
            if random.random() < 0.4 and hesitation in ["sanırım", "bence", "galiba", "muhtemelen"]:
                # Başa ekle
                sentences[i] = f"{hesitation} {sentence}"
            else:
                # Ortaya ekle (ikinci veya üçüncü kelimeden sonra)
                if len(words) >= 3:
                    insert_pos = random.randint(1, min(3, len(words) - 1))
                    words.insert(insert_pos, hesitation)
                    sentences[i] = " ".join(words)
                else:
                    sentences[i] = f"{sentence} {hesitation}"

            modified = True
            break

    return "".join(sentences)


def add_colloquial_shortcuts(text: str, probability: float = 0.18) -> str:
    """
    Günlük konuşma kısaltmaları ekler (Türkçe konuşma diline özgü).

    Args:
        text: Düzenlenecek metin
        probability: Kısaltma ekleme olasılığı (varsayılan %18)

    Returns:
        Kısaltmalarla doğallaştırılmış metin
    """
    if not text or random.random() > probability:
        return text

    # Türkçe konuşma dilindeki yaygın kısaltmalar
    shortcuts = {
        " bir ": " bi' ",
        " bir şey": " bi şey",
        " birşey": " bi şey",
        " değil mi": " değil mi",
        " yok mu": " yok mu",
        " var mı": " var mı",
        " falan": " falan",
        " filan": " filan",
        " işte": " işte",
        " hani": " hani",
    }

    # Sadece birkaç kısaltma uygula (aşırıya kaçmasın)
    modified = False
    attempts = 0
    max_attempts = 2  # En fazla 2 kısaltma

    for full, short in shortcuts.items():
        if attempts >= max_attempts:
            break

        if full in text and random.random() < 0.5:
            text = text.replace(full, short, 1)  # Sadece ilk geçtiği yerde
            modified = True
            attempts += 1

    return text


def apply_natural_imperfections(text: str, probability: float = 0.15) -> str:
    """
    Doğal kusurlar ekler: bazen yazım hataları yapıp düzeltir.

    Args:
        text: Düzenlenecek metin
        probability: Kusur ekleme olasılığı (varsayılan %15)

    Returns:
        Düzenlenmiş metin (kusur varsa düzeltmeyle birlikte)
    """
    if not text or random.random() > probability:
        return text

    # Türkçe'de sık yapılan yazım hataları ve düzeltmeleri
    typo_patterns = [
        # Klavye yakınlığı hataları (yanyana tuşlar)
        ("artık", "artıl"),  # k -> l
        ("değil", "deği"),   # l eksik
        ("çok", "vok"),      # ç -> v (Türkçe Q klavye)
        ("gibi", "gıbi"),    # i -> ı
        ("için", "ıcın"),    # i -> ı
        ("yani", "yanı"),    # i -> ı
        ("oldu", "oldu"),    # tekrar (aslında doğru)
        ("sanki", "sankı"),  # i -> ı
        ("bence", "bense"),  # c -> s
        ("şimdi", "şimdi"),  # tekrar (doğru)
        ("bunlar", "bunalr"), # r ile l yer değiştirme
    ]

    # Metinde uygulanabilecek bir pattern ara
    available_patterns = []
    for correct, typo in typo_patterns:
        if correct in text.lower():
            available_patterns.append((correct, typo))

    if not available_patterns:
        return text

    # Rastgele bir hata seç
    correct, typo = random.choice(available_patterns)

    # Metinde ilk geçtiği yeri bul (case-insensitive)
    words = text.split()
    modified = False

    for i, word in enumerate(words):
        clean_word = word.strip('.,!?;:').lower()
        if clean_word == correct:
            # Orijinal kelimenin punctuation'ını koru
            prefix = ""
            suffix = ""
            for char in word:
                if not char.isalnum() and not char in "çğıöşü":
                    prefix += char
                else:
                    break
            for char in reversed(word):
                if not char.isalnum() and not char in "çğıöşü":
                    suffix = char + suffix
                else:
                    break

            # Hatalı kelimeyi ekle, sonra düzeltme yap
            typo_word = prefix + typo + suffix
            words[i] = typo_word

            # Düzeltme şekilleri
            correction_styles = [
                f"{typo_word} *{word}",  # Markdown düzeltme
                f"{typo_word}, yani {word}",  # Açıklayıcı düzeltme
                f"{typo_word} pardon {word}",  # Özür dileyerek düzeltme
            ]

            words[i] = random.choice(correction_styles)
            modified = True
            break

    if modified:
        return " ".join(words)

    return text


def choose_message_length_category(
    profile: Optional[Dict[str, float]], *, rng: Optional[random.Random] = None
) -> str:
    """Sample a message length category from a normalized profile."""

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


_MESSAGE_LENGTH_HINTS = {
    "short": "bu tur: kısa tut (1-2 cümle)",
    "medium": "bu tur: orta uzunluk (2-3 cümle)",
    "long": "bu tur: biraz daha detay (3-4 cümle)",
}


def compose_length_hint(
    *, persona_profile: Optional[Dict[str, Any]], selected_category: str
) -> str:
    """Combine persona style length with the sampled category hint."""

    parts: List[str] = []
    if persona_profile:
        style = persona_profile.get("style") or {}
        persona_length = style.get("length")
        if persona_length:
            parts.append(str(persona_length))

    parts.append(_MESSAGE_LENGTH_HINTS.get(selected_category, selected_category))

    return " | ".join(parts)


def normalize_text(s: str) -> str:
    """Tekrar kontrolü için basit normalizasyon."""
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)          # sık boşlukları tek boşluğa indir
    s = re.sub(r"[^\w\sçğıöşü]", "", s) # emojiler/işaretler hariç sadeleştir
    return s[:400]  # kısa kesit yeterli


def fetch_bot_memories(
    db: Session,
    bot_id: int,
    *,
    limit: int = 10,
    memory_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Bot'un kişisel hafızalarını çeker ve relevance_score'a göre sıralar.

    Args:
        db: Database session
        bot_id: Bot ID
        limit: Maksimum hafıza sayısı (varsayılan 10)
        memory_types: Filtrelenecek hafıza tipleri (None ise hepsi)

    Returns:
        Hafıza listesi [{"type": ..., "content": ..., "usage_count": ...}, ...]
    """
    query = db.query(BotMemory).filter(BotMemory.bot_id == bot_id)

    if memory_types:
        query = query.filter(BotMemory.memory_type.in_(memory_types))

    # Relevance score'a göre sırala, en alakalılar önce
    memories = (
        query
        .order_by(BotMemory.relevance_score.desc(), BotMemory.last_used_at.desc())
        .limit(limit)
        .all()
    )

    result = []
    for m in memories:
        result.append({
            "id": m.id,
            "type": m.memory_type,
            "content": m.content,
            "relevance": m.relevance_score,
            "usage_count": m.usage_count,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    return result


def update_memory_usage(db: Session, memory_id: int) -> None:
    """
    Hafıza kullanıldığında usage_count ve last_used_at güncellenir.

    Args:
        db: Database session
        memory_id: Hafıza ID
    """
    memory = db.query(BotMemory).filter(BotMemory.id == memory_id).first()
    if memory:
        memory.usage_count += 1
        memory.last_used_at = now_utc()
        db.add(memory)
        db.commit()


def format_memories_for_prompt(memories: List[Dict[str, Any]]) -> str:
    """
    Hafızaları LLM prompt'u için formatlı string'e dönüştürür.

    Args:
        memories: Hafıza listesi

    Returns:
        Formatlanmış string (örn: "Kişisel: İstanbul'da yaşıyorum | Geçmiş: 2023'te kazandım")
    """
    if not memories:
        return ""

    # Tip bazında gruplama
    grouped: Dict[str, List[str]] = {}
    for m in memories:
        mtype = m.get("type", "other")
        content = (m.get("content") or "").strip()
        if content:
            if mtype not in grouped:
                grouped[mtype] = []
            grouped[mtype].append(content)

    # Türkçe tip isimleri
    type_names = {
        "personal_fact": "Kişisel",
        "past_event": "Geçmiş",
        "relationship": "İlişki",
        "preference": "Tercih",
        "routine": "Rutin",
    }

    parts: List[str] = []
    for mtype, contents in grouped.items():
        type_label = type_names.get(mtype, mtype.capitalize())
        # Her tipten en fazla 3 hafıza göster
        sample = contents[:3]
        parts.append(f"{type_label}: {'; '.join(sample)}")

    return " | ".join(parts)


def extract_message_metadata(text: str, topic: str) -> Dict[str, Any]:
    """
    Mesaj metninden metadata çıkarır (konu, semboller, ton).

    Args:
        text: Mesaj metni
        topic: Mesajın konusu

    Returns:
        Metadata dictionary
    """
    metadata: Dict[str, Any] = {
        "topic": topic,
        "symbols": [],
        "keywords": [],
        "sentiment": "neutral",
    }

    # Sembol tespiti (hisse, kripto, parite)
    text_upper = text.upper()

    # BIST hisse kodları (3-5 karakter)
    bist_pattern = re.findall(r'\b[A-Z]{3,5}\b', text_upper)
    for symbol in bist_pattern:
        if symbol in ["BIST", "USD", "EUR", "TRY", "BTC", "ETH"]:
            continue  # Genel terimler
        if len(symbol) >= 3:
            metadata["symbols"].append(symbol)

    # Kripto sembolleri
    crypto_keywords = ["BTC", "ETH", "BITCOIN", "ETHEREUM", "USDT", "XRP", "SOL"]
    for kw in crypto_keywords:
        if kw in text_upper:
            metadata["symbols"].append(kw)

    # Parite sembolleri
    fx_keywords = ["USDTRY", "EURTRY", "EURUSD", "GBPUSD", "XAUUSD"]
    for kw in fx_keywords:
        if kw in text_upper:
            metadata["symbols"].append(kw)

    # Tekilleştir
    metadata["symbols"] = list(set(metadata["symbols"]))[:5]

    # Duygusal ton tespiti (basit anahtar kelime analizi)
    positive_words = ["yükseliş", "artış", "kazanç", "kar", "fırsat", "güzel", "iyi", "pozitif"]
    negative_words = ["düşüş", "azalış", "zarar", "risk", "kötü", "negatif", "tehlike"]

    text_lower = text.lower()
    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)

    if pos_count > neg_count:
        metadata["sentiment"] = "positive"
    elif neg_count > pos_count:
        metadata["sentiment"] = "negative"

    # Önemli kelimeleri çıkar (gelecekte referans için)
    important_keywords = []
    for word in text.split():
        word_clean = word.strip(".,!?;:").lower()
        if len(word_clean) >= 4 and word_clean not in ["ancak", "fakat", "çünkü", "ama", "için"]:
            important_keywords.append(word_clean)

    metadata["keywords"] = important_keywords[:8]

    return metadata


def find_relevant_past_messages(
    db: Session,
    *,
    bot_id: int,
    current_topic: str,
    current_symbols: List[str],
    days_back: int = 7,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Bot'un geçmişte aynı konu/sembollerde yaptığı mesajları bulur.

    Args:
        db: Database session
        bot_id: Bot ID
        current_topic: Mevcut mesaj konusu
        current_symbols: Mevcut mesaj sembolleri
        days_back: Kaç gün geriye bak
        limit: Maksimum sonuç sayısı

    Returns:
        İlgili geçmiş mesajlar listesi
    """
    cutoff_date = now_utc() - timedelta(days=days_back)

    # Bot'un geçmiş mesajlarını çek (metadata'lı olanlar)
    past_messages = (
        db.query(Message)
        .filter(
            Message.bot_id == bot_id,
            Message.created_at >= cutoff_date,
            Message.created_at < now_utc() - timedelta(hours=2),  # Son 2 saat hariç
            Message.msg_metadata.isnot(None)
        )
        .order_by(Message.created_at.desc())
        .limit(50)  # İlk 50'yi kontrol et
        .all()
    )

    # Relevance skorlama
    relevant: List[tuple[float, Message]] = []

    for msg in past_messages:
        if not msg.msg_metadata:
            continue

        score = 0.0
        msg_meta = msg.msg_metadata

        # Aynı konu mu?
        if msg_meta.get("topic") == current_topic:
            score += 3.0

        # Ortak semboller var mı?
        msg_symbols = set(msg_meta.get("symbols", []))
        current_symbols_set = set(current_symbols)
        common_symbols = msg_symbols.intersection(current_symbols_set)
        score += len(common_symbols) * 2.0

        # Zamana göre azalma (yeni mesajlar daha alakalı)
        msg_time = msg.created_at
        if msg_time.tzinfo is None:
            from datetime import timezone
            msg_time = msg_time.replace(tzinfo=timezone.utc)
        age_hours = (now_utc() - msg_time).total_seconds() / 3600
        recency_multiplier = max(0.5, 1.0 - (age_hours / (days_back * 24)))
        score *= recency_multiplier

        if score > 0.5:  # Minimum eşik
            relevant.append((score, msg))

    # En alakalıları sırala ve döndür
    relevant.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, msg in relevant[:limit]:
        msg_time = msg.created_at
        if msg_time.tzinfo is None:
            from datetime import timezone
            msg_time = msg_time.replace(tzinfo=timezone.utc)
        days_ago = (now_utc() - msg_time).days
        hours_ago = int((now_utc() - msg_time).total_seconds() / 3600)

        # Zaman ifadesi
        if days_ago == 0:
            if hours_ago <= 3:
                time_ref = "biraz önce"
            elif hours_ago <= 12:
                time_ref = "bugün"
            else:
                time_ref = "bugün"
        elif days_ago == 1:
            time_ref = "dün"
        elif days_ago == 2:
            time_ref = "önceki gün"
        elif days_ago <= 7:
            time_ref = f"{days_ago} gün önce"
        else:
            time_ref = "geçen hafta"

        results.append({
            "id": msg.id,
            "text": (msg.text or "")[:150],  # İlk 150 karakter
            "topic": msg.msg_metadata.get("topic"),
            "symbols": msg.msg_metadata.get("symbols", []),
            "sentiment": msg.msg_metadata.get("sentiment"),
            "time_reference": time_ref,
            "relevance_score": score,
        })

    return results


def format_past_references_for_prompt(references: List[Dict[str, Any]]) -> str:
    """
    Geçmiş mesaj referanslarını LLM prompt'u için formatlar.

    Args:
        references: Geçmiş mesaj referansları

    Returns:
        Formatlanmış string
    """
    if not references:
        return "—"

    lines: List[str] = []
    for ref in references[:3]:  # En fazla 3 referans
        time_ref = ref.get("time_reference", "önceden")
        text_snippet = ref.get("text", "")[:100]
        symbols = ref.get("symbols", [])

        symbol_str = ""
        if symbols:
            symbol_str = f" ({', '.join(symbols[:2])})"

        lines.append(f"- {time_ref}: \"{text_snippet}\"{symbol_str}")

    return "\n".join(lines)


# ---------------------------
# Ayar okuma
# ---------------------------
def load_settings(db: Session) -> Dict[str, Any]:
    rows = db.query(Setting).all()
    d = {r.key: unwrap_setting_value(r.value) for r in rows}
    # Varsayılanlar (güvenli)
    d.setdefault("max_msgs_per_min", 6)
    d.setdefault("typing_enabled", True)
    d.setdefault("prime_hours_boost", True)
    d.setdefault("prime_hours", ["09:30-12:00", "14:00-18:00"])
    d.setdefault("reply_probability", 0.65)
    d.setdefault("mention_probability", 0.35)
    d.setdefault("short_reaction_probability", 0.12)
    d.setdefault("new_message_probability", 0.35)
    d.setdefault("message_length_profile", DEFAULT_MESSAGE_LENGTH_PROFILE.copy())
    d["message_length_profile"] = normalize_message_length_profile(d.get("message_length_profile"))
    d.setdefault("typing_speed_wpm", {"min": 2.5, "max": 4.5})
    d.setdefault("bot_hourly_msg_limit", {"min": 6, "max": 12})
    d.setdefault("simulation_active", False)
    d.setdefault("scale_factor", 1.0)
    # Tutarlılık koruması
    d.setdefault("consistency_guard_enabled", True)
    # Dedup ve cooldown ayarları
    d.setdefault("dedup_enabled", True)
    d.setdefault("dedup_window_hours", 12)   # son 12 saatte aynı metni engelle
    d.setdefault("dedup_max_attempts", 2)    # yeniden yazdırma denemesi
    d.setdefault("cooldown_filter_enabled", True)  # cooldown aktif konuları topic seçiminden çıkar
    # HABER tetikleyici
    d.setdefault("news_trigger_enabled", True)     # market_trigger aktif mi?
    d.setdefault("news_trigger_probability", 0.75) # %75 olasılıkla tetik kullan

    stored_feeds = d.get("news_feed_urls")
    if not isinstance(stored_feeds, list):
        stored_feeds = []
    stored_feeds = [str(u).strip() for u in stored_feeds if str(u).strip()]

    env_urls = os.getenv("NEWS_RSS_URLS", "")
    env_feeds = [u.strip() for u in env_urls.split(",") if u.strip()]

    merged: List[str] = []
    for candidate in env_feeds + stored_feeds:
        if candidate not in merged:
            merged.append(candidate)

    d["news_feed_urls"] = merged or list(DEFAULT_FEEDS)
    return d


# ---------------------------
# Engine sınıfı
# ---------------------------
class BehaviorEngine:
    """
    - Aktif sohbetler ve botları DB'den seçer
    - Poisson gecikme, reply/@mention, typing simülasyonu, reaksiyon uygular
    - Limitlere saygı duyar (dk başı, saat başı)
    - Redis 'config_updates' kanalını dinleyip ayar cache'ini canlı günceller (opsiyonel)
    - Botun persona/stance/holding bilgilerini prompt'a enjekte eder
    - Tutarlılık koruması: çıktı STANCE ve cooldown kurallarıyla çelişirse yumuşak düzeltme yapar
    - Dedup: son X saatte aynı metni tekrar etmeyi önler
    - Cooldown filtre: cooldown’u bitmemiş konuları topic seçiminden çıkarır
    - Haber tetikleyici: RSS’ten kısa “gündem” cümlesi ekler (market_trigger)
    """

    def __init__(self) -> None:
        self.llm = LLMClient()
        self.tg = TelegramClient()
        self._last_settings: Dict[str, Any] = {}
        self._settings_loaded_at: datetime = datetime.min.replace(tzinfo=UTC)

        # Haber tetikleyici (opsiyonel, bağımlılık yoksa bozulmasın)
        self.news: Optional[NewsClient] = None
        try:
            self.news = NewsClient()
        except Exception as e:
            logger.warning("NewsClient init failed: %s", e)
            self.news = None
        self._active_news_feeds: List[str] = list(self.news.feeds) if self.news else []

        # Redis (opsiyonel) - async subscriber ve priority queue
        self._redis_url: Optional[str] = os.getenv("REDIS_URL") or None
        self._redis = None  # type: ignore
        self._redis_task: Optional[asyncio.Task] = None
        self._redis_sync_client = None  # Sync client for priority queue polling

        # Priority queue Redis client (sync)
        if self._redis_url:
            try:
                import redis
                self._redis_sync_client = redis.Redis.from_url(self._redis_url, decode_responses=True)
                self._redis_sync_client.ping()
                logger.info("Priority queue Redis client initialized")
            except Exception as e:
                logger.warning("Priority queue Redis init failed: %s. User message responses disabled.", e)
                self._redis_sync_client = None

        # Message queue for rate-limited messages
        self.msg_queue = MessageQueue(self._redis_sync_client)
        self._queue_processor_task: Optional[asyncio.Task] = None
        logger.info("Message queue initialized")

        # Persona yenileme takibi (bot bazlı)
        self._persona_refresh: Dict[int, Dict[str, Any]] = {}

        # PHASE 2 Week 3 Day 1-3: Semantic Deduplication
        self.semantic_dedup = None
        try:
            from semantic_dedup import SemanticDeduplicator
            self.semantic_dedup = SemanticDeduplicator(similarity_threshold=0.85)
            logger.info("Semantic deduplicator initialized")
        except Exception as e:
            logger.warning(f"Semantic deduplicator init failed: {e}. Will use exact-match dedup only.")

        # PHASE 2 Week 3 Day 4-5: Voice Profiles & Writing Style
        self.voice_generator = VoiceProfileGenerator()
        self.bot_voices: Dict[int, Any] = {}  # Cache: bot_id -> VoiceProfile
        logger.info("Voice profile generator initialized")

    # ---- Settings cache ----
    def settings(self, db: Session) -> Dict[str, Any]:
        if (now_utc() - self._settings_loaded_at) > timedelta(seconds=15):
            self._last_settings = load_settings(db)
            self._settings_loaded_at = now_utc()
            feeds = self._last_settings.get("news_feed_urls")
            if isinstance(feeds, list):
                self._update_news_feeds(feeds)
        return self._last_settings

    def _invalidate_settings_cache(self):
        # Bir sonraki erişimde yeniden yüklensin
        self._settings_loaded_at = datetime.min.replace(tzinfo=UTC)
        logger.info("Settings cache invalidated via config update.")

    def _update_news_feeds(self, feeds: List[str]) -> None:
        if self.news is None:
            return
        normalized = [str(u).strip() for u in feeds if str(u).strip()]
        if not normalized:
            normalized = list(DEFAULT_FEEDS)
        if normalized == self._active_news_feeds:
            return
        try:
            self.news.set_feeds(normalized)
            self._active_news_feeds = list(self.news.feeds)
            logger.info("News feed list updated (%d entries).", len(self._active_news_feeds))
        except Exception as exc:
            logger.warning("Failed to update news feeds: %s", exc)

    def get_bot_voice(self, bot):
        """
        Bot için voice profile al (cache'den veya yeni oluştur)

        PHASE 2 Week 3 Day 4-5: Voice Profiles
        """
        if bot.id not in self.bot_voices:
            self.bot_voices[bot.id] = self.voice_generator.generate(bot)
            logger.debug(f"Voice profile cached for bot {bot.name} (id={bot.id})")
        return self.bot_voices[bot.id]

    # ---- Redis listener ----
    async def _config_listener(self):
        """
        REDIS_URL varsa 'config_updates' kanalını dinler. Her mesajda settings cache invalid edilir.
        """
        if not self._redis_url:
            return

        try:
            # redis>=4.2 ile birlikte gelen asyncio istemcisini kullan
            from redis import asyncio as aioredis  # type: ignore
        except Exception:
            logger.warning("redis.asyncio bulunamadı; canlı config sync devre dışı.")
            return

        try:
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            pubsub = self._redis.pubsub()
            await pubsub.subscribe("config_updates")
            logger.info("Subscribed to Redis channel: config_updates")

            async for m in pubsub.listen():
                if m is None:
                    await asyncio.sleep(0.1)
                    continue
                if m.get("type") != "message":
                    continue
                try:
                    data = json.loads(m.get("data") or "{}")
                except Exception:
                    data = {}

                # Şimdilik herkes için cache invalid
                self._invalidate_settings_cache()

                if (
                    self.news is not None
                    and isinstance(data.get("keys"), list)
                    and "news_feed_urls" in data.get("keys", [])
                ):
                    try:
                        db = SessionLocal()
                        try:
                            fresh = load_settings(db)
                        finally:
                            db.close()
                        feeds = fresh.get("news_feed_urls")
                        if isinstance(feeds, list):
                            self._update_news_feeds(feeds)
                    except Exception as exc:
                        logger.warning("Failed to refresh news feeds after config update: %s", exc)

                # İleride: data['type'] kontrolü ile hedefli aksiyonlar (örn. belirli chat/bot)
                logger.debug("Config update received: %s", data)
        except asyncio.CancelledError:
            logger.info("Config listener cancelled.")
        except Exception as e:
            logger.warning("Config listener error: %s", e)
        finally:
            # Temizlik
            try:
                if self._redis:
                    await self._redis.close()
            except Exception:
                pass
            self._redis = None

    # ---- Seçimler ----
    def pick_chat(self, db: Session) -> Optional[Chat]:
        chats = db.query(Chat).filter(Chat.is_enabled.is_(True)).all()
        if not chats:
            return None
        return random.choice(chats)

    def pick_bot(
        self,
        db: Session,
        hourly_limit: Dict[str, Any],
        chat: Optional[Chat] = None,
    ) -> Optional[Bot]:
        bots = db.query(Bot).filter(Bot.is_enabled.is_(True)).all()
        if not bots:
            return None

        # Saatlik limit kontrolü
        one_hour_ago = now_utc() - timedelta(hours=1)
        eligible: List[Bot] = []
        for b in bots:
            if not self._bot_is_active_now(b):
                continue
            sent_last_hour = (
                db.query(Message)
                .filter(Message.bot_id == b.id, Message.created_at >= one_hour_ago)
                .count()
            )
            if sent_last_hour < hourly_limit.get("max", 12):
                eligible.append(b)

        if not eligible:
            return None

        last_bot_id: Optional[int] = None
        if chat is not None:
            last_message = (
                db.query(Message)
                .filter(Message.chat_db_id == chat.id)
                .order_by(Message.created_at.desc())
                .first()
            )
            if last_message and last_message.bot_id is not None:
                last_bot_id = last_message.bot_id

        if last_bot_id is not None:
            alternative = [b for b in eligible if b.id != last_bot_id]
            if alternative:
                eligible = alternative

        return random.choice(eligible)

    def _bot_is_active_now(self, bot: Bot) -> bool:
        try:
            ranges = bot.active_hours  # type: ignore[attr-defined]
        except Exception:
            ranges = None
        return is_within_active_hours(ranges if isinstance(ranges, list) else None)

    def _active_cooldown_topics(self, stances: List[Dict[str, Any]]) -> List[str]:
        active: List[str] = []
        now = now_utc()
        for s in stances or []:
            cu = s.get("cooldown_until")
            if not cu:
                continue
            try:
                dt = datetime.fromisoformat(cu)
            except Exception:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            if dt > now:
                t = (s.get("topic") or "").strip()
                if t:
                    active.append(t)
        return active

    # ---- Helper functions for Smart Reply Target Selection ----

    def _detect_topics(self, text: str) -> List[str]:
        """Mesajdaki konuları tespit et (BIST, FX, Kripto, Makro)"""
        topics = []
        text_lower = text.lower()

        # BIST (Turkish stock market)
        if any(w in text_lower for w in ["bist", "borsa", "hisse", "imkb", "endeks"]):
            topics.append("BIST")

        # FX (Foreign exchange)
        if any(w in text_lower for w in ["dolar", "euro", "tl", "kur", "forex", "usd", "eur"]):
            topics.append("FX")

        # Kripto
        if any(w in text_lower for w in ["btc", "eth", "kripto", "bitcoin", "ethereum", "coin", "altcoin"]):
            topics.append("Kripto")

        # Makro
        if any(w in text_lower for w in ["enflasyon", "faiz", "tcmb", "merkez", "fed", "piyasa", "ekonomi"]):
            topics.append("Makro")

        return topics

    def _detect_sentiment(self, text: str) -> float:
        """Basit sentiment analizi (-1.0 to +1.0)"""
        positive_words = [
            "yükseldi", "arttı", "güçlü", "olumlu", "iyi", "kazanç", "başarılı",
            "pozitif", "yükseliş", "artış", "rally", "boğa", "al", "alım"
        ]
        negative_words = [
            "düştü", "azaldı", "zayıf", "olumsuz", "kötü", "zarar", "başarısız",
            "negatif", "düşüş", "azalış", "satış", "ayı", "sat", "risk"
        ]

        text_lower = text.lower()

        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)

        total = pos_count + neg_count
        if total == 0:
            return 0.0

        return (pos_count - neg_count) / total

    def _extract_symbols(self, text: str) -> List[str]:
        """Mesajdan sembol/hisse kodlarını çıkar (AKBNK, GARAN, BTCUSDT, etc.)"""
        import re

        symbols = []
        text_upper = text.upper()

        # Türk hisse kodları (4-6 harf, tüm büyük)
        turkish_stocks = re.findall(r'\b[A-Z]{4,6}\b', text_upper)
        symbols.extend(turkish_stocks)

        # Kripto sembolleri (BTC, ETH, USDT, etc.)
        crypto_pattern = r'\b(BTC|ETH|USDT|BNB|XRP|ADA|SOL|DOGE|AVAX|MATIC|DOT)\b'
        cryptos = re.findall(crypto_pattern, text_upper)
        symbols.extend(cryptos)

        # Duplicate'leri temizle
        return list(set(symbols))

    def pick_reply_target(
        self,
        db: Session,
        chat: Chat,
        reply_p: float,
        *,
        active_bot_id: Optional[int] = None,
        active_bot_username: Optional[str] = None,
        active_bot: Optional[Bot] = None,
    ) -> tuple[Optional[Message], Optional[str]]:
        """
        Smart Reply Target Selection V2 (Week 2 Day 1-3)

        Bot-to-bot interaction'ı TEŞVİK EDER:
        - Bot mesajlarına artık pozitif puan (+2.5)
        - Akıllı scoring: mention, soru, uzmanlık alanı, sentiment, popülerlik
        - Top 3'ten weighted random seçim (çeşitlilik için)
        """
        if random.random() > reply_p:
            return None, None

        # Son 30 mesajı al (20'den artırıldı)
        last_msgs = (
            db.query(Message)
            .filter(Message.chat_db_id == chat.id)
            .order_by(Message.created_at.desc())
            .limit(30)
            .all()
        )
        if not last_msgs:
            return None, None

        normalized_username = (active_bot_username or "").lstrip("@").lower()
        mention_tokens = [
            f"@{normalized_username}" if normalized_username else "",
            normalized_username,
        ]

        # Bot'un persona bilgilerini al
        bot_watchlist = []
        bot_empathy = 0.5
        if active_bot and hasattr(active_bot, "persona_profile"):
            persona = active_bot.persona_profile or {}
            bot_watchlist = persona.get("watchlist", [])

        if active_bot and hasattr(active_bot, "emotion_profile"):
            emotion = active_bot.emotion_profile or {}
            bot_empathy = emotion.get("empathy", 0.5)
            if isinstance(bot_empathy, str):
                # Eğer string ise, float'a çevirmeyi dene
                try:
                    bot_empathy = float(bot_empathy)
                except:
                    bot_empathy = 0.5

        scored_candidates: list[tuple[float, int, Message, Optional[str]]] = []
        now = now_utc()

        for idx, msg in enumerate(last_msgs):
            # Kendi mesajına cevap verme
            if active_bot_id is not None and msg.bot_id == active_bot_id:
                continue

            text = getattr(msg, "text", "") or ""
            lower_text = text.lower()

            score = 0.0

            # === 1. KİM YAZDI? ===
            if msg.bot_id is None:
                # İnsan mesajı - yüksek öncelik
                score += 8.0
            else:
                # Bot mesajı - ARTIK POZİTİF! (önceden -1.0 idi)
                score += 2.5  # Bot-to-bot interaction TEŞVİK EDİLİYOR!

            # === 2. TAZELIK ===
            age_minutes = (now - msg.created_at).total_seconds() / 60
            if age_minutes < 3:
                score += 3.0  # Çok taze
            elif age_minutes < 10:
                score += 2.0
            elif age_minutes < 30:
                score += 1.0
            else:
                score -= 1.0  # Eski mesaj

            # === 3. SORU VAR MI? ===
            if "?" in text:
                score += 4.0  # Soru kesinlikle cevap bekliyor

            # Merak ifadeleri
            curiosity_phrases = [
                "ne düşünüyorsun", "sizce", "fikrin", "ne dersin",
                "katılıyor musun", "öyle mi", "emin misin", "nasıl yapmalı",
                "ne yapmalı", "önerir misin"
            ]
            if any(phrase in lower_text for phrase in curiosity_phrases):
                score += 3.0

            # === 4. MENTION VAR MI? ===
            if normalized_username:
                for token in mention_tokens:
                    if token and token in lower_text:
                        score += 15.0  # Kesinlikle cevap ver!
                        break

            # === 5. UZMANLIK ALANI (watchlist overlap) ===
            if bot_watchlist:
                msg_symbols = self._extract_symbols(text)
                overlap = set(msg_symbols) & set(bot_watchlist)
                score += len(overlap) * 2.5  # Her eşleşen sembol +2.5

            # === 6. KONU UYUMU ===
            msg_topics = self._detect_topics(text)
            if msg_topics:
                # Eğer bot'un expertise'i varsa kontrol et
                # (Şimdilik basit: her topic +1.5)
                score += len(msg_topics) * 1.5

            # === 7. SENTIMENT UYUMU ===
            # Empatik botlar negatif mesajlara daha çok tepki verir
            msg_sentiment = self._detect_sentiment(text)
            if msg_sentiment < -0.3 and bot_empathy > 0.7:
                score += 2.0  # Empatik bot, negatif mesaja tepki verir

            # === 8. POPÜLER MESAJ (çok cevap alıyorsa) ===
            # Eğer birçok bot cevap verdiyse, bu bot da katılabilir
            try:
                reply_count = db.query(Message).filter(
                    Message.reply_to_message_id == msg.telegram_message_id
                ).count()

                if reply_count >= 2:
                    score += 1.5  # Popüler tartışma
            except:
                pass  # Hata olursa geç

            # Mention handle'ı belirle
            mention_handle = None
            msg_bot = getattr(msg, "bot", None)
            username = getattr(msg_bot, "username", None) if msg_bot else None
            if isinstance(username, str) and username.strip():
                mention_handle = username.lstrip("@")

            scored_candidates.append((score, idx, msg, mention_handle))

        if not scored_candidates:
            return None, None

        # Score'a göre sırala
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        # Top 3'ten weighted random seç (biraz randomness, çeşitlilik için)
        top_n = min(3, len(scored_candidates))
        top_candidates = scored_candidates[:top_n]

        # Weighted random selection
        weights = [max(c[0], 0.1) for c in top_candidates]  # Negatif score'ları 0.1'e çevir
        selected = random.choices(top_candidates, weights=weights, k=1)[0]

        score, _idx, target, candidate_mention_handle = selected

        logger.info(
            f"Reply target selected: '{target.text[:50]}...' (score={score:.1f}, "
            f"from_bot={target.bot_id is not None}, age={(now - target.created_at).seconds / 60:.1f}min)"
        )

        # Mention handle'ı belirle (probability ile)
        settings = self.settings(db)
        mention_handle = None
        if (
            candidate_mention_handle
            and random.random() < settings.get("mention_probability", 0.0)
        ):
            mention_handle = candidate_mention_handle

        return target, mention_handle

    # ---- Gecikme ve hız ----
    def next_delay_seconds(self, db: Session, *, bot: Optional[Bot] = None) -> float:
        s = self.settings(db)
        # prime saatlerde gecikmeyi kısalt
        base = 30.0  # ortalama gecikme tabanı
        if s.get("prime_hours_boost") and is_prime_hours(s.get("prime_hours", [])):
            base = 18.0
        # scale factor uygula (daha yüksek scale = daha hızlı mesajlar = daha kısa gecikme)
        scale_factor = max(float(s.get("scale_factor", 1.0)), 0.1)  # Minimum 0.1 to avoid division by zero
        base = base / scale_factor
        delay_profile = self._resolve_delay_profile(bot)

        if "base_delay_seconds" in delay_profile:
            base = _safe_float(delay_profile.get("base_delay_seconds"), base)

        multiplier = _safe_float(
            delay_profile.get("delay_multiplier", delay_profile.get("multiplier", 1.0)), 1.0
        )
        mean = max(base * multiplier, 0.0)

        jitter_min = _safe_float(
            delay_profile.get("jitter_min", delay_profile.get("delay_jitter_min", 0.7)), 0.7
        )
        jitter_max = _safe_float(
            delay_profile.get("jitter_max", delay_profile.get("delay_jitter_max", 1.3)), 1.3
        )
        if jitter_max < jitter_min:
            jitter_min, jitter_max = jitter_max, jitter_min

        delay = exp_delay(mean if mean > 0 else 1.0) * random.uniform(jitter_min, jitter_max)

        min_delay = _safe_float(
            delay_profile.get(
                "min_seconds",
                delay_profile.get("delay_min_seconds", delay_profile.get("seconds_min", 2.0)),
            ),
            2.0,
        )
        max_delay = _safe_float(
            delay_profile.get(
                "max_seconds",
                delay_profile.get("delay_max_seconds", delay_profile.get("seconds_max", 180.0)),
            ),
            180.0,
        )
        return clamp(delay, min_delay, max_delay)

    def typing_seconds(
        self,
        db: Session,
        est_chars: int,
        *,
        bot: Optional[Bot] = None,
        tempo_multiplier: float = 1.0,
    ) -> float:
        wpm = self.settings(db).get("typing_speed_wpm", {"min": 2.5, "max": 4.5})
        min_wpm = _safe_float(wpm.get("min"), 2.5)
        max_wpm = _safe_float(wpm.get("max"), 4.5)

        typing_profile = self._resolve_typing_profile(bot)
        if isinstance(typing_profile.get("wpm"), dict):
            wpm_dict = typing_profile.get("wpm", {})
            min_wpm = _safe_float(wpm_dict.get("min"), min_wpm)
            max_wpm = _safe_float(wpm_dict.get("max"), max_wpm)

        min_wpm = _safe_float(
            typing_profile.get("wpm_min", typing_profile.get("typing_wpm_min", min_wpm)),
            min_wpm,
        )
        max_wpm = _safe_float(
            typing_profile.get("wpm_max", typing_profile.get("typing_wpm_max", max_wpm)),
            max_wpm,
        )

        multiplier = _safe_float(
            typing_profile.get("typing_multiplier", typing_profile.get("multiplier", 1.0)), 1.0
        )
        min_wpm *= multiplier
        max_wpm *= multiplier

        if max_wpm < min_wpm:
            min_wpm, max_wpm = max_wpm, min_wpm

        mean_wpm = max((min_wpm + max_wpm) / 2.0, 0.1)
        cps = (mean_wpm * 5.0) / 60.0  # 1 kelime ~5 karakter varsayımı
        seconds = est_chars / max(cps, 1.0)

        min_seconds = _safe_float(
            typing_profile.get(
                "min_seconds",
                typing_profile.get("typing_min_seconds", typing_profile.get("seconds_min", 2.0)),
            ),
            2.0,
        )
        max_seconds = _safe_float(
            typing_profile.get(
                "max_seconds",
                typing_profile.get("typing_max_seconds", typing_profile.get("seconds_max", 8.0)),
            ),
            8.0,
        )
        seconds = clamp(seconds, min_seconds, max_seconds)
        tempo_multiplier = clamp(float(tempo_multiplier or 1.0), 0.5, 1.6)
        return seconds * tempo_multiplier

    def _resolve_delay_profile(self, bot: Optional[Bot]) -> Dict[str, Any]:
        profile = getattr(bot, "speed_profile", None) if bot else None
        if isinstance(profile, dict):
            delay = profile.get("delay")
            if isinstance(delay, dict):
                return delay
            return profile
        return {}

    def _resolve_typing_profile(self, bot: Optional[Bot]) -> Dict[str, Any]:
        profile = getattr(bot, "speed_profile", None) if bot else None
        if isinstance(profile, dict):
            typing = profile.get("typing")
            if isinstance(typing, dict):
                return typing
            return profile
        return {}

    # ---- Rate limit ----
    def global_rate_ok(self, db: Session) -> bool:
        s = self.settings(db)
        per_min_limit = int(s.get("max_msgs_per_min", 6))
        one_min_ago = now_utc() - timedelta(seconds=60)
        last_min_msgs = db.query(Message).filter(Message.created_at >= one_min_ago).count()
        return last_min_msgs < per_min_limit

    # ---- Persona/Stance/Holdings çekme ----
    def fetch_psh(
        self,
        db: Session,
        bot: Bot,
        topic_hint: Optional[str],
    ) -> tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], str]:
        """Bot için persona/emotion profilleri ile stance/holding verilerini oku ve sadeleştir."""
        persona_profile = bot.persona_profile or {}
        emotion_profile = bot.emotion_profile or {}
        persona_hint = (bot.persona_hint or "").strip()

        # Stance'ler: son güncellenene öncelik
        stance_rows: List[BotStance] = (
            db.query(BotStance)
            .filter(BotStance.bot_id == bot.id)
            .order_by(BotStance.updated_at.desc())
            .all()
        )
        stances: List[Dict[str, Any]] = []
        for s in stance_rows:
            stances.append({
                "topic": s.topic,
                "stance_text": (s.stance_text or "").strip(),
                "confidence": s.confidence,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "cooldown_until": s.cooldown_until.isoformat() if s.cooldown_until else None,
            })

        # İpucu verilen topic'i öne taşı (okunurluk için)
        if topic_hint:
            stances.sort(key=lambda x: (0 if (x.get("topic") or "").lower() == topic_hint.lower() else 1))

        # Holdings: son güncellenene öncelik
        holding_rows: List[BotHolding] = (
            db.query(BotHolding)
            .filter(BotHolding.bot_id == bot.id)
            .order_by(BotHolding.updated_at.desc())
            .all()
        )
        holdings: List[Dict[str, Any]] = []
        for h in holding_rows:
            holdings.append({
                "symbol": h.symbol,
                "avg_price": h.avg_price,
                "size": h.size,
                "note": h.note,
                "updated_at": h.updated_at.isoformat() if h.updated_at else None,
            })

        return persona_profile, emotion_profile, stances, holdings, persona_hint

    # ---- Tutarlılık koruması ----
    def apply_consistency_guard(
        self,
        *,
        draft_text: str,
        persona_profile: Dict[str, Any],
        stances: List[Dict[str, Any]],
    ) -> Optional[str]:
        """
        LLM çıktısını persona/stance ile karşılaştırıp bariz çelişki varsa nazikçe düzeltir.
        Çelişki yoksa None döndürerek mevcut metnin kullanılmasını önerir.
        """
        if not draft_text or not stances:
            return None

        persona_summary = summarize_persona(persona_profile)
        stance_summary = summarize_stances(stances)

        guard_prompt = f"""\
[PERSONA]
{persona_summary}

[STANCE]
{stance_summary}

[DRAFT]
{draft_text}

[GÖREV]
- DRAFT metnini STANCE ve (varsa) cooldown kurallarıyla karşılaştır.
- Eğer bariz çelişki YOKSA DRAFT'ı olduğu gibi geri ver (değiştirme).
- Eğer çelişki VARSA veya cooldown sürerken zıt pozisyon içeriyorsa:
  1) Tonu yumuşat ve kısa bir gerekçe ekleyerek metni düzelt.
  2) Aynı dilde (Türkçe) 2-3 cümle yaz.
  3) Aşırı iddiadan kaçın, ama doğal ve insan gibi konuş.
- SADECE nihai metni döndür, başka açıklama yazma.
"""
        # Düşük sıcaklık, kısa yanıt
        revised = self.llm.generate(user_prompt=guard_prompt, temperature=0.3, max_tokens=220)
        if not revised:
            return None

        # Eğer çıktı DRAFT ile neredeyse aynıysa değişiklik yapmamış say
        if revised.strip() == draft_text.strip():
            return None

        return revised

    def apply_reaction_overrides(self, text: str, plan: ReactionPlan) -> str:
        if not text or not plan:
            return text

        updated = text.strip()

        phrase = (plan.signature_phrase or "").strip()
        if phrase and phrase.lower() not in updated.lower():
            if updated.endswith(('.', '!', '?')):
                updated = f"{updated} {phrase}".strip()
            else:
                updated = f"{updated}. {phrase}".strip()

        anecdote = (plan.anecdote or "").strip()
        if anecdote and anecdote.lower() not in updated.lower():
            if updated.endswith(('.', '!', '?')):
                updated = f"{updated} {anecdote}".strip()
            else:
                updated = f"{updated}. {anecdote}".strip()

        emoji = (plan.emoji or "").strip()
        if emoji and emoji not in updated:
            updated = f"{updated} {emoji}".strip()

        return updated

    async def send_message_with_queue(
        self,
        bot: Bot,
        chat: Chat,
        text: str,
        *,
        reply_to_message_id: Optional[int] = None,
        disable_preview: bool = True,
        parse_mode: Optional[str] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        db_message_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Send message to Telegram with automatic queuing on rate limit.

        If rate limited, the message is queued for later delivery.

        Args:
            bot: Bot to send from
            chat: Chat to send to
            text: Message text
            reply_to_message_id: Optional reply target
            disable_preview: Disable link preview
            parse_mode: Markdown/HTML
            priority: Message priority (affects queue order)
            db_message_id: Optional database message ID for tracking

        Returns:
            Telegram message ID if sent immediately, None if queued
        """
        try:
            # Attempt immediate send
            msg_id = await self.tg.send_message(
                token=bot.token,
                chat_id=chat.chat_id,
                text=text,
                reply_to_message_id=reply_to_message_id,
                disable_preview=disable_preview,
                parse_mode=parse_mode,
                skip_rate_limit=False,
            )

            if msg_id:
                # Successfully sent immediately
                return msg_id

            # Send returned None (likely rate limited) - enqueue
            logger.info(
                "Message rate limited, enqueueing: bot=%s, chat=%s, priority=%s",
                bot.name, chat.chat_id, priority.name
            )

            queued_msg = QueuedMessage(
                bot_token=bot.token,
                chat_id=chat.chat_id,
                text=text,
                priority=priority,
                reply_to_message_id=reply_to_message_id,
                disable_preview=disable_preview,
                parse_mode=parse_mode,
                message_id=db_message_id,
                bot_id=bot.id,
            )

            if self.msg_queue.enqueue(queued_msg):
                logger.debug("Message enqueued successfully")
                return None
            else:
                logger.warning("Failed to enqueue rate-limited message")
                return None

        except Exception as e:
            logger.exception("Error sending message with queue: %s", e)
            return None

    def apply_micro_behaviors(
        self,
        text: str,
        *,
        emotion_profile: Dict[str, Any],
        plan: ReactionPlan,
    ) -> str:
        if not text:
            return text

        updated = text
        tone = str((emotion_profile or {}).get("tone") or "").lower()
        energy = str((emotion_profile or {}).get("energy") or "").lower()

        if any(keyword in (tone + " " + energy) for keyword in ["sakin", "yumuşak", "dingin"]) and "…" not in updated:
            if random.random() < 0.35:
                if "," in updated:
                    updated = updated.replace(",", "…", 1)
                else:
                    updated = updated + "…"

        emoji = (plan.emoji or "").strip()
        if emoji and emoji in updated and random.random() < 0.5:
            updated = updated.replace(f" {emoji}", "", 1).strip()
            parts = re.split(r"([.!?])", updated)
            if len(parts) > 1:
                parts[0] = parts[0].strip() + f" {emoji}"
                updated = "".join(parts).strip()
            else:
                updated = f"{emoji} {updated}".strip()

        return updated

    def add_filler_words(self, text: str, probability: float = 0.20) -> str:
        """
        Mesaja doğal konuşma dolgu kelimeleri ekler.

        Args:
            text: Düzenlenecek metin
            probability: Dolgu kelime ekleme olasılığı (varsayılan %20)

        Returns:
            Dolgu kelimelerle zenginleştirilmiş metin
        """
        if not text or random.random() > probability:
            return text

        # Türkçe konuşma dilindeki yaygın dolgu kelimeleri
        fillers_start = [
            "aa",
            "haa",
            "hmm",
            "şey",
            "yani",
            "işte",
            "hani",
            "valla",
            "ya",
            "ee",
            "off",
        ]

        fillers_middle = [
            "yani",
            "işte",
            "hani",
            "şey",
            "demek istediğim",
        ]

        # Cümleleri ayır
        sentences = re.split(r'([.!?])', text)
        modified_sentences = []

        for i, part in enumerate(sentences):
            # Noktalama işaretlerini aynen koru
            if part in '.!?':
                modified_sentences.append(part)
                continue

            sentence = part.strip()
            if not sentence:
                modified_sentences.append(part)
                continue

            # İlk cümle için başa dolgu ekle (%30 olasılık)
            if i == 0 and random.random() < 0.30:
                filler = random.choice(fillers_start)
                sentence = f"{filler.capitalize()}, {sentence.lower()}"
            # Diğer cümleler için ortaya dolgu ekle (%15 olasılık)
            elif i > 0 and random.random() < 0.15:
                words = sentence.split()
                if len(words) >= 3:
                    # Ortaya yakın bir yere ekle
                    insert_pos = random.randint(1, len(words) - 1)
                    filler = random.choice(fillers_middle)
                    words.insert(insert_pos, filler + ",")
                    sentence = " ".join(words)

            modified_sentences.append(sentence if i == 0 else " " + sentence)

        return "".join(modified_sentences)

    # ---- Dedup (tekrar) kontrolü ----
    def is_duplicate_recent(self, db: Session, *, bot_id: int, text: str, hours: int) -> bool:
        if not text:
            return False
        cutoff = now_utc() - timedelta(hours=int(max(1, hours)))
        last_msgs = (
            db.query(Message)
            .filter(Message.bot_id == bot_id, Message.created_at >= cutoff)
            .order_by(Message.created_at.desc())
            .limit(100)
            .all()
        )
        target = normalize_text(text)
        for m in last_msgs:
            if normalize_text(m.text or "") == target:
                return True
        return False

    def paraphrase_safe(self, text: str) -> Optional[str]:
        """Basit yeniden yazım; anlamı korur, tekrar algılamayı aşmaya çalışır."""
        prompt = f"""Metni aynı anlamla, 1-2 kısa cümlede farklı ifade et; iddialı/kesin ton kullanma:

METİN:
{text}
"""
        return self.llm.generate(user_prompt=prompt, temperature=0.4, max_tokens=120)

    # ---- Priority Queue İşleme ----
    def _check_priority_queue(self, db: Session) -> Optional[Dict[str, Any]]:
        """
        Redis priority queue'dan yüksek öncelikli mesajları kontrol eder.
        Returns: Priority queue item veya None
        """
        if not self._redis_sync_client:
            return None

        try:
            # Önce high priority queue'yu kontrol et
            raw_item = self._redis_sync_client.rpop("priority_queue:high")
            if raw_item:
                return json.loads(raw_item)

            # High yoksa normal queue'dan al
            raw_item = self._redis_sync_client.rpop("priority_queue:normal")
            if raw_item:
                return json.loads(raw_item)

            return None
        except Exception as e:
            logger.warning("Priority queue check failed: %s", e)
            return None

    async def _process_priority_message(self, db: Session, priority_item: Dict[str, Any]) -> bool:
        """
        Priority queue'dan gelen mesajı işle ve bot'un yanıt vermesini sağla.
        Returns: True if successfully processed
        """
        try:
            bot_id = priority_item.get("bot_id")
            chat_id = priority_item.get("chat_id")
            telegram_message_id = priority_item.get("telegram_message_id")
            user_text = priority_item.get("text", "")
            is_mentioned = priority_item.get("is_mentioned", False)
            is_reply_to_bot = priority_item.get("is_reply_to_bot", False)

            if not bot_id or not chat_id:
                logger.warning("Invalid priority item: missing bot_id or chat_id")
                return False

            # Bot'u DB'den çek
            bot = db.query(Bot).filter(Bot.id == bot_id, Bot.is_enabled.is_(True)).first()
            if not bot:
                logger.warning("Bot %s not found or disabled for priority response", bot_id)
                return False

            # Chat'i DB'den çek
            chat = db.query(Chat).filter(Chat.id == chat_id).first()
            if not chat:
                logger.warning("Chat %s not found for priority response", chat_id)
                return False

            # Kullanıcı mesajını DB'den bul (context için)
            incoming_msg = db.query(Message).filter(
                Message.telegram_message_id == telegram_message_id,
                Message.chat_db_id == chat_id,
            ).first()

            logger.info(
                "Processing priority message: bot=%s, chat=%s, mentioned=%s, reply=%s",
                bot.name,
                chat.title,
                is_mentioned,
                is_reply_to_bot,
            )

            # Persona/Stance/Holdings verileri
            (
                persona_profile,
                emotion_profile,
                stances,
                holdings,
                persona_hint,
            ) = self.fetch_psh(db, bot, topic_hint=None)

            # Son mesajları context olarak al
            recent_msgs = (
                db.query(Message)
                .filter(Message.chat_db_id == chat.id)
                .order_by(Message.created_at.desc())
                .limit(40)
                .all()
            )

            # History transcript (kullanıcı mesajları da dahil!)
            history_source = list(recent_msgs[:8])  # Daha fazla context
            history_excerpt = build_history_transcript(list(reversed(history_source)))

            # Contextual examples
            contextual_examples = build_contextual_examples(
                list(reversed(recent_msgs)), bot_id=bot.id, max_pairs=3
            )

            # Topic seçimi (kullanıcı mesajından)
            topic_pool = chat.topics or ["BIST", "FX", "Kripto", "Makro"]
            topic = choose_topic_from_messages([incoming_msg] if incoming_msg else history_source, topic_pool)

            # Haber tetikleyici (priority mesajlar için daha düşük olasılık)
            s = self.settings(db)
            market_trigger = ""
            if bool(s.get("news_trigger_enabled", True)) and self.news is not None:
                if random.random() < 0.4:  # Priority response için %40 olasılık
                    try:
                        brief = self.news.get_brief(topic)
                        if brief:
                            market_trigger = brief
                    except Exception as e:
                        logger.debug("News trigger error in priority response: %s", e)

            # Reaction plan
            reaction_plan = synthesize_reaction_plan(
                emotion_profile=emotion_profile,
                market_trigger=market_trigger,
            )
            tempo_multiplier = derive_tempo_multiplier(emotion_profile, reaction_plan)

            # Length hint
            selected_length_category = choose_message_length_category(
                s.get("message_length_profile")
            )
            length_hint = compose_length_hint(
                persona_profile=persona_profile,
                selected_category=selected_length_category,
            )

            # Time context
            time_context = generate_time_context()

            # Memories
            bot_memories = fetch_bot_memories(db, bot.id, limit=8)
            memories_text = format_memories_for_prompt(bot_memories)

            # Past references
            temp_metadata = extract_message_metadata(text=user_text, topic=topic)
            current_symbols = temp_metadata.get("symbols", [])
            past_references = find_relevant_past_messages(
                db,
                bot_id=bot.id,
                current_topic=topic,
                current_symbols=current_symbols,
                days_back=7,
                limit=3,
            )
            past_references_text = format_past_references_for_prompt(past_references)

            # User prompt için reply context
            reply_excerpt = shorten(user_text, 240)
            mention_ctx = ""

            # Priority response'da MUTLAKA reply mode
            user_prompt = generate_user_prompt(
                topic_name=topic,
                history_excerpt=shorten(history_excerpt, 400),
                reply_context=reply_excerpt,
                market_trigger=market_trigger,
                mode="reply",  # Priority mesajlar için her zaman reply
                mention_context=mention_ctx,
                persona_profile=persona_profile,
                reaction_guidance=reaction_plan.instructions,
                emotion_profile=emotion_profile,
                contextual_examples=contextual_examples,
                stances=stances,
                holdings=holdings,
                memories=memories_text,
                past_references=past_references_text,
                length_hint=length_hint,
                persona_hint=persona_hint,
                persona_refresh_note="",  # Priority için persona refresh atlayalım
                time_context=time_context,
            )

            # LLM üretimi
            text = self.llm.generate(user_prompt=user_prompt, temperature=0.75, max_tokens=220)
            if not text:
                logger.warning("LLM returned empty response for priority message")
                return False

            # Tutarlılık koruması
            if bool(s.get("consistency_guard_enabled", True)):
                revised = self.apply_consistency_guard(
                    draft_text=text,
                    persona_profile=persona_profile,
                    stances=stances,
                )
                if revised:
                    text = revised

            text = self.apply_reaction_overrides(text, reaction_plan)
            text = self.apply_micro_behaviors(
                text,
                emotion_profile=emotion_profile,
                plan=reaction_plan,
            )

            # İnsancıl geliştirmeler
            text = add_conversation_openings(text, probability=0.35)  # Priority için daha yüksek
            text = add_hesitation_markers(text, probability=0.25)
            text = add_colloquial_shortcuts(text, probability=0.20)
            text = self.add_filler_words(text, probability=0.25)
            text = apply_natural_imperfections(text, probability=0.12)

            # Typing simülasyonu
            if bool(s.get("typing_enabled", True)):
                await self.tg.send_typing(
                    bot.token,
                    chat.chat_id,
                    self.typing_seconds(
                        db,
                        len(text),
                        bot=bot,
                        tempo_multiplier=tempo_multiplier,
                    ),
                )

            # Mesajı gönder (reply olarak)
            msg_id = await self.tg.send_message(
                token=bot.token,
                chat_id=chat.chat_id,
                text=text,
                reply_to_message_id=telegram_message_id,  # Kullanıcı mesajına yanıt
                disable_preview=True,
            )

            # DB log
            msg_metadata = extract_message_metadata(text, topic)
            msg_metadata["is_priority_response"] = True
            msg_metadata["responded_to_message_id"] = telegram_message_id

            db.add(Message(
                bot_id=bot.id,
                chat_db_id=chat.id,
                telegram_message_id=msg_id,
                text=text,
                reply_to_message_id=telegram_message_id,
                msg_metadata=msg_metadata,
            ))
            db.commit()

            logger.info("Priority response sent: bot=%s, text_preview=%s", bot.name, text[:50])
            return True

        except Exception as e:
            logger.exception("Priority message processing failed: %s", e)
            return False

    # ---- Akış ----
    async def tick_once(self) -> None:
        db: Session = SessionLocal()
        try:
            s = self.settings(db)
            if not bool(s.get("simulation_active", False)):
                await asyncio.sleep(1.0)
                return

            # ÖNCELİK 1: Priority queue'dan gelen mesajları kontrol et
            priority_item = self._check_priority_queue(db)
            if priority_item:
                # Priority mesajı işle (kullanıcı mention/reply'leri)
                success = await self._process_priority_message(db, priority_item)
                if success:
                    # Priority mesaj işlendikten sonra kısa bir gecikme
                    await asyncio.sleep(2.0)
                else:
                    # Başarısızsa biraz daha bekle
                    await asyncio.sleep(5.0)
                return  # Priority işlendikten sonra normal akışa geri dön

            # Global rate limit
            if not self.global_rate_ok(db):
                await asyncio.sleep(2.5)
                return

            chat = self.pick_chat(db)
            if not chat:
                logger.info("Aktif chat yok; bekleniyor.")
                await asyncio.sleep(2.0)
                return

            bot = self.pick_bot(
                db,
                hourly_limit=s.get("bot_hourly_msg_limit", {"max": 12}),
                chat=chat,
            )
            if not bot:
                logger.info("Saatlik sınır nedeniyle uygun bot bulunamadı; bekleniyor.")
                await asyncio.sleep(3.0)
                return

            # Persona/Stance/Holdings verilerini çek (erken çekiyoruz çünkü topic seçiminde cooldown gerekiyor)
            topic_hint_pool = (chat.topics or ["BIST", "FX", "Kripto", "Makro"]).copy()

            (
                persona_profile,
                emotion_profile,
                stances,
                holdings,
                persona_hint,
            ) = self.fetch_psh(db, bot, topic_hint=None)

            refresh_state = self._persona_refresh.setdefault(
                bot.id,
                {
                    "messages_since": 0,
                    "last": datetime.min.replace(tzinfo=UTC),
                },
            )
            now = now_utc()
            refresh_interval = int(s.get("persona_refresh_interval", 8))
            refresh_minutes = int(s.get("persona_refresh_minutes", 30))
            should_refresh, normalized_state = should_refresh_persona(
                refresh_state,
                refresh_interval=refresh_interval,
                refresh_minutes=refresh_minutes,
                now=now,
            )
            refresh_state.update(normalized_state)

            persona_refresh_note = (
                compose_persona_refresh_note(persona_profile, persona_hint, emotion_profile)
                if should_refresh
                else ""
            )

            # Cooldown filtre: cooldown'da olan konuları pool'dan çıkar
            if bool(s.get("cooldown_filter_enabled", True)):
                active_cd = set(self._active_cooldown_topics(stances))
                filtered = [t for t in topic_hint_pool if t not in active_cd]
                if filtered:
                    topic_hint_pool = filtered

            # Reaksiyon-only olayı
            if random.random() < float(s.get("short_reaction_probability", 0.12)):
                last = (
                    db.query(Message)
                    .filter(Message.chat_db_id == chat.id)
                    .order_by(Message.created_at.desc())
                    .limit(10)
                    .all()
                )
                candidates = [m for m in last if m.bot_id != bot.id]
                if candidates:
                    target = random.choice(candidates)
                    ok = await self.tg.try_set_reaction(bot.token, chat.chat_id, target.telegram_message_id)
                    if not ok:
                        # fallback: çok kısa bir emoji mesajı
                        emoji = LLMClient.pick_reaction_for_text(getattr(target, "text", ""))
                        msg_id = await self.tg.send_message(
                            token=bot.token,
                            chat_id=chat.chat_id,
                            text=emoji,
                            reply_to_message_id=target.telegram_message_id,
                            disable_preview=True,
                        )
                        # logla (metadata ile)
                        emoji_metadata = extract_message_metadata(emoji, topic_hint_pool[0] if topic_hint_pool else "")
                        db.add(Message(
                            bot_id=bot.id,
                            chat_db_id=chat.id,
                            telegram_message_id=msg_id,
                            text=emoji,
                            reply_to_message_id=target.telegram_message_id,
                            msg_metadata=emoji_metadata,
                        ))
                        db.commit()
                    await asyncio.sleep(self.next_delay_seconds(db, bot=bot))
                    return

            # Geçmiş özet (son mesajlardan örnekler) - önce al ki son mesajı kontrol edebiliriz
            recent_msgs = (
                db.query(Message)
                .filter(Message.chat_db_id == chat.id)
                .order_by(Message.created_at.desc())
                .limit(40)
                .all()
            )

            # Week 2 Day 4-5: Reply Probability Tuning
            # Son mesaj bot'tansa, reply_to_bots_probability kullan
            reply_prob = float(s.get("reply_probability", 0.65))
            if recent_msgs and len(recent_msgs) > 0:
                last_msg = recent_msgs[0]
                if last_msg.bot_id is not None:
                    # Son mesaj bot'tan - farklı probability kullan
                    reply_prob = float(s.get("reply_to_bots_probability", 0.5))
                    logger.debug(f"Last message from bot, using reply_to_bots_probability={reply_prob}")

            # Reply hedefi ve mention
            reply_msg, mention_handle = self.pick_reply_target(
                db,
                chat,
                reply_prob,  # Dinamik probability
                active_bot_id=bot.id,
                active_bot_username=getattr(bot, "username", None),
                active_bot=bot,  # Smart Reply Target Selection V2 için gerekli
            )
            mode = "reply" if reply_msg else "new"
            mention_ctx = f"@{mention_handle}" if mention_handle else ""
            # Week 2 Day 6-7: Context Window Expansion (6 → 15 mesaj)
            history_source = list(recent_msgs[:15])  # 6'dan 15'e çıkarıldı
            history_excerpt = build_history_transcript(list(reversed(history_source)))
            reply_excerpt = shorten(reply_msg.text if reply_msg else "", 240)

            contextual_examples = build_contextual_examples(
                list(reversed(recent_msgs[:30])),  # 30 mesaj içinden örnek seç (daha zengin)
                bot_id=bot.id,
                max_pairs=4  # 3'ten 4'e çıkarıldı
            )

            # Topic seç (cooldown filtreli havuzdan)
            topic = choose_topic_from_messages(history_source, topic_hint_pool)

            # ---- HABER TETIKLEYICI ----
            market_trigger = ""
            try:
                if bool(s.get("news_trigger_enabled", True)) and self.news is not None:
                    # Her mesajda değil; bir miktar rastgelelik:
                    if random.random() < float(s.get("news_trigger_probability", 0.75)):
                        brief = self.news.get_brief(topic)
                        if brief:
                            market_trigger = brief
            except Exception as e:
                logger.debug("news trigger error: %s", e)

            reaction_plan = synthesize_reaction_plan(
                emotion_profile=emotion_profile,
                market_trigger=market_trigger,
            )
            tempo_multiplier = derive_tempo_multiplier(emotion_profile, reaction_plan)

            # (prompt için) Stance/holding özetleri; topic'i ipucu olarak veriyoruz
            selected_length_category = choose_message_length_category(
                s.get("message_length_profile")
            )
            length_hint = compose_length_hint(
                persona_profile=persona_profile,
                selected_category=selected_length_category,
            )

            # Zaman bağlamı oluştur
            time_context = generate_time_context()

            # ---- KİŞİSEL HAFIZA SİSTEMİ ----
            # Bot'un kişisel hafızalarını çek ve prompt'a ekle
            bot_memories = fetch_bot_memories(db, bot.id, limit=8)
            memories_text = format_memories_for_prompt(bot_memories)

            # Kullanılan hafızaları işaretle (usage_count güncelle)
            for memory in bot_memories:
                try:
                    update_memory_usage(db, memory["id"])
                except Exception as e:
                    logger.debug("Memory usage update error: %s", e)

            # ---- GEÇMİŞ REFERANS SİSTEMİ ----
            # Metadata çıkar (kullanılacak sembolleri tespit et)
            temp_metadata = extract_message_metadata(text="", topic=topic)
            current_symbols = temp_metadata.get("symbols", [])

            # Bot'un bu konu/sembollerde daha önce söylediklerini bul
            past_references = find_relevant_past_messages(
                db,
                bot_id=bot.id,
                current_topic=topic,
                current_symbols=current_symbols,
                days_back=7,
                limit=3,
            )
            past_references_text = format_past_references_for_prompt(past_references)

            user_prompt = generate_user_prompt(
                topic_name=topic,
                history_excerpt=shorten(history_excerpt, 400),
                reply_context=reply_excerpt,
                market_trigger=market_trigger,  # <-- Burada kullanılıyor
                mode=mode,
                mention_context=mention_ctx,
                persona_profile=persona_profile,
                reaction_guidance=reaction_plan.instructions,
                emotion_profile=emotion_profile,
                contextual_examples=contextual_examples,
                stances=stances,
                holdings=holdings,
                memories=memories_text,  # <-- Kişisel hafızalar
                past_references=past_references_text,  # <-- Yeni: Geçmiş referanslar
                length_hint=length_hint,
                persona_hint=persona_hint,
                persona_refresh_note=persona_refresh_note,
                time_context=time_context,
            )

            # ==== YENİ: UNIQUE SYSTEM PROMPT ÜRET ====
            system_prompt = generate_system_prompt(
                persona_profile=persona_profile,
                emotion_profile=emotion_profile,
                bot_name=bot.name,
            )

            # ==== YENİ: DİNAMİK LLM PARAMETRELERİ ====
            # Temperature: Bot kişiliğine göre değişir
            base_temp = 1.0
            tone = (persona_profile or {}).get("tone", "").lower()
            if "profesyonel" in tone or "akademik" in tone:
                temperature = base_temp + random.uniform(0.05, 0.10)  # 1.05-1.10 (kontrollü)
            else:
                temperature = base_temp + random.uniform(0.10, 0.20)  # 1.10-1.20 (yaratıcı)

            # Max tokens: Bot persona'ya göre dinamik
            if "akademik" in tone or "tecrübeli" in tone or "profesyonel" in tone:
                max_tokens = random.randint(150, 250)  # Uzun mesajlar
            elif "genç" in tone or "enerjik" in tone:
                max_tokens = random.randint(80, 150)  # Kısa-orta
            else:
                max_tokens = random.randint(100, 200)  # Orta

            # Reply ise daha kısa
            if mode == "reply":
                max_tokens = int(max_tokens * 0.7)

            # Top-p sampling
            top_p = 0.95

            # Frequency penalty (tekrarları önle)
            frequency_penalty = 0.5

            logger.debug(
                "LLM params for %s: temp=%.2f, max_tokens=%d, top_p=%.2f, freq_penalty=%.2f",
                bot.name, temperature, max_tokens, top_p, frequency_penalty
            )

            # ==== LLM ÜRETİMİ (YENİ PARAMETRELERLE) ====
            text = self.llm.generate(
                user_prompt=user_prompt,
                system_prompt=system_prompt,  # <-- UNIQUE!
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
            )
            if not text:
                logger.warning("LLM boş/filtreli çıktı; atlanıyor.")
                await asyncio.sleep(self.next_delay_seconds(db, bot=bot))
                return

            # Tutarlılık koruması
            if bool(s.get("consistency_guard_enabled", True)):
                revised = self.apply_consistency_guard(
                    draft_text=text,
                    persona_profile=persona_profile,
                    stances=stances,
                )
                if revised:
                    text = revised

            text = self.apply_reaction_overrides(text, reaction_plan)

            text = self.apply_micro_behaviors(
                text,
                emotion_profile=emotion_profile,
                plan=reaction_plan,
            )

            # İnsancıl geliştirmeler (sıralama önemli!)
            # 1. Konuşma açılışları ekle
            text = add_conversation_openings(text, probability=0.25)

            # 2. Belirsizlik belirteçleri ekle (en kritik özellik)
            text = add_hesitation_markers(text, probability=0.30)

            # 3. Günlük kısaltmalar ekle
            text = add_colloquial_shortcuts(text, probability=0.18)

            # 4. Dolgu kelimeleri ekle
            text = self.add_filler_words(text, probability=0.20)

            # 5. Doğal kusurlar uygula (yazım hataları + düzeltmeler)
            text = apply_natural_imperfections(text, probability=0.15)

            # Mention'ı metne kibarca ekle (başta değilse)
            if mention_ctx and mention_ctx not in text:
                if random.random() < 0.6:
                    text = f"{mention_ctx} {text}"
                else:
                    text = f"{text} {mention_ctx}"

            # Dedup kontrolü: son X saatte aynısı varsa yeniden yazdırmayı dene
            # Exact-match deduplication (mevcut)
            if bool(s.get("dedup_enabled", True)):
                window_h = int(s.get("dedup_window_hours", 12))
                attempts = int(s.get("dedup_max_attempts", 2))
                tries = 0
                while self.is_duplicate_recent(db, bot_id=bot.id, text=text, hours=window_h) and tries < attempts:
                    alt = self.paraphrase_safe(text)
                    if not alt or alt.strip() == text.strip():
                        break
                    text = alt.strip()
                    tries += 1
                # Hâlâ birebir aynıysa mesajı es geç
                if self.is_duplicate_recent(db, bot_id=bot.id, text=text, hours=window_h):
                    logger.info("Dedup: aynı metin tespit edildi, gönderim atlandı.")
                    await asyncio.sleep(self.next_delay_seconds(db, bot=bot))
                    return

            # PHASE 2 Week 3 Day 1-3: Semantic Deduplication
            if bool(s.get("semantic_dedup_enabled", True)) and self.semantic_dedup and self.semantic_dedup.enabled:
                # Son 50 bot mesajını al
                recent_bot_msgs = [
                    m.text for m in recent_msgs[:50]
                    if m.text and m.bot_id == bot.id
                ]

                if recent_bot_msgs:
                    is_dup, similarity = self.semantic_dedup.is_duplicate(text, recent_bot_msgs)

                    if is_dup:
                        logger.warning(f"Semantic duplicate detected! Similarity={similarity:.3f}")

                        # 2 deneme: Paraphrase et
                        paraphrase_attempts = 2
                        for attempt in range(paraphrase_attempts):
                            text = self.semantic_dedup.paraphrase_message(text, self.llm)
                            is_dup, similarity = self.semantic_dedup.is_duplicate(text, recent_bot_msgs)

                            if not is_dup:
                                logger.info(f"Paraphrase successful! New similarity={similarity:.3f}")
                                break

                        # Hâlâ duplicate ise mesajı atla
                        if is_dup:
                            logger.error("Paraphrase failed after 2 attempts, skipping message")
                            await asyncio.sleep(self.next_delay_seconds(db, bot=bot))
                            return

            # PHASE 2 Week 3 Day 4-5: Voice Profile Application
            # Mesaja bot'un unique writing style'ını uygula
            voice = self.get_bot_voice(bot)
            original_text = text
            text = self.voice_generator.apply_voice(text, voice)
            if text != original_text:
                logger.debug(f"Voice profile applied: '{original_text[:50]}...' -> '{text[:50]}...'")

            # Typing simülasyonu
            if bool(s.get("typing_enabled", True)):
                await self.tg.send_typing(
                    bot.token,
                    chat.chat_id,
                    self.typing_seconds(
                        db,
                        len(text),
                        bot=bot,
                        tempo_multiplier=tempo_multiplier,
                    ),
                )

            # Mesajı gönder
            msg_id = await self.tg.send_message(
                token=bot.token,
                chat_id=chat.chat_id,
                text=text,
                reply_to_message_id=reply_msg.telegram_message_id if reply_msg else None,
                disable_preview=True,
            )

            # DB log (metadata ile birlikte kaydet)
            msg_metadata = extract_message_metadata(text, topic)
            db.add(Message(
                bot_id=bot.id,
                chat_db_id=chat.id,
                telegram_message_id=msg_id,
                text=text,
                reply_to_message_id=reply_msg.telegram_message_id if reply_msg else None,
                msg_metadata=msg_metadata,  # <-- Yeni: Mesaj metadata'sını kaydet
            ))
            db.commit()

            self._persona_refresh[bot.id] = update_persona_refresh_state(
                refresh_state,
                triggered=should_refresh,
                now=now_utc(),
            )

            # Sonraki gecikme
            await asyncio.sleep(self.next_delay_seconds(db, bot=bot))

        except Exception as e:
            logger.exception("tick_once error: %s", e)
            await asyncio.sleep(3.0)
        finally:
            db.close()

    # ---- Message queue processor ----
    async def _process_message_queue(self) -> None:
        """
        Background task to process queued messages.

        Continuously dequeues messages and attempts to send them via Telegram.
        Uses blocking dequeue with timeout to avoid busy-waiting.
        """
        logger.info("Message queue processor started")

        while True:
            try:
                # Dequeue next message (blocks for up to 1 second)
                message = self.msg_queue.dequeue(block=True, timeout=1.0)

                if message is None:
                    # No messages in queue, continue
                    await asyncio.sleep(0.1)
                    continue

                # Attempt to send message
                try:
                    msg_id = await self.tg.send_message(
                        token=message.bot_token,
                        chat_id=message.chat_id,
                        text=message.text,
                        reply_to_message_id=message.reply_to_message_id,
                        disable_preview=message.disable_preview,
                        parse_mode=message.parse_mode,
                        skip_rate_limit=False,  # Apply rate limiting
                    )

                    if msg_id:
                        # Success - acknowledge message
                        self.msg_queue.ack(message)
                        logger.debug(
                            "Queued message sent successfully: chat=%s, msg_id=%s",
                            message.chat_id, msg_id
                        )

                        # Update database if message_id provided
                        if message.message_id and message.bot_id:
                            db = SessionLocal()
                            try:
                                db_msg = db.query(Message).filter(Message.id == message.message_id).first()
                                if db_msg:
                                    db_msg.telegram_message_id = msg_id
                                    db.commit()
                            except Exception as e:
                                logger.warning("Failed to update message in DB: %s", e)
                            finally:
                                db.close()
                    else:
                        # Send failed - nack and retry
                        self.msg_queue.nack(message, "send_message returned None")

                except Exception as e:
                    # Send error - nack and retry
                    error_msg = str(e)
                    logger.warning(
                        "Failed to send queued message (retry %d/%d): %s",
                        message.retry_count + 1, message.max_retries, error_msg
                    )
                    self.msg_queue.nack(message, error_msg)

                # Small delay between messages
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.exception("Error in message queue processor: %s", e)
                await asyncio.sleep(1.0)

    async def run_forever(self):
        logger.info("BehaviorEngine started. CTRL+C ile durdurabilirsiniz.")

        # Redis listener'ı başlat
        if self._redis_url and self._redis_task is None:
            self._redis_task = asyncio.create_task(self._config_listener(), name="config_listener")

        # Message queue processor'ı başlat
        if self._queue_processor_task is None:
            self._queue_processor_task = asyncio.create_task(
                self._process_message_queue(),
                name="queue_processor"
            )
            logger.info("Message queue processor task created")

        while True:
            await self.tick_once()

    # ---- Temiz kapanış ----
    async def shutdown(self) -> None:
        """Worker sinyali geldiğinde kaynakları nazikçe kapat."""
        # Redis listener iptali
        if self._redis_task:
            self._redis_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._redis_task
            self._redis_task = None

        # Queue processor iptali
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._queue_processor_task
            self._queue_processor_task = None
            logger.info("Message queue processor stopped")

        # Telegram HTTP istemcisi
        try:
            await self.tg.close()
        except Exception:
            pass
        logger.info("BehaviorEngine shutdown completed.")


# ---------------------------
# Çalıştırma
# ---------------------------
async def run_engine_forever():
    global _ENGINE
    engine = BehaviorEngine()
    _ENGINE = engine
    try:
        await engine.run_forever()
    finally:
        # Çalışma döngüsü biterse (iptal/çökme), referansı temizle
        _ENGINE = None


# ---------------------------
# Modül seviyesi kapanış kancası
# ---------------------------
async def shutdown() -> None:
    """worker.py bu fonksiyonu çağırır: aktif engine varsa kapatır."""
    if _ENGINE is None:
        logger.info("No active BehaviorEngine to shutdown.")
        return
    try:
        await _ENGINE.shutdown()
    finally:
        logger.info("Module-level shutdown done.")
