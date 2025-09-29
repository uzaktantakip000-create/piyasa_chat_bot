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

### Seçenek C: Windows'ta `setup_all.cmd` ile tam otomatik kurulum
Windows 10/11 kullanıcıları için `setup_all.cmd` betiği, manuel olarak yapmanız gereken adımların tamamını tek seferde gerçekleştirir. Betik çalışırken komut istemcisinde birkaç soru sorulur ve bazı pencereler açılır; bu durum normaldir. Betik aynı zamanda GitHub Actions üzerinde **CI modunda** (etkileşim olmadan) koşturularak her commit'te doğrulanır; dolayısıyla aşağıdaki adımların çalıştığını düzenli olarak test ediyoruz.

1. **Betik neleri yapar?**
   - `.venv` klasörü içinde Python sanal ortamını oluşturur ve aktive eder.
   - `pip install -r requirements.txt` komutunu çalıştırarak Python bağımlılıklarını kurar.
   - `npm install` ile React paneli için Node.js paketlerini yükler.
   - `.env` dosyasını kontrol edip varsa eksik alanları doldurmanız için sizi yönlendirir; `OPENAI_API_KEY`, isteğe bağlı `REDIS_URL` ve `DATABASE_URL` değerlerini girmeniz istenir.
   - FastAPI sunucusunu, worker sürecini ve Vite geliştirme sunucusunu sırasıyla başlatır. Her biri kendi terminal penceresinde açılabilir; kapanmasını beklemeyin. (CI modunda bu süreçler yerine API sağlık testi ve worker modül kontrolü yapılır, npm tarafında ise `npm run build` ile derleme doğrulanır.)
2. **Nasıl çalıştırılır?**
   - Dosya gezgininde proje klasörüne gidin (`piyasa_chat_bot`).
   - `setup_all.cmd` dosyasına çift tıklayın **ya da** CMD penceresinde klasöre geçip `setup_all.cmd` yazın.
   - Komut istemcisi sizden OpenAI anahtarınızı (zorunlu) ve Redis/PostgreSQL bağlantı adreslerini (isteğe bağlı, boş bırakabilirsiniz) girdi olarak isteyecektir. Anahtarı girerken gözükmez; yazıp Enter'a basın.
   - Betik sırasında açılan API, worker ve frontend pencereleri çalışmaya devam etmelidir; kurulum tamamlandığında tarayıcıdan `http://localhost:5173` adresine bağlanıp panelde oturum açabilirsiniz.
   - Betiği tekrar çalıştırmak isterseniz pencereleri kapatıp CMD'de `Ctrl + C` ile süreçleri durdurduktan sonra adımları tekrarlayın.
3. **Otomasyon/Cİ modu nasıl çalışır?**
   - Etkileşimsiz bir ortamda çalıştırmanız gerekiyorsa `setup_all.cmd --ci` komutunu kullanabilir veya `SETUP_ALL_NONINTERACTIVE=1` ortam değişkenini ayarlayabilirsiniz.
   - Bu modda OpenAI/Redis/Database değişkenlerini ortam değişkenleriyle (`OPENAI_API_KEY`, `REDIS_URL`, `DATABASE_URL`, `OPENAI_BASE_URL`) besleyebilirsiniz.
   - CI modunda betik API sağlık testini (`/healthz`), worker'ın `--check-only` modunu ve `npm run build` derlemesini otomatik doğrular. GitHub Actions üzerindeki `windows-setup-all` iş akışı her push/pull request'te bu adımları koşturur.
