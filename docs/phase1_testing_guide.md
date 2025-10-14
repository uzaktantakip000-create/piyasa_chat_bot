# Phase 1 - Incoming Message System Testing Guide

## Overview

This guide provides comprehensive testing instructions for the Phase 1 Incoming Message System implementation. The system enables bots to:

- Receive incoming messages from real Telegram users
- Detect mentions and replies
- Prioritize responses via Redis queue
- Use user messages as context for natural conversations

## Test Environment Setup

### Option 1: Docker Compose (Recommended)

```bash
# Start all services
docker compose up --build

# Services started:
# - API (port 8000)
# - Worker (behavior engine + message listener)
# - Frontend (port 5173)
# - Redis (port 6379)
```

### Option 2: Manual Setup

```bash
# Terminal 1 - API
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2 - Worker
python worker.py

# Terminal 3 - Frontend
npm install
npm run dev
```

## Configuration

### Webhook Mode (Production - Recommended)

Set in `.env`:
```env
USE_LONG_POLLING=false
REDIS_URL=redis://localhost:6379/0
```

Webhook endpoint format:
```
https://your-domain.com/webhook/telegram/{bot_token}
```

Configure in Telegram:
```bash
curl -X POST "https://api.telegram.org/bot{YOUR_BOT_TOKEN}/setWebhook" \
  -d "url=https://your-domain.com/webhook/telegram/{YOUR_BOT_TOKEN}"
```

### Long Polling Mode (Fallback)

Set in `.env`:
```env
USE_LONG_POLLING=true
LISTENER_POLLING_INTERVAL=1.0
LISTENER_LONG_POLL_TIMEOUT=30
```

Delete webhook first:
```bash
curl -X POST "https://api.telegram.org/bot{YOUR_BOT_TOKEN}/deleteWebhook"
```

## Test Scenarios

### Test 1: Basic Incoming Message

**Objective**: Verify webhook receives and stores user messages

**Steps**:
1. Create a bot via Dashboard or API:
   ```bash
   curl -X POST http://localhost:8000/bots \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Test Bot",
       "token": "YOUR_BOT_TOKEN",
       "username": "your_bot_username",
       "is_enabled": true
     }'
   ```

2. Send message to bot in Telegram:
   ```
   User: BIST 100 bugün nasıl?
   ```

3. Check database for stored message:
   ```bash
   # Via API
   curl http://localhost:8000/logs?limit=10

   # Or check SQLite directly
   sqlite3 app.db "SELECT * FROM messages WHERE bot_id IS NULL ORDER BY id DESC LIMIT 5;"
   ```

**Expected Result**:
- Message stored with `bot_id = NULL` (user message)
- `msg_metadata` contains: `from_user_id`, `username`, `is_incoming: true`
- `text` field contains the message content

**Validation**:
```json
{
  "id": 123,
  "bot_id": null,
  "chat_db_id": 1,
  "telegram_message_id": 456,
  "text": "BIST 100 bugün nasıl?",
  "msg_metadata": {
    "from_user_id": 123456789,
    "username": "testuser",
    "is_incoming": true,
    "update_id": 789
  }
}
```

### Test 2: Mention Detection

**Objective**: Verify bot detects @mentions and prioritizes response

**Steps**:
1. Send message with bot mention:
   ```
   User: @your_bot_username USD/TRY hakkında ne düşünüyorsun?
   ```

2. Check Redis high priority queue:
   ```bash
   redis-cli
   > LLEN priority_queue:high
   > LINDEX priority_queue:high 0
   ```

3. Observe bot response time (should be faster than normal)

**Expected Result**:
- Message added to `priority_queue:high` in Redis
- Priority data includes:
  ```json
  {
    "type": "incoming_message",
    "is_mentioned": true,
    "priority": "high",
    "message_id": 123,
    "bot_id": 1,
    "chat_id": 1
  }
  ```
