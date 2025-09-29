# Telegram Piyasa Sohbet Simülasyonu

Bu rehber, teknik geçmişi olmayan kişilerin bile projeyi kurup çalıştırabilmesi için yazıldı. Aşağıdaki adımları sırasıyla izlerseniz, Telegram üzerinde piyasa sohbetlerini canlandıran bu sistemi kendi bilgisayarınızda veya bir sunucuda çalıştırabilirsiniz.

## Bu doküman kimin için?
- Telegram botlarını yönetmek isteyen ama yazılım altyapısına hâkim olmayan ekipler
- Projeyi devralıp "nasıl ayağa kaldırırım?" sorusuna cevap arayan yeni ekip arkadaşları
- Sistem yöneticileri veya proje sahipleri

> **İpucu:** Adımları uygularken bilmediğiniz bir kavramla karşılaşırsanız paniğe gerek yok. Her bölümde kısa açıklamalar ve görsel benzeri tarifler bulunuyor.

## Proje ne yapar?
- Birden fazla Telegram botunu (örneğin 10 bot) aynı anda çalıştırır.
- Botlar; belirlediğiniz kişilik, tutum ve haber akışına göre mesaj üretir.
- Üretilen mesajlar gerçek bir grup sohbetindeymişsiniz gibi Telegram'a gönderilir.
- Tüm ayarları ve bot listesini web tabanlı bir yönetim panelinden kontrol edebilirsiniz.

## Ana bileşenler (kısaca)
| Bileşen | Ne işe yarıyor? |
| --- | --- |
| **FastAPI (backend)** | Botlar, sohbetler, ayarlar ve metrikler için web servislerini sunar. |
| **Davranış motoru (worker.py)** | Botların nasıl cevap vereceğini hesaplar ve Telegram'a mesaj yollar. |
| **React yönetim paneli** | Tarayıcıdan bot ekleyip ayarları değiştirdiğiniz arayüz. |
| **Veritabanı** | Bot bilgileri, sohbetler ve mesaj geçmişi burada saklanır. Varsayılan olarak SQLite dosyası kullanılır. |
| **Redis (isteğe bağlı)** | Ayar değişikliklerini anında çalışan motora iletmek için kullanılır. Olmasa da sistem çalışır. |

## Başlamadan önce bilmeniz gerekenler

### Gerekli araçlar
| Araç | Ne işe yarar? | Minimum sürüm |
| --- | --- | --- |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Tüm sistemi tek komutla çalıştırmak için tavsiye edilir. | 4.x |
| Alternatif: Python + Node.js | Docker kullanmak istemiyorsanız gereklidir. | Python 3.11, Node.js 18 |
| Bir Telegram hesabı | Bot oluşturmak ve grup yönetmek için zorunludur. | - |

### Telegram bot token'ı nasıl alınır?
1. Telegram uygulamasını açın ve `@BotFather` hesabına mesaj atın.
2. `/newbot` komutunu gönderin, bot ismini ve kullanıcı adını seçin.
3. BotFather size `123456789:ABCDEF...` formatında bir **token** verecek. Bu değeri güvenle saklayın; README'nin ilerleyen bölümünde kullanacağız.
4. Birden fazla bot istiyorsanız adımları tekrarlayın.

### API anahtarı ne işe yarar?
Yönetim paneline erişmek için bir parola gibi düşünün. Panelde gördüğünüz her ekran bu anahtarı kullanarak API'ye bağlanır. Anahtarı `.env` dosyasında belirleyeceksiniz.

## Kurulum için iki seçenek
Çoğu kullanıcı için en kolay yol **Docker Compose** kullanmaktır. Bilgisayarınızda Docker yoksa veya kullanmak istemiyorsanız, manuel kurulum adımlarını izleyebilirsiniz.

### Seçenek A: Docker Compose (önerilen)
1. **Kaynak dosyaları indirin**
   - GitHub'da sağ üstten **Code → Download ZIP** diyerek projeyi indirin.
   - ZIP dosyasını çıkartın ve klasöre girin (ör. `piyasa_chat_bot`).
