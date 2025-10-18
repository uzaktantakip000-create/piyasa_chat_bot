# 🚀 piyasa_chat_bot v2.0 - Master Implementation Plan

**Tarih:** 18 Ekim 2025
**Versiyon:** 2.0 Master Roadmap
**Strateji:** Quick Wins → Progressive Architecture Evolution
**Toplam Süre:** 10 hafta (opsiyonel 12 hafta)

---

## 🎯 Executive Summary

Bu plan, **version_update_todo.md** ve **system_architecture_v2.md** dokümanlarını birleştirerek öncelik sırasına göre yeniden yapılandırılmıştır.

### **Ana Strateji:**
1. **Hızlı Kazanımlar İlk** (Week 1-2): Mimari değişiklik gerektirmeyen kritik düzeltmeler
2. **Doğallık ve Çeşitlilik** (Week 3-4): Monolitik sistemde kaliteli iyileştirmeler
3. **Mikroservis Temeli** (Week 5-6): Mimari geçiş başlangıcı
4. **Gelişmiş Özellikler** (Week 7-10): Departman sistemleri ve zekâ katmanı

### **Kritik Metrikler:**

| Metrik | Mevcut | Week 2 Hedef | Week 10 Hedef |
|--------|--------|--------------|---------------|
| Bot-to-bot reply rate | ~10% | **40%** | **70%** |
| Message diversity | ~40% | **60%** | **85%** |
| Naturalness score | 3/10 | **6/10** | **9/10** |
| News-driven debates | ~5% | **25%** | **60%** |
| Conversation chain depth | 1-2 | **3-4** | **6-8** |

---

## 🔴 PHASE 1: Critical Fixes & Quick Wins (Week 1-2)

**Hedef:** Robot davranışını hemen düzeltecek kritik güncellemeler
**Risk:** Düşük (kod değişiklikleri, mimari değişiklik yok)
**ROI:** ⭐⭐⭐⭐⭐ ÇOOK YÜKSEK

### **Week 1: Prompt Engineering Overhaul**

#### **Day 1-2: System Prompt Revolution**
**Dosya:** `system_prompt.py` (tamamen yeniden yaz)

- [x] **SORUN:** Tüm botlar aynı system prompt'u alıyor → robotik
- [x] **ÇÖZÜM:** Her bot için dinamik system prompt

**İmplementasyon:**

```python
def generate_system_prompt(bot_profile: dict) -> str:
    """Her bot için unique sistem talimatı"""

    base = "Sen bir Telegram kullanıcısısın, gerçek bir insansın. "

    # Risk profili
    risk = bot_profile.get("risk_profile", "orta")
    if risk == "yüksek":
        base += "Cesursun, risk almaktan çekinmezsin. İddialarını net söylersin. "
    elif risk == "düşük":
        base += "Temkinlisin, sabırlısın. 'Belki', 'sanırım' gibi ifadeler kullanırsın. "
    else:
        base += "Dengeli yaklaşırsın, bazen cesur bazen temkinli olursun. "

    # Ton
    tone = bot_profile.get("tone", "").lower()
    if "genç" in tone or "sokak" in tone:
        base += "Güncel dil kullanırsın: aga, yaw, valla, lan gibi. "
    elif "profesyonel" in tone:
        base += "Düzgün ama samimi yazarsın. Argo kullanmazsın. "

    # Yazım stili
    style = bot_profile.get("style", {})
    if style.get("emojis"):
        base += "Bazen emoji kullanırsın ama abartmazsın. "
    else:
        base += "Emoji kullanmazsın. "

    if "genç" in tone:
        base += "Kısaltmalar kullan: bi, tmm, niye, yok, var. Bazen yazım hatası yap: 'mi' bitişik, noktalama atla. "

    # Mesaj uzunluğu
    base += "Genelde 1-3 cümle yaz, çok uzatma. "

    # Önemli: Robot olma
    base += "\n\nÖNEMLİ: Robot gibi yazma. Gerçek insan gibi doğal, samimi ol. Mükemmel gramer kullanma."

    return base
```

**Test Kriteri:** 10 farklı bot için 10 mesaj üret, her bot'un system prompt'u benzersiz olmalı

---

#### **Day 3-4: Rich User Prompt Template**
**Dosya:** `system_prompt.py` (USER_TEMPLATE_V2)

- [x] **SORUN:** Template çok basit, çoğu context kullanılmıyor
- [x] **ÇÖZÜM:** Tüm context bilgilerini dahil et

**Yeni Template:**

```python
USER_TEMPLATE_V2 = """
## SENİN KİŞİLİĞİN
{persona_full_description}

## SENİN GÖRÜŞLERİN (Tutarlı Kal!)
{stance_summary}

## SENİN POZİSYONLARIN
{holdings_summary}

## GEÇMIŞTE BU KONUDA SÖYLEDİKLERİN
{past_references}

## SON SOHBET (DİKKATLE OKU!)
{history_excerpt}

## ŞİMDİ SENİN SIRAN
{reply_instruction}

{market_news_if_any}

## TALİMATLAR
- Yukarıdaki sohbeti OKU, doğal devam ettir
- Kişiliğine uygun yaz (persona/emotion)
- Görüşlerine sadık kal (stance)
- Önceki söylediklerinle çelişme (past_references)
- {length_hint}
- Gerçek insan gibi yaz, robot DEĞİLSİN!

{time_context}
{contextual_examples}
"""
```

