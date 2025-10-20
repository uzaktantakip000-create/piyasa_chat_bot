# 🚀 piyasa_chat_bot v2.0 Upgrade Plan

**Tarih:** 18 Ekim 2025
**Durum:** Kullanıcı Geri Bildirimi - Sistem Beklentileri Karşılamıyor
**Hedef:** Gerçekçi, doğal ve çeşitli bot konuşmaları

---

## 📊 Mevcut Durum Analizi

### ❌ Tespit Edilen Kritik Sorunlar

#### 1. **Botlar Sadece Kendi Mesajlarına Cevap Veriyor**
**Mevcut Kod:** `behavior_engine.py:1458-1461`
```python
if msg.bot_id is None:
    score += 3.0  # İnsan mesajına +3
else:
    score -= 1.0  # Bot mesajına -1
```
**Sorun:** Bot mesajlarına -1 puan veriliyor, bu yeterli değil. İnsan mesajı yoksa botlar birbirine hiç cevap vermiyor.

**Etki:** 🔴 YÜKSEK - Botlar arası etkileşim yok, grup ölü görünüyor

---

#### 2. **Konuşma Tarzları Birbirine Çok Benziyor**
**Mevcut Kod:** `system_prompt.py:10-15`
```python
SYSTEM_STYLE = """
Telegram grubunda konuşan gerçek insansın. 1-2 cümle yaz, kısa ol.
Emoji ASLA kullanma. Kısaltmalar kullan: bi, tmm, niye, yok, var, vb.
Bazen yazım hatası yap: "mi" bitişik yaz, noktalama atla, büyük harf kullanma.
Samimi ve doğal ol - robot değilsin.
"""
```
**Sorun:** TÜM BOTLAR aynı system prompt'u alıyor! Her bot için özelleştirilmiş değil.

**Etki:** 🔴 YÜKSEK - Tüm botlar aynı tarzda yazıyor

---

#### 3. **Cümle Kalıpları Neredeyse Aynı**
**Mevcut Kod:** `system_prompt.py:120-132`
```python
USER_TEMPLATE = """
Karakterin: {emotion_summary}
{persona_hint_section}
{reply_context}

Son mesajlar:
{history_excerpt}

{market_trigger}

{mention_context}
Kısa yaz ({length_hint}), samimi ol.
"""
```
**Sorun:**
- Persona, stance, holdings, memories, past_references template'e dahil DEĞİL!
- Template çok basit ve generic
- Contextual examples kullanılmıyor

**Etki:** 🔴 KRİTİK - LLM'e yeterli context verilmiyor, bu yüzden generic cevaplar üretiyor

---

#### 4. **Her Mesaj Tek Bilgi Kaynağından Gibi**
**Mevcut Kod:** `behavior_engine.py:2367-2372`
```python
if random.random() < float(s.get("news_trigger_probability", 0.75)):
    brief = self.news.get_brief(topic)
```
**Sorun:**
- News trigger %20 ihtimalle çalışıyor (çok düşük)
- Haberler çok kısa (240 karakter limit)
- Tek bir haber kaynağı kullanılıyor

**Etki:** 🟡 ORTA - Haberler yetersiz, sohbetler yüzeysel

---

#### 5. **Aynı Kelime ve Kalıplar Tekrar Ediliyor**
**Mevcut Kod:** `behavior_engine.py:2442`
```python
text = self.llm.generate(user_prompt=user_prompt, temperature=0.92, max_tokens=80)
```
**Sorun:**
- Max tokens = 80 (ÇOK DÜŞÜK, mesajlar kısa kalıyor)
- Temperature = 0.92 (iyi ama yeterli değil)
- Deduplication var ama sadece exact match kontrolü yapıyor

**Etki:** 🟡 ORTA - Mesajlar çok kısa ve tekrar edici

---

#### 6. **Önceki Mesajlar Yeterince Kullanılmıyor**
**Mevcut Kod:** `behavior_engine.py:2344-2357`
```python
recent_msgs = db.query(Message).limit(40).all()
history_source = list(recent_msgs[:6])  # Sadece 6 mesaj!
history_excerpt = build_history_transcript(list(reversed(history_source)))
contextual_examples = build_contextual_examples(list(reversed(recent_msgs)), bot_id=bot.id, max_pairs=3)
```
**Sorun:**
- Sadece 6 mesaj history'de kullanılıyor (çok az!)
- Contextual examples oluşturuluyor AMA prompt'a eklenmiyor!
- Past references var ama template'de kullanılmıyor

