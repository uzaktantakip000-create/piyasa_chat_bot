# Code Review Checklist

Her commit öncesi bu kontrolü yap:

## Security ✓
- [ ] Secrets hardcode edilmemiş
- [ ] SQL injection koruması var
- [ ] Input validation yapılıyor
- [ ] Rate limiting aktif

## Performance ✓
- [ ] Async/await kullanılmış
- [ ] Database indexler uygun
- [ ] Cache stratejisi var

## Code Quality ✓
- [ ] Type hints eklenmiş
- [ ] Docstrings var
- [ ] Complex logic commented
- [ ] DRY principle

## Testing ✓
- [ ] Unit tests var
- [ ] Edge cases test edilmiş
- [ ] Coverage %80+

## Documentation ✓
- [ ] README güncellendi
- [ ] CHANGELOG güncellendi
- [ ] Docstrings eksiksiz