2. **Ortam dosyasını hazırlayın**
   - `piyasa_chat_bot` klasörü içinde `.env.example` dosyasını bulun.
   - Dosyayı kopyalayıp yeni adını `.env` yapın. (Windows'ta dosya adı başına nokta koymak için "Farklı Kaydet" kısmında "`.env`" yazabilirsiniz.)
     - `.env` dosyasını bir metin editöründe açın ve şu alanları düzenleyin:
       - `API_KEY=...` → Panel girişinde kullanılacak güçlü bir cümle yazın. (Örnek: `API_KEY=Benim-Cok-Gizli-Anahtarim`)
       - `TOKEN_ENCRYPTION_KEY=...` → Tek satırda uzun bir anahtar olmalı. Terminaliniz varsa `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` komutunu kullanabilirsiniz. Terminal yoksa [online Fernet key generator](https://asecuritysite.com/encryption/fernet) gibi bir araçtan kopyalayabilirsiniz.
       - `OPENAI_API_KEY=...` → Sohbet mesajlarının üretilebilmesi için [OpenAI hesap panelinden](https://platform.openai.com/account/api-keys) oluşturduğunuz anahtarı girin. Gerekirse `LLM_MODEL=` satırını `gpt-4o-mini` dışındaki bir modelle güncelleyebilirsiniz.
       - `DATABASE_URL=` → Varsayılan değeri (`sqlite:///./app.db`) bırakabilirsiniz. PostgreSQL kullanmak istiyorsanız burada bağlantı adresini yazın.
       - `ALLOWED_ORIGINS=` → Yönetim paneline hangi web adreslerinden erişileceğini yazın. Yerel kullanım için `http://localhost:5173` yeterlidir.
       - `VITE_API_KEY=` ve `VITE_DASHBOARD_PASSWORD=` → Panelin tarayıcı tarafında hatırlayacağı değerlerdir. `VITE_API_KEY`, az önce belirlediğiniz `API_KEY` ile aynı olmalıdır. İsterseniz panel için ayrıca bir şifre (`VITE_DASHBOARD_PASSWORD`) tanımlayabilirsiniz.
3. **Docker'ı başlatın**
   - Terminal (PowerShell, CMD, macOS Terminal vb.) açın.
   - Proje klasörüne geçin. Örnek: `cd C:\Users\kullanici\Downloads\piyasa_chat_bot`
   - Aşağıdaki komutu çalıştırın:
     ```bash
     docker compose up --build
     ```
   - İlk kurulum birkaç dakika sürebilir. İşlem bittiğinde FastAPI, worker, PostgreSQL ve Redis servisleri hazır olacaktır.
4. **Yönetim paneline bağlanın**
   - Tarayıcıdan `http://localhost:3000` (veya Vite geliştirme sunucusu kullanıyorsanız `http://localhost:5173`) adresine gidin.
   - Açılan giriş ekranında `.env` dosyasında tanımladığınız `API_KEY` (ve varsa `VITE_DASHBOARD_PASSWORD`) değerlerini girin.
   - Başarılı girişten sonra dashboard yüklenir.
5. **Servisi kapatmak**
   - Terminalde `Ctrl + C` ile komutu durdurabilir veya başka bir terminalde `docker compose down` çalıştırabilirsiniz.

### Seçenek B: Manuel kurulum (Docker yoksa)
1. **Python ortamını kurun**
   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate
   # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Node.js bağımlılıkları**
   ```bash
   npm install
   ```
3. **.env dosyasını hazırlayın**
   - Docker adımlarındaki aynı ayarları buraya da uygulayın.
   - Özellikle `OPENAI_API_KEY=sk-...` satırını doldurmayı unutmayın; aksi halde LLM tabanlı mesaj üretimi çalışmaz. Modeli değiştirmek isterseniz `.env` içinde `LLM_MODEL=` değerini güncelleyebilirsiniz.
4. **API'yi başlatın**
   ```bash
   uvicorn main:app --reload
   ```
5. **Worker'ı başlatın** (ayrı bir terminalde sanal ortamı tekrar aktive etmeyi unutmayın)
   ```bash
   python worker.py
   ```
6. **Yönetim panelini başlatın**
   ```bash
   npm run dev
   ```
7. **Tarayıcıdan giriş yapın**
   - `http://localhost:5173` adresine gidin ve `API_KEY` + panel şifrenizle giriş yapın.
8. **Servisi durdurmak**
   - Her terminalde `Ctrl + C` kombinasyonu ile süreçleri kapatın.

## Yönetim panelini adım adım kullanma
1. **Bot ekleme**
   - Sol menüden **Bots** sayfasına gidin.
   - `Add bot` butonuna basın.
   - Telegram bot tokenınızı "Token" alanına yapıştırın (sistem arka planda şifreler).
   - Botun adını, kullanıcı adını ve varsa kişilik ipuçlarını girin.
   - Kaydettikten sonra bot listesinde maskelemiş token (`1234******abcd`) görünecektir.
2. **Sohbet oluşturma**
   - **Chats** sekmesine gidin.
   - Telegram grup kimliğini (ör. `-1001234567890`) ve açıklamasını ekleyin.
   - Hangi botların o sohbete mesaj atacağını belirtin.
3. **Ayarları düzenleme**
   - **Settings** bölümünde mesaj sıklığı, yazma hızı, prime saatler gibi seçenekler bulunur.
   - Kaydettiğiniz her değişiklik worker'a otomatik gönderilir.
   - Değerleri aşırı uçlara çekmeden önce küçük artışlarla test etmeniz önerilir.
4. **Simülasyonu başlatma/durdurma**
   - Dashboard ana sayfasında yer alan kontrol butonları ile tüm botları durdurup yeniden başlatabilirsiniz.
   - `Scale` butonları ile hız çarpanını değiştirebilirsiniz.
5. **Logları inceleme**
   - **Logs** sekmesi, API ve worker tarafından yakalanan hataları gösterir.
   - Telegram rate limit uyarıları (ör. `429 Too Many Requests`) görürseniz mesaj hızını azaltın.

## Günlük kullanım önerileri
- Önemli değişikliklerden önce `.env` dosyasının ve `app.db` veritabanının yedeğini alın.
- Çok sayıda bot ekledikten sonra sistemi yeniden başlatmak (API + worker) yapılandırmayı temizler.
- Uzun süreli çalışmalarda Docker konteynerlerinin loglarını arada bir kontrol edin: `docker compose logs -f api` gibi.

## Sorun giderme
| Belirti | Muhtemel sebep | Çözüm |
| --- | --- | --- |
| Panelde "Invalid or missing API key" hatası | Paneldeki `VITE_API_KEY` değeri ile `.env` dosyasındaki `API_KEY` eşleşmiyor | `.env` dosyasını kontrol edin, paneli kapatıp yeniden açın. |
| API başlarken `TOKEN_ENCRYPTION_KEY is not set` uyarısı | `.env` içinde boş bıraktınız | Yeni bir Fernet anahtarı üretin ve `.env` dosyasına yazın, API'yi yeniden başlatın. |
| Bot mesaj göndermiyor | Token yanlış veya bot sohbet grubuna eklenmemiş | Telegram'da botu ilgili gruba ekleyip admin yetkisi verin, ardından worker'ı yeniden başlatın. |
| Docker konteynerleri hemen kapanıyor | `.env` içindeki PostgreSQL/Redis bağlantıları ulaşılamıyor | İlk etapta varsayılan SQLite + Redis'siz ayarlarla deneyin. |

## Sık sorulan küçük sorular
- **Bu sistem gerçek para işlemi yapar mı?** Hayır. Sadece sohbet simülasyonu üretir.
- **Tek botla çalıştırabilir miyim?** Evet, bot sayısı size bağlıdır.
- **İnternete bağlı olmak zorunda mıyım?** Telegram'a mesaj gönderebilmek için internet şarttır.
- **Hangi işletim sistemleri destekleniyor?** Windows 10/11, macOS ve modern Linux dağıtımları. Docker veya Python + Node.js kurabiliyorsanız sistem çalışır.

## Daha fazla bilgi
- Ayrıntılı operasyon ve bakım adımları için `RUNBOOK.md` dosyasına bakın.
- Teknik mimari, plan ve yapılacaklar listesi için `PLAN.md` ve `todo.md` dosyalarını inceleyebilirsiniz.

Kurulum sırasında takıldığınız nokta olursa dosyadaki adımlara geri dönüp eksik kalemleri tamamlayın. Her adımı tamamladığınızda sistemi güvenle çalıştırabilir, Telegram üzerinde kendi piyasa sohbet simülasyonunuzu başlatabilirsiniz.
