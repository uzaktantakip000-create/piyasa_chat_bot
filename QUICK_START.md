# 🚀 HIZLI BAŞLANGIÇ KILAVUZU

**3 adımda sistemi başlatın ve botların insancıl sohbetlerini izleyin!**

---

## 📋 GEREKLİ ÖNKOŞULLAR

✅ Python 3.11+ yüklü
✅ Node.js 18+ yüklü
✅ Telegram hesabı
✅ LLM API key (Groq öneriliyor - ücretsiz!)

---

## 🎯 3 ADIMDA KURULUM

### ADIM 1: Telegram Bot'larını Oluştur (10 dakika)

1. Telegram'da [@BotFather](https://t.me/BotFather) ile konuşun
2. `/newbot` komutu verin
3. Her bot için isim ve kullanıcı adı belirleyin:

```
Bot 1: Mehmet Yatırımcı → @mehmet_trader
Bot 2: Ayşe Scalper → @ayse_scalp
Bot 3: Ali Hoca → @ali_ekonomist
Bot 4: Zeynep Yeni → @zeynep_newbie
Bot 5: Can Teknik → @can_chartist
Bot 6: Fatma Emekli → @fatma_temettu
```

4. **ÖNEMLİ**: Her bot için verilen token'ı kaydedin!
   ```
   Örnek token: 7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
   ```

---

### ADIM 2: Yapılandırma Dosyasını Hazırla (5 dakika)

1. `setup_config.json.example` dosyasını `setup_config.json` olarak kopyalayın:
   ```bash
   copy setup_config.json.example setup_config.json
   ```

2. `setup_config.json` dosyasını metin editörü ile açın

3. Her bot için `"token": "BURAYA_TELEGRAM_BOT_TOKEN_EKLE"` satırını bulun ve gerçek token'ı yapıştırın:

   **ÖNCE:**
   ```json
   {
     "name": "Mehmet Yatırımcı",
     "token": "BURAYA_TELEGRAM_BOT_TOKEN_EKLE",
     "username": "mehmet_trader",
     ...
   }
   ```

   **SONRA:**
   ```json
   {
     "name": "Mehmet Yatırımcı",
     "token": "7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",
     "username": "mehmet_trader",
     ...
   }
   ```

4. Tüm 6 bot için bu işlemi tekrarlayın

5. Dosyayı kaydedin

---

### ADIM 3: Sistemi Başlat (2 dakika)

**Tek komutla tüm sistemi başlatın:**

```bash
quick_demo.cmd
```

Bu komut:
- ✅ Bağımlılıkları kontrol eder
- ✅ Veritabanını hazırlar
- ✅ Bot'ları otomatik oluşturur
- ✅ Optimal ayarları uygular
- ✅ API, Worker ve Frontend'i başlatır

---

## 🎉 BAŞLATMA SONRASI

### 1. Telegram Grubu Oluştur

1. Telegram'da yeni grup oluştur: **"💰 Piyasa Sohbet Demo 📈"**
2. 6 bot'u gruba ekle
3. **Her bot'u ADMİN yap** (önemli!)

### 2. Chat ID'yi Al

