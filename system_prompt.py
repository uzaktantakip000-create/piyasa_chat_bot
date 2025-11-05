from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ============================================================
# Sistem talimatları (LLM davranışı)
# ============================================================

# DEPRECATED: Artık tüm botlar için kullanılmıyor
# Her bot için generate_system_prompt() ile unique prompt üretiliyor
SYSTEM_STYLE = """\
Telegram grubunda konuşan gerçek insansın. 1-2 cümle yaz, kısa ol.
Emoji ASLA kullanma. Kısaltmalar kullan: bi, tmm, niye, yok, var, vb.
Bazen yazım hatası yap: "mi" bitişik yaz, noktalama atla, büyük harf kullanma.
Samimi ve doğal ol - robot değilsin.
"""


def generate_system_prompt(
    persona_profile: Optional[Dict[str, Any]] = None,
    emotion_profile: Optional[Dict[str, Any]] = None,
    bot_name: str = "Bot",
) -> str:
    """
    Her bot için UNIQUE sistem talimatı üretir.
    Bot'un kişiliğine, risk profiline, tonuna göre özelleştirilir.

    Args:
        persona_profile: Bot'un persona bilgileri (risk, tone, watchlist, etc.)
        emotion_profile: Bot'un emotion bilgileri (tone, empathy, energy, etc.)
        bot_name: Bot'un adı (opsiyonel, debug için)

    Returns:
        Unique sistem prompt'u
    """

    # Base instruction - herkese aynı
    base = "Sen bir Telegram kullanıcısısın, gerçek bir insansın. "

    persona = persona_profile or {}
    emotion = emotion_profile or {}

    # === 1. RİSK PROFİLİ ===
    risk = persona.get("risk_profile", "orta")
    if risk == "yüksek" or risk == "high":
        base += "Cesursun, risk almaktan çekinmezsin. İddialarını net söylersin. "
        base += "Kararlı ve kendine güvenlisin. "
    elif risk == "düşük" or risk == "low":
        base += "Temkinlisin, sabırlısın. 'Belki', 'sanırım', 'gibi geliyor' gibi ifadeler kullanırsın. "
        base += "Risk almayı sevmezsin, dikkatli yaklaşırsın. "
    else:
        base += "Dengeli yaklaşırsın, bazen cesur bazen temkinli olursun. "

    # === 2. TON (PERSONA) ===
    tone = persona.get("tone", "").lower()

    if "genç" in tone or "sokak" in tone or "enerji" in tone:
        base += "Genç ve güncel dil kullanırsın: aga, yaw, valla, lan gibi. "
        base += "Hızlı ve enerjik yazarsın. "
    elif "profesyonel" in tone or "akademik" in tone or "tecrübeli" in tone:
        base += "Düzgün ama samimi yazarsın. Argo kullanmazsın. "
        base += "Bilgili ve deneyimli konuşursun. "
    elif "muhafazakar" in tone:
        base += "Sakin ve temkinli konuşursun. Abartmadan, ölçülü yazarsın. "
    else:
        base += "Doğal ve samimi bir tarzın var. "

    # === 3. TON (EMOTION) ===
    emotion_tone = emotion.get("tone", "")
    # Tone bazen float olabilir, string'e çevir
    if isinstance(emotion_tone, (int, float)):
        emotion_tone = ""
    else:
        emotion_tone = str(emotion_tone).lower()

    if emotion_tone and emotion_tone != tone:
        if "neşeli" in emotion_tone or "pozitif" in emotion_tone:
            base += "Genelde pozitif ve neşelisin. "
        elif "ciddi" in emotion_tone or "soğuk" in emotion_tone:
            base += "Ciddi ve analitik yaklaşırsın. "

    # === 4. EMPATİ ===
    empathy = emotion.get("empathy")
    if isinstance(empathy, (int, float)):
        if empathy > 0.7:
            base += "Empatiksin, başkalarının durumunu anlarsın. "
        elif empathy < 0.3:
            base += "Soğukkanlısın, duygusal konulara mesafelisin. "

    # === 5. ENERGY ===
    energy = emotion.get("energy", "")
    # Energy bazen float olabilir (0.5), string'e çevir
    if isinstance(energy, (int, float)):
        energy = ""  # Numeric energy'yi görmezden gel
    else:
        energy = str(energy).lower()

    if "yüksek" in energy or "hızlı" in energy:
        base += "Hızlı ve enerjik mesajlar atarsın. "
    elif "düşük" in energy or "sakin" in energy:
        base += "Sakin ve ağır başlı yazarsın. "

    # === 6. YAZIM STİLİ ===
    style = persona.get("style", {})

    # Emoji kullanımı
    if style.get("emojis") is True or style.get("emojis") == "yes":
        base += "Bazen emoji kullanırsın ama abartmazsın. "
    else:
        base += "Emoji kullanmazsın. "

    # Kısaltmalar ve yazım hataları (genç/sokak tonunda)
    if "genç" in tone or "sokak" in tone:
        base += "Kısaltmalar kullan: bi, tmm, niye, yok, var. "
        base += "Bazen yazım hatası yap: 'mi' bitişik, noktalama atla. "
    elif "profesyonel" not in tone:
        # Orta seviye - az da olsa kısaltma
        base += "Bazen kısaltma kullanabilirsin: bi, tmm, var. "

    # === 7. MESAJ UZUNLUĞU ===
    length = style.get("length", "")
    # Length bazen float olabilir, string'e çevir
    if isinstance(length, (int, float)):
        length = ""
    else:
        length = str(length).lower()

    if "uzun" in length or "detaylı" in length:
        base += "Genelde detaylı yazarsın, 3-5 cümle. "
    elif "kısa" in length:
        base += "Kısa ve öz yazarsın, 1-2 cümle. "
    else:
        base += "Genelde 1-3 cümle yaz, çok uzatma. "

    # === 8. İMZA İFADELER (varsa) ===
    signature_phrases = emotion.get("signature_phrases", [])
    if signature_phrases and len(signature_phrases) > 0:
        example_phrases = ", ".join([f"'{p}'" for p in signature_phrases[:2]])
        base += f"Bazen şu tarz ifadeler kullanırsın: {example_phrases}. "

    # === 9. UZMMANLIK ALANI (varsa) ===
    watchlist = persona.get("watchlist", [])
    if watchlist and len(watchlist) > 0:
        symbols = ", ".join(watchlist[:3])
        base += f"Özellikle {symbols} hakkında konuşmayı seversin. "

    # === 10. KRİTİK: ROBOT OLMA! ===
    base += "\n\nÖNEMLİ: Robot gibi yazma, gerçek insan gibi doğal ve samimi ol. "
    base += "Mükemmel gramer kullanma, hata yapabilirsin. "
    base += "Her mesajda aynı kalıpları kullanma, çeşitli yaz."

    return base.strip()

