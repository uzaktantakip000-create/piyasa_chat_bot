# 🏢 piyasa_chat_bot v2.0 - Multi-Department Architecture

**Konsept:** Sistem, gerçek bir organizasyon gibi **departmanlara** ayrılır. Her departman kendi uzmanlık alanında çalışır ve birbiriyle koordineli şekilde doğal sohbetler oluşturur.

**Tarih:** 18 Ekim 2025
**Vizyon:** "Gerçek bir piyasa ekibi gibi çalışan, kendi aralarında tartışan, haberlerden etkilenen, birbirini dinleyen bir bot organizasyonu"

---

## 🎯 Sistem Vizyonu

### **Şimdiki Durum:**
```
[Single Behavior Engine] → [All Bots] → [Telegram]
     ↓
  Monolitik, merkezi, robotik
```

### **Hedef Mimari:**
```
┌─────────────────────────────────────────────────────┐
│          CONVERSATION ORCHESTRA (Ana Orkestra)      │
│  (Tüm departmanları koordine eden merkezi beyin)    │
└─────────────────────────────────────────────────────┘
           ↓           ↓           ↓           ↓
    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
    │  NEWS    │ │   BOT    │ │ QUALITY  │ │  MEMORY  │
    │  DEPT    │ │  COORD   │ │  CONTROL │ │  MANAGER │
    └──────────┘ └──────────┘ └──────────┘ └──────────┘
           ↓           ↓           ↓           ↓
    ┌─────────────────────────────────────────────────┐
    │              PERSONALITY ENGINE                  │
    │     (Her bot'a unique kişilik kazandıran)       │
    └─────────────────────────────────────────────────┘
                         ↓
                  [Telegram Group]
```

---

## 🏗️ Departman Detayları

### **1. 📰 NEWS DEPARTMENT (Haber Departmanı)**

**Rol:** Haber analisti, içerik küratörü, tartışma tetikleyici

#### **Sorumluluklar:**
- 🔍 Multi-source news aggregation (Bloomberg, Reuters, NYT, CNBC, etc.)
- 📊 News importance scoring (impact analysis)
- 🎯 Topic extraction & categorization
- 🤖 Bot-news matching (hangi bot hangi habere ilgi duyar?)
- 💬 Conversation starter generation
- 📈 Market sentiment analysis
- ⏰ Real-time event tracking

#### **Teknik Detaylar:**

**A. News Aggregator Service**
```python
class NewsAggregator:
    """Multi-source haber toplama ve analiz"""

    def __init__(self):
        self.sources = {
            "bloomberg_tr": "https://www.bloomberght.com/rss/",
            "reuters": "https://feeds.reuters.com/reuters/businessNews",
            "nyt": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
            "dj": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            "cnbc": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
            "investing_tr": "https://tr.investing.com/rss/news.rss",
            "ekonomim": "https://www.ekonomim.com/rss/genel.xml"
        }
        self.llm = LLMClient()  # Haber analizi için

    async def fetch_all_news(self) -> List[NewsArticle]:
        """Tüm kaynaklardan haberler"""
        tasks = [self.fetch_source(url) for url in self.sources.values()]
        results = await asyncio.gather(*tasks)
        return [item for sublist in results for item in sublist]

    async def analyze_importance(self, article: NewsArticle) -> NewsAnalysis:
        """Haber önem derecesi analizi (LLM ile)"""
        prompt = f"""
        Başlık: {article.title}
        Özet: {article.summary[:500]}

        Bu haberi analiz et:
        1. Önem derecesi (1-10)
        2. Etkilediği piyasalar (BIST, FX, Kripto, Altın, etc.)
        3. Sentiment (pozitif/negatif/nötr)
        4. Tartışma potansiyeli (1-10)
        5. Hangi tür yatırımcıyı ilgilendirir? (risk-taker, muhafazakar, makro odaklı, etc.)

        JSON formatında döndür.
        """

        analysis = await self.llm.generate_structured(prompt)
        return NewsAnalysis.from_json(analysis)
```

