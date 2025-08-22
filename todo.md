## Yapılacaklar Listesi

### Aşama 1: Proje gereksinimlerini anlama ve planlama
- [x] Yüklenen dosyayı okuma ve içeriğini analiz etme
- [ ] Proje planını güncelleme (yapıldı)

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
- [ ] Docker Compose dosyasını oluşturma (tüm servisleri ayağa kaldır)
- [ ] .env.example dosyasını oluşturma

### Aşama 7: Dokümantasyon (README, runbook) oluşturma
- [ ] README ve runbook oluşturma (kurulum, ortam değişkenleri, ölçekleme, sorun giderme, Telegram rate-limit notları)

### Aşama 8: Sistemi test etme ve doğrulama
- [ ] 30 dk stres testi yapma
- [ ] UI’dan bot kapatma/açma testi
- [ ] Yeni bot ekleme testi
- [ ] AI izi kontrolü
- [ ] Yatırım tavsiyesi anahtar kelimeleri kontrolü

### Aşama 9: Teslimatları hazırlama ve kullanıcıya sunma
- [ ] Çalışır Docker Compose paketi hazırlama
- [ ] UI erişimi ve yönetim kullanıcıları (şimdilik basit auth) hazırlama
- [ ] .env.example dosyasını hazırlama
- [ ] README + 5 dakikalık “Quickstart” + sorun giderme bölümü hazırlama
- [ ] Kısa video/gif veya ekran görüntüleri (opsiyonel ama tercih) hazırlama

