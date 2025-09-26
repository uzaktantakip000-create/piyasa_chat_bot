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
- **VITE_API_KEY**: Panel build'i sırasında kullanılan varsayılan API anahtarı. Panel açıldığında bu değer otomatik olarak giriş formuna doldurulur.
- **VITE_DASHBOARD_PASSWORD**: (Opsiyonel) Panelin giriş ekranını koruyan şifre. Tanımlanırsa kullanıcılar API anahtarına ek olarak bu şifreyi girmelidir.

### Panel giriş akışı

Panel ilk açıldığında kullanıcıyı basit bir giriş formu karşılar:

1. API anahtarı (`VITE_API_KEY` env değerinden veya daha önce kaydedilen localStorage verisinden okunur) giriş alanına otomatik taşınır.
2. `VITE_DASHBOARD_PASSWORD` tanımlı ise ikinci bir şifre alanı görünür. Şifre eşleşmezse oturum açılmaz.
3. Başarılı doğrulama sonrası ana uygulama yüklenir ve oturum bilgisi localStorage'da saklanır. API 401 döndürdüğünde oturum otomatik olarak sonlandırılır ve kullanıcı giriş ekranına yönlendirilir.

İlk çalıştırmada `TOKEN_ENCRYPTION_KEY` sağlanmışsa, veritabanındaki mevcut düz metin tokenlar otomatik olarak şifrelenir.

### Veritabanı notu

Geliştirme için SQLite kullanılabilir; üretimde PostgreSQL veya benzeri çok kullanıcılı bir veritabanına geçip `DATABASE_URL` değişkenini güncelleyin. Worker ve API aynı anda yoğun yazma yaptığından SQLite üretim yükü altında önerilmez.

---

## 2) Test & doğrulama

- **Statik kontrol**: `python -m compileall -x '/\.venv' .`
- **API entegrasyon testleri**: `pytest`
- **Yük testi**: `python scripts/stress_test.py --duration 1800 --concurrency 6 --api-key $API_KEY`

`scripts/stress_test.py` aracı FastAPI uygulamasını bellekte çalıştırıp eşzamanlı isteklerle `/metrics`, `/bots`, `/control/*` uçlarını zorlar. Yerelde hızlı doğrulama için `--duration 30` parametresi yeterlidir.