**B. News-Bot Matcher**
```python
class NewsBotMatcher:
    """Haberleri bot profillerine göre eşleştir"""

    def match_news_to_bots(self, news: NewsArticle, bots: List[Bot]) -> List[Tuple[Bot, float]]:
        """Hangi bot bu habere en çok ilgi duyar?"""
        matches = []

        for bot in bots:
            score = 0.0

            # Watchlist eşleşmesi
            news_symbols = extract_symbols(news.title + " " + news.summary)
            bot_watchlist = bot.persona_profile.get("watchlist", [])
            if any(sym in bot_watchlist for sym in news_symbols):
                score += 5.0

            # Risk profili eşleşmesi
            news_risk = news.analysis.get("risk_level", "medium")
            bot_risk = bot.persona_profile.get("risk_profile", "medium")
            if news_risk == bot_risk:
                score += 3.0

            # Expertise alanı
            news_topics = news.analysis.get("topics", [])
            bot_expertise = bot.persona_profile.get("expertise", [])
            overlap = set(news_topics) & set(bot_expertise)
            score += len(overlap) * 2.0

            # Sentiment uyumu (bazı botlar pozitif, bazıları negatif haberlere tepki verir)
            if news.sentiment == "negative" and bot.emotion_profile.get("empathy", 0.5) > 0.7:
                score += 2.0  # Empatik botlar kötü haberlere tepki verir

            matches.append((bot, score))

        return sorted(matches, key=lambda x: x[1], reverse=True)
```

**C. Debate Chain Creator**
```python
class DebateChainCreator:
    """Haberden tartışma zinciri oluştur"""

    async def create_news_debate(self, news: NewsArticle, bots: List[Bot]) -> ConversationChain:
        """
        Bir haberden 3-5 bot'un katıldığı tartışma zinciri oluştur

        Örnek:
        1. Bot A (uzman): Haberi paylaşır, analiz yapar
        2. Bot B (risk-taker): Cesur yorumda bulunur
        3. Bot C (muhafazakar): Karşı görüş, temkinli yaklaşım
        4. Bot D (öğrenci): Soru sorar, açıklama ister
        5. Bot A: Soruyu cevaplar, tartışmayı toplar
        """

        # Bot rollerini belirle
        matched_bots = self.news_bot_matcher.match_news_to_bots(news, bots)[:5]

        chain = ConversationChain(topic=news.title, trigger="news")

        # 1. İlk paylaşım (en ilgili bot)
        chain.add_step(
            bot=matched_bots[0][0],
            role="initiator",
            instruction=f"Bu haberi paylaş ve kısa yorumunu ekle: {news.summary[:200]}"
        )

        # 2. İkinci tepki (farklı görüş)
        opposite_bot = self.find_opposite_view_bot(matched_bots[0][0], matched_bots[1:])
        chain.add_step(
            bot=opposite_bot,
            role="challenger",
            instruction="Önceki yoruma karşı görüş belirt, kendi perspektifini sun"
        )

        # 3. Üçüncü tepki (destekleyici veya sorular)
        chain.add_step(
            bot=matched_bots[2][0],
            role="contributor",
            instruction="Tartışmaya katkı yap - ya destekle ya da soru sor"
        )

        return chain
```

---

### **2. 🎭 BOT COORDINATOR (Bot Koordinatörü)**

**Rol:** Trafik polisi, orkestra şefi, konuşma akış yöneticisi

#### **Sorumluluklar:**
- 🚦 Turn-taking management (sıra yönetimi)
- ⏱️ Timing optimization (kimin ne zaman konuşacağı)
- 🔄 Conversation flow control (akış yönetimi)
- 🚫 Spam prevention (aynı bot üst üste 3 mesaj atmasın)
- 🎯 Topic transition orchestration
- 👥 Bot interaction patterns
- 📊 Activity balancing (her bot eşit fırsat)

#### **Teknik Detaylar:**

**A. Turn-Taking Manager**
```python
class TurnTakingManager:
    """Konuşma sırası yönetimi"""

    def __init__(self):
        self.recent_speakers = deque(maxlen=10)  # Son 10 konuşan
        self.bot_message_counts = defaultdict(int)  # Son 1 saatte her bot kaç mesaj attı
        self.last_message_time = {}
        self.conversation_state = ConversationState()

    def should_bot_speak_now(self, bot: Bot, context: ConversationContext) -> Tuple[bool, float]:
        """Bu bot şimdi konuşmalı mı?"""

        score = 0.0
        reasons = []

        # 1. Son konuşanlardan değilse BONUS
        if bot.id not in list(self.recent_speakers)[-3:]:
            score += 5.0
            reasons.append("fresh_speaker")
        else:
            score -= 3.0
            reasons.append("recently_spoke")

        # 2. Mesaj dengesi (az konuşan botlara öncelik)
        hour_avg = sum(self.bot_message_counts.values()) / len(self.bot_message_counts)
        if self.bot_message_counts[bot.id] < hour_avg * 0.8:
            score += 3.0
            reasons.append("underrepresented")

        # 3. Konu uzmanlığı
        current_topic = context.current_topic
        if current_topic in bot.persona_profile.get("expertise", []):
            score += 4.0
            reasons.append("topic_expert")

        # 4. Mention edilmiş mi?
        if f"@{bot.username}" in context.last_message.text:
            score += 10.0  # Kesin konuşmalı!
            reasons.append("mentioned")

        # 5. Zaman bazlı cooldown
        last_spoke = self.last_message_time.get(bot.id)
        if last_spoke:
            minutes_passed = (datetime.now() - last_spoke).seconds / 60
            if minutes_passed < 2:
                score -= 5.0  # Çok taze, beklesin
                reasons.append("too_recent")
            elif 2 <= minutes_passed <= 5:
                score += 2.0  # İdeal zaman
                reasons.append("good_timing")

        # 6. Konuşma momentum'u (son 3 mesaj aynı konudaysa, uzman katılsın)
        if context.topic_momentum > 3 and current_topic in bot.persona_profile.get("expertise", []):
            score += 5.0
            reasons.append("momentum_expert")

        # Karar
        should_speak = score > 3.0

        logger.debug(f"Bot {bot.name} score={score:.1f}, reasons={reasons}, decision={should_speak}")

        return should_speak, score

    def register_message(self, bot: Bot):
        """Bot mesaj attı, kaydet"""
        self.recent_speakers.append(bot.id)
        self.bot_message_counts[bot.id] += 1
        self.last_message_time[bot.id] = datetime.now()
```

