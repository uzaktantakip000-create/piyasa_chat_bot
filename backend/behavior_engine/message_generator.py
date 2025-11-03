"""
Message Generation Functions

Functions for generating and enhancing messages with natural language behaviors,
consistency guards, and micro-behaviors.

Extracted from behavior_engine.py (Session 17 - Modularization Phase 1)
"""

import random
import re
from typing import Any, Dict, List, Optional

from backend.behavior import ReactionPlan
from llm_client import LLMClient
from system_prompt import summarize_persona, summarize_stances


# ==============================================================================
# Consistency & Reaction Application
# ==============================================================================

def apply_consistency_guard(
    llm: LLMClient,
    *,
    draft_text: str,
    persona_profile: Dict[str, Any],
    stances: List[Dict[str, Any]],
) -> Optional[str]:
    """
    LLM çıktısını persona/stance ile karşılaştırıp bariz çelişki varsa nazikçe düzeltir.
    Çelişki yoksa None döndürerek mevcut metnin kullanılmasını önerir.

    Args:
        llm: LLM client instance
        draft_text: Draft message text
        persona_profile: Bot persona profile
        stances: Bot stances list

    Returns:
        Revised text if inconsistency found, None otherwise
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
    revised = llm.generate(user_prompt=guard_prompt, temperature=0.3, max_tokens=220)
    if not revised:
        return None

    # Eğer çıktı DRAFT ile neredeyse aynıysa değişiklik yapmamış say
    if revised.strip() == draft_text.strip():
        return None

    return revised


def apply_reaction_overrides(text: str, plan: ReactionPlan) -> str:
    """
    Apply reaction plan (signature phrases, anecdotes, emojis) to message text.

    Args:
        text: Message text
        plan: Reaction plan with phrases/anecdotes/emojis

    Returns:
        Enhanced message text
    """
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


def apply_micro_behaviors(
    text: str,
    *,
    emotion_profile: Dict[str, Any],
    plan: ReactionPlan,
) -> str:
    """
    Apply micro-behaviors (ellipsis, emoji positioning) based on emotion.

    Args:
        text: Message text
        emotion_profile: Bot emotion profile
        plan: Reaction plan

    Returns:
        Text with micro-behaviors applied
    """
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


def paraphrase_safe(llm: LLMClient, text: str) -> Optional[str]:
    """
    Basit yeniden yazım; anlamı korur, tekrar algılamayı aşmaya çalışır.

    Args:
        llm: LLM client instance
        text: Text to paraphrase

    Returns:
        Paraphrased text or None
    """
    prompt = f"""Metni aynı anlamla, 1-2 kısa cümlede farklı ifade et; iddialı/kesin ton kullanma:

METİN:
{text}
"""
    return llm.generate(user_prompt=prompt, temperature=0.4, max_tokens=120)


# ==============================================================================
# Natural Language Enhancements
# ==============================================================================

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


def add_filler_words(text: str, probability: float = 0.20) -> str:
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
