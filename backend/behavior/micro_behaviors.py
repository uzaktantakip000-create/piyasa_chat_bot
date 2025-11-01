"""
Micro-behaviors module for natural text enhancement

This module provides functions to add human-like imperfections,
conversational style, and natural language patterns to generated messages.

Functions:
- generate_time_context(): Time-of-day context generation
- add_conversation_openings(): Natural conversation starters
- add_hesitation_markers(): Uncertainty and hedging expressions
- add_colloquial_shortcuts(): Informal shortcuts and contractions
- apply_natural_imperfections(): Typos with corrections

Extracted from behavior_engine.py (lines 495-794)
"""

import random
import re
from datetime import datetime


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


__all__ = [
    "generate_time_context",
    "add_conversation_openings",
    "add_hesitation_markers",
    "add_colloquial_shortcuts",
    "apply_natural_imperfections",
]
