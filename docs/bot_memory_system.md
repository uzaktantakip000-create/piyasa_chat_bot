# Bot Memory System - User Guide

## Overview

The Bot Memory System allows bots to maintain persistent, personal memories that shape their personality, preferences, and conversation history. Memories are automatically injected into LLM prompts to create more consistent and contextual responses.

**Introduced**: Session 12 (database model), Session 41 (API + UI + lifecycle management)

## Memory Types

Each memory has a specific type that categorizes its content:

| Type | Description | Example |
|------|-------------|---------|
| **personal_fact** | Core identity traits, beliefs, background | "Türk piyasalarında aktif bir yatırımcıyım" |
| **past_event** | Historical experiences, anecdotes | "2008 krizinde paniğe kapılmadan portföyümü korumuştum" |
| **relationship** | Connections with people, entities, markets | "Bankacılık sektörünü yakından takip ediyorum" |
| **preference** | Likes, dislikes, habits, risk tolerance | "Yüksek risk alırım, büyük kazançlar için cesur kararlar veririm" |
| **routine** | Regular behaviors, communication style | "Kısa ve öz yazmayı severim, fazla detaya girmem" |

## Memory Fields

- **bot_id**: Bot association (foreign key)
- **memory_type**: One of the 5 types above
- **content**: Natural language description (Turkish)
- **relevance_score**: 0.0-1.0 importance score (higher = more important)
- **created_at**: Timestamp of creation
- **last_used_at**: Last time memory was injected into LLM prompt
- **usage_count**: Number of times memory has been used

## Auto-Generation

Memories are automatically generated from bot persona profiles when:
1. Creating a new bot via **POST /bots**
2. Using the wizard setup via **POST /wizard/setup**
3. Running batch script for existing bots

### Persona Mapping

The system extracts memories from these persona fields:

| Persona Field | → | Memory Type | Example |
|---------------|---|-------------|---------|
| `risk_profile: "moderate"` | → | **preference** | "Dengeli bir yatırımcıyım, risk ve getiri arasında denge kurarım" |
| `watchlist: ["BIST:AKBNK", "XAUUSD"]` | → | **personal_fact** | "Sürekli takip ettiğim piyasalar: BIST:AKBNK, XAUUSD" |
| `tone: "analytical"` | → | **personal_fact** | "Analitik düşünürüm, her kararımı verilere dayanarak alırım" |
| `style: "concise"` | → | **routine** | "Kısa ve öz yazmayı severim, fazla detaya girmem" |
| `emotion.signature_phrases: ["şahsi fikrim"]` | → | **routine** | "Konuşmalarımda sık kullandığım ifade: 'şahsi fikrim'" |
| `emotion.anecdotes: ["..."]` | → | **past_event** | (First 200 chars of anecdote) |
| `emotion.energy: "high"` | → | **personal_fact** | "Enerjik ve hareketli biriyim, hızlı karar alırım" |

**Default Memories**: If no persona profile exists, 2 generic memories are created:
- "Türk piyasalarında aktif bir yatırımcıyım" (personal_fact)
- "Günlük piyasa gelişmelerini takip etmeyi severim" (preference)

## API Endpoints

### List Bot Memories
```http
GET /bots/{bot_id}/memories
Authorization: X-API-Key or Cookie
Role: viewer, operator, admin
```

**Response**: Array of memories ordered by relevance_score (desc), then last_used_at (desc)

```json
[
  {
    "id": 1,
    "bot_id": 42,
    "memory_type": "preference",
    "content": "Dengeli bir yatırımcıyım, risk ve getiri arasında denge kurarım.",
    "relevance_score": 0.9,
    "created_at": "2025-11-05T10:00:00Z",
    "last_used_at": "2025-11-05T11:00:00Z",
    "usage_count": 15
  }
]
```

### Create Memory
```http
POST /bots/{bot_id}/memories
Authorization: X-API-Key or Cookie
Role: operator, admin
Content-Type: application/json
```

**Request Body**:
```json
{
  "memory_type": "past_event",
  "content": "Geçen ayki dalgalanmada sakin kalıp planıma sadık kaldım",
  "relevance_score": 0.85
}
```

**Validation**:
- `memory_type`: Required, must be one of 5 valid types
- `content`: Required, min 1 character
- `relevance_score`: Optional, 0.0-1.0 (default: 1.0)

### Update Memory
```http
PATCH /memories/{memory_id}
Authorization: X-API-Key or Cookie
Role: operator, admin
Content-Type: application/json
```

**Request Body** (all fields optional):
```json
{
  "memory_type": "preference",
  "content": "Updated memory content",
  "relevance_score": 0.95
}
```

### Delete Memory
```http
DELETE /memories/{memory_id}
Authorization: X-API-Key or Cookie
Role: operator, admin
```

**Response**: 204 No Content