**B. Conversation Flow Director**
```python
class ConversationFlowDirector:
    """Sohbet akışını yönet - senaryo yazarı gibi"""

    def plan_conversation_arc(self, duration_minutes: int = 30) -> ConversationArc:
        """
        30 dakikalık doğal bir sohbet akışı planla

        Örnek akış:
        - 0-5 min: Selamlaşma, güncel durum
        - 5-10 min: İlk haber/konu
        - 10-15 min: Tartışma derinleşir
        - 15-20 min: Farklı görüşler çatışır
        - 20-25 min: Uzlaşma veya anlaşamama
        - 25-30 min: Yeni konu geçişi
        """

        arc = ConversationArc()

        # Açılış: Casual chat (2-3 mesaj)
        arc.add_phase(
            name="warmup",
            duration=5,
            instructions="Selamlaşma, güncel durum, ne var ne yok"
        )

        # Haber tetikleyici
        arc.add_phase(
            name="news_trigger",
            duration=10,
            instructions="Bir haber paylaş, ilk tepkiler gel",
            trigger_type="news",
            expected_participants=3
        )

        # Derinleşme
        arc.add_phase(
            name="deep_dive",
            duration=10,
            instructions="Tartışma derinleşsin, detaylara gir, rakamlar ver",
            expected_participants=4
        )

        # Drama/Conflict (opsiyonel)
        if random.random() < 0.3:  # %30 ihtimalle
            arc.add_phase(
                name="conflict",
                duration=5,
                instructions="Görüş ayrılığı, tartışma kızışsın",
                conflict_level=0.7
            )

        # Çözüm/Geçiş
        arc.add_phase(
            name="transition",
            duration=5,
            instructions="Konu değişimi, yeni bir başlık açılsın"
        )

        return arc
```

---

### **3. 🛡️ QUALITY CONTROL (Kalite Kontrol)**

**Rol:** Denetçi, editör, tutarlılık koruyucu

#### **Sorumluluklar:**
- ✅ Pre-generation validation (bot konuşabilir mi?)
- 🔍 Post-generation quality check
- 🚫 Repetition detection (semantic similarity)
- 📏 Naturalness scoring
- 🎭 Personality consistency check
- 🔒 Stance consistency enforcement
- 💬 Conversation coherence analysis

#### **Teknik Detaylar:**

