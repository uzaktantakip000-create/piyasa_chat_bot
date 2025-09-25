# Telegram Piyasa Sohbet Simülasyonu — Çalıştırma Rehberi

Bu proje, Telegram’da gerçek kullanıcılar gibi görünen (10 → 60+) “piyasalar” sohbetini simüle eder.
Aşağıdaki adımlarla yerelde veya Docker ile çalıştırabilirsiniz.

---

## 0) Gereksinimler

- Python 3.10+ (3.11 önerilir)
- (Opsiyonel) Redis 6/7+
- (Yerel) Telegram bot tokenları (en az 10 adet)
- OpenAI API anahtarı
- `TOKEN_ENCRYPTION_KEY` üretmek için `cryptography` paketi

> Not: Redis olmadan da çalışır; ancak canlı/ani ayar güncellemeleri pub/sub ile daha akıcı olur.
> Redis yoksa `REDIS_URL` boş kalsın — sistem gracefully degrade eder.

---

## 1) Kurulum (Yerel)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env içindeki API_KEY ve TOKEN_ENCRYPTION_KEY değerlerini doldurun
# API_KEY panel istekleriyle FastAPI'ye gönderilir; TOKEN_ENCRYPTION_KEY bot tokenlarını şifreler.
```

### Güvenlik değişkenleri

- **API_KEY**: Paneldeki tüm HTTP çağrıları `X-API-Key` başlığında bu değeri taşır. Boş bırakılamaz.
- **TOKEN_ENCRYPTION_KEY**: Telegram bot tokenları şifreli saklanır. `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` komutu ile 44 karakterlik bir anahtar üretip `.env` dosyasına yazın.
- **ALLOWED_ORIGINS**: Panel domain(ler)ini virgülle ayırarak tanımlayın. Varsayılan `http://localhost:3000`.

İlk çalıştırmada `TOKEN_ENCRYPTION_KEY` sağlanmışsa, veritabanındaki mevcut düz metin tokenlar otomatik olarak şifrelenir.

### Veritabanı notu

Geliştirme için SQLite kullanılabilir; üretimde PostgreSQL veya benzeri çok kullanıcılı bir veritabanına geçip `DATABASE_URL` değişkenini güncelleyin. Worker ve API aynı anda yoğun yazma yaptığından SQLite üretim yükü altında önerilmez.