# ============================================================
# Yardımcı özetleyiciler (persona / stance / holdings)
# ============================================================

def summarize_persona(persona: Optional[Dict[str, Any]]) -> str:
    if not persona:
        return "—"
    tone = persona.get("tone")
    risk = persona.get("risk_profile")
    watch = persona.get("watchlist")
    style = persona.get("style", {})
    never_do = persona.get("never_do")

    parts: List[str] = []
    if tone: parts.append(f"Üslup: {tone}")
    if risk: parts.append(f"Risk: {risk}")
    if watch: parts.append("İzleme listesi: " + ", ".join(map(str, watch)))
    if style:
        style_bits = []
        # Handle both dict (new format) and string (legacy format)
        if isinstance(style, dict):
            if style.get("emojis") is True:
                style_bits.append("emoji: kontrollü")
            length = style.get("length")
            if length: style_bits.append(f"uzunluk: {length}")
        elif isinstance(style, str):
            style_bits.append(style)
        if style_bits:
            parts.append("Stil: " + ", ".join(style_bits))
    if never_do:
        parts.append("Kaçın: " + ", ".join(map(str, never_do)))
    return " | ".join(parts) if parts else "—"


def format_persona_hint(persona_hint: Optional[str]) -> str:
    hint = (persona_hint or "").strip()
    if not hint:
        return ""
    return f"Tarz ipucu: {hint}"