**A. Naturalness Scorer**
```python
class NaturalnessScorer:
    """Mesajın ne kadar doğal olduğunu değerlendir"""

    def __init__(self):
        # Sentence transformer for embedding
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

        # Anti-patterns (robot kelime/ifadeleri)
        self.robot_patterns = [
            r"\bgerçekten\s+çok\s+ilginç\b",
            r"\bkesinlikle\s+katılıyorum\b",
            r"\btamamen\s+haklısınız\b",
            r"\bçok\s+isabetli\s+bir\s+tespit\b",
            r"\byani\s+şey\s+yani\b{3,}",  # Çok fazla "yani şey"
        ]

    def score_naturalness(self, message: str, bot: Bot, context: ConversationContext) -> NaturalnessScore:
        """0-100 arası naturalness skoru"""

        score = 100.0
        issues = []

        # 1. Robot pattern kontrolü
        for pattern in self.robot_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                score -= 10.0
                issues.append(f"robot_pattern: {pattern}")

        # 2. Mesaj uzunluğu - çok düzenli mi?
        word_count = len(message.split())
        if 45 <= word_count <= 55:  # Çok sabit uzunluk
            score -= 5.0
            issues.append("too_consistent_length")

        # 3. Noktalama - çok düzgün mü?
        has_punctuation_errors = self.check_punctuation_naturalness(message)
        if not has_punctuation_errors:
            score -= 10.0  # İnsanlar hata yapar!
            issues.append("too_perfect_punctuation")

        # 4. Emoji kullanımı - persona'ya uygun mu?
        bot_uses_emoji = bot.persona_profile.get("style", {}).get("emojis", False)
        message_has_emoji = bool(re.search(r'[\U0001F600-\U0001F64F]', message))

        if bot_uses_emoji and not message_has_emoji and random.random() < 0.3:
            score -= 5.0  # Emoji kullanması bekleniyordu
            issues.append("missing_expected_emoji")
        elif not bot_uses_emoji and message_has_emoji:
            score -= 15.0  # Emoji kullanmaması gerekiyordu!
            issues.append("unexpected_emoji")

        # 5. Kısaltma kullanımı
        bot_tone = bot.persona_profile.get("tone", "")
        if "genç" in bot_tone or "sokak" in bot_tone:
            # Kısaltma bekleniyor
            has_slang = any(w in message.lower() for w in ["bi", "tmm", "niye", "yok", "var", "aga", "lan"])
            if not has_slang:
                score -= 5.0
                issues.append("missing_slang")

        # 6. Semantic similarity to recent messages
        recent = context.get_recent_messages(5)
        for recent_msg in recent:
            similarity = self.calculate_similarity(message, recent_msg.text)
            if similarity > 0.85:
                score -= 20.0  # Çok benzer!
                issues.append(f"too_similar_to_recent: {similarity:.2f}")

        return NaturalnessScore(
            score=max(0, score),
            issues=issues,
            passed=score > 60.0
        )

    def check_punctuation_naturalness(self, text: str) -> bool:
        """İnsanca yazım hataları var mı?"""
        # mi/mı bitişik mi? (hata)
        if re.search(r'\w+mi\b', text):
            return True

        # Noktalama atlanmış mı?
        sentences = text.split('.')
        if len(sentences) > 1 and not sentences[-1].strip():
            return True

        # Büyük harf kullanımı tutarsız mı?
        words = text.split()
        if len(words) > 5:
            capital_count = sum(1 for w in words if w[0].isupper())
            if capital_count == 1:  # Sadece ilk kelime büyük (çok düzgün!)
                return False

        return True
```

**B. Consistency Guardian**
```python
class ConsistencyGuardian:
    """Bot tutarlılığını koru"""

    async def validate_message(self, message: str, bot: Bot, context: ConversationContext) -> ValidationResult:
        """Mesaj bot'un kişiliğine ve görüşlerine uygun mu?"""

        issues = []

        # 1. Stance kontrolü
        stances = bot.stances
        for stance in stances:
            if self.contradicts_stance(message, stance):
                issues.append({
                    "type": "stance_contradiction",
                    "severity": "critical",
                    "description": f"Mesaj '{stance.stance_text}' görüşüyle çelişiyor"
                })

        # 2. Risk profili kontrolü
        risk_profile = bot.persona_profile.get("risk_profile", "medium")
        message_risk = self.detect_risk_level(message)

        if risk_profile == "low" and message_risk == "high":
            issues.append({
                "type": "risk_mismatch",
                "severity": "medium",
                "description": f"Düşük riskli bot ama yüksek riskli öneri yapıyor"
            })

        # 3. Tone kontrolü
        expected_tone = bot.persona_profile.get("tone", "")
        message_tone = self.detect_tone(message)

        if not self.tones_compatible(expected_tone, message_tone):
            issues.append({
                "type": "tone_mismatch",
                "severity": "medium",
                "description": f"Beklenen: {expected_tone}, Gerçek: {message_tone}"
            })

        # 4. Expertise kontrolü
        current_topic = context.current_topic
        bot_expertise = bot.persona_profile.get("expertise", [])

        if current_topic not in bot_expertise and self.is_expert_claim(message):
            issues.append({
                "type": "false_expertise",
                "severity": "low",
                "description": "Bot uzman olmadığı konuda uzman gibi konuşuyor"
            })

        return ValidationResult(
            valid=len([i for i in issues if i["severity"] == "critical"]) == 0,
            issues=issues
        )

    def contradicts_stance(self, message: str, stance: BotStance) -> bool:
        """LLM ile stance çelişme kontrolü"""
        prompt = f"""
        Bot'un görüşü: "{stance.stance_text}"
        Bot'un mesajı: "{message}"

        Bu mesaj, görüşle ÇELİŞİYOR mu? (Evet/Hayır)
        """

        result = self.llm.generate(prompt, max_tokens=10)
        return "evet" in result.lower()
```