**Helper Functions:**

```python
def format_persona_full(persona_profile: dict) -> str:
    """Persona'yı zengin formatta döndür"""
    parts = []

    if "tone" in persona_profile:
        parts.append(f"Tarzın: {persona_profile['tone']}")

    if "risk_profile" in persona_profile:
        parts.append(f"Risk iştahın: {persona_profile['risk_profile']}")

    if "watchlist" in persona_profile:
        symbols = ", ".join(persona_profile["watchlist"][:5])
        parts.append(f"Takip ettiğin hisseler: {symbols}")

    if "never_do" in persona_profile:
        parts.append(f"Asla yapmazsın: {', '.join(persona_profile['never_do'])}")

    return "\n".join(parts)

def format_stances(stances: List[BotStance]) -> str:
    """Stance'ları okunabilir formatta"""
    if not stances:
        return "(Belirgin bir görüşün yok)"

    lines = []
    for stance in stances[:5]:  # İlk 5
        confidence = "⭐⭐⭐" if stance.confidence > 0.8 else "⭐⭐" if stance.confidence > 0.5 else "⭐"
        lines.append(f"- {stance.topic}: {stance.stance_text} {confidence}")

    return "\n".join(lines)

def format_past_references(db, bot_id: int, current_topic: str) -> str:
    """Bot'un geçmişte bu konuda söylediklerini getir"""
    # Son 100 mesajdan topic'e uygun olanları bul
    past_msgs = db.query(Message).filter(
        Message.bot_id == bot_id
    ).order_by(Message.created_at.desc()).limit(100).all()

    relevant = [
        msg for msg in past_msgs
        if current_topic.lower() in msg.text.lower() or
        any(sym in msg.text for sym in extract_symbols_from_topic(current_topic))
    ][:3]

    if not relevant:
        return "(Bu konuda daha önce konuşmamışsın)"

    lines = []
    for msg in relevant:
        age = (datetime.now() - msg.created_at).days
        lines.append(f"- {age} gün önce: '{msg.text[:80]}...'")

    return "\n".join(lines)
```

**Test Kriteri:** Template'deki her `{placeholder}` dolu olmalı, boş olmamalı

---

#### **Day 5-7: LLM Parameter Optimization**
**Dosya:** `llm_client.py`, `behavior_engine.py:2442`

- [x] **SORUN:** max_tokens=80 (çok düşük), diversity parametreleri yok
- [x] **ÇÖZÜM:** Dinamik token limiti, temperature range, frequency_penalty

**Değişiklik:**

```python
# behavior_engine.py - tick_once() içinde
def generate_message_params(self, bot: Bot, context: dict) -> dict:
    """Bot ve context'e göre LLM parametreleri"""

    persona = bot.persona_profile

    # Max tokens (bot persona'ya göre)
    tone = persona.get("tone", "").lower()
    if "akademik" in tone or "tecrübeli" in tone:
        max_tokens = random.randint(150, 250)  # Uzun mesajlar
    elif "genç" in tone or "enerjik" in tone:
        max_tokens = random.randint(80, 150)  # Kısa-orta
    else:
        max_tokens = random.randint(100, 200)  # Orta

    # Temperature (çeşitlilik için yüksek)
    base_temp = float(self.settings.get("base_temperature", 1.0))
    temperature = base_temp + random.uniform(0.05, 0.15)  # 1.05-1.15

    # Top-p sampling
    top_p = 0.95

    # Frequency penalty (tekrarları önle)
    frequency_penalty = 0.4

    return {
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "frequency_penalty": frequency_penalty
    }

# Kullanım
params = self.generate_message_params(bot, context)
text = self.llm.generate(
    user_prompt=user_prompt,
    **params
)
```

**llm_client.py Güncellemesi:**

```python
def generate(self, user_prompt: str, temperature: float = 0.9,
             max_tokens: int = 150, top_p: float = 0.95,
             frequency_penalty: float = 0.0, **kwargs) -> str:
    """LLM çağrısı - tüm parametrelerle"""

    # ... mevcut kod ...

    response = openai.ChatCompletion.create(
        model=self.model,
        messages=[
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        **kwargs
    )

    return response.choices[0].message.content.strip()
```

**Test Kriteri:**
- 100 mesaj üret, ortalama uzunluk 100-150 kelime olmalı
- Variance yüksek olmalı (std dev > 30 kelime)

---

### **Week 2: Bot Interaction Revolution**

#### **Day 1-3: Smart Reply Target Selection**
**Dosya:** `behavior_engine.py` (pick_reply_target fonksiyonu)

- [x] **SORUN:** Botlar sadece kendi mesajlarına cevap veriyor (bot mesajlarına -1 puan)
- [x] **ÇÖZÜM:** Bot mesajlarını değerli hale getir, akıllı scoring

