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
- [x] **P1:** Kurulum sürecini uçtan uca otomatikleştiren ve bağımlılık kontrollerini yapan `setup_all` sihirbazını CI'da doğrula, README talimatlarını bu akışla uyumlu hale getir.
- [x] **P1:** Docker Compose + one-click senaryosu için ilk çalıştırma smoke testini genişleterek tüm servislerin healthcheck sonuçlarını raporla.
- [x] **P2:** QuickStart ve README kullanım senaryolarını kapsayan uçtan uca entegrasyon testlerini yazıp `scripts/oneclick.py` sonrası otomatik koştur.
- [x] **P2:** API, worker ve UI loglarını merkezileştiren ve kritik hatalar için alarm eşikleri tanımlayan hata yönetimi stratejisi tasarla.
- [x] **P2:** UI'da beklenmedik hatalarda gösterilen geri bildirim bileşenlerini standartlaştırıp gerekli destek bağlantılarıyla güncelle.
- [x] **P3:** Dashboard ve ayarlar akışları için ayar değişikliklerini kapsayan regresyon test paketleri oluştur.
- [x] **P3:** README ve QuickStart rehberlerini görsel sorun giderme akışlarıyla zenginleştirerek kullanıcı onboarding'ini iyileştir.
- [x] **P4:** Test sonuçları ve sistem sağlığı trendlerini gösteren raporlama/grafik modülü için kapsam ve roadmap planı hazırla.
- [x] Mesaj uzunluk profili değerlerini API katmanında otomatik normalize ederek toplamın %100 olmasını garanti altına alma.
- [x] Ayarlar panelindeki mesaj uzunluk kaydırıcılarını normalize eden ve toplam yüzdelik göstergesi sunan kullanıcı dostu arayüz geliştirmesi.

- [x] Bot ve sohbet listelerinde kullanılan arama ve durum filtrelerini tarayıcı depolamasında saklayarak sayfa yenilemelerinde kaybolmalarını önle.
- [x] Liste tablolarında sütun başlıklarına göre sıralama özelliği ekleyerek kalabalık veri setlerinde aranan kaydı hızla bulmayı kolaylaştır.
- [x] Dashboard manuel yenileme ve kritik aksiyonları için klavye kısayolları tanımlayarak güç kullanıcılarına daha hızlı erişim sun.
- [x] QuickStart ilerleme durumunu kullanıcı bazında hatırlayarak onboarding rehberine kaldığı yerden devam etme deneyimi sağla.
- [x] Tek komutla API, worker ve paneli ayağa kaldırıp sağlık kontrollerini yürüten `scripts/oneclick.py` komutunu hazırla.
- [x] One-click başlatma sonrasında smoke test ve stres testi sırayla koşturan otomasyon akışını uygula.
- [x] Test sonuçlarını veritabanında saklayıp `/system/checks/latest` uç noktasıyla panele servis et.
- [x] Dashboard'da son test özetini ve stres testi kontrollerini gösteren yeni kart ekle.

### Sistem Doğrulama Sonrası Aksiyonlar
- [x] **P0:** Panelde API anahtarını `localStorage` yerine oturum bazlı (örn. `sessionStorage` + HttpOnly session) sakla ve XSS’ye dayanıklı hale getir.
  - Açıklama: Kimlik doğrulama anahtarını kalıcı depolamadan taşıyarak saldırı yüzeyini daralt.
  - Beklenen Fayda: Anahtar sızıntı riskini azaltarak yönetim paneli güvenliğini artırır.
  - Kabul Kriteri: Güvenlik testinde `localStorage` anahtarı bulunmuyor, XSS simülasyonunda anahtar ele geçirilemiyor.
  - Efor: M
- [x] **P0:** `_startup` loglarında dönen varsayılan admin API anahtarı ve MFA sırrını maskele veya yalnızca tek seferlik CLI çıktısı olarak göster.
  - Açıklama: Başlatma loglarında gizli bilgiler yerine güvenli placeholder kullan.
  - Beklenen Fayda: Üretim log’larında gizli veri tutmayarak mevzuat uyumu ve güvenlik sağlar.
  - Kabul Kriteri: Uygulama başlatıldığında loglarda API anahtarı/MFA sırrı görünmez; güvenlik taraması bunu doğrular.
  - Efor: S