- Bot responds within 2-5 seconds
- Response is a direct reply to user's message

### Test 3: Reply Detection

**Objective**: Verify bot detects when user replies to bot message

**Steps**:
1. Wait for bot to send a message in chat
2. Use Telegram's reply feature to reply to that bot message:
   ```
   Bot: BIST 100 yükselişte devam ediyor
   User: [Reply to above] Ne kadar yükselir sence?
   ```

3. Check Redis queue and bot response

**Expected Result**:
- Message detected as reply to bot
- Added to `priority_queue:high`:
  ```json
  {
    "is_reply_to_bot": true,
    "priority": "high",
    "reply_to_message_id": 456
  }
  ```
- Bot responds contextually to the original message

### Test 4: Context Integration

**Objective**: Verify bot uses user messages in conversation context

**Steps**:
1. Create conversation with multiple user and bot messages:
   ```
   User: BIST 100 bugün nasıl?
   Bot: BIST 100 güzel yükselişte
   User: Devam eder mi?
   ```

2. Check bot's next response includes context

**Expected Result**:
- Bot's response references previous conversation
- User messages included in prompt history
- Natural conversational flow maintained

**Validation**:
- Check worker logs for prompt generation:
  ```
  [behavior_engine] History context: 3 messages
  [behavior_engine] Including 2 user messages in context
  ```

### Test 5: Priority Queue Processing

**Objective**: Verify high priority messages processed before normal behavior

**Steps**:
1. Disable simulation: `simulation_active = false`
2. Send mention message to bot
3. Enable simulation: `simulation_active = true`
4. Monitor response timing

**Expected Result**:
- Bot processes priority queue BEFORE random message generation
- High priority queue checked first, then normal queue
- Response sent within seconds of enabling simulation

**Code Reference**: `behavior_engine.py:2130-2141`

### Test 6: Auto-Chat Creation

**Objective**: Verify webhook auto-creates chats for new groups

**Steps**:
1. Add bot to a new Telegram group/channel
2. Send message in that group
3. Check database for auto-created chat

**Expected Result**:
```bash
sqlite3 app.db "SELECT * FROM chats ORDER BY id DESC LIMIT 1;"
```
- New chat created with `chat_id` from Telegram
- `is_enabled = true` by default
- Default topics assigned: `["BIST", "FX", "Kripto", "Makro"]`

### Test 7: Bot Message Filtering

**Objective**: Verify webhook ignores messages from other bots

**Steps**:
1. Add another bot to the test group
2. Let other bot send a message
3. Check database - other bot's message should NOT be stored

**Expected Result**:
- Messages with `from.is_bot = true` are ignored
- No entry in `messages` table
- No Redis queue entry

**Code Reference**: `main.py:1515` (webhook), `message_listener.py:145` (polling)

### Test 8: Concurrent Message Handling

**Objective**: Test system handles multiple users simultaneously

**Steps**:
1. Setup: 5 enabled bots in same chat
2. Simulate 10 users sending messages rapidly:
   ```bash
   # Use manual test script
   python tests/manual_incoming_test.py
   ```

3. Monitor:
   - Database insertion rate
   - Redis queue length
   - Bot response distribution

**Expected Result**:
- All messages stored correctly
- No duplicate responses
- Even distribution of bot responses
- No race conditions or deadlocks

**Performance Metrics**:
- Message storage: < 100ms per message
- Priority queue add: < 50ms
- Bot response time (mention): 2-10 seconds
- System handles 10+ messages/second

## Automated Test Suite

### Run Unit Tests

```bash
# All Phase 1 tests
pytest tests/test_incoming_message_system.py -v

# Specific test class
pytest tests/test_incoming_message_system.py::TestWebhookEndpoint -v

# With coverage
pytest tests/test_incoming_message_system.py --cov=main --cov=behavior_engine
```

### Run Manual Integration Test

```bash
# Requires running API + Worker
python tests/manual_incoming_test.py
```