**Yeni Algoritma:**

```python
def pick_reply_target_v2(self, db, chat, bot, max_candidates=30):
    """Akıllı cevap hedefi seçimi - bot-to-bot etkileşimi teşvik eder"""

    recent_msgs = db.query(Message).filter(
        Message.chat_id == chat.id
    ).order_by(Message.created_at.desc()).limit(max_candidates).all()

    if not recent_msgs:
        return None

    candidates = []

    for msg in recent_msgs:
        score = 0.0

        # === 1. KİM YAZDI? ===
        if msg.bot_id is None:
            # İnsan mesajı - yüksek öncelik
            score += 8.0
        else:
            # Bot mesajı
            if msg.bot_id == bot.id:
                continue  # Kendi mesajına cevap verme!

            # BAŞKA bot'tan mesaj - ARTIK POZİTİF!
            score += 2.5  # Önceden -1 idi, şimdi +2.5

        # === 2. TAZELIK ===
        age_minutes = (now_utc() - msg.created_at).total_seconds() / 60
        if age_minutes < 3:
            score += 3.0  # Çok taze
        elif age_minutes < 10:
            score += 2.0
        elif age_minutes < 30:
            score += 1.0
        else:
            score -= 1.0  # Eski mesaj

        # === 3. SORU VAR MI? ===
        if "?" in msg.text:
            score += 4.0  # Soru kesinlikle cevap bekliyor

        # Merak ifadeleri
        curiosity_phrases = ["ne düşünüyorsun", "sizce", "fikrin", "ne dersin",
                             "katılıyor musun", "öyle mi", "emin misin"]
        if any(phrase in msg.text.lower() for phrase in curiosity_phrases):
            score += 3.0

        # === 4. MENTION VAR MI? ===
        if f"@{bot.username}" in msg.text:
            score += 15.0  # Kesinlikle cevap ver!

        # === 5. UZMLIK ALANI ===
        msg_symbols = extract_symbols(msg.text)
        bot_watchlist = bot.persona_profile.get("watchlist", [])
        overlap = set(msg_symbols) & set(bot_watchlist)
        score += len(overlap) * 2.5  # Her eşleşen sembol +2.5

        # === 6. KONU UYUMU ===
        msg_topics = self.detect_topics(msg.text)
        bot_expertise = bot.persona_profile.get("expertise", [])
        if any(topic in bot_expertise for topic in msg_topics):
            score += 3.0

        # === 7. SENTIMENT UYUMU ===
        # Bazı botlar pozitif, bazıları negatif haberlere tepki verir
        msg_sentiment = self.detect_sentiment(msg.text)
        bot_empathy = bot.emotion_profile.get("empathy", 0.5)

        if msg_sentiment < -0.3 and bot_empathy > 0.7:
            score += 2.0  # Empatik bot, negatif mesaja tepki verir

        # === 8. POPÜLER MESAJ ===
        # Eğer çok kişi cevap verdiyse, bu bot da katılabilir
        reply_count = db.query(Message).filter(
            Message.msg_metadata.contains(f'"reply_to": {msg.id}')
        ).count()

        if reply_count >= 2:
            score += 1.5  # Popüler tartışma

        candidates.append((score, msg))

    # En yüksek skorlu mesajı seç
    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)

    # Top 3'ten rastgele seç (biraz randomness)
    top_3 = candidates[:3]
    weights = [c[0] for c in top_3]  # Score'lara göre ağırlık
    selected = random.choices(top_3, weights=weights, k=1)[0]

    logger.info(f"Reply target selected: {selected[1].text[:50]} (score={selected[0]:.1f})")

    return selected[1]
```

**Helper Functions:**

```python
def detect_topics(self, text: str) -> List[str]:
    """Mesajdaki konuları tespit et"""
    topics = []

    text_lower = text.lower()

    if any(w in text_lower for w in ["bist", "borsa", "hisse"]):
        topics.append("BIST")
    if any(w in text_lower for w in ["dolar", "euro", "tl", "kur"]):
        topics.append("FX")
    if any(w in text_lower for w in ["btc", "eth", "kripto", "bitcoin"]):
        topics.append("Kripto")
    if any(w in text_lower for w in ["enflasyon", "faiz", "tcmb", "merkez"]):
        topics.append("Makro")

    return topics

def detect_sentiment(self, text: str) -> float:
    """Basit sentiment (-1 to +1)"""
    positive_words = ["yükseldi", "arttı", "güçlü", "olumlu", "iyi", "kazanç", "başarılı"]
    negative_words = ["düştü", "azaldı", "zayıf", "olumsuz", "kötü", "zarar", "başarısız"]

    text_lower = text.lower()

    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)

    total = pos_count + neg_count
    if total == 0:
        return 0.0

    return (pos_count - neg_count) / total
```

**Test Kriteri:**
- 100 mesaj simülasyonu çalıştır
- Bot-to-bot reply rate >= %40 olmalı (şimdi ~%10)

---

#### **Day 4-5: Reply Probability Tuning**
**Dosya:** `database.py` (settings), `behavior_engine.py`

