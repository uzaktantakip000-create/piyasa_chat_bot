# Piyasa Paneli Stil Rehberi ve Bileşen Kütüphanesi

## Amaç
Bu rehber, panel tasarımında kullanılan tipografi, renk, arayüz kuralları ve React bileşenlerinin davranış sözleşmelerini tek kaynakta toplar. Tasarım ve geliştirme ekipleri, yeni ekranlar üretirken veya mevcut akışları revize ederken bu kuralları referans almalıdır.

## Tipografi
- **Ana Yazı Tipi:** `Inter`, varsayılan metin boyutu 16px.
- **Başlıklar:** `font-semibold` kullanılır, h1-h3 arasında 1.25x artış uygulanır.
- **Vurgu Metinleri:** `text-muted-foreground` yardımcı tonu, `font-medium` ile kombinlenir.

## Renk Paleti
| Kullanım | Açık Tema | Koyu Tema |
| --- | --- | --- |
| Arka plan | `#ffffff` | `#0f172a` |
| Ön plan | `#0f172a` | `#e2e8f0` |
| Birincil | `#0ea5e9` | `#38bdf8` |
| Uyarı | `#fbbf24` | `#f59e0b` |
| Hata | `#f87171` | `#ef4444` |

## Izgara ve Spacing
- Ana içerik maksimum 1280px genişlikte tutulur.
- Kartlar arası boşluk 24px, kart içi blok boşluklar 16px.
- Çok sütunlu düzenlerde 16px kolon boşluğu korunur.

## Form Bileşenleri
| Bileşen | Kullanım | İletişim |
| --- | --- | --- |
| `Input` | Sayısal girişler için `type="number"` + ipucu | Hata durumunda `InlineNotice` veya `FormMessage` |
| `Slider` | Yüzdelik/katsayı ayarlarında | Değer etiketi `%` formatı |
| `Switch` | İkili tercih ve kanal seçimi | Sağ yanında etiket |
| `Textarea` | Çok satırlı not/iletisim | Minimum 3 satır, placeholder zorunlu |

## Reaktif Durumlar
- **Yükleme:** `Skeleton` veya `animate-pulse` bloklar.
- **Boş Durum:** `AlertCircle` veya `Wand2` ikonları + eylem çağrısı.
- **Hata:** `InlineNotice type="error"` ve yeniden dene butonu.

## Bileşen Kataloğu
1. **Wizard.Stepper** – Çok adımlı formlarda ilerleme çubuğu ve otomatik taslak etiketi sunar.
2. **ViewModeToggle** – Kart/tablo görünüm geçişini gerçekleştirir, kullanıcı tercihini `localStorage`'da saklar; `useAdaptiveView` kancası ile birlikte kullanılır.
3. **AlertPreferencesPanel** – Kritik metrik eşiklerini ve kanal eşleşmelerini yönetir; `normalizeAlertPreferences` yardımcı fonksiyonlarını kullanır.
4. **SmartSuggestionBanner** – Dashboard boş durumlarında bağlamsal öneri sağlar; `suggestionAppearance` varyantları kritik/uyarı/başarı etiketlerini otomatik renkler.
5. **WizardAutosaveBadge** – Taslak kayıt durumunu, son kayıt zamanını ve ilgili çevirileri göstermek için `formatRelativeTime` yardımcı fonksiyonunu kullanır.

### Örnek Kullanım

```jsx
const [viewMode, , viewActions] = useAdaptiveView('dashboard.metrics', 'cards');

<ViewModeToggle
  mode={viewMode}
  onChange={viewActions.set}
  cardsLabel={t('view.cards')}
  tableLabel={t('view.table')}
/>;

<AutosaveBadge
  status={autosaveState.status}
  savedAt={autosaveState.savedAt}
  tf={(key, fallback) => t(key) || fallback}
  locale={locale}
/>
```

## Yerelleştirme
- Metinler `useTranslation` kancası ve `translation_core` sözlüğü üzerinden servis edilir.
- Yeni anahtar eklerken hem Türkçe hem İngilizce değerleri doldurun.

## Test Kapsamı
- `node --test` ile çalışan `useAdaptiveView` ve alert tercih yardımcıları otomatik testlerle doğrulanır.
- Eklenen her bileşen, en azından smoke testi veya jest/vitest eşdeğeri ile korunmalıdır.

## Çevrimdışı Senaryolar
- Tema ve görünüm tercihleri `ThemeProvider` ve `useAdaptiveView` kancaları aracılığıyla `localStorage`'a yazılır.
- Ağ hatalarında `ToastProvider` üzerinden kullanıcı bilgilendirilir.

Bu rehber düzenli olarak güncellenmelidir. Yeni bileşenler eklendiğinde örnek kullanım kodu ve stil varyasyonları burada listelenmelidir.