Expected output:
```
============================================================
Phase 1 - Incoming Message System Tests
============================================================

[TEST 1] Webhook - Basic User Message
✓ Webhook accepted message: ok
✓ Message stored in DB with ID: 123

[TEST 2] Webhook - Mention Detection
✓ Webhook accepted mention message
✓ Message added to HIGH priority queue (length: 1)
✓ Mention flag detected correctly
✓ Priority level set to 'high'

...

============================================================
Test Summary
============================================================

  PASS  Basic User Message
  PASS  Mention Detection
  PASS  Reply Detection
  PASS  Ignore Bot Messages
  PASS  Invalid Token
  PASS  Priority Queue Structure

Total: 6/6 tests passed
```

## Monitoring & Debugging

### Check Webhook Status

```bash
# Get webhook info from Telegram
curl "https://api.telegram.org/bot{YOUR_BOT_TOKEN}/getWebhookInfo"
```

Expected response:
```json
{
  "ok": true,
  "result": {
    "url": "https://your-domain.com/webhook/telegram/YOUR_BOT_TOKEN",
    "has_custom_certificate": false,
    "pending_update_count": 0,
    "max_connections": 40
  }
}
```

### Monitor Redis Queues

```bash
redis-cli
> LLEN priority_queue:high
> LLEN priority_queue:normal
> LRANGE priority_queue:high 0 -1  # View all high priority messages
```

### Check Worker Logs

```bash
# Docker
docker compose logs worker -f

# Local
# Worker outputs to stdout
```

Key log messages:
```
[message_listener] Incoming message saved: msg_id=123, chat=456, user=testuser
[behavior_engine] Priority queue item detected: high priority
[behavior_engine] Responding to incoming message: msg_id=123
[telegram] sendMessage success: chat=456, msg_id=789
```

### Database Queries

```bash
# Recent user messages
sqlite3 app.db "SELECT id, text, msg_metadata FROM messages WHERE bot_id IS NULL ORDER BY id DESC LIMIT 10;"

# Bot responses to user messages
sqlite3 app.db "SELECT m1.text as user_msg, m2.text as bot_response
FROM messages m1
JOIN messages m2 ON m2.reply_to_message_id = m1.telegram_message_id
WHERE m1.bot_id IS NULL AND m2.bot_id IS NOT NULL
ORDER BY m1.id DESC LIMIT 5;"

# Message count by type
sqlite3 app.db "SELECT
  COUNT(CASE WHEN bot_id IS NULL THEN 1 END) as user_messages,
  COUNT(CASE WHEN bot_id IS NOT NULL THEN 1 END) as bot_messages,
  COUNT(*) as total
FROM messages;"
```

## Troubleshooting

### Issue: Messages not being stored

**Symptoms**:
- User sends message but no entry in database
- Webhook returns 200 OK but no data

**Diagnosis**:
1. Check webhook endpoint is correct
2. Verify bot token matches database entry
3. Check user is not a bot (`is_bot: false`)
4. Review API logs for errors

**Solution**:
```bash
# Verify bot exists
curl http://localhost:8000/bots

# Check webhook logs
docker compose logs api | grep webhook

# Test webhook manually
curl -X POST http://localhost:8000/webhook/telegram/YOUR_TOKEN \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_update.json
```

### Issue: Priority queue not working

**Symptoms**:
- Messages stored but bot doesn't respond
- No entries in Redis queues

**Diagnosis**:
1. Check Redis connection
2. Verify `REDIS_URL` in `.env`
3. Check worker is running

**Solution**:
```bash
# Test Redis connection
redis-cli ping
# Should return: PONG

# Check environment variable
echo $REDIS_URL

# Restart worker
docker compose restart worker

# Check Redis in code
python -c "import redis; r = redis.Redis.from_url('redis://localhost:6379/0'); print(r.ping())"
```

### Issue: Bot not responding to mentions