- [x] **AYAR:** `reply_probability` ayarını 0.3'ten 0.6'ya çıkar
- [x] **YENİ AYAR:** `reply_to_bots_probability` ekle

**Settings Güncellemesi:**

```python
# database.py - init_default_settings()
settings_defaults = {
    # ... mevcut ayarlar ...

    "reply_probability": 0.6,  # Genel cevap verme ihtimali (0.3'ten arttı)
    "reply_to_bots_probability": 0.5,  # Bot mesajlarına özel cevap ihtimali
    "new_message_probability": 0.4,  # Yeni mesaj başlatma
}
```

**behavior_engine.py Kullanımı:**

```python
# tick_once() içinde
is_reply = False

if len(recent_msgs) > 0:
    # Bot mesajı mı var son mesajlarda?
    last_msg = recent_msgs[0]

    if last_msg.bot_id is not None:
        # Son mesaj bot'tan
        reply_prob = float(self.settings.get("reply_to_bots_probability", 0.5))
    else:
        # Son mesaj insandan
        reply_prob = float(self.settings.get("reply_probability", 0.6))

    is_reply = random.random() < reply_prob
```

**Test Kriteri:**
- Reply oranı %60 civarı olmalı
- Bot mesajlarına reply oranı %50 civarı olmalı

---

#### **Day 6-7: Context Window Expansion**
**Dosya:** `behavior_engine.py:2344-2357`

- [x] **SORUN:** Sadece 6 mesaj history kullanılıyor (çok az!)
- [x] **ÇÖZÜM:** History'yi 15-20 mesaja çıkar, contextual examples'ı template'e ekle

**Değişiklik:**

```python
# behavior_engine.py - tick_once() içinde

# ÖNCE:
# history_source = list(recent_msgs[:6])

# SONRA:
history_limit = 15  # 6'dan 15'e çıkar
history_source = list(recent_msgs[:history_limit])

# Contextual examples KULLAN (şimdi template'de yok!)
contextual_examples = build_contextual_examples(
    list(reversed(recent_msgs[:30])),  # Son 30 mesajdan pattern çıkar
    bot_id=bot.id,
    max_pairs=4  # 3'ten 4'e çıkar
)

# Template'e ekle
user_prompt = USER_TEMPLATE_V2.format(
    # ... diğer parametreler ...
    contextual_examples=contextual_examples if contextual_examples else "",
    # ...
)
```

**build_contextual_examples İyileştirmesi:**

```python
def build_contextual_examples(messages: List[Message], bot_id: int, max_pairs: int = 4) -> str:
    """Bot'un geçmiş davranış örneklerini çıkar"""

    bot_messages = [m for m in messages if m.bot_id == bot_id]

    if len(bot_messages) < 2:
        return ""

    examples = []

    for i, bot_msg in enumerate(bot_messages[:max_pairs]):
        # Bu mesajdan önce gelen context'i bul
        idx = messages.index(bot_msg)
        if idx > 0:
            prev_msg = messages[idx - 1]

            examples.append(
                f"[Örnek {i+1}]\n"
                f"{prev_msg.bot.name if prev_msg.bot else 'Kullanıcı'}: {prev_msg.text[:100]}\n"
                f"Sen: {bot_msg.text[:100]}\n"
            )

    if not examples:
        return ""

    return "## SENİN ÖNCEKİ KONUŞMA TARZI:\n" + "\n".join(examples)
```

**Test Kriteri:**
- Her mesaj üretiminde 15 mesaj history kullanılmalı
- Contextual examples template'de görünmeli

---

### **Phase 1 Test & Validation**

**Checkpoint Kriterleri:**
- [ ] Her bot farklı system prompt alıyor ✅
- [ ] Template tüm context bilgilerini içeriyor ✅
- [ ] Max tokens 100-250 arasında dinamik ✅
- [ ] Bot-to-bot reply rate >= %40 ✅
- [ ] Message diversity artmış (n-gram analizi) ✅

**Test Senaryosu:**
1. 5 bot oluştur (farklı persona/risk/tone)
2. 100 mesaj simülasyonu çalıştır
3. Metrikleri ölç:
   - Bot-to-bot reply count
   - Unique n-gram ratio
   - Average message length
   - Stance consistency

**Eğer başarısız:** Phase 2'ye geçme, önce düzelt!

---

## 🟡 PHASE 2: Diversity & Naturalness (Week 3-4)

**Hedef:** Mesajları çeşitlendirmek, robot kalıplarını kırmak
**Risk:** Orta (yeni algoritmalar, performans etkisi)
**ROI:** ⭐⭐⭐⭐ YÜKSEK

### **Week 3: Advanced Deduplication & Voice Profiles**

#### **Day 1-3: Semantic Deduplication**
**Yeni Dosya:** `semantic_dedup.py`

- [x] **SORUN:** Exact match dedup var ama anlamsal benzerlik kontrolü yok
- [x] **ÇÖZÜM:** Sentence transformers ile embedding-based similarity

**İmplementasyon:**

