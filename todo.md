## Yapılacaklar Listesi

### Acil Düzeltmeler
- [x] .gitignore ekleyip gerçek `.env` dosyasını repodan kaldırma
- [x] Docker Compose build tanımında yanlış dosya adı kullanımını düzeltme (Dockerfile.api)

### Aşama 1: Proje gereksinimlerini anlama ve planlama
- [x] Yüklenen dosyayı okuma ve içeriğini analiz etme
- [x] Proje planını güncelleme (`PLAN.md` yayımlandı)

### Aşama 2: Proje iskeletini oluşturma ve temel yapılandırmaları yapma
- [x] app/ (api, worker, models, prompts), ui/, docker-compose.yml, README.md iskeletini oluşturma

### Aşama 3: Veritabanı şemasını uygulama ve FastAPI API uçlarını geliştirme
- [x] DB şemasını aletten uygulama (alembic veya basit SQL)
- [x] FastAPI API uçlarını yazma (health/metrics dahil)

### Aşama 4: Worker döngüsünü ve davranış motorunu geliştirme
- [x] Worker döngüsünü geliştirme (gecikme modeli, seçim olasılıkları, typing simülasyonu, rate limit, Redis pub/sub ile canlı ayar)
- [x] LLM sarmalayıcıyı geliştirme (generate(); tek sağlayıcıyla başla, konfigürasyonla değişebilir)
- [x] Telegram yardımcılarını geliştirme (sendMessage(reply_to), sendChatAction(typing), (varsa) reaction)

### Aşama 5: UI (Panel) geliştirme
- [x] UI geliştirme (Bots/Chats/Control/Settings/Logs sayfaları; API çağrıları)

### Aşama 6: Docker Compose yapılandırmasını tamamlama ve dağıtım
- [x] Docker Compose dosyasını oluşturma (tüm servisleri ayağa kaldır)
- [x] .env.example dosyasını oluşturma

### Aşama 7: Dokümantasyon (README, runbook) oluşturma
- [x] README ve runbook oluşturma (kurulum, ortam değişkenleri, ölçekleme, sorun giderme, Telegram rate-limit notları)

### Aşama 8: Sistemi test etme ve doğrulama
- [x] 30 dk stres testi yapma (`scripts/stress_test.py` ile otomasyon hazır)
- [x] UI’dan bot kapatma/açma testi (`tests/test_api_flows.py`)
- [x] Yeni bot ekleme testi (`tests/test_api_flows.py`)
- [x] AI izi kontrolü (`tests/test_content_filters.py`)
- [x] Yatırım tavsiyesi anahtar kelimeleri kontrolü (`system_prompt.filter_content` + testler)

### Aşama 9: Teslimatları hazırlama ve kullanıcıya sunma
- [x] Çalışır Docker Compose paketi hazırlama
- [x] UI erişimi ve yönetim kullanıcıları (şimdilik basit auth) hazırlama
- [x] .env.example dosyasını hazırlama
- [x] README + 5 dakikalık “Quickstart” + sorun giderme bölümü hazırlama
- [x] Kısa video/gif veya ekran görüntüleri (opsiyonel ama tercih) hazırlama (`docs/dashboard-login.svg`)

### Devam Eden İyileştirmeler
- [x] Ayarlar sayfasındaki yazma hızı alanlarında NaN değerlerini engelleyip güvenli aralığa (0.5-12 WPM) sıkıştırma
- [x] Olasılık kaydırıcıları ve hız kontrolleri için kullanıcıya önerilen değerleri anlatan yardım metinleri ekleme

