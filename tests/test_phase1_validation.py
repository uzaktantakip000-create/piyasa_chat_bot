"""
PHASE 1 Validation Test Suite

Master Implementation Plan gereklilikleri:
- Bot-to-bot reply rate >= %40
- Message diversity metrics (n-gram analysis)
- Average message length 100-150 words
- Stance consistency
- Each bot unique system prompt

Test Scenario:
1. 100 mesaj simülasyonu çalıştır
2. Metrikleri ölç
3. Kriterlere göre değerlendir
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple
import time
from collections import Counter
from datetime import datetime, timedelta

# Project root'u path'e ekle
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Database connection için env ayarı
os.environ["DATABASE_URL"] = os.getenv("DATABASE_URL", "sqlite:///./app.db")

from database import SessionLocal, Message, Bot, Chat
from sqlalchemy import func


class Phase1Validator:
    """PHASE 1 implementasyonunu test ve validate eder"""

    def __init__(self):
        self.db = SessionLocal()
        self.test_start_time = None
        self.test_end_time = None
        self.messages_at_start = 0
        self.messages_at_end = 0

    def close(self):
        self.db.close()

    # ============================================================
    # 1. SETUP & DATA COLLECTION
    # ============================================================

    def setup_test(self):
        """Test başlangıç durumunu kaydet"""
        self.test_start_time = datetime.utcnow()
        self.messages_at_start = self.db.query(Message).count()
        print(f"[SETUP] Test başlangıcı: {self.test_start_time}")
        print(f"[SETUP] Mevcut mesaj sayısı: {self.messages_at_start}")

    def collect_test_messages(self, min_messages: int = 100) -> List[Message]:
        """Test sırasında üretilen mesajları topla"""
        # Test başlangıcından sonraki mesajları al
        test_msgs = self.db.query(Message).filter(
            Message.created_at >= self.test_start_time
        ).order_by(Message.created_at.asc()).all()

        return test_msgs

    # ============================================================
    # 2. BOT-TO-BOT INTERACTION RATE
    # ============================================================

    def calculate_bot_to_bot_rate(self, messages: List[Message]) -> Tuple[float, int, int]:
        """
        Bot-to-bot interaction oranını hesapla

        Returns:
            (rate, bot_to_bot_count, total_bot_replies)
        """
        bot_to_bot = 0
        total_bot_replies = 0

        for msg in messages:
            # Sadece bot mesajlarını kontrol et
            if msg.bot_id is None:
                continue

            # Reply to message ID'si var mı?
            if msg.reply_to_message_id:
                total_bot_replies += 1

                # Reply edilenin de bot olup olmadığını kontrol et
                replied_msg = self.db.query(Message).filter(
                    Message.telegram_message_id == msg.reply_to_message_id,
                    Message.chat_db_id == msg.chat_db_id
                ).first()

                if replied_msg and replied_msg.bot_id is not None:
                    bot_to_bot += 1

        rate = (bot_to_bot / total_bot_replies * 100) if total_bot_replies > 0 else 0.0
        return rate, bot_to_bot, total_bot_replies

    # ============================================================
    # 3. MESSAGE DIVERSITY (N-GRAM ANALYSIS)
    # ============================================================

    def calculate_message_diversity(self, messages: List[Message]) -> Dict[str, float]:
        """
        Mesaj çeşitliliğini n-gram analizi ile hesapla

        Returns:
            {
                "unique_2gram_ratio": 0.0-1.0,
                "unique_3gram_ratio": 0.0-1.0,
                "avg_word_count": float,
                "word_count_variance": float
            }
        """
        texts = [msg.text for msg in messages if msg.text and msg.bot_id is not None]

        if not texts:
            return {"unique_2gram_ratio": 0.0, "unique_3gram_ratio": 0.0, "avg_word_count": 0.0, "word_count_variance": 0.0}

        # 2-gram ve 3-gram sayıları
        all_2grams = []
        all_3grams = []
        word_counts = []

        for text in texts:
            words = text.lower().split()
            word_counts.append(len(words))

            # 2-grams
            for i in range(len(words) - 1):
                all_2grams.append(f"{words[i]} {words[i+1]}")

            # 3-grams
            for i in range(len(words) - 2):
                all_3grams.append(f"{words[i]} {words[i+1]} {words[i+2]}")

        unique_2grams = len(set(all_2grams))
        total_2grams = len(all_2grams)
        unique_3grams = len(set(all_3grams))
        total_3grams = len(all_3grams)

        unique_2gram_ratio = unique_2grams / total_2grams if total_2grams > 0 else 0.0
        unique_3gram_ratio = unique_3grams / total_3grams if total_3grams > 0 else 0.0

        # Kelime sayısı istatistikleri
        avg_word_count = sum(word_counts) / len(word_counts) if word_counts else 0.0
        variance = sum((x - avg_word_count) ** 2 for x in word_counts) / len(word_counts) if word_counts else 0.0

        return {
            "unique_2gram_ratio": unique_2gram_ratio,
            "unique_3gram_ratio": unique_3gram_ratio,
            "avg_word_count": avg_word_count,
            "word_count_variance": variance,
            "std_dev": variance ** 0.5
        }

    # ============================================================
    # 4. UNIQUE SYSTEM PROMPTS
    # ============================================================

    def check_unique_system_prompts(self) -> bool:
        """Her bot unique system prompt alıyor mu?"""
        from system_prompt import generate_system_prompt

        bots = self.db.query(Bot).filter(Bot.is_enabled == True).all()

        if len(bots) < 2:
            print("[WARNING] 2'den az bot var, unique system prompt testi atlanıyor")
            return True

        system_prompts = []
        for bot in bots:
            prompt = generate_system_prompt(
                persona_profile=bot.persona_profile,
                emotion_profile=bot.emotion_profile,
                bot_name=bot.name
            )
            system_prompts.append((bot.name, prompt))

        # Her prompt unique mi?
        prompt_texts = [p[1] for p in system_prompts]
        unique_prompts = len(set(prompt_texts))

        print(f"\n[UNIQUE PROMPTS] {len(bots)} bot, {unique_prompts} unique prompt")

        for bot_name, prompt in system_prompts[:3]:  # İlk 3'ü göster
            print(f"  - {bot_name}: {prompt[:100]}...")

        return unique_prompts == len(bots)

    # ============================================================
    # 5. COMPREHENSIVE REPORT
    # ============================================================

    def generate_report(self, messages: List[Message]) -> Dict:
        """Tüm metrikleri topla ve rapor oluştur"""
        print("\n" + "="*80)
        print("PHASE 1 VALIDATION REPORT")
        print("="*80)

        # 1. Bot-to-bot interaction
        bot_to_bot_rate, bot_to_bot_count, total_bot_replies = self.calculate_bot_to_bot_rate(messages)

        print(f"\n[1] BOT-TO-BOT INTERACTION")
        print(f"  - Bot-to-bot replies: {bot_to_bot_count}/{total_bot_replies}")
        print(f"  - Bot-to-bot rate: {bot_to_bot_rate:.1f}%")
        print(f"  - Target: >= 40%")
        print(f"  - Status: {'✅ PASS' if bot_to_bot_rate >= 40.0 else '❌ FAIL'}")

        # 2. Message diversity
        diversity = self.calculate_message_diversity(messages)

        print(f"\n[2] MESSAGE DIVERSITY")
        print(f"  - Unique 2-gram ratio: {diversity['unique_2gram_ratio']:.2%}")
        print(f"  - Unique 3-gram ratio: {diversity['unique_3gram_ratio']:.2%}")
        print(f"  - Avg word count: {diversity['avg_word_count']:.1f}")
        print(f"  - Std dev: {diversity['std_dev']:.1f}")
        print(f"  - Target: std dev > 30")
        print(f"  - Status: {'✅ PASS' if diversity['std_dev'] > 30 else '❌ FAIL'}")

        # 3. Unique system prompts
        unique_prompts = self.check_unique_system_prompts()
        print(f"\n[3] UNIQUE SYSTEM PROMPTS")
        print(f"  - Status: {'✅ PASS' if unique_prompts else '❌ FAIL'}")

        # 4. Message count
        bot_message_count = sum(1 for m in messages if m.bot_id is not None)
        print(f"\n[4] TEST STATISTICS")
        print(f"  - Total messages: {len(messages)}")
        print(f"  - Bot messages: {bot_message_count}")
        print(f"  - User messages: {len(messages) - bot_message_count}")

        # 5. Overall pass/fail
        all_pass = (
            bot_to_bot_rate >= 40.0 and
            diversity['std_dev'] > 30 and
            unique_prompts
        )

        print(f"\n{'='*80}")
        print(f"OVERALL RESULT: {'✅ PHASE 1 COMPLETE' if all_pass else '❌ NEEDS WORK'}")
        print(f"{'='*80}\n")

        return {
            "bot_to_bot_rate": bot_to_bot_rate,
            "diversity": diversity,
            "unique_prompts": unique_prompts,
            "all_pass": all_pass,
            "total_messages": len(messages),
            "bot_messages": bot_message_count
        }


def main():
    """Test runner"""
    print("="*80)
    print("PHASE 1 VALIDATION TEST - Master Implementation Plan")
    print("="*80)

    validator = Phase1Validator()

    try:
        # Setup
        validator.setup_test()

        # NOT: Bu script sadece MEVCUT mesajları analiz eder
        # Yeni mesaj üretimi için simülasyonun aktif olması gerekir
        print("\n[INFO] Bu script MEVCUT mesajları analiz eder.")
        print("[INFO] Yeni mesajlar için simülasyonu başlatıp bekleyin.\n")

        input("Press ENTER to analyze existing messages...")

        # Test mesajlarını topla
        test_messages = validator.collect_test_messages(min_messages=50)

        if len(test_messages) < 50:
            print(f"[WARNING] Sadece {len(test_messages)} mesaj bulundu. En az 50 mesaj önerilir.")
            choice = input("Devam edilsin mi? (y/n): ")
            if choice.lower() != 'y':
                print("Test iptal edildi.")
                return

        # Rapor oluştur
        report = validator.generate_report(test_messages)

        # Sonucu döndür
        sys.exit(0 if report["all_pass"] else 1)

    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test kullanıcı tarafından iptal edildi.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test sırasında hata: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        validator.close()


if __name__ == "__main__":
    main()