```python
# semantic_dedup.py

from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Tuple

class SemanticDeduplicator:
    """Anlamsal benzerlik ile tekrar tespiti"""

    def __init__(self):
        # Lightweight Türkçe destekli model
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.similarity_threshold = 0.85  # %85 benzerlik = tekrar

    def is_duplicate(self, new_message: str, recent_messages: List[str]) -> Tuple[bool, float]:
        """Yeni mesaj mevcut mesajlara çok mu benziyor?"""

        if not recent_messages:
            return False, 0.0

        # Embeddings hesapla
        new_embedding = self.model.encode([new_message])[0]
        recent_embeddings = self.model.encode(recent_messages)

        # Cosine similarity
        similarities = [
            np.dot(new_embedding, rec_emb) / (
                np.linalg.norm(new_embedding) * np.linalg.norm(rec_emb)
            )
            for rec_emb in recent_embeddings
        ]

        max_similarity = max(similarities)

        is_dup = max_similarity > self.similarity_threshold

        return is_dup, max_similarity

    def paraphrase_message(self, message: str, llm_client) -> str:
        """Mesajı paraphrase et (LLM ile)"""

        prompt = f"""
        Şu mesajı başka kelimelerle yaz ama anlamı aynı kalsın:
        "{message}"

        Farklı kelimeler, farklı cümle yapısı kullan ama aynı fikri anlat.
        Sadece yeni versiyonu yaz, başka bir şey yazma.
        """

        paraphrased = llm_client.generate(prompt, temperature=1.2, max_tokens=150)

        return paraphrased.strip()
```

**behavior_engine.py Entegrasyonu:**

```python
# behavior_engine.py

from semantic_dedup import SemanticDeduplicator

class BehaviorEngine:
    def __init__(self):
        # ... mevcut init ...
        self.semantic_dedup = SemanticDeduplicator()

    async def tick_once(self, db):
        # ... mesaj üretimi ...

        text = self.llm.generate(user_prompt, **params)

        # SEMANTIC DEDUP
        if self.settings.get("semantic_dedup_enabled", True):
            recent_texts = [m.text for m in recent_msgs[:50]]  # Son 50 mesaj

            is_dup, similarity = self.semantic_dedup.is_duplicate(text, recent_texts)

            if is_dup:
                logger.warning(f"Duplicate detected! Similarity={similarity:.2f}")

                # 2 deneme: Paraphrase veya yeniden üret
                for attempt in range(2):
                    text = self.semantic_dedup.paraphrase_message(text, self.llm)
                    is_dup, similarity = self.semantic_dedup.is_duplicate(text, recent_texts)

                    if not is_dup:
                        logger.info(f"Paraphrase successful! New similarity={similarity:.2f}")
                        break

                if is_dup:
                    logger.error("Paraphrase failed, skipping message")
                    return  # Mesaj atma

        # Devam et...
```

**Test Kriteri:**
- 10 benzer mesaj üret, dedup hepsini yakalamali
- Paraphrase edilen mesajlar anlamca aynı ama kelimeler farklı olmalı

---

#### **Day 4-5: Voice Profiles & Writing Style**
**Yeni Dosya:** `voice_profiles.py`

- [x] **SORUN:** Her bot aynı tarzda yazıyor (emoji, kısaltma, hata kullanımı aynı)
- [x] **ÇÖZÜM:** Her bot için unique voice profile, mesaja uygula

**İmplementasyon:**