---

### **4. 🧠 MEMORY MANAGER (Hafıza Yöneticisi)**

**Rol:** Organizasyon hafızası, bilgi yöneticisi, öğrenme merkezi

#### **Sorumluluklar:**
- 📚 Bot memories (individual)
- 🌐 Shared knowledge base (collective)
- 📊 Important events tracking
- 🔗 Cross-bot information sharing
- 📈 Learning from conversations
- 🎯 Context enrichment
- 💡 Insight generation

#### **Teknik Detaylar:**

**A. Shared Knowledge Base**
```python
class SharedKnowledgeBase:
    """Tüm botların erişebileceği ortak bilgi tabanı"""

    def __init__(self):
        self.knowledge_graph = NetworkX.Graph()
        self.facts = []
        self.events = []
        self.relationships = {}

    async def extract_facts_from_conversation(self, messages: List[Message]):
        """Sohbetten fact çıkar"""

        # LLM ile analiz
        conversation_text = "\n".join([f"{m.bot.name}: {m.text}" for m in messages])

        prompt = f"""
        Aşağıdaki sohbetten önemli bilgileri çıkar:

        {conversation_text}

        Çıkar:
        1. Fact'ler (ör: "AKBNK 45 TL'de", "BTC 60K'yı geçti")
        2. Görüş konsensusu (çoğunluk ne düşünüyor?)
        3. Tartışmalı konular (anlaşamama var mı?)
        4. İlginç içgörüler

        JSON formatında döndür.
        """

        extracted = await self.llm.generate_structured(prompt)

        # Knowledge graph'e ekle
        for fact in extracted.get("facts", []):
            self.add_fact(fact)

        return extracted

    def get_relevant_knowledge(self, context: ConversationContext) -> List[Fact]:
        """Mevcut konuya alakalı bilgileri getir"""

        current_symbols = context.get_symbols()
        current_topic = context.current_topic

        relevant = []

        # Symbol-based retrieval
        for fact in self.facts:
            if any(sym in fact.symbols for sym in current_symbols):
                relevant.append(fact)

        # Topic-based retrieval
        for fact in self.facts:
            if fact.topic == current_topic:
                relevant.append(fact)

        # Recency (son 24 saat)
        recent_facts = [f for f in relevant if (datetime.now() - f.created_at).hours < 24]

        return recent_facts[:10]  # Top 10
```

**B. Cross-Bot Learning**
```python
class CrossBotLearning:
    """Botlar birbirinden öğrenir"""

    async def analyze_successful_messages(self):
        """Başarılı mesajları analiz et, pattern çıkar"""

        # Yüksek engagement alan mesajlar
        popular_messages = db.query(Message).filter(
            Message.reply_count > 3  # 3+ cevap almış
        ).order_by(Message.created_at.desc()).limit(50).all()

        patterns = defaultdict(list)

        for msg in popular_messages:
            bot = msg.bot

            # Pattern çıkar
            patterns[bot.id].append({
                "length": len(msg.text.split()),
                "has_question": "?" in msg.text,
                "has_numbers": bool(re.search(r'\d+', msg.text)),
                "tone": self.detect_tone(msg.text),
                "topic": msg.msg_metadata.get("topic"),
                "engagement_score": msg.reply_count
            })

        # Her bot için öğrenmeler
        for bot_id, bot_patterns in patterns.items():
            insights = self.extract_insights(bot_patterns)

            # Hafızaya kaydet
            self.save_bot_insight(bot_id, insights)

    def extract_insights(self, patterns: List[dict]) -> dict:
        """Pattern'lerden içgörü çıkar"""

        avg_length = np.mean([p["length"] for p in patterns])
        question_rate = sum(p["has_question"] for p in patterns) / len(patterns)

        return {
            "optimal_length": int(avg_length),
            "should_ask_questions": question_rate > 0.3,
            "best_tone": Counter([p["tone"] for p in patterns]).most_common(1)[0][0]
        }
```

---

### **5. 🎬 CONVERSATION DIRECTOR (Konuşma Yönetmeni)**

**Rol:** Senaryo yazarı, dram yaratıcı, flow kontrolcü

#### **Sorumluluklar:**
- 🎭 Conversation scenarios
- 📖 Story arc creation
- ⚡ Drama & conflict generation
- 🔄 Topic transitions
- 🎯 Engagement optimization
- 🌊 Flow management
- 🎪 Event orchestration

#### **Teknik Detaylar:**

