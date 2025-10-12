# Piyasa Chat Bot - Proje Context

## Proje Özeti
Multi-bot Telegram sohbet simülatörü. Birden fazla bot aynı anda konuşarak gerçekçi piyasa tartışmaları oluşturur.

## Teknoloji Stack
- **Backend:** FastAPI (Python 3.11+)
- **Database:** SQLite (dev), PostgreSQL (prod)
- **Cache:** Redis (opsiyonel)
- **LLM:** OpenAI GPT-4o-mini
- **Frontend:** React + Vite
- **Messaging:** Telegram Bot API

## Önemli Kurallar
1. ASLA localStorage kullanma (artifacts'te desteklenmiyor)
2. Her zaman async/await kullan
3. Type hints zorunlu
4. Her function docstring'e sahip olmalı
5. Minimum %80 test coverage
6. Güvenlik: Secrets asla hardcode edilmez

## Coding Standards
- Line length: 100 karakter max
- Import sıralaması: stdlib, third-party, local
- Docstring: Google style
- Error handling: Custom exceptions kullan
- Logging: structlog JSON format

## Database Conventions
- Model adları tekil (Bot, Chat, Message)
- Tablo adları çoğul (bots, chats, messages)
- ID field: UUID yerine integer
- Timestamps: created_at, updated_at (UTC)

## API Conventions
- Versioning: /api/v1/
- Response: JSON snake_case
- Rate limiting: slowapi
- Authentication: API key (X-API-Key header)

## Testing Strategy
- Unit tests: 70%
- Integration tests: 20%
- E2E tests: 10%
- Mock external APIs (OpenAI, Telegram)

## Common Patterns
**Repository Pattern:**
```python
class BotRepository:
    async def get_by_id(self, bot_id: int) -> Optional[Bot]
    async def create(self, bot: BotCreate) -> Bot
```

**Service Pattern:**
```python
class BotService:
    def __init__(self, repo: BotRepository)
    async def activate_bot(self, bot_id: int) -> None
```

## Known Issues
- Worker process argparse import eksikti (düzeltildi)
- Rate limiting Redis gerektiriyor (fallback: memory)
- Telegram API 429 errors (retry logic ekle)