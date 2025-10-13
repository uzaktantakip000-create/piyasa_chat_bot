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

DOĞAL KONUŞMA KURALLARI:
- Belirsizlik ve şüphe ifadeleri kullan: "Emin değilim ama...", "Belki yanılıyorum", "Kafam karışık açıkçası", "İki ateş arasında kaldım", "Tam karar veremedim"
- Bazen soru sor: "Sizce de öyle mi?", "Bu konuda ne düşünüyorsunuz?", "Daha önce deneyimleyen var mı?"
- Kendi görüşünü sorgula: "Acaba hata mı yapıyorum", "Belki fazla iyimserim", "Biraz abartmış olabilirim"
- Cümlelerini bazen tamamlama: "Yani... şey... ne desem", "BIST bugün... aslında bilmiyorum ki", "Hmm, nasıl açıklasam"
- Düzeltme yap: "Yanlış yazmışım, *doğrusu", "Pardon, demek istediğim...", "Dur, yanlış anladım"

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
# Prompt oluşturucu (USER tarafı)
# ============================================================

USER_TEMPLATE = """\
[PERSONA]
{persona_summary}
{persona_hint_section}

[DUYGU PROFİLİ]
{emotion_summary}

[STANCE]
{stance_summary}

[HOLDINGS]
{holdings_summary}

[KONU]
Şu konu üzerinde konuş: {topic_name}

[GEÇMİŞ DİYALOG TRANSKRİPTİ]
Aşağıdaki satırlar kronolojik sırada konuşmacı ve mesaj içerir.
Formatı aynen yorumla ve gerektiğinde doğrudan referans al (örn. "[Ali]: ..."):
{history_excerpt}

[ÖRNEK DİYALOG PARÇALARI]
{contextual_examples}

[CEVAP BAĞLAMI]
{reply_context}

[HABER/TETİKLEYİCİ]
{market_trigger}

[TEPKİ REHBERİ]
{reaction_guidance}

[PERSONA YENİLEME NOTU]
{persona_refresh_note}

[MOD]
{mode}  # "reply" ise kibarca yanıtla; "new" ise sohbeti doğal biçimde ilerlet.

[ZAMAN BAĞLAMI]
{time_context}

[EK TALİMAT]
- Aşırı iddiadan kaçın; rakam gerekiyorsa yuvarlak/bağlamsal anlatım tercih et.
- Kısa ve okunaklı yaz ({length_hint}). Gereksiz listeleme yapma.
- Eğer görüş, mevcut STANCE ile belirgin çelişiyorsa kısaca "nedenini" belirt veya tonunu yumuşat.
- Gerektiğinde "yatırım tavsiyesi değildir." cümlesini kısa bir not olarak ekleyebilirsin.
- Geçmiş diyalog satırlarının formatını bozma; gerektiğinde katılımcıları aynı etiketlerle an.
- SORU SORMA: %40 olasılıkla mesajını soru ile bitir veya başkalarının görüşünü sor. Örnek: "Siz ne düşünüyorsunuz?", "Sizce mantıklı mı?", "Başka ne önerirsiniz?"

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
    reaction_guidance: str = "",
    emotion_profile: Optional[Dict[str, Any]] = None,
    contextual_examples: str = "",
    persona_refresh_note: str = "",
    stances: Optional[List[Dict[str, Any]]] = None,
    holdings: Optional[List[Dict[str, Any]]] = None,
    length_hint: str = "gerekirse 2-3 cümle",
    persona_hint: str = "",
    time_context: str = "",
) -> str:
    """
    Geriye dönük uyumlu kullanıcı prompt'u. persona/stances/holdings verilirse
    botun tutarlılığını artırmak için prompt'a eklenir.
    """
    p_summary = summarize_persona(persona_profile)
    e_summary = summarize_emotion_profile(emotion_profile)
    s_summary = summarize_stances(stances)
    h_summary = summarize_holdings(holdings)

    prompt = USER_TEMPLATE.format(
        persona_summary=p_summary,
        persona_hint_section=format_persona_hint(persona_hint),
        emotion_summary=e_summary,
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
    # Aşırı uzun metni yumuşakça kısalt (Telegram okunabilirliği için)
    if len(t) > 900:
        t = t[:880].rstrip() + "…"
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

    # "yatırım tavsiyesi" ifadesi kullanılıyorsa, dipnotu ekle (tek seferlik).
    if "yatırım tavsiyesi" in lower and _DISCLAIMER_PHRASE not in lower:
        if cleaned.endswith(('.', '!', '?')):
            cleaned = f"{cleaned} {_DISCLAIMER_PHRASE.capitalize()}."
        else:
            cleaned = f"{cleaned}\n\n(Not: {_DISCLAIMER_PHRASE}.)"

    return cleaned