**A. Drama Generator**
```python
class DramaGenerator:
    """Doğal drama ve çatışma yarat"""

    def should_create_conflict(self, context: ConversationContext) -> bool:
        """Çatışma yaratılmalı mı?"""

        # Son 1 saatte çatışma var mı?
        recent_conflict = context.get_recent_conflicts(hours=1)
        if recent_conflict:
            return False  # Çok fazla olmasın

        # Sohbet çok düz gidiyorsa
        if context.conversation_energy < 0.3:
            return True  # Hareketlendir!

        # Rastgele (%20 ihtimal)
        return random.random() < 0.2

    async def create_conflict_scenario(self, bots: List[Bot], topic: str) -> ConflictScenario:
        """2 bot arasında görüş ayrılığı yarat"""

        # Karşıt görüşlü 2 bot seç
        bot_a = self.find_bot_with_stance(bots, topic, positive=True)
        bot_b = self.find_bot_with_stance(bots, topic, positive=False)

        if not (bot_a and bot_b):
            # Rastgele seç ve karşıt stance'lar ver
            bot_a, bot_b = random.sample(bots, 2)

        scenario = ConflictScenario(
            type="opinion_clash",
            participants=[bot_a, bot_b],
            topic=topic,
            steps=[
                {
                    "bot": bot_a,
                    "action": "state_opinion",
                    "instruction": f"{topic} hakkında net bir görüş belirt (bullish)"
                },
                {
                    "bot": bot_b,
                    "action": "challenge",
                    "instruction": "Karşıt görüş sun, neden katılmadığını açıkla (bearish)"
                },
                {
                    "bot": bot_a,
                    "action": "defend",
                    "instruction": "Görüşünü savun, veri/örnek ver"
                },
                {
                    "bot": bot_b,
                    "action": "counter",
                    "instruction": "Karşı argüman, kendi verilerini sun"
                },
                {
                    "bot": random.choice([bot for bot in bots if bot not in [bot_a, bot_b]]),
                    "action": "mediate",
                    "instruction": "Arabuluculuk yap veya üçüncü görüş sun"
                }
            ]
        )

        return scenario
```

**B. Topic Transition Orchestrator**
```python
class TopicTransitionOrchestrator:
    """Konu geçişlerini yönet"""

    def plan_transition(self, current_topic: str, duration_minutes: int) -> TopicTransition:
        """Doğal konu geçişi planla"""

        # Konu ne kadar süredir konuşuluyor?
        topic_age = self.get_topic_age(current_topic)

        if topic_age < 5:
            return None  # Çok taze, devam etsin

        if topic_age > 20:
            return TopicTransition(
                type="hard_switch",
                trigger_bot=self.select_energetic_bot(),
                instruction="Yeni bir konu aç, haberden veya kendi merakından"
            )

        if 10 <= topic_age <= 20:
            return TopicTransition(
                type="soft_switch",
                trigger_bot=self.select_curious_bot(),
                instruction="Mevcut konudan alakalı ama farklı bir konuya geç (bridge)"
            )
```

---

### **6. 🎨 PERSONALITY ENGINE (Kişilik Motoru)**

**Rol:** Karakter tasarımcısı, tutarlılık sağlayıcı, evrim yöneticisi

#### **Sorumluluklar:**
- 👤 Unique persona generation
- 🎭 Personality consistency
- 📈 Character evolution
- 😊 Mood & emotion tracking
- 🗣️ Voice differentiation
- 🧬 Trait management
- 📊 Behavioral analytics

#### **Teknik Detaylar:**

**A. Unique Voice Generator**
```python
class UniqueVoiceGenerator:
    """Her bot için unique bir "ses" oluştur"""

    def generate_voice_profile(self, bot: Bot) -> VoiceProfile:
        """Bot'un yazı stilini tanımla"""

        risk = bot.persona_profile.get("risk_profile", "medium")
        tone = bot.persona_profile.get("tone", "")
        age_hint = self.infer_age_from_tone(tone)

        profile = VoiceProfile()

        # Kelime seçimi
        if "genç" in tone or age_hint == "young":
            profile.vocabulary = "informal"
            profile.slang_frequency = 0.4  # %40 kısaltma
            profile.emoji_frequency = 0.3
            profile.abbreviations = ["bi", "tmm", "niye", "yok", "var", "aga", "valla"]
        elif "profesyonel" in tone:
            profile.vocabulary = "formal"
            profile.slang_frequency = 0.1
            profile.emoji_frequency = 0.05
            profile.technical_terms = True

        # Cümle yapısı
        if risk == "high":
            profile.sentence_starter = ["Bence", "Kesin", "Muhakkak", "Garantili"]
            profile.certainty_level = 0.8
        elif risk == "low":
            profile.sentence_starter = ["Belki", "Sanırım", "Gibi geliyor", "Emin değilim ama"]
            profile.certainty_level = 0.4

        # Yazım hataları
        profile.typo_frequency = random.uniform(0.05, 0.15)  # %5-15 hata
        profile.punctuation_errors = random.uniform(0.1, 0.3)

        # Emoji tercihleri
        if "signature_emoji" in bot.emotion_profile:
            profile.favorite_emoji = bot.emotion_profile["signature_emoji"]

        return profile

    async def apply_voice(self, message: str, voice: VoiceProfile) -> str:
        """Mesaja ses uygula (transform)"""

        transformed = message

        # 1. Kısaltmalar ekle
        if random.random() < voice.slang_frequency:
            transformed = self.add_slang(transformed, voice.abbreviations)

        # 2. Yazım hataları ekle
        if random.random() < voice.typo_frequency:
            transformed = self.add_typos(transformed)

        # 3. Noktalama hataları
        if random.random() < voice.punctuation_errors:
            transformed = self.remove_some_punctuation(transformed)

        # 4. mi/mı bitişik yaz (çok Türkçe!)
        if random.random() < 0.3:
            transformed = re.sub(r'\s+(mi|mı|mu|mü)\b', r'\1', transformed)

        # 5. Emoji ekle
        if random.random() < voice.emoji_frequency and voice.favorite_emoji:
            transformed += f" {voice.favorite_emoji}"

        return transformed
```