**Symptoms**:
- Mention detected in logs
- No bot response

**Diagnosis**:
1. Check `simulation_active` setting is `true`
2. Verify bot is enabled
3. Check bot's `active_hours` includes current time
4. Review LLM API key configuration

**Solution**:
```bash
# Enable simulation
curl -X PATCH http://localhost:8000/settings \
  -H "Content-Type: application/json" \
  -d '{"simulation_active": true}'

# Check bot status
curl http://localhost:8000/bots/1

# Verify OpenAI API key
echo $OPENAI_API_KEY

# Check worker logs for LLM errors
docker compose logs worker | grep -i error
```

### Issue: Long polling not working

**Symptoms**:
- Worker running but no messages received
- Telegram shows webhook is active

**Diagnosis**:
- Long polling and webhook conflict

**Solution**:
```bash
# Delete webhook
curl -X POST "https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"

# Set USE_LONG_POLLING=true in .env
echo "USE_LONG_POLLING=true" >> .env

# Restart worker
docker compose restart worker

# Verify in logs
docker compose logs worker | grep "LONG POLLING"
```

## Success Criteria

✅ **Phase 1 Complete** when all of the following work:

1. ✓ Webhook receives messages from real users
2. ✓ Messages stored in database with correct metadata
3. ✓ Mentions detected and added to high priority queue
4. ✓ Replies to bot detected and prioritized
5. ✓ Bot messages filtered out (not stored)
6. ✓ User messages included in conversation context
7. ✓ Priority messages processed before random behavior
8. ✓ Chats auto-created for new groups
9. ✓ System handles 5 bots + 10 concurrent users
10. ✓ Both webhook and long polling modes functional

## Next Steps

After Phase 1 validation:

**Phase 2 - Personal Memory System** (from `todo.md`)
- Implement per-bot memory storage
- Add personality consistency tracking
- Create memory recall mechanism
- Develop memory cleanup/summarization

**Phase 3 - Advanced Interactions**
- Multi-bot conversations
- Topic-based routing
- Emotion-driven responses
- Time-based patterns

## Reference Implementation

### Webhook Handler
Location: `main.py:1473-1617`

Key features:
- Bot token verification
- Auto-chat creation
- Mention/reply detection
- Redis priority queue integration
- Metadata tracking

### Priority Queue Processing
Location: `behavior_engine.py:1875-2141`

Key methods:
- `_check_priority_queue()`: Poll Redis for messages
- `_process_priority_message()`: Generate contextual response
- `tick_once()`: Priority-first processing loop

### Message Listener
Location: `message_listener.py:26-259`

Key features:
- Long polling loop
- Update ID tracking
- Concurrent bot polling
- Same priority queue integration as webhook

## Test Data Examples

### Sample Telegram Update (Basic Message)
```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 1001,
    "chat": {
      "id": -1001234567890,
      "title": "Market Discussion",
      "type": "supergroup"
    },
    "from": {
      "id": 987654321,
      "is_bot": false,
      "first_name": "John",
      "username": "johndoe"
    },
    "date": 1704067200,
    "text": "BIST 100 bugün nasıl gidiyor?"
  }
}
```

### Sample Priority Queue Item
```json
{
  "type": "incoming_message",
  "message_id": 123,
  "telegram_message_id": 1001,
  "chat_id": 1,
  "telegram_chat_id": "-1001234567890",
  "bot_id": 1,
  "text": "@mybot USD/TRY analizi?",
  "is_mentioned": true,
  "is_reply_to_bot": false,
  "priority": "high",
  "timestamp": "2025-01-01T12:00:00Z"
}
```

## Additional Resources

- **Telegram Bot API**: https://core.telegram.org/bots/api
- **Redis Commands**: https://redis.io/commands
- **FastAPI Testing**: https://fastapi.tiangolo.com/tutorial/testing/
- **Project README**: `README.md`
- **Architecture Docs**: `CLAUDE.md`
