"""
Message Metadata Analysis Functions

Functions for extracting, analyzing, and managing message metadata, bot memories,
and relevance scoring for past messages.

Extracted from behavior_engine.py (Session 19 - Modularization Phase 2)
"""

import re
from datetime import timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import BotMemory, Message
from backend.behavior import now_utc


# ==============================================================================
# Bot Memory Management
# ==============================================================================

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


# ==============================================================================
# Message Metadata Extraction
# ==============================================================================

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


# ==============================================================================
# Relevant Past Messages
# ==============================================================================

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