## Frontend UI

### Accessing Memory Management

1. Navigate to **Bots** tab
2. Click the **Brain icon** (🧠) for any bot (table or card view)
3. Memory management dialog opens

### UI Features

- **Memory List**: Shows all memories with type badges, relevance scores, usage stats
- **Create/Edit Dialog**: Form with type selector, content textarea, relevance slider
- **Delete Confirmation**: Prevents accidental deletion
- **Real-time Updates**: Changes immediately visible after save

### Memory Type Colors

- **personal_fact**: Blue badge
- **past_event**: Purple badge
- **relationship**: Green badge
- **preference**: Orange badge
- **routine**: Gray badge

## LLM Prompt Integration

Memories are automatically injected into the system prompt when generating messages:

```
## KİŞİSEL NOTLARIN / HAFIZALARIN
- [personal_fact] Türk piyasalarında aktif bir yatırımcıyım
- [preference] Dengeli bir yatırımcıyım, risk ve getiri arasında denge kurarım
- [routine] Kısa ve öz yazmayı severim, fazla detaya girmem
...
```

**Selection Logic**:
- Top 8-10 memories by relevance_score
- Ordered by relevance (descending)
- Usage tracking: `usage_count` incremented, `last_used_at` updated

**Location in Prompt**: After holdings, before chat history (see `system_prompt.py:USER_TEMPLATE_V2`)

## Memory Lifecycle Management

### Automatic Cleanup Script

**File**: `scripts/cleanup_memories.py`

**Strategies**:
1. **Low-Relevance Deletion**: Remove memories with:
   - `relevance_score < 0.3`
   - `usage_count < 2`
   - `last_used_at > 6 months ago`

2. **Memory Limit Enforcement**: Keep max 50 memories per bot
   - Deletes lowest scoring excess memories

3. **Relevance Decay**: Reduce score by 10% for memories older than 6 months
   - Prevents stale memories from dominating prompts

**Usage**:
```bash
# Dry run (preview only)
python scripts/cleanup_memories.py --dry-run

# Real cleanup
python scripts/cleanup_memories.py

# Aggressive mode (3 months, score < 0.5, max 30/bot)
python scripts/cleanup_memories.py --aggressive

# Statistics only
python scripts/cleanup_memories.py --stats-only
```

**Recommended Schedule**: Monthly via cron job (see Setup section)

### Scaling Considerations

| Scale | Memories | Database Size | Performance | Action |
|-------|----------|---------------|-------------|--------|
| Small (< 10 bots) | < 500 | < 1 MB | Excellent | No action needed |
| Medium (10-50 bots) | 500-2,500 | 1-5 MB | Good | Monthly cleanup recommended |
| Large (50-100 bots) | 2,500-5,000 | 5-10 MB | Fair | Weekly cleanup, consider archiving |
| Enterprise (100+ bots) | 5,000+ | 10+ MB | Monitor | Daily cleanup, implement archiving |

**Indexes**: Bot memories table has composite indexes on `(bot_id, memory_type)` and `(bot_id, relevance_score)` for fast queries.

## Automated Cleanup Setup (Cron)

Add to `docker-compose.yml` under services:

```yaml
  memory-cleanup:
    build:
      context: .
      dockerfile: Dockerfile.api
    container_name: piyasa-memory-cleanup
    env_file:
      - .env
    environment:
      - DATABASE_URL=postgresql+psycopg://app:app@db:5432/app
    command: >
      sh -c "while true; do
        python scripts/cleanup_memories.py;
        sleep 2592000;
      done"
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
```

**Schedule**: Runs every 2,592,000 seconds (30 days)

**Alternative**: Use system cron on host machine instead of Docker container.

## Best Practices

### Creating Effective Memories

✅ **DO**:
- Write memories in first person ("Ben...")
- Use natural Turkish language
- Be specific and concrete
- Set appropriate relevance scores (0.8-1.0 for core traits, 0.5-0.7 for preferences)
- Update memories as bot personality evolves

❌ **DON'T**:
- Duplicate information (memories should be unique)
- Use overly generic statements
- Create contradictory memories
- Set all memories to 1.0 relevance (defeats prioritization)

### Memory Hierarchy

**High Relevance (0.9-1.0)**: Core identity, unchanging beliefs
- "Yatırımlarımda çok temkinliyim"
- "Bankacılık sektörü uzmanıyım"

**Medium Relevance (0.7-0.8)**: Preferences, habits
- "Günlük piyasa gelişmelerini takip ederim"
- "Teknik analiz kullanmayı severim"

**Low Relevance (0.5-0.6)**: Minor details, evolving opinions
- "Bugünlerde altın fiyatları ilgimi çekiyor"
- "Geçen hafta BIST'te karlı işlem yaptım"

### Maintenance