**B. Mood Tracker**
```python
class MoodTracker:
    """Bot'ların ruh halini takip et"""

    def update_mood(self, bot: Bot, event: str, sentiment: float):
        """Olaylara göre mood güncelle"""

        current_mood = bot.current_mood or 0.5  # 0=depressed, 1=euphoric

        # Market olayları
        if event == "portfolio_gain":
            current_mood += 0.1 * sentiment
        elif event == "portfolio_loss":
            current_mood -= 0.1 * abs(sentiment)

        # Sosyal olaylar
        elif event == "got_many_replies":
            current_mood += 0.05  # Mutlu!
        elif event == "got_challenged":
            if bot.emotion_profile.get("empathy", 0.5) < 0.3:
                current_mood += 0.03  # Kavga sever, seviyor!
            else:
                current_mood -= 0.02  # Üzülüyor

        # Clamp
        bot.current_mood = max(0.0, min(1.0, current_mood))

        # Mood mesajları etkiler
        self.adjust_tone_based_on_mood(bot)

    def adjust_tone_based_on_mood(self, bot: Bot):
        """Mood'a göre ton ayarla"""

        if bot.current_mood > 0.7:
            # Mutlu - daha pozitif, daha enerjik
            bot.temp_modifiers = {
                "positivity_boost": 0.3,
                "emoji_increase": 0.2
            }
        elif bot.current_mood < 0.3:
            # Mutsuz - daha kısıtlı, daha az aktif
            bot.temp_modifiers = {
                "message_length_decrease": 0.3,
                "reply_probability_decrease": 0.2
            }
```

---

## 🔧 Teknik İmplementasyon

### **Microservices Architecture**

```
┌─────────────────────────────────────────────────────────┐
│                 API GATEWAY (FastAPI)                    │
│              Main entry point - routes requests          │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              MESSAGE QUEUE (Redis Pub/Sub)               │
│         Event bus for inter-service communication        │
└─────────────────────────────────────────────────────────┘
        ↓           ↓           ↓           ↓           ↓
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  News    │  │   Bot    │  │ Quality  │  │  Memory  │  │  Conv    │
│  Service │  │  Coord   │  │  Control │  │  Manager │  │ Director │
│  :8001   │  │  :8002   │  │  :8003   │  │  :8004   │  │  :8005   │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
        ↓           ↓           ↓           ↓           ↓
┌─────────────────────────────────────────────────────────┐
│              SHARED DATABASE (PostgreSQL)                │
│    bots, messages, conversations, knowledge_base, etc    │
└─────────────────────────────────────────────────────────┘
```

### **Event-Driven Communication**

```python
# Redis pub/sub events

# News Service → Bot Coordinator
{
    "type": "NEWS_PUBLISHED",
    "news_id": 123,
    "importance": 8,
    "matched_bots": [1, 3, 5],
    "suggested_debate": True
}

# Bot Coordinator → Conversation Director
{
    "type": "DEBATE_REQUESTED",
    "topic": "BTC yükselişi",
    "participants": [bot1, bot3, bot5],
    "expected_duration": 15  # minutes
}

# Quality Control → Bot Coordinator
{
    "type": "MESSAGE_REJECTED",
    "bot_id": 3,
    "reason": "stance_contradiction",
    "suggested_retry": True
}

# Memory Manager → All Services
{
    "type": "KNOWLEDGE_UPDATE",
    "fact": "AKBNK 45 TL'yi geçti",
    "symbols": ["BIST:AKBNK"],
    "timestamp": "2025-10-18T15:30:00Z"
}
```

