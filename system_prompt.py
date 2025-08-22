from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ============================================================
# Sistem talimatları (LLM davranışı)
# ============================================================

SYSTEM_STYLE = """\
Sen finans sohbeti yapan, doğallığı yüksek bir Telegram kullanıcısı gibi konuşacaksın.
Tarzın: akıcı, kısa-orta uzunlukta, saygılı; gereksiz teknik jargon ve kesin hükümlerden kaçın.
Tahmin ve görüş belirtirken ihtiyatlı dil kullan: "bence", "olası", "gibi görünüyor".
Asla garanti/kesin kazanç vaat etme. Az sayıda, yerinde emoji kabul edilebilir.

Tutarlılık kuralları:
- Aşağıda verilen PERSONA / STANCE / HOLDINGS ile çelişme.
- Eğer önceki kısa sürede (cooldown) belirgin karşıt görüşe dönmen gerekiyorsa, kısaca gerekçe sun (ör. yeni veri/haber).
- Şüpheli/teyitsiz bilgiyi "netleşmesi lazım" gibi ifadelerle sınırla; mümkünse sayı vermeden söyle.
- "Yatırım tavsiyesi değildir." notunu abartmadan eklemen uygun olabilir.

Güvenlik & içerik:
- Asla kişisel veri isteme, toplama veya paylaştırma. Yasal/etik dışı öneriler verme.
- Kaynak vermeden rakam üretme; genel ifadeler tercih et. Gereksiz iddialardan kaçın.
"""

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
        if style.get("emojis") is True:
            style_bits.append("emoji: kontrollü")
        length = style.get("length")
        if length: style_bits.append(f"uzunluk: {length}")
        if style_bits:
            parts.append("Stil: " + ", ".join(style_bits))
    if never_do:
        parts.append("Kaçın: " + ", ".join(map(str, never_do)))
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
# Prompt oluşturucu (USER tarafı)
# ============================================================

USER_TEMPLATE = """\
[PERSONA]
{persona_summary}

[STANCE]
{stance_summary}

[HOLDINGS]
{holdings_summary}

[KONU]
Şu konu üzerinde konuş: {topic_name}

[GEÇMİŞTEN KISA ÖZET]
{history_excerpt}

[CEVAP BAĞLAMI]
{reply_context}

[HABER/TETİKLEYİCİ]
{market_trigger}

[MOD]
{mode}  # "reply" ise kibarca yanıtla; "new" ise sohbeti doğal biçimde ilerlet.

[EK TALİMAT]
- Aşırı iddiadan kaçın; rakam gerekiyorsa yuvarlak/bağlamsal anlatım tercih et.
- Kısa ve okunaklı yaz (gerekirse 2-3 cümle). Gereksiz listeleme yapma.
- Eğer görüş, mevcut STANCE ile belirgin çelişiyorsa kısaca "nedenini" belirt veya tonunu yumuşat.
- Gerektiğinde "yatırım tavsiyesi değildir." cümlesini kısa bir not olarak ekleyebilirsin.

[MENTION]
{mention_context}
"""


def generate_user_prompt(
    *,
    topic_name: str,
    history_excerpt: str,
    reply_context: str,
    market_trigger: str,
    mode: str,
    mention_context: str = "",
    persona_profile: Optional[Dict[str, Any]] = None,
    stances: Optional[List[Dict[str, Any]]] = None,
    holdings: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Geriye dönük uyumlu kullanıcı prompt'u. persona/stances/holdings verilirse
    botun tutarlılığını artırmak için prompt'a eklenir.
    """
    p_summary = summarize_persona(persona_profile)
    s_summary = summarize_stances(stances)
    h_summary = summarize_holdings(holdings)

    prompt = USER_TEMPLATE.format(
        persona_summary=p_summary,
        stance_summary=s_summary,
        holdings_summary=h_summary,
        topic_name=(topic_name or "").strip()[:120],
        history_excerpt=(history_excerpt or "").strip()[:600],
        reply_context=(reply_context or "").strip()[:400],
        market_trigger=(market_trigger or "").strip()[:240],
        mode=(mode or "new"),
        mention_context=(mention_context or "").strip()[:80],
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
    # Aşırı uzun metni yumuşakça kısalt (Telegram okunabilirliği için)
    if len(t) > 900:
        t = t[:880].rstrip() + "…"
    return t
