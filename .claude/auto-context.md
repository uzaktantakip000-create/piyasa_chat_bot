# Otomatik Context Enjeksiyonu

Claude Code her prompt aldığında otomatik olarak bu bilgileri hatırla:

---

## 🎯 Proje Kimliği

**Proje:** Piyasa Chat Bot
**Amaç:** Multi-bot Telegram conversation simulator
**Dil:** Türkçe (bot konuşmaları) + İngilizce (kod)
**Stack:** FastAPI + React + OpenAI + Telegram + PostgreSQL + Redis

---

## 📐 Mimari Prensipleri

- **Pattern:** Repository + Service layers
- **Async:** Her yerde async/await kullan
- **Type Hints:** Zorunlu (no Any types)
- **Docstrings:** Google style, zorunlu
- **Test Coverage:** Minimum %80
- **Line Length:** Maximum 100 karakter

---

## 🔒 Güvenlik Kuralları

- ❌ ASLA secrets hardcode etme
- ❌ ASLA localStorage kullanma (artifacts'te desteklenmiyor)
- ✅ Her zaman environment variables kullan
- ✅ Her zaman input validation yap
- ✅ Her zaman rate limiting uygula

---

## 📊 Kalite Standartları

**Her görevde kontrol et:**
- [ ] Type hints eklenmiş mi?
- [ ] Docstrings var mı?
- [ ] Tests yazıldı mı? (%80+ coverage)
- [ ] Code review yapıldı mı?
- [ ] CHANGELOG güncellendi mi?
- [ ] README güncellendi mi?

---

## 🗂️ Dosya Yapısı

```
app/
├── core/          # Config, security, logging
├── api/v1/        # REST endpoints
├── models/        # Database models
├── schemas/       # Pydantic schemas
├── services/      # Business logic
├── repositories/  # Data access
└── worker/        # Background jobs
```

---

## 💾 Database Conventions

- **Model adları:** Tekil (Bot, Chat, Message)
- **Tablo adları:** Çoğul (bots, chats, messages)
- **ID tipi:** Integer (not UUID)
- **Timestamps:** created_at, updated_at (UTC)
- **Soft delete:** is_deleted + deleted_at

---

## 🌐 API Conventions

- **Versioning:** /api/v1/
- **Response:** JSON snake_case
- **Auth:** X-API-Key header
- **Rate limit:** slowapi
- **Errors:** Custom exceptions

---

## 🧪 Test Stratejisi

- **Unit:** %85 coverage target
- **Integration:** %70 coverage target
- **E2E:** %50 coverage target
- **Mock:** External APIs (OpenAI, Telegram)
- **Database:** SQLite in-memory for tests

---

## 🚨 Bilinen Sorunlar

1. **Worker argparse import:** Fixed
2. **Telegram rate limit 429:** Needs retry logic
3. **Redis optional:** Fallback to memory if not available

---

## 🎯 Her Prompt'ta Hatırla

**Görev alınca:**
1. TODO.md oluştur
2. memory.json'dan öğrendiklerini kullan
3. decision-tree.md'ye göre karar ver
4. code-review-checklist.md ile kontrol et
5. Test yaz (%80+ coverage)
6. CHANGELOG.md güncelle
7. Perfect commit yap

**Emin değilsen:** KULLANICIYA SOR
**Hata yaparsan:** memory.json'a KAYDET
**Yavaş çalışıyorsa:** Performance optimize et
**Test fail olursa:** Root cause bul ve düzelt

---

## 📝 Commit Message Format

```
{type}({scope}): {description}

{body}

{footer}
```

**Types:** feat, fix, docs, style, refactor, perf, test, chore
**Scopes:** api, worker, database, telegram, openai, tests

**Örnek:**
```
feat(api): add rate limiting to bot endpoints

Implemented slowapi-based rate limiting to prevent abuse.
Bot operations limited to 30 req/min.

Closes #45
```

---

## 🔧 Common Commands

- `run tests` → pytest -v
- `check coverage` → pytest --cov
- `create migration` → alembic revision --autogenerate
- `run migrations` → alembic upgrade head
- `lint code` → black . && isort .

---

## 📚 External APIs

**OpenAI:**
- Model: gpt-4o-mini
- Timeout: 30s
- Max retries: 3
- Cache: 15 min TTL

**Telegram:**
- Rate limit: 30 msg/sec
- Retry: exponential backoff
- Webhook: ngrok for dev

**Redis:**
- Optional (fallback: memory)
- TTL: 5-15 minutes
- Use for: caching, rate limiting

---

## 💡 Optimization Checklist

**Performance:**
- [ ] Async operations kullanıldı mı?
- [ ] Database indexes var mı?
- [ ] N+1 query problemi yok mu?
- [ ] Cache stratejisi var mı?

**Security:**
- [ ] Secrets environment'tan okunuyor mu?
- [ ] Input validation yapılıyor mu?
- [ ] SQL injection koruması var mı?
- [ ] Rate limiting aktif mi?

**Quality:**
- [ ] Type hints tam mı?
- [ ] Docstrings eksiksiz mi?
- [ ] Tests yeterli mi?
- [ ] Code review yapıldı mı?

---

## 🎓 Learning Mode

**Her görevden sonra:**
1. Ne öğrendim?
2. Hangi pattern işe yaradı?
3. Hangi yaklaşım başarısız oldu?
4. memory.json'a ne eklemeliyim?

**Başarılı pattern:** → memory.json → successful_approaches
**Başarısız pattern:** → memory.json → failed_approaches
**Yeni bug:** → memory.json → common_bugs_and_fixes

---

## 🚀 Ready Checklist

Her görev öncesi kendine sor:

- [ ] Proje context'i okudum mu?
- [ ] Code review checklist'e bakacağım
- [ ] Test yazacağım (%80+ coverage)
- [ ] Dokümantasyon güncelleyeceğim
- [ ] memory.json'a bakacağım
- [ ] decision-tree.md'yi kullanacağım

✅ Hepsi tamam → "READY TO CODE!" de
❌ Eksik var → Önce hazırlan

---

**BU DOSYA HER PROMPT'TA OTOMATİK OLARAK HATIRLANMALI!**