4. **Smoke test ve sağlık raporu**
   - `setup_all.cmd` ile kurulum yaptıktan sonra `scripts/oneclick.py` komutunu koşturursanız API, veritabanı, Redis, worker ve panel için sağlık kontrolleri de dahil olmak üzere tüm smoke test sonuçları `latest_oneclick_report.json` dosyasına yazılır.
   - Aynı rapor `/system/checks` API'sine gönderilir; paneldeki **Servis Sağlık Durumu** listesi bu verileri kullanarak tüm servislerin durumunu gösterir.

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
      - `DATABASE_URL=` → Varsayılan değeri (`sqlite:///./app.db`) bırakabilirsiniz. PostgreSQL kullanmak istiyorsanız burada bağlantı adresini yazın; boş bırakırsanız uygulama proje klasöründeki `app.db` dosyasını kullanır.
      - `ALLOWED_ORIGINS=` → Yönetim paneline hangi web adreslerinden erişileceğini yazın. Yerel kullanım için `http://localhost:5173` yeterlidir.
      - `VITE_API_KEY=` ve `VITE_DASHBOARD_PASSWORD=` → Panelin tarayıcı tarafında hatırlayacağı değerlerdir. `VITE_API_KEY`, az önce belirlediğiniz `API_KEY` ile aynı olmalıdır. `VITE_DASHBOARD_PASSWORD` boş bırakılırsa (varsayılan) panel yalnızca API anahtarı ister; ekstra güvenlik istiyorsanız güçlü bir parola girin.
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
  - Açılan giriş ekranında `.env` dosyasında tanımladığınız `API_KEY` (ve varsa `VITE_DASHBOARD_PASSWORD`) değerlerini girin. Panel şifresi boşsa yalnızca API anahtarını yazmanız yeterlidir.
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
  - `http://localhost:5173` adresine gidin ve `API_KEY` + panel şifrenizle giriş yapın. Panel şifresi tanımlamadıysanız yalnızca `API_KEY` alanını doldurmanız yeterlidir.

### Sık Sorulan Yapılandırma Soruları
- **Varsayılan panel şifresi nedir?**
  Panel şifresi varsayılan olarak **boştur**. `.env` dosyasındaki `VITE_DASHBOARD_PASSWORD` alanını boş bırakırsanız giriş ekranı yalnızca `API_KEY` ister. Ek bir parola kullanmak istiyorsanız aynı dosyada güçlü bir değer belirleyip servisleri yeniden başlatın.

- **`REDIS_URL` nedir? Nasıl kullanılır?**
  Redis, bot davranış motoruna gerçek zamanlı ayar değişikliklerini iletmek için kullanılan bir mesaj kuyruğudur. Yerel kurulumda Redis şart değildir; `.env` içinde `REDIS_URL` satırını boş bırakırsanız worker, bellek içi kuyruğu kullanarak çalışmaya devam eder. Eğer ayrı bir Redis sunucunuz varsa bağlantı adresini (ör. `redis://kullanici:sifre@sunucu-adresi:6379/0`) bu alana yazıp API ve worker süreçlerini yeniden başlatın.

- **`DATABASE_URL` nedir? Nasıl kullanılır?**
  Bot ve sohbet kayıtları varsayılan olarak proje klasöründeki `app.db` SQLite dosyasında saklanır. `.env` içindeki `DATABASE_URL` alanını değiştirmediğiniz sürece ek kurulum gerekmez. Kurumsal ortamda PostgreSQL gibi harici bir veritabanı kullanacaksanız bağlantı cümlenizi (ör. `postgresql+psycopg://kullanici:sifre@sunucu:5432/veritabani`) bu satıra yazıp API ve worker süreçlerini yeniden başlatmanız yeterlidir.

### Opsiyonel Olarak Doldurabileceğiniz Alanlar
Aşağıdaki `.env` anahtarları sistemi çalıştırmak için zorunlu değildir; ihtiyacınıza göre güncelleyebilirsiniz:

- `REDIS_URL` → Redis altyapısı kullanmak istiyorsanız bağlantı adresini girin; aksi hâlde boş bırakabilirsiniz.
- `DATABASE_URL` → Varsayılan SQLite yerine farklı bir veritabanı kullanacaksanız değiştirin.
- `ALLOWED_ORIGINS` → Yönetim paneline yalnızca belirli alan adlarından erişilmesini istiyorsanız güncelleyin.
- `LOG_LEVEL` → Uygulama loglarını `DEBUG`, `INFO`, `WARNING` gibi seviyelerle ayarlamak için kullanabilirsiniz.
- `LLM_MODEL` (ve varsa `LLM_FALLBACK_MODEL`) → OpenAI tarafında hangi modeli kullanacağınızı seçmenizi sağlar; varsayılan `gpt-4o-mini` olarak gelir.

