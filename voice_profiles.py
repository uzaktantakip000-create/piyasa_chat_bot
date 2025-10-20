"""
Voice Profiles & Writing Style Module

PHASE 2 Week 3 Day 4-5: Her bot için unique yazı tarzı
Master Implementation Plan requirement

Bot'un persona ve emotion profiline göre unique voice profile oluşturur.
Kısaltma, emoji, yazım hatası, noktalama gibi özellikleri kontrol eder.
"""

import random
import re
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class VoiceProfile:
    """Bot'un yazı tarzı profili"""

    def __init__(self):
        # Frekanslar (0.0-1.0)
        self.slang_frequency = 0.0  # Kısaltma kullanım oranı
        self.emoji_frequency = 0.0  # Emoji kullanım oranı
        self.typo_frequency = 0.0  # Yazım hatası oranı
        self.punctuation_errors = 0.0  # Noktalama hatası oranı

        # İçerik
        self.abbreviations: List[str] = []  # Kullanılacak kısaltmalar
        self.favorite_emoji: Optional[str] = None  # İmza emoji
        self.sentence_starters: List[str] = []  # Cümle başlatıcılar
        self.certainty_level = 0.5  # 0=şüpheci, 1=kesin konuşan


class VoiceProfileGenerator:
    """Her bot için unique ses profili oluşturur"""

    def generate(self, bot) -> VoiceProfile:
        """
        Bot persona'sına göre voice profili oluştur

        Args:
            bot: Bot instance (persona_profile ve emotion_profile ile)

        Returns:
            VoiceProfile instance
        """
        profile = VoiceProfile()

        # Bot profiles'ı al
        persona = bot.persona_profile or {}
        emotion = bot.emotion_profile or {}

        # Tone ve risk profili
        tone = str(persona.get("tone", "")).lower()
        risk = persona.get("risk_profile", "orta")
        if isinstance(risk, str):
            risk = risk.lower()

        # === 1. KELIME SEÇİMİ (SLANG & ABBREVIATIONS) ===
        if "genç" in tone or "sokak" in tone or "enerjik" in tone:
            profile.slang_frequency = 0.4
            profile.emoji_frequency = 0.3
            profile.abbreviations = ["bi", "tmm", "niye", "yok", "var", "aga", "valla", "la", "lan"]
        elif "profesyonel" in tone or "akademik" in tone or "tecrübeli" in tone:
            profile.slang_frequency = 0.05
            profile.emoji_frequency = 0.02
            profile.abbreviations = []  # Profesyonel: kısaltma yok
        else:
            # Orta seviye
            profile.slang_frequency = 0.2
            profile.emoji_frequency = 0.15
            profile.abbreviations = ["bi", "tmm", "yok", "var"]

        # === 2. CÜMLE BAŞLANGIÇLARI (CERTAINTY) ===
        if risk == "yüksek" or risk == "high":
            profile.sentence_starters = ["Bence", "Kesin", "Muhakkak", "Garantili", "Net", "Kesinlikle"]
            profile.certainty_level = 0.85
        elif risk == "düşük" or risk == "low":
            profile.sentence_starters = ["Belki", "Sanırım", "Gibi geliyor", "Emin değilim ama", "Olabilir", "Sanki"]
            profile.certainty_level = 0.3
        else:
            # Orta risk
            profile.sentence_starters = ["Bana göre", "Düşünüyorum ki", "Sanırım", "Bence", "Galiba"]
            profile.certainty_level = 0.6

        # === 3. YAZIM HATALARI ===
        if "genç" in tone or "enerjik" in tone:
            profile.typo_frequency = 0.15  # %15 hata
            profile.punctuation_errors = 0.3  # %30 noktalama hatası
        elif "profesyonel" in tone or "akademik" in tone:
            profile.typo_frequency = 0.0  # Profesyonel: hata yok
            profile.punctuation_errors = 0.0
        else:
            profile.typo_frequency = 0.05  # %5 hata
            profile.punctuation_errors = 0.1  # %10 noktalama hatası

        # === 4. EMOJİ ===
        signature_emoji = emotion.get("signature_emoji")
        if signature_emoji and isinstance(signature_emoji, str):
            profile.favorite_emoji = signature_emoji

        logger.debug(
            f"Voice profile generated: slang={profile.slang_frequency:.2f}, "
            f"emoji={profile.emoji_frequency:.2f}, typo={profile.typo_frequency:.2f}"
        )

        return profile

    def apply_voice(self, message: str, voice: VoiceProfile, bot_id: int = 0) -> str:
        """
        Mesaja ses profili uygula

        P0.3: Deterministic transformations using bot_id as seed

        Kısaltma, emoji, yazım hatası, noktalama hataları ekler.

        Args:
            message: Orijinal mesaj
            voice: Voice profile
            bot_id: Bot ID for deterministic seed (P0.3)

        Returns:
            Transformed message
        """
        if not message or not message.strip():
            return message

        # P0.3: Use bot_id + message hash as seed for deterministic behavior
        message_hash = hash(message + str(bot_id))
        rng = random.Random(message_hash)  # Deterministic RNG

        transformed = message

        # === 1. KISALTMALAR EKLE ===
        if voice.abbreviations and rng.random() < voice.slang_frequency:
            # Kısaltma transformations
            transforms = {
                r'\bbir\b': 'bi',
                r'\btamam\b': 'tmm',
                r'\byoktur\b': 'yok',
                r'\bniçin\b': 'niye',
                r'\bneden\b': 'niye',
                r'\bvardır\b': 'var',
            }

            # Deterministic 1-2 transform uygula
            for pattern, replacement in transforms.items():
                if rng.random() < 0.5:
                    transformed = re.sub(pattern, replacement, transformed, count=1, flags=re.IGNORECASE)

        # === 2. YAZIM HATALARI (mi/mı bitişik) ===
        if voice.typo_frequency > 0 and rng.random() < voice.typo_frequency:
            # Soru eklerini bitişik yaz
            transformed = re.sub(r'\s+(mi|mı|mu|mü)\b', r'\1', transformed)

        # === 3. NOKTALAMA HATALARI ===
        if voice.punctuation_errors > 0 and rng.random() < voice.punctuation_errors:
            # Nokta veya virgül atla
            if rng.random() < 0.5:
                transformed = re.sub(r'\.$', '', transformed)  # Son noktayı sil
            else:
                transformed = re.sub(r',', '', transformed, count=1)  # İlk virgülü sil

        # === 4. BÜYÜK HARF HATALARI ===
        if voice.typo_frequency > 0 and rng.random() < voice.typo_frequency:
            # İlk harfi küçük yap
            if transformed and transformed[0].isupper():
                transformed = transformed[0].lower() + transformed[1:]

        # === 5. EMOJİ EKLE ===
        if voice.favorite_emoji and rng.random() < voice.emoji_frequency:
            # Sona emoji ekle
            transformed = transformed.rstrip() + f" {voice.favorite_emoji}"

        # === 6. CÜMLE BAŞLATICI EKLE (bazen) ===
        if voice.sentence_starters and rng.random() < 0.25:  # %25 ihtimal
            starter = rng.choice(voice.sentence_starters)

            # Zaten başlamıyorsa ekle
            if not transformed.lower().startswith(starter.lower()):
                # İlk harfi küçük yap ve başlatıcı ekle
                if transformed:
                    first_char = transformed[0].lower() if transformed[0].isupper() else transformed[0]
                    transformed = f"{starter}, {first_char}{transformed[1:]}"

        return transformed