```python
# voice_profiles.py

import random
import re
from typing import List

class VoiceProfile:
    """Bot'un yazı tarzı"""

    def __init__(self):
        self.slang_frequency = 0.0  # Kısaltma kullanım oranı
        self.emoji_frequency = 0.0
        self.typo_frequency = 0.0  # Yazım hatası
        self.punctuation_errors = 0.0
        self.abbreviations = []
        self.favorite_emoji = None
        self.sentence_starters = []
        self.certainty_level = 0.5  # 0=şüpheci, 1=kesin

class VoiceProfileGenerator:
    """Her bot için unique ses profili"""

    def generate(self, bot) -> VoiceProfile:
        """Bot persona'sına göre voice profili oluştur"""

        profile = VoiceProfile()

        persona = bot.persona_profile
        emotion = bot.emotion_profile

        tone = persona.get("tone", "").lower()
        risk = persona.get("risk_profile", "medium")

        # === KELIME SEÇİMİ ===
        if "genç" in tone or "sokak" in tone:
            profile.slang_frequency = 0.4
            profile.emoji_frequency = 0.3
            profile.abbreviations = ["bi", "tmm", "niye", "yok", "var", "aga", "valla", "la"]
        elif "profesyonel" in tone:
            profile.slang_frequency = 0.05
            profile.emoji_frequency = 0.02
            profile.abbreviations = []
        else:
            profile.slang_frequency = 0.2
            profile.emoji_frequency = 0.15
            profile.abbreviations = ["bi", "tmm", "yok", "var"]

        # === CÜMLE BAŞLANGIÇLARI ===
        if risk == "high":
            profile.sentence_starters = ["Bence", "Kesin", "Muhakkak", "Garantili", "Net"]
            profile.certainty_level = 0.85
        elif risk == "low":
            profile.sentence_starters = ["Belki", "Sanırım", "Gibi geliyor", "Emin değilim ama", "Olabilir"]
            profile.certainty_level = 0.3
        else:
            profile.sentence_starters = ["Bana göre", "Düşünüyorum ki", "Sanırım", "Bence"]
            profile.certainty_level = 0.6

        # === YAZIM HATALARI ===
        if "genç" in tone:
            profile.typo_frequency = 0.15  # %15 hata
            profile.punctuation_errors = 0.3
        else:
            profile.typo_frequency = 0.05
            profile.punctuation_errors = 0.1

        # === EMOJİ ===
        if "signature_emoji" in emotion:
            profile.favorite_emoji = emotion["signature_emoji"]

        return profile

    def apply_voice(self, message: str, voice: VoiceProfile) -> str:
        """Mesaja ses profili uygula"""

        transformed = message

        # 1. Kısaltmalar ekle
        if voice.abbreviations and random.random() < voice.slang_frequency:
            transforms = {
                r'\bbir\b': 'bi',
                r'\btamam\b': 'tmm',
                r'\byoktur\b': 'yoktur yok',
                r'\bniçin\b': 'niye',
                r'\bneden\b': 'niye'
            }

            for pattern, replacement in transforms.items():
                if random.random() < 0.5:
                    transformed = re.sub(pattern, replacement, transformed, count=1, flags=re.IGNORECASE)

        # 2. Yazım hataları (mi/mı bitişik)
        if random.random() < voice.typo_frequency:
            transformed = re.sub(r'\s+(mi|mı|mu|mü)\b', r'\1', transformed)

        # 3. Noktalama hataları
        if random.random() < voice.punctuation_errors:
            # Nokta veya virgül atla
            transformed = re.sub(r'\.$', '', transformed)
            transformed = re.sub(r',', '', transformed, count=1)

        # 4. Büyük harf hataları
        if random.random() < voice.typo_frequency:
            # İlk harfi küçük yap
            if transformed:
                transformed = transformed[0].lower() + transformed[1:]

        # 5. Emoji ekle
        if voice.favorite_emoji and random.random() < voice.emoji_frequency:
            transformed += f" {voice.favorite_emoji}"

        # 6. Cümle başlangıcı ekle (bazen)
        if voice.sentence_starters and random.random() < 0.3:
            starter = random.choice(voice.sentence_starters)
            if not transformed.lower().startswith(starter.lower()):
                transformed = f"{starter}, {transformed[0].lower()}{transformed[1:]}"

        return transformed
```

**behavior_engine.py Entegrasyonu:**

```python
# behavior_engine.py

from voice_profiles import VoiceProfileGenerator

class BehaviorEngine:
    def __init__(self):
        # ... mevcut init ...
        self.voice_generator = VoiceProfileGenerator()
        self.bot_voices = {}  # Cache

    def get_bot_voice(self, bot):
        """Bot voice profile'ı al (cache)"""
        if bot.id not in self.bot_voices:
            self.bot_voices[bot.id] = self.voice_generator.generate(bot)

        return self.bot_voices[bot.id]

    async def tick_once(self, db):
        # ... mesaj üretimi ...

        text = self.llm.generate(user_prompt, **params)

        # VOICE PROFILI UYGULA
        voice = self.get_bot_voice(bot)
        text = self.voice_generator.apply_voice(text, voice)

        # ... devam et ...
```

**Test Kriteri:**
- 5 bot, her biri 20 mesaj
- Her bot'un emoji/kısaltma/hata kullanımı farklı olmalı
- "Genç" bot %40 kısaltma, "profesyonel" bot %5 kısaltma

---

### **Week 4: News Integration & Message Length Diversity**

#### **Day 1-3: Rich News Integration**
**Dosya:** `news_aggregator.py` (yeni), `behavior_engine.py`

- [x] **SORUN:** News trigger %20 (çok düşük), tek kaynak, kısa özet
- [x] **ÇÖZÜM:** Multi-source, %50 probability, zengin haber

**settings Güncelleme:**

```python
{
    "news_trigger_probability": 0.5,  # 0.2'den 0.5'e
    "news_feed_urls": [
        "https://www.bloomberght.com/rss/",
        "https://tr.investing.com/rss/news.rss",
        "https://www.ekonomim.com/rss/genel.xml"
    ],
    "news_max_length": 500  # 240'tan 500'e
}
```

**İyileştirme (behavior_engine.py):**

```python
# tick_once() içinde news trigger

if bool(s.get("news_trigger_enabled", True)) and self.news is not None:
    trigger_prob = float(s.get("news_trigger_probability", 0.5))

    if random.random() < trigger_prob:
        # Haber getir
        brief = self.news.get_brief(topic, max_length=500)

        if brief:
            # Market trigger'a ekle
            market_trigger = f"SON HABER: {brief}"

            # Ve bazen 2-3 bot tetiklenir (chain reaction)
            if random.random() < 0.3:
                # Chain: Bu haberden sonra başka bir bot da tepki verecek
                # (Bu özellik Phase 3'te geliştirilecek)
                pass
```