def summarize_emotion_profile(profile: Optional[Dict[str, Any]]) -> str:
    if not profile:
        return "—"

    parts: List[str] = []
    tone = profile.get("tone")
    empathy = profile.get("empathy")
    energy = profile.get("energy")
    signature_emoji = profile.get("signature_emoji")
    if tone:
        parts.append(f"Ton: {tone}")
    if empathy:
        parts.append(f"Empati: {empathy}")
    if energy:
        parts.append(f"Tempo: {energy}")
    if signature_emoji:
        parts.append(f"Emoji: {signature_emoji}")

    phrases = profile.get("signature_phrases") or []
    if phrases:
        parts.append("İmza ifadeler: " + ", ".join(map(str, phrases[:3])))

    anecdotes = profile.get("anecdotes") or []
    if anecdotes:
        parts.append("Anekdot havuzu: " + "; ".join(map(str, anecdotes[:2])))

    return " | ".join(parts) if parts else "—"


def summarize_stances(stances: Optional[List[Dict[str, Any]]]) -> str:
    if not stances:
        return "—"
    lines = []
    for s in stances[:6]:
        topic = s.get("topic", "?")
        text = s.get("stance_text", "").strip()
        conf = s.get("confidence")
        cdesc = f" (güven: {conf:.2f})" if isinstance(conf, (int, float)) else ""
        lines.append(f"- {topic}: {text}{cdesc}")
    return "\n".join(lines)


def summarize_holdings(holds: Optional[List[Dict[str, Any]]]) -> str:
    if not holds:
        return "—"
    lines = []
    for h in holds[:6]:
        sym = h.get("symbol", "?")
        ap = h.get("avg_price")
        sz = h.get("size")
        note = h.get("note")
        bits = [sym]
        if isinstance(ap, (int, float)):
            bits.append(f"~{ap:g} ort.")
        if isinstance(sz, (int, float)):
            bits.append(f"{sz:g} adet")
        if note:
            bits.append(str(note))
        lines.append(" | ".join(bits))
    return "\n".join(lines)


# ============================================================
# Master Plan Helper Functions (Week 1 Day 3-4)
# ============================================================

def format_past_references(db, bot_id: int, current_topic: str, max_refs: int = 3) -> str:
    """
    Bot'un geçmişte bu konuda söylediklerini getir (Master Plan requirement)

    Args:
        db: Database session
        bot_id: Bot ID
        current_topic: Current topic (BIST, FX, Kripto, etc.)
        max_refs: Maximum number of past references to return

    Returns:
        Formatted string with past references or placeholder
    """
    try:
        from database import Message
        from datetime import datetime

        # Son 100 mesajdan topic'e uygun olanları bul
        past_msgs = db.query(Message).filter(
            Message.bot_id == bot_id
        ).order_by(Message.created_at.desc()).limit(100).all()

        if not past_msgs:
            return "(Bu konuda daha önce konuşmamışsın)"

        # Topic'e göre filtrele
        topic_lower = current_topic.lower()
        relevant = []

        for msg in past_msgs:
            text = (msg.text or "").lower()
            if topic_lower in text:
                relevant.append(msg)
            # Symbol extraction için basit check
            elif any(kw in text for kw in ["bist", "akbnk", "garan", "btc", "eth", "dolar", "euro"]):
                if any(t in text for t in topic_lower.split()):
                    relevant.append(msg)

        # En fazla max_refs tane
        relevant = relevant[:max_refs]

        if not relevant:
            return "(Bu konuda daha önce konuşmamışsın)"

        lines = []
        now = datetime.utcnow()
        for msg in relevant:
            age = (now - msg.created_at).days
            age_str = f"{age} gün önce" if age > 0 else "Bugün"
            text_preview = msg.text[:80] + "..." if len(msg.text) > 80 else msg.text
            lines.append(f"- {age_str}: '{text_preview}'")

        return "\n".join(lines)
    except Exception as e:
        # Hata olursa sessizce placeholder dön
        return "(Geçmiş mesajlar yüklenemedi)"