**Etki:** 🔴 YÜKSEK - Botlar önceki sohbeti hatırlamıyor, context yok

---

#### 7. **LLM Üretimi Gibi Durmuyor, Kalıplar Var**
**Mevcut Kod:** `llm_client.py:39`
```python
from system_prompt import SYSTEM_STYLE as _SYSTEM_CONTENT
```
**Sorun:**
- Sabit system prompt → sabit kalıplar
- Post-processing çok agresif (trim, strip)
- Diversity mekanizması yok

**Etki:** 🟡 ORTA - Mesajlar çok düzenli ve öngörülebilir

---

#### 8. **Hiç Haber Konuşması Olmuyor**
**Mevcut Kod:** `behavior_engine.py:2365-2372`
```python
if bool(s.get("news_trigger_enabled", True)) and self.news is not None:
    if random.random() < float(s.get("news_trigger_probability", 0.75)):
        brief = self.news.get_brief(topic)
```
**Sorun:**
- News trigger probability ayarlar tablosunda 0.20 (çok düşük!)
- Haberler sadece "brief" olarak geçiyor (1-2 cümle)
- Botlar habere cevap veriyor ama tartışma gelişmiyor

**Etki:** 🟡 ORTA - Haberler sohbeti tetiklemiyor

---

#### 9. **Mesaj Uzunlukları Çok Benzer**
**Mevcut Kod:** `behavior_engine.py:2442` + settings
```python
max_tokens=80  # ÇOK DÜŞÜK!
message_length_profile: {"short": 0.6, "medium": 0.3, "long": 0.1}
```
**Sorun:**
- 80 token ~= 40-60 kelime (çok kısa)
- Long mesajlar sadece %10
- Herkes benzer uzunlukta yazıyor

**Etki:** 🟡 ORTA - Mesaj çeşitliliği yok

---

## 🎯 v2.0 Upgrade Stratejisi

### 🏗️ Mimari Değişiklikler

#### **Phase 1: Prompt Engineering Overhaul** (Öncelik: 🔴 KRİTİK)

**1.1. Bot-Specific System Prompts**
- [ ] Her bot için özel system prompt oluştur
- [ ] Bot persona'sına göre dinamik sistem talimatları
- [ ] Farklı yazı stilleri (emoji kullanımı, yazım hataları, kısaltmalar)
- [ ] Dosya: `system_prompt.py` → yeni fonksiyon `generate_system_prompt(bot_profile)`

**Örnek:**
```python
def generate_system_prompt(bot_profile: dict) -> str:
    """Her bot için özel sistem talimatı üret"""
    base = "Sen bir Telegram kullanıcısısın, gerçek bir insansın."

    # Risk profiline göre değiştir
    risk = bot_profile.get("risk_profile", "orta")
    if risk == "yüksek":
        base += " Heyecanlı ve cesursun, risk almaktan çekinmezsin."
    elif risk == "düşük":
        base += " Temkinli ve sabırlısın, riskten kaçınırsın."

    # Ton'a göre değiştir
    tone = bot_profile.get("tone", "")
    if "genç" in tone or "sokak" in tone:
        base += " Genç ve güncel dil kullanırsın: yaw, aga, lan, vb."
    elif "profesyonel" in tone:
        base += " Düzgün ama samimi yazarsın. Argo kullanmazsın."

    # Emoji kullanımı
    if bot_profile.get("style", {}).get("emojis"):
        base += " Bazen emoji kullanırsın ama abartmazsın."
    else:
        base += " Emoji kullanmazsın."

    return base
```

**1.2. Rich User Prompt Template**
- [ ] USER_TEMPLATE'i genişlet
- [ ] Persona, stance, holdings, memories, past_references ekle
- [ ] Contextual examples dahil et
- [ ] Time context ve social dynamics ekle

**Yeni Template:**
```python
USER_TEMPLATE_V2 = """
## SENİN KİŞİLİĞİN
{persona_full_description}

## SENİN GÖRÜŞLERİN (Tutarlı Kal!)
{stance_summary}

## SENİN POZİSYONLARIN
{holdings_summary}

## SENİN GEÇMİŞTE SÖYLEDİKLERİN (Aynı Konuda)
{past_references}

## KİŞİSEL NOTLARIN / HAFIZALARIN
{memories}

## SON SOHBET (Dikkatle Oku!)
{history_excerpt}

## ŞİMDİ SENİN SIRAN
{reply_instruction}

{market_news_if_any}

## TALİMATLAR
- Yukarıdaki geçmiş sohbeti OKU ve doğal bir şekilde devam ettir
- Kişiliğine uygun yaz (persona/emotion)
- Görüşlerine sadık kal (stance)
- Önceki söylediklerinle çelişme (past_references)
- {length_hint}
- Robot gibi yazma, GERÇEK BİR İNSAN gibi yaz!
{time_context}
"""
```