- [ ] **P1:** FastAPI ve bağlı Starlette/AnyIO paketlerini desteklenen LTS sürümüne yükselt; şema uyumunu ve testleri güncelle.
  - Açıklama: Çekirdek web çerçevesini güncel tutarak güvenlik yamalarını uygula.
  - Beklenen Fayda: Güvenlik yamalarını almak ve Python 3.11+ uyumluluğunu korumak.
  - Kabul Kriteri: `pytest` ve `preflight` güncel sürümle geçer; bağımlılık güvenlik taraması kritik açık göstermiyor.
  - Efor: M
- [x] **P1:** `apiFetch` için offline/timeout hata yakalayıcıları ekle; kullanıcıya yeniden dene / bağlantı durumu bildirimi göster.
  - Açıklama: Ağ hata senaryolarında kullanıcıya rehberlik eden dayanıklı istemci davranışı ekle.
  - Beklenen Fayda: Kullanıcı deneyimini iyileştirir, ağ kesintilerinde destek taleplerini azaltır.
  - Kabul Kriteri: Ağ bağlantısı kesildiğinde UI’da anlamlı uyarı/yeniden dene butonu görülür; manuel testte doğrulanır.
  - Efor: S
- [ ] **P1:** React bileşenleri için Vitest/Jest tabanlı smoke & kritik akış testleri ekle (giriş, bot/sohbet CRUD, metrik görüntüleme).
  - Açıklama: Ön uç katmanı için temel regresyon test paketi oluştur.
  - Beklenen Fayda: Regresyon riskini azaltır, CI güvenini artırır.
  - Kabul Kriteri: Yeni test suiti CI’da çalışır ve temel akışlar için >70% satır kapsamı raporlanır.
  - Efor: M
- [ ] **P2:** Dashboard’da `/ws/dashboard` WebSocket akışını kullanıp periyodik REST poll’u azalt; fallback mekanizması ekle.
  - Açıklama: Canlı veri beslemesini gerçek zamanlı akışa taşıyarak gereksiz istekleri azalt.
  - Beklenen Fayda: API yükünü düşürür, metrik güncellemelerinde gecikmeyi azaltır.
  - Kabul Kriteri: WebSocket açıkken REST istek sıklığı %80 azalır; metrik gecikmesi <1 sn ölçülür.
  - Efor: M

### Stratejik Sistem Geliştirme Fikirleri
- [ ] **P0:** Servisler arası trafiği sıfır güven modeliyle yeniden tasarlayarak mTLS + kısa ömürlü servis kimlikleri kullanan güvenli bir ağ katmanı uygula.
  - Açıklama: FastAPI API, worker ve WebSocket bileşenleri arasında karşılıklı TLS ve dinamik olarak döndürülen sertifikalarla kimlik doğrulaması kur.
  - Beklenen Fayda: Kimlik sahteciliği ve yatay hareket riskini azaltarak üretim ortamında veri sızıntısı yüzeyini daraltır.
  - Kabul Kriteri: Tüm servis çağrıları mTLS üzerinden başarılır; yetkisiz sertifikayla yapılan bağlantı girişimleri reddedilir ve gözlemlenebilir loglara kaydedilir.
  - Efor: L
- [ ] **P0:** OpenTelemetry tabanlı izleme, metrik ve dağıtılmış iz (trace) altyapısını kurarak uçtan uca gözlemlenebilirlik sağlayan merkezi bir observability yığını oluştur.
  - Açıklama: Python API/worker ve React istemci için otel SDK'larını entegre edip Jaeger + Prometheus + Grafana ile birleşik gösterge panelleri hazırla.
  - Beklenen Fayda: Performans darboğazlarını hızla tespit etmeye ve SLA ihlallerini kök nedenleriyle birlikte izlemeye olanak tanır.
  - Kabul Kriteri: Ana iş akışları için 95. yüzdelik yanıt süreleri ve trace korelasyonu dashboard'da görselleşir; hata oranı alarmı Prometheus alertmanager üzerinden tetiklenir.
  - Efor: M