## Görsel sorun giderme akışı

- Paneldeki **QuickStart → Sorun Giderme Akışı** kartı, en sık karşılaşılan hatalar için adım adım çözüm rehberi içerir. Bu kartta giriş ekranının görseli ve kontrol etmeniz gereken `.env` alanları bulunur.
- Aşağıdaki ekran görüntüsünde API anahtarını ve panel şifresini doğrularken nelere dikkat etmeniz gerektiği gösterilir:

  ![Dashboard giriş ekranı örneği](docs/dashboard-login.svg)

- Eğer panel hâlâ yüklenmiyorsa README’deki [Log ve alarm yönetimi](docs/error_management.md) rehberini takip edin veya QuickStart kartındaki destek bağlantıları aracılığıyla `destek@piyasa-sim.dev` adresine ulaşın.

## Yol haritası notu

- Test sonuçları ve sistem sağlığı grafiklerini içerecek raporlama modülünün kapsamı için [`docs/reporting_roadmap.md`](docs/reporting_roadmap.md) belgesine göz atın.
- `VITE_DASHBOARD_PASSWORD` → Panel girişine ek şifre eklemek isterseniz doldurun, aksi hâlde boş bırakılabilir.
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

### Toplu bot eklemek için komut satırı
- Aşağıdaki komut, yönetim paneline girmeden birden fazla botu aynı anda eklemenin en hızlı yoludur:
  ```bash
  python bootstrap.py --chat-id -1001234567890 --tokens-file tokens.json --start
  ```
- Betik çalışırken sırasıyla şu adımları uygular:
  - API'nin hazır olduğunu doğrulamak için `http://localhost:8000/healthz` uç noktasına istek atar.
  - Belirttiğiniz `--chat-id` değerine sahip sohbet kayıtlı değilse otomatik olarak oluşturur.
  - `tokens.json` dosyasındaki listeyi okuyup her token için bot kaydı açar.
  - `--start` parametresini verdiyseniz simülasyonu başlatmak için API'ye kontrol isteği gönderir.
- `tokens.json` dosyası basit bir JSON dizisidir. Örnek:
  ```json
  ["111:AAA", "222:BBB"]
  ```
- `bootstrap.py` dosyasının başarılı şekilde bot ekleyebilmesi için arka planda `python worker.py` komutuyla çalışan bir worker sürecinin açık olması gerekir.
- Betik, işlemler sırasında oluşan hata ve durum mesajlarını doğrudan terminale yazdırır; sorun yaşarsanız çıktıyı inceleyerek hangi adımda takıldığınızı görebilirsiniz.

## Günlük kullanım önerileri
- Önemli değişikliklerden önce `.env` dosyasının ve `app.db` veritabanının yedeğini alın.
- Çok sayıda bot ekledikten sonra sistemi yeniden başlatmak (API + worker) yapılandırmayı temizler.
- Uzun süreli çalışmalarda Docker konteynerlerinin loglarını arada bir kontrol edin: `docker compose logs -f api` gibi.

## Test ve doğrulama adımları
- **Ön koşul:** `npm install` komutunun daha önce çalıştırılmış olması gerekir.
- Yönetim panelinin derleme aşamasını sınamak için proje kök dizininde `npm run build` komutunu çalıştırın. Bu işlem Vite üretim derlemesini oluşturur ve Tailwind yapılandırmasının bütünlüğünü doğrular.
- Derleme başarılı olduğunda `dist/` klasörü altındaki çıktı dosyalarını yeni bir dağıtım için kullanabilir veya `npm run preview` komutuyla yerelde test edebilirsiniz.

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
