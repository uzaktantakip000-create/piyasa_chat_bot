# Proje Planı — Telegram Piyasa Simülasyonu

Bu plan, uygulamanın yol haritasını ve tamamlanan/planlanan çalışmaları özetler.

## 1. Mimari Bileşenler
- **FastAPI API**: Bot/sohbet CRUD, ayar yönetimi, metrikler ve kontrol uçları.
- **Davranış Motoru (worker)**: LLM çağrıları, Telegram gönderimi, tutarlılık ve içerik filtreleri.
- **Yönetim Paneli (React)**: Dashboard, bot/sohbet/ayar/log ekranları, kurulum sihirbazı.
- **Destekleyici servisler**: Redis (opsiyonel canlı ayar yayını), PostgreSQL (üretim veritabanı).

## 2. Tamamlanan Çalışmalar
- API anahtarı zorunluluğu, bot token şifreleme ve maskeleme.
- Yönetim panelinde API anahtarı + opsiyonel şifre ile giriş akışı.
- Ayar ekranı validasyonları ve LLM çıktı filtreleri (AI izleri, yatırım tavsiyesi anahtar kelimeleri).
- Entegrasyon testleri (`pytest`) ile bot ekleme/kapatma, chat/metrics ve kontrol uçlarının doğrulanması.
- `scripts/stress_test.py` ile 30 dakikalık yük testi için otomasyon şablonu.
- README ve RUNBOOK güncellemeleri, hızlı başlangıç ve operasyon notları.

## 3. Sıradaki Adımlar
- PostgreSQL / Redis ile staging ortamı kurup davranış motorunu gerçek trafikte gözlemlemek.
- Websocket/SSE tabanlı canlı metrik aktarımı.
- Bot persona yönetimi için ek UI/endpoint iyileştirmeleri.
- LLM sağlayıcı fallback stratejilerini genişletmek (Azure OpenAI vb.).

Bu plan `todo.md` ile senkron çalışır; yapılan her geliştirme ilgili aşamaların işaretlenmesiyle takip edilir.
