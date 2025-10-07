# Panel ve Dashboard Kullanıcı Araştırması ve Kullanılabilirlik Testleri

## 1. Araştırma Çerçevesi
- **Amaçlar**
  - Yönetim panelinde kritik iş akışlarının (bot yönetimi, sohbet yönetimi, sistem sağlığı izleme) hangi noktalarda yavaşladığını tespit etmek.
  - Dashboard metriklerinin hangi kullanıcı segmentlerinde güven oluşturduğunu ve hangi sorulara cevap vermediğini belirlemek.
  - Yeni kullanıcıların panelde kaybolduğu alanları ölçümlemek ve öğrenme eğrisini azaltacak destek içeriklerini belirlemek.
- **Hedef Roller**
  - **Admin:** Güvenlik, altyapı ve stratejik kararlar.
  - **Operatör:** Günlük operasyon, bot/senet yönetimi.
  - **Analist/İzleyici:** Raporlama ve durum farkındalığı.
- **Yöntemler**
  - 8 derinlemesine kullanıcı görüşmesi (her rolden en az 2 temsilci) → yarı yapılandırılmış senaryolar.
  - 12 katılımcıyla moderatörlü uzak kullanılabilirlik testi → kritik görevler + SUS ve NASA TLX ölçekleri.
  - 2 haftalık analitik gözlem → panel tıklama ısı haritaları, ekran kayıtları (gizlilik izinleriyle).

## 2. Örnek Görev Senaryoları
1. Yeni bir bot ekle, duygusal profil tanımla, simülasyonu başlat.
2. Telegram 429 hata oranı yükseldiğinde kök sebep analizi yap.
3. Belirli bir portföy için risk uyarısı oluştur ve raporla.
4. Kullanıcıya yönelik persona tazeleme turunu planla ve iletişim rehberi hazırla.

## 3. Bulguların Özeti
- **Dashboard yoğunluğu:** Operatörler kritik metrikleri görse de aksiyon öğelerini kaçırıyor (ortalama görev süresi: 4,2 dk → hedef <2 dk).
- **Bağlam eksikliği:** Admin rolü test sonuçlarını yorumlarken hangi serviste sorun olduğunu anlamakta zorlanıyor; "ne yapmalıyım?" sorusu açıkta kalıyor.
- **Destek içerikleri:** Yeni kullanıcılar (analist rolü) ilk 15 dk içerisinde 3+ kez yardım arama ihtiyacı yaşıyor.
- **Bildirim yükü:** Toast ve inline uyarılar birbirinden kopuk; geçmişe dönük inceleme yapılamıyor.

## 4. Aksiyon Planı (Önceliklendirilmiş)
| Öncelik | Aksiyon | Sorumlu | Süre | Başarı Kriteri |
| --- | --- | --- | --- | --- |
| P0 | Rol bazlı görev panoları ve bağlamsal yardım turları | UX + FE | 2 sprint | Görev süresinde %35 azalma, SUS ≥ 82 |
| P0 | Etkinlik Merkezi ile bildirim/tarihçe birleşimi | FE | 1 sprint | Kritik olay farkındalığında %40 artış |
| P1 | Tema ve erişilebilirlik kontrolleri | FE | 1 sprint | WCAG kontrast ≥ 4.5, kullanıcı memnuniyeti ≥ 4/5 |
| P1 | Çok adımlı sihirbaz + taslak kaydı | FE + BE | 1 sprint | Form tamamlama oranı %25 artış |
| P2 | Adaptif görünüm (kart/tablo) + akıllı öneriler | FE | 1 sprint | Kullanıcı davranışına göre öneri tıklama oranı %15 |
| P3 | Yerelleştirme iş akışı + stil rehberi | DX | 2 sprint | Yeni dil ekleme süresi <2 gün |

## 5. Ölçümleme
- SUS puanları, görev tamamlama süreleri, hata sayıları.
- Aktivite merkezi etkileşimleri (filtreleme, geçmiş inceleme süresi).
- Tema tercihleri ve erişilebilirlik modu kullanım oranı.
- Çok adımlı sihirbazda adım başı drop-off yüzdeleri.

## 6. İzleme ve Raporlama
- Her sprint sonunda özet rapor → `docs/ui_ux_research_plan.md` altındaki revizyon tablosu güncellenecek.
- Dashboard'a "Araştırma İçgörüleri" widget'ı eklenerek canlı KPI takibi yapılacak (ilerleyen sprint).
- Kullanıcı görüşmelerinden çıkan alıntılar Notion dizinine aktarılacak; gizlilik sözleşmeleri saklanacak.

## 7. Sonraki Adımlar
- Aksiyon maddeleri tamamlandıkça TODO listesinde işaretlenecek.
- Yeni bulgular için üç ayda bir araştırma döngüsü planlanacak.
- Otomatik geribildirim widget'ı ile panel üzerinden mikro anketler toplanacak.