# Test function
def test_voice_profiles():
    """Test voice profile generation and application"""
    from database import SessionLocal, Bot

    db = SessionLocal()
    try:
        # İlk botu al
        bot = db.query(Bot).first()
        if not bot:
            print("❌ No bots found in database")
            return

        # Voice profile oluştur
        generator = VoiceProfileGenerator()
        voice = generator.generate(bot)

        print(f"\n📊 Voice Profile for Bot: {bot.name}")
        print(f"  - Slang frequency: {voice.slang_frequency:.2%}")
        print(f"  - Emoji frequency: {voice.emoji_frequency:.2%}")
        print(f"  - Typo frequency: {voice.typo_frequency:.2%}")
        print(f"  - Punctuation errors: {voice.punctuation_errors:.2%}")
        print(f"  - Favorite emoji: {voice.favorite_emoji}")
        print(f"  - Sentence starters: {', '.join(voice.sentence_starters[:3])}")

        # Test mesajları
        test_messages = [
            "Merhaba, bugün borsa çok iyi yükseldi.",
            "Ben bir pozisyon aldım, ne düşünüyorsunuz?",
            "Dolar yükseldi mi, yoktur galiba.",
        ]

        print(f"\n📝 Sample Transformations:")
        for msg in test_messages:
            transformed = generator.apply_voice(msg, voice)
            print(f"  Original:    {msg}")
            print(f"  Transformed: {transformed}\n")

    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_voice_profiles()