- [ ] **P1:** Özellik bayrakları (feature flag) ve kademeli yayın mekanizması ekleyerek riskli dağıtımları kontrollü şekilde yönet.
  - Açıklama: FastAPI tarafında yapılandırılabilir bayrak deposu ve React istemcide gerçek zamanlı flag okuma/kaynak önbellekleme katmanı uygula.
  - Beklenen Fayda: Yeni işlevleri sınırlı kullanıcı segmentlerinde deneyip geri alma maliyetini düşürür, üretim kesintilerini engeller.
  - Kabul Kriteri: En az iki kritik özellik bayrak üzerinden yönetilir; flag güncellemeleri dakikalar içinde istemciye yansır ve rollback testiyle doğrulanır.
  - Efor: M
- [ ] **P1:** Kişisel verileri maskeleyip saklama sürelerini denetleyen veri yönetişimi ve uyumluluk pipeline'ı kur.
  - Açıklama: SQLite/PostgreSQL şemasında PII alanlarını tespit edip ETL ile arşive aktarma, maskeleme ve otomatik silme rutinleri ekle.
  - Beklenen Fayda: KVKK/GDPR gibi regülasyonlarla uyumlu veri yaşam döngüsü yönetimini sağlar, denetim riskini azaltır.
  - Kabul Kriteri: PII alanları için maskeleme raporu üretilir; belirlenen saklama süresini aşan kayıtlar otomatik temizlenir ve denetim loglarına yazılır.
  - Efor: M
- [ ] **P2:** Panel için offline-first deneyimi destekleyen akıllı önbellekleme ve arka plan senkronizasyonu uygula.
  - Açıklama: Service Worker + IndexedDB ile kritik API yanıtlarını sakla, çevrimdışı işlemleri kuyruğa alıp bağlantı geri geldiğinde otomatik gönder.
  - Beklenen Fayda: Kararsız ağ koşullarında bile yönetim panelinin kullanılabilirliğini artırır ve operasyon kesintilerini azaltır.
  - Kabul Kriteri: Ağ bağlantısı kesildiğinde temel bot/sohbet görüntüleme ve kayıt işlemleri yerel veriden çalışır; yeniden bağlanınca kuyruğa alınan işlemler otomatik işlenir.
  - Efor: M

### Profesyonel Geliştirme Fırsatları
- [x] **P0:** RBAC, çok faktörlü kimlik doğrulama ve API anahtarı rotasyonu içeren kapsamlı bir erişim yönetimi katmanı tasarlayıp uygulamaya alma. _Açıklama: Yeni `api_users` modeli, PBKDF2 tabanlı parola/anahtar saklama, TOTP doğrulaması ve rol hiyerarşisi ile login/anahtar döndürme uçları eklendi; tüm yetki kontrolleri FastAPI tarafında role göre sınırlandı._
- [x] **P0:** Dashboard verilerini WebSocket tabanlı canlı akışa taşıyarak test sonuçları ve uyarıları gecikmesiz güncelle. _Açıklama: `/ws/dashboard` WebSocket kanalında rol doğrulamalı canlı metrik ve sistem kontrolü özetleri yayınlanıyor; istemci bağlantıları periyodik JSON snapshot alıyor._
- [ ] **P1:** Sistem sağlık verilerinden yola çıkarak haftalık özet e-posta/slack raporları ve dışa aktarılabilir PDF/CSV üretimi yapan kurumsal raporlama modülü oluştur.
- [ ] **P1:** WCAG 2.1 AA uyumluluğu için kontrast, klavye navigasyonu ve ekran okuyucu etiketlerini kapsayan kapsamlı erişilebilirlik iyileştirmeleri planla ve uygula.
- [ ] **P1:** Yeni kullanıcılar için rehberli turlar, bağlamsal yardım makaleleri ve arama yapılabilir bilgi tabanını entegre ederek self-servis destek deneyimini güçlendir.
- [ ] **P2:** Otomatik toparlanma (self-healing) senaryoları için başarısız testleri yeniden deneme, olay kaydı açma ve sorumlu ekiplere bildirim zincirini tetikleyen orkestrasyon akışı geliştir.

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