**Test Kriteri:**
- 100 mesajdan ~50'si haber tetikli olmalı
- Haberler çeşitli kaynaklardan gelmeli

---

#### **Day 4-5: Dynamic Message Length**
**Dosya:** `behavior_engine.py`

- [x] **SORUN:** Mesaj uzunlukları çok benzer (hep 40-60 kelime)
- [x] **ÇÖZÜM:** Bot persona + context'e göre dinamik uzunluk

**İmplementasyon:**

```python
def generate_message_params(self, bot: Bot, context: dict) -> dict:
    """Bot ve context'e göre LLM parametreleri"""

    persona = bot.persona_profile
    tone = persona.get("tone", "").lower()

    # === BASE LENGTH (bot kişiliğine göre) ===
    if "akademik" in tone or "tecrübeli" in tone or "profesyonel" in tone:
        base_min, base_max = 150, 250  # Uzun mesajlar
    elif "genç" in tone or "enerjik" in tone:
        base_min, base_max = 60, 120  # Kısa-orta
    else:
        base_min, base_max = 80, 180  # Orta

    # === CONTEXT MODIFIERS ===
    is_reply = context.get("is_reply", False)
    is_question = context.get("is_question", False)
    is_news_trigger = context.get("is_news_trigger", False)

    if is_reply:
        # Cevaplar biraz daha kısa
        base_min = int(base_min * 0.7)
        base_max = int(base_max * 0.8)

    if is_question:
        # Sorulan sorulara uzun cevap
        base_min = int(base_min * 1.3)
        base_max = int(base_max * 1.4)

    if is_news_trigger:
        # Haberlerden sonra daha detaylı
        base_min = int(base_min * 1.2)
        base_max = int(base_max * 1.3)

    # Random seç
    max_tokens = random.randint(base_min, base_max)

    # ... diğer parametreler (temperature, etc.) ...

    return {
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": 0.95,
        "frequency_penalty": 0.4
    }
```

**Test Kriteri:**
- "Akademik" bot: ortalama 180-200 kelime
- "Genç" bot: ortalama 70-90 kelime
- Variance yüksek olmalı (std dev > 40 kelime)

---

#### **Day 6-7: Multi-Voice Generation (Opsiyonel)**
**Dosya:** `behavior_engine.py`

- [x] **İDEA:** Aynı prompt için 2-3 mesaj üret, en doğalını seç
- [x] **MALIYET:** 2-3x LLM call (Groq ücretsiz, sorun yok)

**İmplementasyon:**

```python
def generate_with_selection(self, user_prompt: str, params: dict, n_candidates: int = 2) -> str:
    """N aday üret, en doğalını seç"""

    if not self.settings.get("multi_voice_enabled", False):
        # Disabled ise direkt 1 mesaj üret
        return self.llm.generate(user_prompt, **params)

    candidates = []

    for i in range(n_candidates):
        # Her seferinde temperature biraz değiştir
        temp = params["temperature"] + random.uniform(-0.1, 0.1)
        text = self.llm.generate(user_prompt, temperature=temp,
                                 max_tokens=params["max_tokens"])

        # Naturalness score
        score = self.score_naturalness(text)

        candidates.append((score, text))

    # En yüksek skorlu seç
    best = max(candidates, key=lambda x: x[0])

    logger.info(f"Selected best candidate (score={best[0]:.2f}) from {n_candidates}")

    return best[1]

def score_naturalness(self, text: str) -> float:
    """Basit naturalness skoru (0-100)"""
    score = 100.0

    # Çok uzun cümleler kötü
    sentences = text.split('.')
    avg_sentence_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
    if avg_sentence_len > 25:
        score -= 10.0

    # Noktalama çok düzgünse kötü
    if text.count(',') + text.count('.') == len(sentences):
        score -= 10.0  # Çok düzenli

    # "Kesinlikle", "mutlaka" gibi robot kelimeler
    robot_words = ["kesinlikle", "mutlaka", "gerçekten çok", "son derece", "oldukça"]
    for word in robot_words:
        if word in text.lower():
            score -= 5.0

    return max(0, score)
```

**Test Kriteri:**
- Multi-voice enabled iken 2 aday üret
- Seçilen mesaj daha doğal olmalı (manual review)

---

### **Phase 2 Test & Validation**

**Checkpoint Kriterleri:**
- [ ] Semantic dedup çalışıyor, benzer mesajları engelliyor ✅
- [ ] Her bot unique voice profile kullanıyor ✅
- [ ] News trigger %50, haberler zengin ✅
- [ ] Mesaj uzunlukları çeşitli (variance yüksek) ✅
- [ ] Bot-to-bot reply rate >= %50 ✅

**Qualitative Test:**
- 3 gerçek kullanıcı 100 mesaj okusun
- "Robot gibi" yorumu %50 azalmalı
- Her bot'un tarzı ayırt edilebilir olmalı

---

## 🟢 PHASE 3: Microservices Foundation (Week 5-6)

