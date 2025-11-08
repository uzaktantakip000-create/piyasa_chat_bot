# Telegram Piyasa Sohbet Simülasyonu

Bu proje, Telegram üzerinde birden fazla botu aynı anda konuşturarak gerçekçi bir piyasa sohbeti yaratır. Kod tabanı; FastAPI ile yazılmış bir REST servisini, arka planda mesaj akışını yöneten bir worker sürecini ve React tabanlı bir yönetim panelini içerir. Aşağıdaki adımlar teknik altyapısı olmayan ekipler için bile kolayca takip edilebilecek şekilde sadeleştirildi.

---

## 1. Sistem Neler Yapar?
- Birden fazla Telegram botunu aynı anda çalıştırır ve belirlediğiniz grup(lar)a mesaj gönderir.
- Botların kişiliklerini, hızlarını ve konuşma konularını yönetim panelinden düzenleyebilirsiniz.
- Worker süreci OpenAI API'si aracılığıyla yeni mesajlar üretir, gerekirse haber akışını da metinlere ekler.
- REST API'si üzerinden bot, sohbet, ayar ve metrik yönetimi yapılır; panel bu API'yi kullanır.

---

## 2. Gerekli Hazırlıklar
| Gerekli unsur | Neden gerekli? |
| --- | --- |
| Telegram hesabı | `@BotFather` ile bot oluşturup token almanız gerekir. |
| OpenAI API anahtarı | Botların gerçekçi mesajlar üretebilmesi için LLM'e ihtiyaç vardır. |
| Kurulum tercihi | **Docker Desktop (önerilir)** ya da Python 3.11 + Node.js 18. |

> İpucu: Sunucu veya CI ortamlarında `API_KEY`, `OPENAI_API_KEY`, `TOKEN_ENCRYPTION_KEY` gibi değerleri `.env` dosyasına yazabilir ya da ortam değişkeni olarak verebilirsiniz.