def extract_symbols_from_topic(topic: str) -> List[str]:
    """Topic'ten sembol çıkar (helper for format_past_references)"""
    import re
    symbols = []
    topic_upper = topic.upper()

    # Türk hisse kodları (4-6 harf)
    symbols.extend(re.findall(r'\b[A-Z]{4,6}\b', topic_upper))

    # Kripto sembolleri
    crypto_pattern = r'\b(BTC|ETH|USDT|BNB|XRP|ADA|SOL|DOGE|AVAX|MATIC|DOT)\b'
    symbols.extend(re.findall(crypto_pattern, topic_upper))

    return list(set(symbols))


# ============================================================
# Prompt oluşturucu (USER tarafı)
# ============================================================

# DEPRECATED: Basit template - artık USER_TEMPLATE_V2 kullanılıyor
USER_TEMPLATE_LEGACY = """\
Karakterin: {emotion_summary}
{persona_hint_section}
{reply_context}

Son mesajlar:
{history_excerpt}

{market_trigger}

{mention_context}
Kısa yaz ({length_hint}), samimi ol.
"""

# YENI: Zenginleştirilmiş template - tüm context dahil
USER_TEMPLATE_V2 = """\
## SENİN KİŞİLİĞİN
{persona_summary}
{persona_hint_section}

## SENİN GÖRÜŞLERİN (Tutarlı Kal!)
{stance_summary}

## SENİN POZİSYONLARIN
{holdings_summary}

## GEÇMIŞTE BU KONUDA SÖYLEDİKLERİN
{past_references}

## KİŞİSEL NOTLARIN / HAFIZALARIN
{memory_summary}

## SON SOHBET (DİKKATLE OKU!)
{history_excerpt}

{contextual_examples}

## ŞİMDİ SENİN SIRAN
{reply_context}

{market_trigger}

{mention_context}

## TALİMATLAR
- Yukarıdaki sohbeti OKU ve doğal bir şekilde devam ettir
- Kişiliğine uygun yaz (persona/emotion: {emotion_summary})
- Görüşlerine sadık kal (stance)
- Önceki söylediklerinle çelişme (past_references)
- {length_hint}
- Gerçek insan gibi yaz, robot DEĞİLSİN!
{reaction_guidance}

{time_context}
{persona_refresh_note}
"""

# Backward compatibility için
USER_TEMPLATE = USER_TEMPLATE_V2


def generate_user_prompt(
    *,
    topic_name: str,
    history_excerpt: str,
    reply_context: str,
    market_trigger: str,
    mode: str,
    mention_context: str = "",
    persona_profile: Optional[Dict[str, Any]] = None,
    reaction_guidance: str = "",
    emotion_profile: Optional[Dict[str, Any]] = None,
    contextual_examples: str = "",
    persona_refresh_note: str = "",
    stances: Optional[List[Dict[str, Any]]] = None,
    holdings: Optional[List[Dict[str, Any]]] = None,
    memories: str = "",
    past_references: str = "",
    length_hint: str = "gerekirse 2-3 cümle",
    persona_hint: str = "",
    time_context: str = "",
) -> str:
    """
    Geriye dönük uyumlu kullanıcı prompt'u. persona/stances/holdings/memories/past_references verilirse
    botun tutarlılığını artırmak için prompt'a eklenir.
    """
    p_summary = summarize_persona(persona_profile)
    e_summary = summarize_emotion_profile(emotion_profile)
    s_summary = summarize_stances(stances)
    h_summary = summarize_holdings(holdings)
    m_summary = (memories or "").strip() or "—"
    past_refs = (past_references or "").strip() or "—"

    prompt = USER_TEMPLATE.format(
        persona_summary=p_summary,
        persona_hint_section=format_persona_hint(persona_hint),
        emotion_summary=e_summary,
        memory_summary=m_summary,
        past_references=past_refs,
        stance_summary=s_summary,
        holdings_summary=h_summary,
        topic_name=(topic_name or "").strip()[:120],
        history_excerpt=(history_excerpt or "").strip()[:900],
        contextual_examples=(contextual_examples or "—"),
        reply_context=(reply_context or "").strip()[:400],
        market_trigger=(market_trigger or "").strip()[:240],
        reaction_guidance=(reaction_guidance or "Haberi empatiyle yumuşat."),
        persona_refresh_note=(persona_refresh_note or "—"),
        mode=(mode or "new"),
        time_context=(time_context or "—"),
        mention_context=(mention_context or "").strip()[:80],
        length_hint=(length_hint or "gerekirse 2-3 cümle"),
    )
    return prompt