**Hedef:** Mimari geçiş başlangıcı - monolitten departmanlara
**Risk:** Yüksek (infra değişikliği, migration)
**ROI:** ⭐⭐⭐ ORTA (uzun vadede yüksek)

### **Week 5: Infrastructure Setup**

#### **Day 1-2: Redis Pub/Sub Setup**
**Yeni Dosya:** `event_bus.py`

```python
# event_bus.py

import redis
import json
import logging
from typing import Callable, Dict

logger = logging.getLogger(__name__)

class EventBus:
    """Redis-based event bus"""

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.pubsub = self.redis.pubsub()
        self.handlers: Dict[str, list] = {}

    def publish(self, event_type: str, payload: dict):
        """Publish event"""
        message = {
            "type": event_type,
            "payload": payload
        }

        self.redis.publish("piyasa_events", json.dumps(message))
        logger.info(f"Published event: {event_type}")

    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to event type"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []

        self.handlers[event_type].append(handler)

    def listen(self):
        """Listen to events (blocking)"""
        self.pubsub.subscribe("piyasa_events")

        for message in self.pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                event_type = data["type"]

                if event_type in self.handlers:
                    for handler in self.handlers[event_type]:
                        handler(data["payload"])
```

**Test:** Redis setup, pub/sub çalışıyor mu?

---

#### **Day 3-5: Service Skeleton**
**Yeni Dosyalar:** `services/news_service.py`, `services/bot_coordinator.py`

```python
# services/news_service.py

from fastapi import FastAPI
from event_bus import EventBus

app = FastAPI()
event_bus = EventBus(os.getenv("REDIS_URL"))

@app.post("/news/aggregate")
async def aggregate_news():
    """Fetch and analyze news"""
    # ... news aggregation logic ...

    # Publish event
    event_bus.publish("NEWS_PUBLISHED", {
        "news_id": news.id,
        "importance": news.importance,
        "matched_bots": [1, 3, 5]
    })

    return {"status": "ok"}
```

---

### **Week 6: Bot Coordinator Service**

#### **Day 1-7: Turn-Taking Manager**
**Dosya:** `services/bot_coordinator.py`

(Full implementation from system_architecture_v2.md - TurnTakingManager class)

---

## 🔵 PHASE 4: Intelligence Layer (Week 7-10)

**Hedef:** Gelişmiş özellikler - Quality Control, Memory, Drama
**Risk:** Orta
**ROI:** ⭐⭐⭐⭐ YÜKSEK

### **Week 7: Quality Control Service**

(NaturalnessScorer, ConsistencyGuardian implementation)

### **Week 8: Memory Manager Service**

(SharedKnowledgeBase, CrossBotLearning implementation)

### **Week 9: Conversation Director**

(DramaGenerator, TopicTransitionOrchestrator implementation)

### **Week 10: Personality Engine**

(UniqueVoiceGenerator, MoodTracker implementation)

---

## 📊 Success Metrics & KPIs

### **Week 2 (Phase 1 Complete):**
- Bot-to-bot reply: **40%+**
- Message diversity: **60%+**
- Naturalness: **6/10**

### **Week 4 (Phase 2 Complete):**
- Bot-to-bot reply: **50%+**
- Message diversity: **75%+**
- Naturalness: **7/10**
- News-driven debates: **30%+**

### **Week 10 (Phase 4 Complete):**
- Bot-to-bot reply: **70%+**
- Message diversity: **85%+**
- Naturalness: **9/10**
- News-driven debates: **60%+**
- Conversation chain depth: **6-8 mesaj**

---

## 🗑️ Files to Remove

**Old/Unused Files:**
- `PHASE1_QUICKSTART.md` → Eski, artık geçersiz
- `PHASE2_SUMMARY.md` → Eski, artık geçersiz
- `PHASE2_TEST_RESULTS.md` → Eski test sonuçları
- `tests/load_test_report_*.json` → Eski load test raporları
- `nul` → Gereksiz dosya
- `load_test_output.txt` → Eski output

**Keep:**
- `version_update_todo.md` → Reference için sakla (arşiv)
- `system_architecture_v2.md` → Reference için sakla (arşiv)
- Bu yeni dosya: `master_implementation_plan.md` → Master plan!

---

## 🚀 Next Steps

**Hemen Başla:**
1. `system_prompt.py` - `generate_system_prompt()` fonksiyonu yaz
2. `system_prompt.py` - `USER_TEMPLATE_V2` oluştur
3. `llm_client.py` - LLM parametreleri güncelle
4. `behavior_engine.py` - `pick_reply_target_v2()` yaz

**Priority Order:**
1. 🔴 Week 1: System & User Prompt (EN KRİTİK)
2. 🔴 Week 2: Bot Interaction (EN KRİTİK)
3. 🟡 Week 3-4: Diversity & News (YÜKSEK)
4. 🟢 Week 5-6: Microservices (ORTA)
5. 🔵 Week 7-10: Intelligence (BONUS)

---

**Son Güncelleme:** 18 Ekim 2025
**Hazırlayan:** Claude Code Assistant
**Versiyon:** Master Implementation Plan v1.0
**Toplam Sayfa:** ~800 satır