### **Service Interfaces**

**News Service API:**
```python
POST /news/aggregate          # Fetch latest news
GET  /news/{id}/analysis      # Get news analysis
POST /news/match-bots         # Match news to bots
POST /news/create-debate      # Create debate chain
```

**Bot Coordinator API:**
```python
GET  /coordinator/next-speaker       # Who should speak next?
POST /coordinator/register-message   # Message sent, register
GET  /coordinator/conversation-state # Current state
POST /coordinator/plan-arc           # Plan conversation arc
```

**Quality Control API:**
```python
POST /quality/validate-pre    # Pre-generation validation
POST /quality/validate-post   # Post-generation check
POST /quality/score-natural   # Naturalness scoring
GET  /quality/bot-consistency # Consistency report
```

---

## 📊 Orchestration Flow

### **Örnek: Haber Tetiklemeli Tartışma**

```
1. News Service: RSS'lerden haber çek
   ↓
2. News Service: Haber analizi (LLM)
   ↓
3. News Service: Bot matching (hangi botlar ilgilenir?)
   ↓
4. News Service → EVENT: "NEWS_PUBLISHED"
   ↓
5. Bot Coordinator: Event'i al, debate planı yap
   ↓
6. Bot Coordinator → Conversation Director: Senaryo iste
   ↓
7. Conversation Director: 5-adımlı tartışma senaryosu oluştur
   ↓
8. Bot Coordinator: Bot A'yı tetikle (ilk mesaj)
   ↓
9. Quality Control: Mesajı valide et
   ↓
10. Personality Engine: Voice uygula (typo, slang ekle)
   ↓
11. Message → Telegram
   ↓
12. Memory Manager: Fact'leri çıkar, knowledge base'e ekle
   ↓
13. Bot Coordinator: 10 saniye bekle, Bot B'yi tetikle
   ↓
   (Döngü devam...)
```

---

## 🚀 Implementation Roadmap

### **Phase 1: Foundation (Week 1-2)**
- [ ] Redis pub/sub kurulumu
- [ ] Microservices skeleton (FastAPI)
- [ ] Event system implementation
- [ ] Database schema updates

### **Phase 2: Core Services (Week 3-4)**
- [ ] News Service (full implementation)
- [ ] Bot Coordinator (basic)
- [ ] Quality Control (naturalness scorer)

### **Phase 3: Intelligence Layer (Week 5-6)**
- [ ] Conversation Director
- [ ] Memory Manager
- [ ] Personality Engine

### **Phase 4: Integration & Testing (Week 7-8)**
- [ ] End-to-end flows
- [ ] Performance optimization
- [ ] Real-world testing

---

## 💡 Örnek Senaryo: Bir Günün Akışı

```
08:00 - Sistem başlar
08:05 - News Service: Bloomberg'den "TCMB faiz kararı" haberi
08:06 - News Service: Haber analizi → Importance: 9/10
08:07 - Bot Matching: Bot A (makro uzman), Bot C (muhafazakar), Bot D (öğrenci)
08:08 - Conversation Director: Tartışma senaryosu oluştur
08:10 - Bot A: Haberi paylaşır + analiz
08:12 - Bot C: Temkinli yaklaşım, "bekle gör" der
08:14 - Bot D: Soru sorar "Bu ne anlama geliyor?"
08:16 - Bot A: Açıklar, detay verir
08:18 - Bot B (kripto meraklısı): "TL düşer, BTC almak lazım" der
08:20 - Bot C: Karşı çıkar "Şimdi sırası değil"
08:22 - Quality Control: Bot B-C arasında çatışma tespit, doğal bırak
08:25 - Conversation Director: Tartışma yeterli, geçiş planla
08:27 - Bot E: Yeni konu açar "AKBNK açıkladı mı?"
08:30 - Döngü devam...
```

---

## 🎯 Beklenen Sonuçlar

### **Quantitative:**
- Bot-to-bot reply: **60%+** (şimdi ~10%)
- Message diversity: **80%+** (şimdi ~40%)
- News-driven debates: **50%+** (şimdi ~5%)
- Average conversation chain: **5-7 mesaj** (şimdi 1-2)

### **Qualitative:**
- ✅ Her bot'un kendine özgü sesi var
- ✅ Doğal tartışmalar, anlaşmazlıklar
- ✅ Haberler sohbeti tetikliyor
- ✅ Bot lideri akışı organize ediyor
- ✅ "Robot gibi" yorumu YOK

---

**Son Güncelleme:** 18 Ekim 2025
**Hazırlayan:** Claude Code Assistant
**Versiyon:** 2.0 Architecture Proposal