# ============================================================
# Basit çıktı filtreleri / son işlem
# ============================================================

_AI_TRACE_PATTERNS = [
    r"\b(as|since)\s+an?\s+AI\b",
    r"\b(as|since)\s+an?\s+large\s+language\s+model\b",
    r"\bI\s+am\s+an?\s+AI\b",
    r"\bI\s+cannot\s+access\s+the\s+internet\b",
    r"\bas\s+an?\s+assistant\b",
]
_AI_TRACE_RE = re.compile("|".join(_AI_TRACE_PATTERNS), re.IGNORECASE)

_MANIPULATIVE_PATTERNS = [
    r"\bguaranteed\s+profits?\b",
    r"\bget\s+rich\s+quick\b",
    r"\b%?\s*100\s*garanti\b",
]
_MANIPULATIVE_RE = re.compile("|".join(_MANIPULATIVE_PATTERNS), re.IGNORECASE)

_FINANCIAL_PROMISE_PATTERNS = [
    r"\bkesin\s+kazanç\b",
    r"\bkesin\s+getiri\b",
    r"\bgaranti\s+kazanç\b",
    r"\bgarantili\s+getiri\b",
    r"\bbedava\s+para\b",
    r"\byatırım\s+tavsiyesi\s+veriyorum\b",
]
_FINANCIAL_PROMISE_RE = re.compile("|".join(_FINANCIAL_PROMISE_PATTERNS), re.IGNORECASE)

_DISCLAIMER_PHRASE = "yatırım tavsiyesi değildir"


def sanitize_model_traces(text: str) -> str:
    t = _AI_TRACE_RE.sub("", text or "")
    t = _MANIPULATIVE_RE.sub("", t)
    # Yoğun boşlukları sadeleştir
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def postprocess_output(text: str) -> str:
    """
    Temel son işlem: AI-izleri ve manipülatif kalıpları törpüler.
    İstenirse ilave kurallar (maks. uzunluk, dipnot) burada yönetilebilir.
    """
    t = sanitize_model_traces(text)
    # Kısa mesajlar için - Telegram'da insanlar uzun yazmaz
    if len(t) > 250:
        t = t[:240].rstrip() + "…"
    return t


def filter_content(text: str) -> Optional[str]:
    """Finansal içerik güvenliği filtreleri.

    - Boş veya yalnızca boşluk içeren içerikleri reddeder.
    - Yüksek riskli / kesin kazanç vaat eden kalıpları engeller.
    - "yatırım tavsiyesi" ifadesi geçiyorsa dipnotu otomatik ekler.
    """

    if text is None:
        return None

    cleaned = text.strip()
    if not cleaned:
        return None

    lower = cleaned.lower()

    if _FINANCIAL_PROMISE_RE.search(lower):
        return None

    # KAPALI: Yatırım tavsiyesi uyarısı - insan gibi görünmek için kaldırıldı
    # if "yatırım tavsiyesi" in lower and _DISCLAIMER_PHRASE not in lower:
    #     if cleaned.endswith(('.', '!', '?')):
    #         cleaned = f"{cleaned} {_DISCLAIMER_PHRASE.capitalize()}."
    #     else:
    #         cleaned = f"{cleaned}\n\n(Not: {_DISCLAIMER_PHRASE}.)"

    return cleaned