Önemli `.env` anahtarları:
- `API_KEY`: Panel girişinde kullanacağınız cümle.
- `VITE_API_KEY`: Tarayıcı tarafı için aynı değerin kopyası.
- `VITE_DASHBOARD_PASSWORD`: İkinci bir şifre eklemek isterseniz kullanılır (boş bırakılabilir).
- `OPENAI_API_KEY`: OpenAI erişimi için zorunludur.
- `TOKEN_ENCRYPTION_KEY`: Telegram tokenlarını şifrelemek için uzun rastgele bir anahtar (ör. `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
- `DATABASE_URL`: Varsayılan `sqlite:///./app.db`. PostgreSQL kullanacaksanız bağlantı adresini buraya yazın.
- `REDIS_URL`: Opsiyoneldir; girilmezse worker yerel bellekte çalışır.
- `DASHBOARD_STREAM_INTERVAL`: Dashboard WebSocket yayınlarının kaç saniyede bir gönderileceğini belirler (varsayılan `5`).
- `DASHBOARD_STREAM_MAX_MESSAGES`: Test veya otomasyon ortamlarında WebSocket'in kaç mesajdan sonra otomatik kapanacağını belirler (varsayılan sınırsız).

`.env.example` dosyasını kopyalayıp `.env` adıyla düzenleyerek başlayın.

---

## 3. Kurulum Adımları
Aşağıdaki yöntemlerden size uyanı seçin. Her yol sonunda paneli `http://localhost:5173` adresinden açabilirsiniz.

### Yöntem A – Docker Compose (önerilen)
1. Projeyi indirin ve klasöre girin.
2. `.env.example` dosyasını `.env` olarak kopyalayıp yukarıdaki alanları doldurun.
3. Terminalde projeye gidip şu komutu çalıştırın (API, worker ve Vite tabanlı panel konteyneri birlikte ayağa kalkar):
   ```bash
   docker compose up --build
   ```
4. Servisler hazır olduğunda tarayıcıdan `http://localhost:5173` adresindeki panele gidin ve `API_KEY` (ve varsa panel şifreniz) ile giriş yapın.
5. Durdurmak için `Ctrl + C` veya başka bir terminalden `docker compose down` komutunu kullanın.

### Yöntem B – Windows için `setup_all.cmd`
1. Windows 10/11'de proje klasörünü açıp `setup_all.cmd` dosyasına çift tıklayın **ya da** Komut İstemcisinde `setup_all.cmd` yazın.
2. Betik sizden OpenAI anahtarınızı ister; Redis veya veritabanı adresiniz yoksa bu alanları boş bırakabilirsiniz.
3. Betik; Python sanal ortamı, Node paketleri, API, worker ve Vite dev sunucusunu sırasıyla başlatır.
4. Açılan terminalleri kapatmadan tarayıcıdan panel adresine gidin. Kapatmak istediğinizde pencerelerde `Ctrl + C` yapmanız yeterlidir.
5. CI/otomasyon için `setup_all.cmd --ci` komutunu kullanabilir, gerekli anahtarları ortam değişkeni olarak sağlayabilirsiniz.

### Yöntem C – Manuel Kurulum (Docker kullanmayanlar için)
1. Sanal ortam oluşturun ve Python bağımlılıklarını kurun:
   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Node.js paketlerini kurun:
   ```bash
   npm install
   ```
3. `.env` dosyanızı doldurun.
4. Üç ayrı terminal açıp aşağıdaki komutları çalıştırın:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   python worker.py
   npm run dev
   ```
5. Panelden giriş yapın. Worker betiği artık eksik `argparse` importu nedeniyle hata vermez.

### Yöntem D – Setup Wizard (İlk Kurulum için Önerilen) 🆕
1. Sistemi yukarıdaki yöntemlerden biriyle başlatın.
2. Tarayıcıdan `http://localhost:5173` adresine gidin.
3. Sistem otomatik olarak Setup Wizard'ı gösterecektir (ilk kurulumda).
4. **Adım 1:** LLM Provider seçin (Groq önerilen - ücretsiz ve hızlı) ve API key'inizi girin.
5. **Adım 2:** Admin kullanıcı oluşturun (kullanıcı adı, güçlü şifre, opsiyonel MFA).
6. **Adım 3:** Kurulumu tamamlayın ve dashboard'a yönlendirileceksiniz.
7. Setup Wizard `.env` dosyasını otomatik oluşturur ve admin kullanıcıyı database'e ekler.

**Avantajlar:**
- ✅ Manuel `.env` düzenlemeye gerek yok
- ✅ 5 dakikada kurulum tamamlanır
- ✅ API key validation ile hata riski minimize
- ✅ Güçlü şifre kontrolü
- ✅ Otomatik admin user oluşturma

---

## 4. Günlük Kullanım
1. **Giriş yapın.** `API_KEY` (ve varsa panel şifresi) ile oturum açın.
2. **Bot ekleyin.** Bots sayfasından `Add bot` düğmesine basıp BotFather'dan aldığınız tokenı girin.
3. **Sohbet ekleyin.** Chats sayfasında Telegram grup kimliğini (`-100...`) yazın ve hangi botların bu grupta yer alacağını seçin.
4. **Ayarları düzenleyin.** Settings sekmesinden mesaj hızları, prime saatler, haber tetikleyicisi gibi seçenekleri kaydedin.
5. **Simülasyonu başlatın.** Dashboard'da `Start` ve `Stop` butonları ile tüm botların konuşmasını yönetebilirsiniz. `Scale` butonları mesaj yoğunluğunu değiştirir.
6. **Logları takip edin.** Logs sekmesi ve `/logs/recent` uç noktası hataları görmenizi sağlar. 429 hatası görürseniz mesaj hızını azaltın.

Ek araçlar:
- `python bootstrap.py --chat-id <id> --tokens-file tokens.json --start` komutu toplu bot ekler.
- `scripts/oneclick.py` çalıştırıldığında API, veritabanı, Redis ve panel için hızlı sağlık kontrolü raporu üretir (`latest_oneclick_report.json`).

---

## 5. Sağlık Kontrolleri ve Testler
- **Birim testleri:**
  ```bash
  pytest
  ```
- **Hızlı sağlık taraması:** API, veritabanı ve dış servisleri kontrol etmek için `python preflight.py` komutunu kullanın. API ayakta değilse bağlantı hatası almanız normaldir; komut amaç gereği bunu raporlar.
- **Worker doğrulaması:** `python worker.py --check-only` komutu gerekli modüllerin yüklenip yüklenmediğini test eder.
- **README kaynak eşitlemesi:** `python scripts/generate_readme_resources.py` komutu `docs/` klasöründeki Markdown dosyalarını okuyup README'deki "Yol Haritası ve Kaynaklar" listesini günceller. GitHub Actions üzerinde çalışan `validate-roadmap` iş akışı `--check` parametresiyle aynı doğrulamayı otomatik olarak yapar ve liste güncel değilse katkıları başarısız olarak işaretler.

---

## 6. Sık Sorulan Sorular
- **Varsayılan panel şifresi var mı?** Hayır. `VITE_DASHBOARD_PASSWORD` boş ise yalnızca `API_KEY` sorulur.
- **Redis zorunlu mu?** Hayır. `REDIS_URL` verilmezse worker yerel bellekte ayarları yönetir.
- **Veritabanını nasıl değiştiririm?** `.env` dosyasında `DATABASE_URL` değerini PostgreSQL bağlantınızla değiştirip servisleri yeniden başlatın.
- **Model seçimi nasıl yapılır?** `.env` içinde `LLM_MODEL` satırını güncelleyerek OpenAI modelini değiştirebilirsiniz (ör. `gpt-4o-mini`).

---

## 7. Yol Haritası ve Kaynaklar
<!-- README_DOCS_START -->
- [Hata Yönetimi ve Log Merkezileştirme Stratejisi](docs/error_management.md)
- [Panel Kullanıcı Deneyimi Geliştirme Planı](docs/panel_user_experience_plan.md)
- [Test Sonuçları ve Sistem Sağlığı Raporlama Modülü — Kapsam & Roadmap](docs/reporting_roadmap.md)
- [Kullanıcı Deneyimini Profesyonelleştirme Önerileri](docs/ux-improvement-suggestions.md)
<!-- README_DOCS_END -->
- QuickStart kartındaki görsel rehber `docs/dashboard-login.svg` dosyasında bulunur.

Kurulum tamamlandıktan sonra tarayıcı paneli üzerinden botları yönetebilir, `pytest` ile regresyon testlerini çalıştırabilir ve `python scripts/oneclick.py` komutuyla tüm servislerin sağlık raporunu alabilirsiniz.
