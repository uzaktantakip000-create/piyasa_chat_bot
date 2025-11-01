# Telegram Grup Kurulum Rehberi

## Amaç
4 demo botu gerçek bir Telegram grubuna bağlayarak baseline test yapmak.

## Adımlar

### 1. Telegram Grubu Oluştur
1. Telegram uygulamasını aç
2. Yeni grup oluştur (Menu → New Group)
3. Grup adı: "Piyasa Test Chat" (veya istediğin ad)
4. Kendini ekle ve grubu oluştur

### 2. Botları Gruba Ekle
Aşağıdaki 4 botu gruba ekle:

1. **@mehmet_trader** (Mehmet Yatırımcı)
   - Telegram'da ara ve gruba ekle

2. **@ayse_scalp** (Ayşe Scalper)
   - Telegram'da ara ve gruba ekle

3. **@ali_ekonomist** (Ali Hoca)
   - Telegram'da ara ve gruba ekle

4. **@zeynep_newbie** (Zeynep Yeni)
   - Telegram'da ara ve gruba ekle

**NOT**: Eğer botları bulamazsan, önce @BotFather'dan botları aktif etmiş olman gerekiyor.

### 3. Chat ID'yi Al

**Yöntem 1: @getidsbot kullan**
1. @getidsbot'u gruba ekle
2. Bot otomatik olarak chat ID'yi gönderecek
3. Örnek: `-1001234567890`
4. Chat ID'yi kopyala
5. @getidsbot'u gruptan çıkar

**Yöntem 2: Herhangi bir bot ile**
1. Botlardan birini kullan (örn: @mehmet_trader)
2. BotFather'da bot token'ını kullanarak `getUpdates` çağrısı yap:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. Response'da `chat.id` değerini bul

### 4. Database'i Güncelle
Chat ID'yi aldıktan sonra:

```bash
python update_chat_id.py --chat-id="-1001234567890"
```

Veya manuel:
```sql
UPDATE chats SET chat_id='GERÇEK_CHAT_ID' WHERE id=1;
```

### 5. Worker'ı Başlat
```bash
python worker.py
```

### 6. Test Et
5-10 dakika bekle ve mesajları kontrol et:
```bash
python check_messages.py
```

## Beklenen Sonuç
- ✅ Botlar gruba mesaj gönderir
- ✅ Throughput > 2 msg/min
- ✅ Database'de mesajlar kaydedilir

## Sorun Giderme

### Botlar gruba eklenmiyor
- BotFather'da botların "privacy mode" ayarını kontrol et
- Privacy mode = disabled olmalı (gruplardan mesaj okuyabilmek için)

### Botlar mesaj göndermiyor
- Botların gruba "send messages" izni olduğundan emin ol
- Worker loglarını kontrol et: `python worker.py`

### Chat ID bulunamıyor
- @getidsbot'u kullan (en kolay yöntem)
- Veya @userinfobot'u kullan