### Planlanan UI/UX Profesyonel Geliştirmeleri
- [x] **P0:** Panel ve dashboard için kapsamlı kullanıcı araştırması + kullanılabilirlik testleri düzenleyip bulguları aksiyon planına dönüştür. _Açıklama: Görüşme/tarayıcı analizi yöntemlerini içeren kapsamlı plan ve önceliklendirilmiş aksiyon listesi `docs/ui_ux_research_plan.md` dosyasında yayınlandı._
- [x] **P0:** Kritik iş akışları için rol bazlı görev panoları ve bağlama duyarlı yardım turları tasarla. _Açıklama: Dashboard'a rol tabanlı görev listeleri ve seçilebilir yardım turu paneli eklendi; durum rozeti ve ipucu akışı rol dinamiklerine göre güncelleniyor._
- [x] **P1:** Gerçek zamanlı bildirimler, toast geçmişi ve sistem durum değişiklikleri için birleşik bir "Etkinlik Merkezi" bileşeni geliştir. _Açıklama: Başlıkta bildirim balonu bulunan yeni Etkinlik Merkezi gerçek zamanlı olay akışı, toast geçmişi ve filtreleme destekleriyle yayınlandı._
- [x] **P1:** Kişiselleştirilebilir tema seçenekleri (karanlık/aydınlık, yüksek kontrast, yazı tipi boyutu) ekleyerek erişilebilirlik kontrollerini kullanıcıya aç. _Açıklama: Yeni Tema ve Erişilebilirlik sekmesi üzerinden mod geçişleri, yüksek kontrast ve metin ölçekleme ayarları anında uygulanabiliyor; tercihleri kalıcı hale getiren ThemeProvider eklendi._
- [x] **P1:** Çok adımlı formlarda ilerleme çubuğu, geri bildirim özetleri ve otomatik taslak kaydı sağlayan sihirbaz bileşeni hazırla.
- [x] **P2:** Dashboard ve liste sayfalarında kart/tablo görünümü arasında geçiş yapabilen adaptif düzen sistemi uygula.
- [x] **P2:** Kritik metrikler için eşik tabanlı uyarıları e-posta/SMS/push bildirimlerine bağlayan tercih yönetim ekranı tasarla.
- [x] **P2:** Kullanıcı davranışını analiz edip proaktif öneriler sunan "akıllı öneri" bannerları ve boş durum içerikleri üret.
- [x] **P3:** Uygulama genelinde metin ve ikonografi için çok dillilik desteğini genişletip yerelleştirme iş akışını otomatikleştir.
- [x] **P3:** İnteraktif stil rehberi ve bileşen kütüphanesi dokümantasyonu hazırlayarak tasarım-tabanlı geliştirme sürecini standardize et.

### Yeni Geliştirme Adımları
- [x] Sistem kontrolü sonuçlarını 7 günlük periyotta özetleyen `/system/checks/summary` API uç noktasını ekle.
- [x] Yeni uç noktayı kapsayan birim testi yazarak API davranışını doğrula.
- [x] Dashboard'da sistem kontrolü özetini gösteren yeni kart ekle.

### Botları Daha İnsancıl Hale Getirme Önerileri
- [x] **P1:** Bot mesajlarında kişisel anekdot ve duygusal ton katmanı üretecek "duygu profili" parametresi ekle; profil ayarları panelden düzenlenebilir olsun.
- [x] **P1:** Davranış motoruna, haber akışına verilen tepkileri kullanıcıyla empati kuran kalıplarla zenginleştiren bir "tepki sentezi" modülü ekle.
- [x] **P2:** LLM istemlerine gerçek kullanıcı sohbetlerinden (anonimleştirilmiş) örnek replikler ekleyerek daha doğal geçişler sağlayan bağlamsal bellek geliştirmesi yap.
- [x] **P2:** Botların konuşma temposunu insana benzetmek için dinamik yazma gecikmesi (ör. duygu durumuna göre hız değişimi) ve ara emojiler uygulayan mikro davranışlar tasarla.
- [x] **P3:** Uzun diyaloglarda karakter tutarlılığı için kişilik özetini periyodik olarak LLM'e hatırlatan otomatize bir "persona yenileme" rutini ekle.

### Kullanıcı Dostu Takip İyileştirmeleri
- [x] Sistem sağlık özet kartına veri kapsamı ve son çalıştırma zamanını açıkça gösteren yardımcı içerik ekle.
- [x] Öne çıkan noktalar ve önerilen aksiyonları özet/expandable hale getirip aksiyonları panoya kopyalama kısayolu ekle.
- [x] Sistem özeti API'sine son koşu detay listesini ekleyip şema doğrulamasıyla güvence altına al.
- [x] Dashboard sağlık kartında son koşuların durum, süre ve tetikleyici bilgilerini kullanıcı dostu biçimde sergile.