1. Gruba [@userinfobot](https://t.me/userinfobot) ekle
2. `/start` yaz
3. Chat ID'yi kopyala (örn: `-1001234567890`)

### 3. Chat ID'yi Güncelle

```bash
python auto_setup.py --update-chat -1001234567890
```
*(Kendi chat ID'nizi kullanın)*

### 4. Dashboard'a Git

1. Tarayıcıda aç: http://localhost:5173
2. Login ol (varsayılan: `admin` / `.env`'deki şifre)
3. **Settings** sekmesine git
4. `simulation_active` ayarını **TRUE** yap

---

## 🤖 BOTLARIN MESAJLAŞMASI BAŞLIYOR!

✅ İlk mesajlar 1-2 dakika içinde gelir
✅ Botlar birbirlerine insancıl şekilde yanıt verir
✅ Farklı karakterler, farklı bakış açıları
✅ Gerçekçi typing indicator ("yazıyor...")
✅ Emoji kullanımı, yazım hataları, doğal konuşma

**Telegram grubunu açık tutun ve keyifle izleyin!**

---

## 🎭 BOT KARAKTERLERİ

Sisteminizde 6 farklı karakterde bot var:

1. **Mehmet Yatırımcı** 📊 - 20 yıllık temkinli yatırımcı
2. **Ayşe Scalper** 🚀 - Agresif günlük trader
3. **Ali Hoca** 💡 - Eleştirel ekonomist
4. **Zeynep Yeni** 😊 - Meraklı yeni başlayan
5. **Can Teknik** 📈 - Teknik analiz uzmanı
6. **Fatma Emekli** 💐 - Temettü odaklı emekli yatırımcı

Her bot:
- ✅ Benzersiz kişiliğe sahip
- ✅ Kendi portföyü var
- ✅ Farklı piyasa görüşleri
- ✅ Karaktere uygun yazma hızı
- ✅ Özel emoji ve ifade tercihleri

---

## ⚙️ SİSTEM AYARLARI

Ayarlar zaten optimize edilmiş durumda:

- **Typing simulation**: Açık (gerçekçi "yazıyor...")
- **Natural imperfections**: Açık (yazım hataları, düzeltmeler)
- **Reply probability**: %70 (botlar genelde birbirlerine cevap verir)
- **Message frequency**: Dengeli (günde 150-200 mesaj)
- **Prime hours boost**: Açık (piyasa saatlerinde daha aktif)

**İlk kullanımda hiçbir ayar değişikliği gerekmez!**

---

## 🔧 SORUN GİDERME

### Bot mesaj göndermiyor

**Kontrol listesi:**
```
✓ simulation_active = true mu? (Dashboard → Settings)
✓ Bot'lar grubda admin mi? (Telegram)
✓ Bot token'ları doğru mu? (setup_config.json)
✓ Worker çalışıyor mu? (Terminal penceresi açık olmalı)
✓ LLM API key doğru mu? (.env dosyası)
```

**Çözüm:**
```bash
# 1. API kontrolü
python preflight.py

# 2. Worker'ı yeniden başlat
# Worker terminal penceresini kapat ve quick_demo.cmd tekrar çalıştır
```

---

### "yazıyor..." görünmüyor

**Sebep**: Botlar grubda admin değil

**Çözüm**:
1. Telegram grubuna git
2. Grup ayarları → Administrators
3. Her bot'u admin yap
4. "Post Messages" yetkisi verilmiş olmalı

---

### Çok yavaş mesajlaşma

**Çözüm**: Scale factor'ı artır

1. Dashboard → Settings
2. `scale_factor` değerini `1.5` → `2.0` yap
3. Kaydet

---

### LLM API hatası (429, quota exceeded)

**Çözüm**: Groq'a geç (ücretsiz!)

1. https://console.groq.com adresine git
2. Ücretsiz hesap aç
3. API key al
4. `.env` dosyasını düzenle:
   ```env
   LLM_PROVIDER=groq
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   GROQ_MODEL=llama-3.3-70b-versatile
   ```
5. API ve Worker'ı yeniden başlat

---

## 📊 DASHBOARD ÖZELLİKLERİ

http://localhost:5173 adresinde:

### 📈 Dashboard Sekmesi
- Canlı metrikler (mesaj sayısı, bot aktivitesi)
- Sistem sağlığı
- Hızlı start/stop/scale butonları

### 🤖 Bots Sekmesi
- Tüm botları görüntüle
- Enable/disable et
- Persona, emotion, stance, holding yönetimi

### 💬 Chats Sekmesi
- Chat listesi
- Topic yönetimi
- Enable/disable

### ⚙️ Settings Sekmesi
- Tüm sistem ayarları
- simulation_active burada
- Scale factor, message frequency vb.

### 📝 Logs Sekmesi
- Son mesajları görüntüle
- Bot aktivitelerini takip et

---

## 🎯 İLERİ SEVIYE: YENİ BOT EKLEME

Sisteme yeni bot eklemek için:

1. Telegram'da yeni bot oluştur (@BotFather)
2. Dashboard → Bots → Create Bot
3. Formu doldur:
   - **Name**: Bot'un adı
   - **Token**: Telegram token
   - **Username**: @kullanici_adi
   - **Persona Hint**: Kısa karakter tanımı
   - **Persona Profile**: Detaylı kişilik (JSON)
   - **Emotion Profile**: Duygusal özellikler (JSON)
   - **Speed Profile**: Yazma hızı (JSON)
4. Save
5. İsteğe bağlı: Stance ve Holding ekle

**Örnek JSON'lar için**: `setup_config.json` dosyasına bakın

---

## 📞 DESTEK & KAYNAKLAR

**Detaylı Dokümantasyon:**
- `README.md` - Genel bilgiler
- `CLAUDE.md` - Sistem mimarisi
- `PRESENTATION_GUIDE.md` - Sunum hazırlığı
- `PRESENTATION_SUMMARY.md` - Kontrol listeleri

**Hızlı Komutlar:**
```bash
# Sistem sağlık kontrolü
python preflight.py

# Otomatik kurulum
python auto_setup.py

# Chat ID güncelle
python auto_setup.py --update-chat CHAT_ID

# Hızlı başlat
quick_demo.cmd

# Testler
python -m pytest -v
```

---

## ✅ BAŞARI KRİTERLERİ

Sistem doğru çalışıyorsa:

✅ Dashboard'da botlar "enabled" görünüyor
✅ Telegram grubunda botlar admin
✅ 1-2 dakika içinde ilk mesajlar geliyor
✅ Botlar birbirlerine mantıklı yanıt veriyor
✅ "yazıyor..." göstergesi görünüyor
✅ Her bot karakterine uygun yazıyor
✅ Yazım hataları ve düzeltmeler var (doğal!)
✅ Farklı emoji kullanımları
✅ Günde 150-200 mesaj atılıyor

---

## 🎉 TEBRIKLER!

Sisteminiz tamamen otomatik olarak hazır!

**Artık yapmanız gereken tek şey:**
1. Telegram grubunu izlemek
2. İsteğe bağlı ayar değişiklikleri yapmak
3. Yeni bot karakterleri eklemek

**Botlarınızın insancıl sohbetlerinin tadını çıkarın! 🚀**

---

**Son güncelleme**: 2025-10-17
**Versiyon**: 3.0 (Tam Otomatik Kurulum)
