# Karar Ağacı

## Yeni Özellik Eklerken

```
Yeni feature mi?
├─ Evet
│  ├─ Database değişikliği var mı?
│  │  ├─ Evet → Migration oluştur (Alembic)
│  │  └─ Hayır → Devam et
│  │
│  ├─ API endpoint gerekli mi?
│  │  ├─ Evet → api/v1/endpoints/ altına ekle
│  │  │         → Pydantic schema oluştur
│  │  │         → Rate limiting ekle
│  │  │         → OpenAPI docs güncelle
│  │  └─ Hayır → Sadece service layer
│  │
│  ├─ External API çağrısı var mı?
│  │  ├─ Evet → Retry logic ekle (tenacity)
│  │  │         → Timeout ayarla (30s)
│  │  │         → Circuit breaker düşün
│  │  │         → Mock test yaz
│  │  └─ Hayır → Devam et
│  │
│  ├─ Cache'lenebilir mi?
│  │  ├─ Evet → Redis cache ekle
│  │  │         → TTL belirle (5-15 dakika)
│  │  │         → Cache invalidation stratejisi
│  │  └─ Hayır → Devam et
│  │
│  ├─ Test coverage %80+ mi?
│  │  ├─ Evet → Code review yap
│  │  │         → CHANGELOG.md güncelle
│  │  │         → Commit yap
│  │  └─ Hayır → Daha fazla test yaz
│  │            → Edge cases ekle
│  │            → Error scenarios test et
│  │
│  └─ CHANGELOG ve README güncellendi mi?
│     ├─ Evet → Git commit yap
│     └─ Hayır → Dokümantasyonu tamamla
│
└─ Hayır (Bug fix)
   ├─ Bug'ı reproduce eden test yaz
   ├─ Root cause analizi yap
   ├─ Fix'i uygula
   ├─ Test'in geçtiğini doğrula
   ├─ Regression test ekle
   └─ memory.json'a ekle
```

---

## Hata Aldığımda

```
Hata türü nedir?
│
├─ ImportError
│  ├─ "No module named 'X'"
│  │  └─ Çözüm: pip install X veya requirements.txt kontrol
│  │
│  ├─ Circular import
│  │  └─ Çözüm: Dependency injection kullan
│  │            → veya import'u fonksiyon içine taşı
│  │
│  └─ "cannot import name 'X' from 'Y'"
│     └─ Çözüm: X tanımlı mı kontrol et
│               → Typo var mı bak
│
├─ DatabaseError
│  ├─ Connection error
│  │  └─ Çözüm: Database çalışıyor mu?
│  │            → Connection string doğru mu?
│  │            → Firewall/network sorunu var mı?
│  │
│  ├─ IntegrityError (UNIQUE constraint)
│  │  └─ Çözüm: get_or_create kullan
│  │            → veya duplicate check ekle
│  │
│  ├─ TooManyConnectionsError
│  │  └─ Çözüm: Connection leak var mı kontrol et
│  │            → Context manager kullan
│  │            → pool_size artır (20-40)
│  │
│  └─ OperationalError
│     └─ Çözüm: Table exists mi?
│               → Migration çalıştırıldı mı?
│
├─ ValidationError (Pydantic)
│  └─ Çözüm: Request body schema kontrol et
│            → Field types uyuşuyor mu?
│            → Required fields eksik mi?
│            → Validation rules çok sıkı mı?
│
├─ RateLimitError (External API)
│  ├─ OpenAI
│  │  └─ Çözüm: Exponential backoff ekle
│  │            → Request queue sistemi
│  │            → Model değiştir (gpt-4o-mini)
│  │
│  └─ Telegram
│     └─ Çözüm: Mesaj gönderme hızını azalt
│               → Batch sending kullan
│               → Retry after X seconds
│
├─ TimeoutError
│  └─ Çözüm: Timeout değerini artır
│            → Async operations kullan
│            → Performance optimize et
│
├─ AuthenticationError
│  ├─ API key invalid
│  │  └─ Çözüm: .env dosyası kontrol et
│  │            → Token encryption key doğru mu?
│  │
│  └─ Unauthorized
│     └─ Çözüm: X-API-Key header gönderiliyor mu?
│               → API_KEY değeri doğru mu?
│
└─ Generic Exception
   └─ Çözüm: Stack trace'i oku
             → memory.json'da benzer var mı?
             → Log'lara bak
             → Debugger kullan
```

---

## Performance Sorununda

