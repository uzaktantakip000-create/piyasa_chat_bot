# Test Sonuçları ve Sistem Sağlığı Raporlama Modülü — Kapsam & Roadmap

Bu belge, test sonuçları (`SystemCheck` kayıtları, `latest_oneclick_report.json`) ve altyapı sağlık göstergelerini görselleştirecek raporlama modülünün kapsamını ve aşamalarını tanımlar.

## 1. Amaç

- QA ekibinin otomasyon sonuçlarını tek panelden takip etmesi.
- Operasyon ekibinin API/worker/UI sağlık trendlerini grafiklerle görmesi.
- One-click smoke testleri sonrası elde edilen verileri kalıcı raporlara dönüştürmek.

## 2. Veri Kaynakları

1. **Veritabanı (`SystemCheck` tablosu):** Her smoke test ve CI koşusunun `steps` + `health_checks` detayları.
2. **`latest_oneclick_report.json`:** Manuel çalıştırmalarda disk üzerinde biriken raporlar.
3. **Log merkezi (planlanan `system_logs` tablosu):** Kritik hata seviyeleri ve eşik aşımı bilgileri.
4. **Ek metrikler:** Redis gecikme süresi, Telegram hata sayısı, worker döngü süresi gibi runtime ölçümleri.

## 3. Özellikler

| Aşama | Özellik | Açıklama |
|-------|---------|----------|
| M1 | Test zaman çizelgesi | `SystemCheck` sonuçlarını tarih ekseninde gösteren çizgi grafik (başarı/başarısız). |
| M1 | Sağlık kartları | API, worker, UI için son 24 saatlik `health_checks` durumunu özetleyen kartlar. |
| M2 | Trend analizleri | Ortalama smoke test süresi, hata yüzdesi, alarm sayıları için line/area chart. |
| M2 | Rapor dışa aktarma | PDF/CSV çıktısı ile paylaşılabilir rapor üretimi. |
| M3 | Anomali uyarıları | Eşik dışı trendlerde Slack/PagerDuty entegrasyonu. |
| M3 | Dashboard embed | Rapor bileşenlerinin ana Dashboard sayfasına widget olarak eklenmesi. |

## 4. Teknoloji Yığın Önerisi

- **Front-end:** React + `@nivo` veya `visx` ile etkileşimli grafikler.
- **Back-end API:** `/reports/summary`, `/reports/trends` gibi yeni FastAPI uçları; PostgreSQL sorguları için Materialized View.
- **Planlanan cron:** `scripts/aggregate_reports.py` günlük olarak geçmiş `SystemCheck` kayıtlarını özet tablolara aktaracak.

## 5. Roadmap

1. **Sprint 1**
   - Sistem gereksinimlerini finalize et (QA/ops ile workshop).
   - `SystemCheck` şemasına indeks ve `health_checks` alanı (halihazırda eklendi) doğrulaması.
   - POC: Basit çizgi grafiği QuickStart veya ayrı bir route altında göster.
2. **Sprint 2**
   - `/reports/summary` ve `/reports/trends` API uçlarını geliştir.
   - Front-end’de filtreleme (tarih aralığı, test tipi, tetikleyen kullanıcı) ekle.
   - `scripts/aggregate_reports.py` için cron job prototipi (Docker Compose ile planla).
3. **Sprint 3**
   - PDF/CSV dışa aktarma, alarm entegrasyonu.
   - Dashboard entegrasyonu ve kullanıcı yetkilendirme (yalnızca admin rolleri görsün).
   - Dokümantasyon + runbook güncellemesi.

## 6. Gereken Kaynaklar & Riskler

- **Kaynaklar:** 1 FE (React), 1 BE (FastAPI + SQL), 0.5 DevOps.
- **Riskler:** Log merkezi hazır değilse trendler eksik kalır; cron job yönetimi için ek gözlem araçları gerekir.
- **Bağımlılıklar:** `docs/error_management.md` planındaki log merkezileştirme, yeni entegrasyon testlerinin sürekliliği.

## 7. Başarı Kriterleri

- QA ve ops ekiplerinin haftalık raporları manuel değil otomatik olarak alması.
- Dashboard üzerinden son 7 gün trendlerinin görüntülenebilmesi.
- Alarm eşikleri ile rapor grafikleri arasında tutarlı veri (sapma < %5).
