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

### Yapılabilecekler
- [ ] **P1:** Kurulum sürecini uçtan uca otomatikleştiren ve bağımlılık kontrollerini yapan `setup_all` sihirbazını CI'da doğrula, README talimatlarını bu akışla uyumlu hale getir.
- [ ] **P1:** Docker Compose + one-click senaryosu için ilk çalıştırma smoke testini genişleterek tüm servislerin healthcheck sonuçlarını raporla.
- [ ] **P2:** QuickStart ve README kullanım senaryolarını kapsayan uçtan uca entegrasyon testlerini yazıp `scripts/oneclick.py` sonrası otomatik koştur.
- [ ] **P2:** API, worker ve UI loglarını merkezileştiren ve kritik hatalar için alarm eşikleri tanımlayan hata yönetimi stratejisi tasarla.
- [ ] **P2:** UI'da beklenmedik hatalarda gösterilen geri bildirim bileşenlerini standartlaştırıp gerekli destek bağlantılarıyla güncelle.
- [ ] **P3:** Dashboard ve ayarlar akışları için ayar değişikliklerini kapsayan regresyon test paketleri oluştur.
- [ ] **P3:** README ve QuickStart rehberlerini görsel sorun giderme akışlarıyla zenginleştirerek kullanıcı onboarding'ini iyileştir.
- [ ] **P4:** Test sonuçları ve sistem sağlığı trendlerini gösteren raporlama/grafik modülü için kapsam ve roadmap planı hazırla.
- [x] Mesaj uzunluk profili değerlerini API katmanında otomatik normalize ederek toplamın %100 olmasını garanti altına alma.
- [x] Ayarlar panelindeki mesaj uzunluk kaydırıcılarını normalize eden ve toplam yüzdelik göstergesi sunan kullanıcı dostu arayüz geliştirmesi.

- [ ] Bot ve sohbet listelerinde kullanılan arama ve durum filtrelerini tarayıcı depolamasında saklayarak sayfa yenilemelerinde kaybolmalarını önle.
- [ ] Liste tablolarında sütun başlıklarına göre sıralama özelliği ekleyerek kalabalık veri setlerinde aranan kaydı hızla bulmayı kolaylaştır.
- [ ] Dashboard manuel yenileme ve kritik aksiyonları için klavye kısayolları tanımlayarak güç kullanıcılarına daha hızlı erişim sun.
- [ ] QuickStart ilerleme durumunu kullanıcı bazında hatırlayarak onboarding rehberine kaldığı yerden devam etme deneyimi sağla.
- [x] Tek komutla API, worker ve paneli ayağa kaldırıp sağlık kontrollerini yürüten `scripts/oneclick.py` komutunu hazırla.
- [x] One-click başlatma sonrasında smoke test ve stres testi sırayla koşturan otomasyon akışını uygula.
- [x] Test sonuçlarını veritabanında saklayıp `/system/checks/latest` uç noktasıyla panele servis et.
- [x] Dashboard'da son test özetini ve stres testi kontrollerini gösteren yeni kart ekle.

### UX İyileştirme Görevleri
- [x] Dashboard metrikleri yüklenene kadar görsel geri bildirim ve "güncelleniyor" durumu ekle.
- [x] Dashboard başlığına manuel yenile düğmesi ekle ve veri gecikmelerini InlineNotice ile bildir.
- [x] Bot ve sohbet CRUD akışlarında tarayıcı uyarıları yerine panel içi toast/diyalog geri bildirimi kullan.
- [x] Bot ve sohbet listelerine arama, durum filtresi ve toplu işlem yetenekleri ekle.
- [x] Bot ve sohbet formlarında alan doğrulaması ve yardım metinleri ekle.
- [x] QuickStart rehberine ilerleme göstergesi ekle.
- [x] QuickStart kopyalama aksiyonlarını geliştirilmiş hata/başarı bildirimleri ve bağlamsal CTA'larla güçlendir.
- [x] Giriş panelinde oturum durumu ve parola gereksinimleri hakkında açıklayıcı içerik sun.
- [x] Dashboard kartlarında eşik temelli tema/ikon göstergeleri ile anlam katmanı oluştur.

