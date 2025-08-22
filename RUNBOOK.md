# Telegram Piyasa Sohbet Simülasyonu — Çalıştırma Rehberi

Bu proje, Telegram’da gerçek kullanıcılar gibi davranan botlarla piyasalar sohbetini simüle eder.
Aşağıdaki adımlarla yerelde veya Docker ile çalıştırabilirsiniz.

---

## 0) Gereksinimler

- Python 3.10+ (3.11 önerilir)
- (Opsiyonel) Redis 6/7+
- (Opsiyonel) Node.js 18+  — frontend panelini çalıştırmak için
- Telegram bot tokenları (en az 10 adet)
- OpenAI API anahtarı

> Redis olmadan da çalışır; `REDIS_URL` boş bırakılabilir.

---

## 1) Hızlı Başlangıç Scripti

Projeyi klonladıktan sonra tek komutla çalıştırabilirsiniz:

```bash
bash setup_all.sh
```

Script şunları yapar:
1. Python sanal ortamı oluşturur ve bağımlılıkları yükler.
2. `.env` dosyasını hazırlar ve gerekli anahtarları ister.
3. API (`uvicorn`), worker (`worker.py`) ve varsa frontend'i paralel başlatır.
4. Çalışan servislerin adreslerini ekrana yazar.

`Ctrl+C` ile scripti sonlandırabilirsiniz; arka plan süreçleri de kapanır.

---

## 2) Manuel Kurulum

Aşağıdaki adımlar scriptin yaptığı işlemleri manuel olarak gerçekleştirir.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` dosyasını kendi anahtarlarınızla düzenledikten sonra servisleri başlatın:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
python worker.py
```

Frontend için `package.json` varsa:

```bash
npm install
npm run dev
```

---

## 3) Docker ile Çalıştırma

```bash
docker compose build
docker compose up
```

Bu komutlar API, worker ve diğer servisleri kapsayan konteynerleri çalıştırır.
İlk çalıştırmadan önce `.env` dosyanızı hazırladığınızdan emin olun.

---

## 4) Kullanım ve Kontrol

- API Dokümantasyonu: [http://localhost:8000/docs](http://localhost:8000/docs)
- Simülasyonu başlatma: `POST /control/start`
- Durdurma: `POST /control/stop`
- Hız değiştirme: `POST /control/scale` (JSON gövde: `{ "factor": 1.2 }`)
- Son loglar: `GET /logs/recent?limit=20`

Wizard/kurulum arayüzü frontend içinde mevcuttur.

---

## 5) Sorun Giderme

- Python veya Node.js bulunamıyorsa PATH ayarlarınızı kontrol edin.
- Port çakışması durumunda `setup_all.sh` yerine manuel kurulum adımlarını kullanıp
  `uvicorn` portunu değiştirin.
- `pip install` sırasında SSL veya ağ hataları alırsanız tekrar deneyin veya
  farklı bir ayna kullanın.

---

Bu rehber sayesinde projeyi hızlıca kurabilir, çalıştırabilir ve sorunları çözebilirsiniz.