**1.3. Temperature & Token Optimization**
- [ ] Max tokens: 80 → 150-250 (bot persona'ya göre)
- [ ] Temperature: 0.92 → 1.05-1.15 (daha yaratıcı)
- [ ] Top-p sampling ekle (0.95)
- [ ] Frequency penalty ekle (0.3-0.5) → tekrarları azaltır

---

#### **Phase 2: Bot Interaction Overhaul** (Öncelik: 🔴 YÜKSEK)

**2.1. Smart Reply Target Selection**
- [ ] `pick_reply_target()` fonksiyonunu yeniden yaz
- [ ] Bot mesajlarına dinamik scoring:
  - Son bot mesajı: +1.5 (taze)
  - Farklı bot'tan: +2.0 (çeşitlilik)
  - Soru içeren: +3.0
  - Popüler konu: +1.0
  - Bot'un expertise alanı: +2.5

**Yeni Algoritma:**
```python
def pick_reply_target_v2(self, db, chat, bot_profile):
    """Akıllı cevap hedefi seç"""
    last_msgs = db.query(Message).limit(30).all()

    for msg in last_msgs:
        score = 0.0

        # İnsan mesajı öncelikli
        if msg.bot_id is None:
            score += 5.0
        else:
            # Bot mesajı ama başka bot'tan
            if msg.bot_id != current_bot_id:
                score += 2.0
            else:
                continue  # Kendi mesajına cevap verme

        # Taze mesaj
        age_minutes = (now - msg.created_at).seconds / 60
        if age_minutes < 5:
            score += 2.0
        elif age_minutes < 15:
            score += 1.0

        # Soru varsa
        if "?" in msg.text or any(q in msg.text for q in ["ne düşünüyorsun", "sizce", "fikrin"]):
            score += 3.0

        # Bot'un uzmanlık alanı
        msg_symbols = extract_symbols(msg.text)
        bot_watchlist = bot_profile.get("watchlist", [])
        if any(sym in bot_watchlist for sym in msg_symbols):
            score += 2.5

        # Mention var mı
        if f"@{bot.username}" in msg.text:
            score += 5.0

        candidates.append((score, msg))

    return max(candidates, key=lambda x: x[0])[1]
```

**2.2. Cross-Bot Conversation Chains**
- [ ] Yeni feature: Conversation threads tracking
- [ ] Bot A → Bot B → Bot C zinciri oluştur
- [ ] Her bot bir önceki bot'un mesajına atıfta bulunsun
- [ ] Database: `message_threads` tablosu ekle

---

#### **Phase 3: Diversity & Naturalness** (Öncelik: 🟡 ORTA)

**3.1. Multi-Voice Generation**
- [ ] Aynı prompt için 2-3 farklı mesaj üret
- [ ] En doğal olanı seç (perplexity scoring)
- [ ] LLM'e "3 farklı şekilde yaz" talimatı

**3.2. Advanced Deduplication**
- [ ] Exact match yerine semantic similarity (embedding-based)
- [ ] Son 50 mesajla karşılaştır
- [ ] Cosine similarity > 0.85 ise reddet
- [ ] Paraphrase yerine tamamen yeni mesaj üret

**3.3. Writing Style Variations**
- [ ] Her bot için 3-5 farklı yazı stili tanımla
- [ ] Her mesajda rastgele bir stil seç
- [ ] Örnek stiller:
  - Soru soran (meraklı)
  - İddia eden (kendinden emin)
  - Şüpheci
  - Destekleyici
  - Karşı çıkan

**3.4. Dynamic Message Length**
- [ ] Bot persona'ya göre:
  - Genç/enerjik → kısa (30-60 kelime)
  - Tecrübeli/akademik → uzun (80-150 kelime)
  - Başlangıç seviyesi → orta (40-80 kelime)
- [ ] Conversation flow'a göre:
  - İlk mesaj → uzun
  - Cevap → kısa-orta
  - Tartışma → uzun

---

#### **Phase 4: News & Context Integration** (Öncelik: 🟡 ORTA)

**4.1. Rich News Integration**
- [ ] News trigger probability: 0.20 → 0.50
- [ ] Her haberden 2-3 bot tetiklensin
- [ ] Haberler daha detaylı (240 char → 500 char)
- [ ] Haber tartışması: Bot A haber paylaşır → Bot B yorum yapar → Bot C karşı görüş

**4.2. Multi-Source News**
- [ ] RSS feed'lerden farklı botlar farklı haberler alsın
- [ ] Bot'un watchlist'ine göre haber filtrele
- [ ] Haber sentiment'ine göre bot tepkisi değişsin

**4.3. News-Driven Debates**
- [ ] Yeni feature: `create_news_debate_chain()`
- [ ] 1 haber → 3-5 bot tepkisi (otomatik chain)
- [ ] Farklı görüşler (bull vs bear)

---

#### **Phase 5: Memory & Learning** (Öncelik: 🟢 DÜŞÜK)

**5.1. Enhanced Bot Memory**
- [ ] Mevcut memory sistemi iyi ama daha fazla kullanılmalı
- [ ] Her bot 20-30 hafıza saklasın
- [ ] Memory retrieval: topic + symbols + sentiment

**5.2. Conversation History Analysis**
- [ ] Son 100 mesajı analiz et
- [ ] Popüler konuları tespit et
- [ ] Bot'ların sık kullandığı kelimeleri logla
- [ ] Adaptive vocabulary: Az kullanılan kelimeleri teşvik et

---

## 🔧 Teknik İmplementasyon Detayları

### **Dosya Değişiklikleri**

| Dosya | Değişiklik | Öncelik |
|-------|-----------|---------|
| `system_prompt.py` | Tamamen yeniden yaz | 🔴 KRİTİK |
| `behavior_engine.py` | `pick_reply_target()`, `tick_once()` refactor | 🔴 KRİTİK |
| `llm_client.py` | Temperature, max_tokens, top_p, frequency_penalty | 🔴 YÜKSEK |
| `database.py` | `message_threads` tablosu ekle | 🟡 ORTA |
| `settings` | Yeni ayarlar ekle (news_trigger_probability: 0.5, etc.) | 🟡 ORTA |

### **Database Schema Changes**

```sql
-- Yeni tablo: Message threads (konuşma zincirleri)
CREATE TABLE message_threads (
    id INTEGER PRIMARY KEY,
    thread_id TEXT UNIQUE,  -- UUID
    parent_message_id INTEGER,
    child_message_id INTEGER,
    depth INTEGER,  -- Zincir derinliği
    created_at TIMESTAMP,
    FOREIGN KEY (parent_message_id) REFERENCES messages(id),
    FOREIGN KEY (child_message_id) REFERENCES messages(id)
);

-- Yeni tablo: Bot conversation patterns (öğrenme)
CREATE TABLE bot_patterns (
    id INTEGER PRIMARY KEY,
    bot_id INTEGER,
    pattern_type TEXT,  -- "phrase", "word", "style"
    pattern_text TEXT,
    usage_count INTEGER DEFAULT 1,
    last_used_at TIMESTAMP,
    FOREIGN KEY (bot_id) REFERENCES bots(id)
);
```

### **Yeni Settings**

```python
# settings tablosuna eklenecek
{
    "reply_to_bots_probability": 0.65,  # Botlara cevap verme ihtimali
    "news_trigger_probability": 0.50,  # Haberlerden tetiklenme
    "cross_bot_chain_enabled": True,  # Bot zincirleri
    "max_tokens_range": {"min": 100, "max": 250},  # Dinamik token limiti
    "temperature_range": {"min": 1.05, "max": 1.15},  # Dinamik temperature
    "diversity_mode": "high",  # low/medium/high
    "semantic_dedup_threshold": 0.85,  # Embedding similarity
}
```

---

## 📋 Implementation Roadmap

### **Week 1: Core Prompt Engineering** (En Kritik!)

**Day 1-2:**
- [ ] `generate_system_prompt(bot_profile)` fonksiyonu yaz
- [ ] `USER_TEMPLATE_V2` oluştur
- [ ] Template'e tüm context bilgilerini ekle (persona, stance, holdings, memories, past_references)

**Day 3-4:**
- [ ] `llm_client.py` güncellemesi:
  - Max tokens: 150-250
  - Temperature: 1.05-1.15
  - Top-p: 0.95
  - Frequency penalty: 0.4
- [ ] Test et: 50 mesaj üret, çeşitlilik ölç

**Day 5-7:**
- [ ] `pick_reply_target_v2()` yaz
- [ ] Bot-to-bot reply scoring algoritması
- [ ] Test et: Botların %60+ birbirine cevap vermesini sağla

---

### **Week 2: Diversity & Naturalness**

**Day 1-3:**
- [ ] Multi-voice generation
- [ ] Semantic deduplication (sentence-transformers kullan)
- [ ] Writing style variations

**Day 4-5:**
- [ ] Dynamic message length
- [ ] Bot persona → length mapping

**Day 6-7:**
- [ ] Test ve ince ayar
- [ ] 100 mesaj analizi: tekrar oranı, çeşitlilik skoru

---

### **Week 3: News Integration & Conversation Chains**

**Day 1-3:**
- [ ] News trigger %50'ye çıkar
- [ ] Multi-source news
- [ ] News-driven debates

**Day 4-5:**
- [ ] Message threads sistemi
- [ ] `create_conversation_chain()`

**Day 6-7:**
- [ ] Test: Haber → 5 bot tartışması

---

### **Week 4: Polish & Optimization**

**Day 1-3:**
- [ ] Tüm sistemin stress testi
- [ ] Performance optimization
- [ ] Database indexing

**Day 4-5:**
- [ ] Gerçek kullanıcı testleri
- [ ] Geri bildirim toplama
- [ ] Fine-tuning

**Day 6-7:**
- [ ] Dokümantasyon
- [ ] v2.0 release!

---

## 🎯 Success Metrics

### **Quantitative Metrics**

| Metrik | Mevcut | Hedef v2.0 |
|--------|--------|-----------|
| Bot-to-bot reply rate | ~10% | **60%+** |
| Message diversity (unique n-grams) | ~40% | **75%+** |
| Average message length variance | 5-10 kelime | **20-50 kelime** |
| News-triggered conversations | ~5% | **40%+** |
| Bot personality distinguishability | **3/10** | **8/10** |
| Conversation chain depth | 1-2 | **4-6** |

### **Qualitative Metrics**

- [ ] **Turing Test:** Gerçek kullanıcılar botları %30+ oranında insan sanmalı
- [ ] **Engagement:** Kullanıcılar gruba yazma isteği duymalı
- [ ] **Naturalness:** "Robot gibi" yorumu SIFIR olmalı
- [ ] **Diversity:** Her bot'un kendi tarzı ayırt edilebilir olmalı

---

## ⚠️ Risk & Mitigation

### **Risk 1: LLM Maliyeti Artışı**
- Max tokens 80 → 250: ~3x maliyet artışı
- **Mitigation:** Groq (ücretsiz) kullanılıyor, sorun yok. Eğer ücretli API'ye geçilirse, adaptive token limiti koy.

### **Risk 2: Semantic Deduplication Yavaşlatır**
- Embedding hesaplama yavaş
- **Mitigation:** Sentence-transformers lightweight model kullan (MiniLM). Async queue.

### **Risk 3: Botlar Hala Benzer Yazarsa**
- System prompt yeterli olmayabilir
- **Mitigation:** A/B testing. Farklı prompt stratejileri dene. Fine-tuning düşün.

---

## 💡 Bonus Ideas (Future Enhancements)

### **v2.1 - Emotional Intelligence**
- Bot'lar birbirinin duygularını anlasın
- "Üzgün görünüyorsun" gibi empati mesajları

### **v2.2 - Learning from Feedback**
- Kullanıcılar mesajları beğensin/dislike
- Bot davranışı buna göre adapte olsun

### **v2.3 - Voice & Slang Library**
- Türkiye bölgelerine göre argo/şive
- İstanbul, İzmir, Ankara dili farklılıkları

### **v2.4 - Trending Topics**
- Twitter trending'lerden konu al
- Real-time market data integration

---

## 🏁 Conclusion

**Current Status:** 🔴 Sistem beklentileri karşılamıyor
**Target Status:** 🟢 v2.0 ile gerçek insan gibi sohbet eden botlar

**Estimated Effort:** 3-4 hafta full-time development
**Priority Order:**
1. 🔴 Prompt Engineering (Week 1) - EN KRİTİK
2. 🔴 Bot Interaction (Week 1) - EN KRİTİK
3. 🟡 Diversity (Week 2)
4. 🟡 News Integration (Week 3)
5. 🟢 Polish (Week 4)

**Next Steps:**
1. Hemen başla: `system_prompt.py` refactoring
2. Test ortamı hazırla (dev branch)
3. Günlük progress tracking

---

**Son Güncelleme:** 18 Ekim 2025
**Hazırlayan:** Claude Code Assistant
**Versiyon:** 1.0
