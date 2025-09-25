# Telegram Piyasa Sohbet Simülasyonu

Bu depo, Telegram'da 10+ botla gerçekçi piyasa sohbetleri üreten sistemin hem FastAPI backend'ini hem de React tabanlı yönetim panelini içerir. Proje; bot/sohbet yönetimi, davranış motoru, LLM entegrasyonu ve dağıtım araçlarını tek pakette sunar.

## Özellikler
- FastAPI tabanlı REST API ile bot, sohbet, ayar ve persona uçları
- Davranış motoru (worker) ile LLM tabanlı mesaj üretimi ve Telegram gönderimi
- Yönetim paneli (React) ile dashboard, bot/sohbet/ayar/log ekranları
- Redis ile anlık konfigürasyon yayını (opsiyonel)
- Docker Compose ile API, worker, PostgreSQL ve Redis'i tek komutla başlatma
- API anahtarı ve bot token şifreleme ile güçlendirilmiş güvenlik katmanı

## Hızlı Başlangıç (5 Dakika)

### 1. Depoyu klonla ve ortamı hazırla
```bash
git clone <repo-url>
cd piyasa_chat_bot
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Ortam değişkenlerini tanımla
```bash
cp .env.example .env
```
`.env` dosyasındaki kritik alanlar:

| Değişken | Açıklama |
| --- | --- |
| `API_KEY` | Panelden API'ye giden tüm istekler `X-API-Key` başlığında bu değeri taşır. Boş bırakılamaz. |
| `TOKEN_ENCRYPTION_KEY` | Telegram bot tokenlarını şifrelemek için kullanılır. `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` ile üret. |
| `DATABASE_URL` | Varsayılan `sqlite:///./app.db`. Üretimde PostgreSQL önerilir. |
| `ALLOWED_ORIGINS` | Paneli barındıran domain(ler). Virgülle ayır. |
| `VITE_API_KEY` | Yönetim paneli build'i için API anahtarı. |

Geliştirme sırasında Redis zorunlu değildir; ancak gerçek zamanlı ayar yayınları için `.env` dosyasında `REDIS_URL` tanımlanabilir.

### 3. API ve worker'ı başlat
```bash
uvicorn main:app --reload
# Ayrı terminalde
python worker.py
```

### 4. Paneli çalıştır (Vite)
```bash
npm install
npm run dev
```
> Not: Panel Vite altyapısı ile çalışır; `VITE_API_KEY` değeri `.env` veya `vite.config.js` üzerinden build'e aktarılmalıdır.

### 5. Docker Compose ile çalıştır
```bash
docker compose up --build
```
Bu komut; FastAPI, worker, PostgreSQL ve Redis servislerini ayağa kaldırır. Varsayılan olarak API 8000 portundan, Redis 6379 portundan yayın yapar.

## Testler ve Kontroller
```bash
python -m compileall -x '/\.venv' .
```
Ek olarak worker/behavior motoru entegrasyon testleri ve Telegram sahte istekleri için pytest senaryoları eklenmesi planlanmaktadır.

## Güvenlik Notları
- `API_KEY` ve `TOKEN_ENCRYPTION_KEY` değerlerini repoya kesinlikle eklemeyin. `.gitignore` dosyası `.env` ve türevlerini dışlar.
- API anahtarı olmadan hiçbir yönetim uç noktası erişilebilir değildir.
- Tokenlar veritabanında Fernet ile şifrelenir; eski düz metin kayıtları `migrate_plain_tokens()` ile otomatik şifrelenir.

## Yapı Taşları
- `main.py`: FastAPI uygulaması, CRUD uçları, ayar yönetimi ve metrikler
- `behavior_engine.py`: Davranış motoru döngüsü, LLM çağrıları, Telegram gönderimleri
- `telegram_client.py`: Telegram Bot API istemcisi, hata sayaçları ve geridönüş mekanizması
- `worker.py`: Davranış motorunu sürekli çalıştıran runner
- `Dashboard.jsx`, `Bots.jsx`, `Chats.jsx`, `Settings.jsx`, `Logs.jsx`: Panel sayfaları
- `docker-compose.yml`: API, worker, Postgres, Redis servisleri için orkestrasyon
- `RUNBOOK.md`: Daha ayrıntılı operasyon rehberi ve ortam kurulum talimatları

## Sorun Giderme
- **`401 Invalid or missing API key`**: Paneldeki `.env` veya barındırma ortamında `VITE_API_KEY` ve API tarafında `API_KEY` değerlerinin eşleştiğinden emin olun.
- **`TOKEN_ENCRYPTION_KEY is not set`**: API başlatılmadan önce `.env` dosyasında geçerli bir anahtar üretildiğinden emin olun. Eski düz metin tokenlar anahtar sağlanmadan migrate edilmez.
- **Docker build başarısız**: `docker-compose.yml` içinde `Dockerfile.api` yolu ve `.env` dosyasındaki gerekli değişkenler doğrulanmalı.
- **Worker Redis'e bağlanamıyor**: `REDIS_URL` boş bırakıldığında worker otomatik olarak Redis senkronizasyonunu devre dışı bırakır; loglardaki uyarılar bilgilendirme amaçlıdır.

## Yol Haritası
- UI bileşenlerinin stil katmanının tamamlanması ve paketlenmesi
- Entegrasyon testleri ile Telegram / LLM uçlarının otomasyonu
- Gelişmiş auth (örn. kullanıcı bazlı oturum) ve rol yönetimi
- Gerçek zamanlı metrikler için SSE/WebSocket desteği

Daha fazla ayrıntı ve operasyonel senaryolar için `RUNBOOK.md` dosyasına göz atın.
