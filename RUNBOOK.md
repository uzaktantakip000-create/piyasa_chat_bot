# Telegram Piyasa Sohbet Simülasyonu — Çalıştırma Rehberi

Bu proje, Telegram’da gerçek kullanıcılar gibi görünen (10 → 60+) “piyasalar” sohbetini simüle eder.
Aşağıdaki adımlarla yerelde veya Docker ile çalıştırabilirsiniz.

---

## 0) Gereksinimler

- Python 3.10+ (3.11 önerilir)
- (Opsiyonel) Redis 6/7+
- (Yerel) Telegram bot tokenları (en az 10 adet)
- OpenAI API anahtarı

> Not: Redis olmadan da çalışır; ancak canlı/ani ayar güncellemeleri pub/sub ile daha akıcı olur.
> Redis yoksa `REDIS_URL` boş kalsın — sistem gracefully degrade eder.

---

## 1) Kurulum (Yerel)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