- **Review Quarterly**: Check if memories still reflect bot's personality
- **Prune Duplicates**: Remove redundant or overlapping memories
- **Update Scores**: Adjust relevance as bot evolves
- **Monitor Usage**: Delete memories with 0 usage after 3+ months

## Troubleshooting

### Memories Not Appearing in Messages

**Check**:
1. Memory relevance_score > 0.3
2. Bot has at least 1 memory
3. Behavior engine is running (workers active)
4. Simulation is enabled

**Debug**: Check `behavior_engine.py` logs for "Fetching bot memories"

### Auto-Generation Not Working

**Common Causes**:
- Persona profile is empty or malformed
- Bot created before Session 41 (run batch script)
- Memory count already > 0 (auto-gen skips)

**Solution**: Manually create memories or run:
```bash
python scripts/auto_generate_memories.py --bot-id {BOT_ID}
```

### High Memory Count (100+)

**Impact**: Slightly slower prompt generation, increased token usage

**Solution**:
```bash
# Aggressive cleanup
python scripts/cleanup_memories.py --aggressive

# Manual pruning via UI
```

## Migration Guide

### Existing Bots (Pre-Session 41)

Run batch auto-generation script:
```bash
# Dry run first
python scripts/auto_generate_memories.py --dry-run

# Generate for all bots
python scripts/auto_generate_memories.py

# Generate for specific bot
python scripts/auto_generate_memories.py --bot-id 42
```

**Output** (Session 41 test):
```
Found 54 bot(s) to process
✅ Created 270 memories total (5/bot avg)
```

### Database Migration

BotMemory table created in Alembic migration `fe686589d4eb` (Session 12).

**No migration needed** for new deployments (table auto-created).

For manual creation:
```sql
CREATE TABLE bot_memories (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    memory_type VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    relevance_score FLOAT NOT NULL DEFAULT 1.0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMP NOT NULL DEFAULT NOW(),
    usage_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX ix_memories_bot_type ON bot_memories(bot_id, memory_type);
CREATE INDEX ix_memories_bot_relevance ON bot_memories(bot_id, relevance_score);
```

## Related Files

- **Database Model**: `database.py` (lines 186-213)
- **API Routes**: `backend/api/routes/bots.py` (lines 445-535)
- **Schemas**: `schemas.py` (MemoryCreate, MemoryUpdate, MemoryResponse)
- **Frontend**: `BotMemories.jsx`, `Bots.jsx`, `App.jsx`
- **Behavior Engine**: `behavior_engine.py` (lines 1357-1367)
- **Prompt Integration**: `system_prompt.py` (lines 352-450)
- **Helper Functions**: `backend/behavior_engine/metadata_analyzer.py`
- **Auto-Generation**: `backend/api/utils/memory_generator.py`
- **Batch Script**: `scripts/auto_generate_memories.py`
- **Cleanup Script**: `scripts/cleanup_memories.py`

## Examples

### Example 1: Risk-Averse Investor

```json
[
  {
    "memory_type": "preference",
    "content": "Yatırımlarımda çok temkinliyim, güvenli limanları tercih ederim",
    "relevance_score": 0.95
  },
  {
    "memory_type": "past_event",
    "content": "2018'de yüksek riskli bir yatırımda zarar ettim, o zamandan beri dikkatli",
    "relevance_score": 0.85
  },
  {
    "memory_type": "routine",
    "content": "Yatırım kararı vermeden önce mutlaka araştırma yaparım",
    "relevance_score": 0.8
  }
]
```

### Example 2: Day Trader

```json
[
  {
    "memory_type": "personal_fact",
    "content": "Full-time day trader'ım, BIST'te günlük işlemler yaparım",
    "relevance_score": 1.0
  },
  {
    "memory_type": "preference",
    "content": "Hızlı kararlar alırım, momentum takip ederim",
    "relevance_score": 0.9
  },
  {
    "memory_type": "relationship",
    "content": "Teknoloji hisselerini yakından takip ediyorum",
    "relevance_score": 0.85
  }
]
```

## Roadmap

### Completed (Session 41)
- ✅ Full CRUD API
- ✅ Frontend UI (BotMemories component)
- ✅ Auto-generation from persona
- ✅ Cleanup lifecycle management
- ✅ Wizard integration
- ✅ Usage tracking

### Future Enhancements
- 🔮 Memory search/filter in UI
- 🔮 Memory templates library
- 🔮 Memory import/export (JSON)
- 🔮 Memory versioning/history
- 🔮 Memory similarity detection (prevent duplicates)
- 🔮 AI-assisted memory suggestions
- 🔮 Memory analytics dashboard

## Support

For issues or questions:
- Check ROADMAP_MEMORY.md for Session 41 notes
- Review error_management.md for troubleshooting
- Check worker logs for memory injection errors

---

**Last Updated**: Session 41 (2025-11-05)
**Version**: 1.0
