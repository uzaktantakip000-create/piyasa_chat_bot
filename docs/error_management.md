# Hata Yönetimi ve Log Merkezileştirme Stratejisi

Bu belge, API, worker ve React tabanlı yönetim panelinden (UI) üretilen logları tek bir kanalda toplayıp kritik durumlar için otomatik alarm üretmeyi amaçlayan stratejiyi açıklar. Tasarım, mevcut FastAPI + worker mimarisi ve paneldeki metrik panosu ile uyumlu olacak şekilde planlanmıştır.

## 1. Hedefler

1. **Merkezileştirme:** API, worker ve UI loglarının aynı formata dönüştürülerek tek bir depoda tutulması.
2. **Gözlemlenebilirlik:** Toplanan loglardan metrikler türeterek Dashboard'da sağlık kartları ve uyarılar üretmek.
3. **Alarm Eşikleri:** Kritik hatalar veya tekrar eden istisnalar için otomatik alarm mekanizmaları tanımlamak.
4. **Geriye dönük izleme:** `latest_oneclick_report.json` ve `/system/checks/latest` uçlarından gelen sağlık raporlarını loglarla ilişkilendirmek.

## 2. Mimarinin Genel Görünümü

```
 API & Worker (Python) ---->
                           \
                            \--> Log Forwarder (Fluent Bit / Vector)
 UI (Vite/React) ---------> /
                              \
                               +--> Central Log Store (OpenSearch / Loki / PostgreSQL JSONB)
                                \
                                 --> Alert Engine (Prometheus Alertmanager / ElastAlert / custom cron)
```

- **Üretici katmanı:**
  - API ve worker süreçleri `logging` modülünde JSON formatter kullanacak.
  - UI tarafı, tarayıcı hatalarını `window.onerror`/`unhandledrejection` yakalayıp API'ye `/logs/ingest` benzeri uç ile gönderecek.
- **Toplayıcı katmanı:** Yerel geliştirmede `scripts/log_forwarder.py` ile STDOUT'u takip eden hafif bir toplayıcı; üretimde Fluent Bit veya Vector container'ı.
- **Depolama:** Başlangıç için PostgreSQL `system_logs` tablosu (JSONB payload + timestamp + service). Orta vadede OpenSearch/Loki.
- **Alarm motoru:**
  - Kısa vadede `scripts/check_alerts.py` ile cron benzeri job (system_checks tablosuna sonuç yazacak).
  - Uzun vadede Prometheus Alertmanager veya Grafana Cloud Alerts.

## 3. Log Formatı

Tüm servisler aynı JSON şemasını yazacak:

```json
{
  "ts": "2024-07-01T12:34:56.789Z",
  "service": "api|worker|ui",
  "level": "INFO|WARNING|ERROR",
  "event": "short_event_key",
  "message": "Human readable text",
  "meta": { "bot_id": 42, "chat_id": "-100..", "trace_id": "..." }
}
```

- Python tarafında `logging.Formatter` yerine `json.dumps` kullanan özel `JsonLogFormatter` eklenecek.
- UI tarafında `console.error` çağrıları `fetch('/logs/ingest')` ile backend'e iletilecek.

## 4. Alarm Eşikleri

| Servis  | Eşik                                                   | Aksiyon |
|---------|-------------------------------------------------------|---------|
| API     | 1 dakika içinde >=5 adet `ERROR` seviyesi log          | Slack #ops kanalına bildirim, `/system/checks` kaydı `status=failed` |
| Worker  | Ardışık 3 döngüde `behavior_engine` istisnası          | Worker otomatik yeniden başlat, PagerDuty düşük öncelik alarm |
| UI      | 10 dakika içinde aynı kullanıcıdan >=10 hata bildirimi | Destek ekibine e-posta, panelde InlineNotice |
| Redis   | `redis` health check başarısızlığı                     | `control/stop` otomatik, ops ekibine yüksek öncelik |

Eşik değerlendirmesi `Alert Engine` tarafından yapılacak ve sonuçlar `system_checks` tablosuna `health_checks` alanı ile ilişkilendirilecek. Dashboard'daki "Servis Sağlık Durumu" kartı bu bilgileri canlı olarak gösterecek.

## 5. Uygulama Adımları

1. **Log formatı standardizasyonu**
   - `logging_config.py` dosyası eklenip API ve worker giriş noktalarında çağrılacak.
   - UI'da `ErrorBoundary` bileşeni ve global hata yakalayıcı eklenecek.
2. **Log Forwarder**
   - Docker Compose'a Fluent Bit servisi ekleyip `stdout` ve `/var/log/ui.log` dosyalarını takip edeceğiz.
   - Geliştirme ortamında `scripts/log_forwarder.py` ile aynı davranış.
3. **Merkezi Depolama**
   - PostgreSQL'de `system_logs` tablosu (`id`, `ts`, `service`, `level`, `event`, `message`, `meta` JSONB).
   - ORM modeli ve `/logs/recent` uçlarının bu tabloyu kullanması.
4. **Alarm Motoru**
   - İlk aşamada cron + Python script: `python scripts/check_alerts.py --window 60`.
   - Sonuçlar `SystemCheck` modeli ile kaydedilerek Dashboard'a aktarılacak.
5. **Görselleştirme**
   - Dashboard'a "Son 15 dakikada kritik hata" badge'i.
   - `latest_oneclick_report.json` dosyasına `log_summary` alanı eklenerek smoke test sonrası durum raporlanacak.

## 6. İzleme ve Runbook

- **Alarm tetiklendiğinde:**
  1. `/logs/recent?service=api&level=ERROR` ile detaylara bak.
  2. `docs/runbook.md` içindeki ilgili prosedürü uygula (ör. Redis yeniden başlatma).
  3. Sorun giderildikten sonra `scripts/check_alerts.py --reset` çalıştırarak alarmı temizle.
- **Periyodik Bakım:** Haftalık olarak log saklama politikasına göre eski kayıtları arşivleyip silelim (örn. 30 gün).
- **Performans:** Log hacmi 500 satır/dk üzerine çıkarsa Fluent Bit'te sampling uygulanacak.

## 7. Açık Maddeler

- Slack/PagerDuty entegrasyon anahtarlarının güvenli yönetimi (`.env` ve Secrets Manager).
- UI tarafında kullanıcı kimliği olmadan alarm üretmemek için anonimleştirme stratejisi.
- Uzun vadede OpenTelemetry entegrasyonu ile tracing + logging birleşimi.

Bu strateji uygulandığında, `scripts/oneclick.py` tarafından üretilen sağlık raporlarına log istatistikleri de eklenecek; böylece hem ilk kurulum hem de sürekli izleme süreçleri aynı kaynaktan beslenecek.