```
Yavaş mı çalışıyor?
│
├─ Database query'leri mi yavaş?
│  ├─ N+1 problem var mı?
│  │  └─ Çözüm: joinedload() kullan
│  │            → selectinload() kullan
│  │            → Eager loading yap
│  │
│  ├─ Index eksik mi?
│  │  └─ Çözüm: EXPLAIN ANALYZE çalıştır
│  │            → Sık sorgulanan kolonlara index ekle
│  │            → created_at, bot_id, chat_id
│  │
│  └─ Çok fazla veri mi çekiliyor?
│     └─ Çözüm: LIMIT ekle
│               → Pagination kullan
│               → Select specific columns
│
├─ External API mi yavaş?
│  ├─ Cache'lenebilir mi?
│  │  └─ Çözüm: Redis cache ekle
│  │            → TTL: 5-15 dakika
│  │
│  ├─ Paralel çalışabilir mi?
│  │  └─ Çözüm: asyncio.gather() kullan
│  │            → Concurrent requests
│  │
│  └─ Timeout uygun mu?
│     └─ Çözüm: Timeout değerini ayarla
│               → 30s genelde yeterli
│
├─ Memory leak mi var?
│  └─ Çözüm: Context manager kullan
│            → Connection'ları kapat
│            → memory_profiler çalıştır
│            → Circular references kontrol et
│
└─ CPU intensive mi?
   └─ Çözüm: Profiler çalıştır (cProfile)
             → Algoritma optimize et
             → Cache sonuçları
             → Async operations kullan
```

---

## Test Yazarken

```
Test türü ne olmalı?
│
├─ Unit Test
│  ├─ Function/method test
│  │  └─ Happy path test et
│  │     → Edge cases test et
│  │     → Error scenarios test et
│  │     → Mock external dependencies
│  │
│  └─ Coverage hedefi: %85
│
├─ Integration Test
│  ├─ API endpoint test
│  │  └─ 200 OK response
│  │     → 400 Bad Request
│  │     → 401 Unauthorized
│  │     → 404 Not Found
│  │     → 422 Validation Error
│  │     → 429 Rate Limit
│  │
│  ├─ Database operations
│  │  └─ CRUD operations
│  │     → Transaction rollback
│  │     → Constraint violations
│  │
│  └─ Coverage hedefi: %70
│
└─ E2E Test
   ├─ Critical user flows
   │  └─ Bot creation → activation → messaging
   │     → Error recovery flows
   │
   └─ Coverage hedefi: %50
```

---

## Commit Yaparken

```
Değişiklik ne?
│
├─ Yeni özellik
│  └─ Commit: "feat(scope): description"
│     Örnek: "feat(api): add rate limiting to bot endpoints"
│
├─ Bug fix
│  └─ Commit: "fix(scope): description"
│     Örnek: "fix(worker): resolve argparse import error"
│
├─ Refactoring
│  └─ Commit: "refactor(scope): description"
│     Örnek: "refactor(services): apply repository pattern"
│
├─ Performance
│  └─ Commit: "perf(scope): description"
│     Örnek: "perf(database): add indexes to frequently queried columns"
│
├─ Documentation
│  └─ Commit: "docs: description"
│     Örnek: "docs: update API endpoint examples in README"
│
├─ Tests
│  └─ Commit: "test(scope): description"
│     Örnek: "test(services): add unit tests for bot service"
│
└─ Chore/Maintenance
   └─ Commit: "chore: description"
      Örnek: "chore: update dependencies to latest versions"
```

---

## Code Review Yaparken

```
Kontrol et:
│
├─ Security
│  ├─ Secrets hardcode edilmemiş mi? ✓
│  ├─ SQL injection koruması var mı? ✓
│  ├─ Input validation yapılıyor mu? ✓
│  └─ Rate limiting aktif mi? ✓
│
├─ Performance
│  ├─ Async/await kullanılmış mı? ✓
│  ├─ N+1 query problemi yok mu? ✓
│  ├─ Cache uygun mu? ✓
│  └─ Connection'lar kapatılıyor mu? ✓
│
├─ Code Quality
│  ├─ Type hints eklenmiş mi? ✓
│  ├─ Docstrings var mı? ✓
│  ├─ Complex logic commented mi? ✓
│  ├─ DRY principle uygulanmış mı? ✓
│  └─ Naming conventions doğru mu? ✓
│
├─ Testing
│  ├─ Unit tests var mı? ✓
│  ├─ Edge cases test edilmiş mi? ✓
│  ├─ Coverage %80+ mı? ✓
│  └─ Mock'lar doğru kullanılmış mı? ✓
│
└─ Documentation
   ├─ README güncellendi mi? ✓
   ├─ CHANGELOG güncellendi mi? ✓
   ├─ API docs güncellendi mi? ✓
   └─ Docstrings eksiksiz mi? ✓
```