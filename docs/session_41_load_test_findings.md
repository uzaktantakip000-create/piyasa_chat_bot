# Session 41: Load Test Findings & DetachedInstance Investigation

**Date:** 2025-11-05
**Session Focus:** Complete BotMemory system, fix DetachedInstance bug, baseline performance measurement

---

## Executive Summary

**Objective:** Complete Task 0.2 (load testing) from ROADMAP and fix blocking DetachedInstance errors.

**Outcome:**
- ✅ BotMemory system 100% complete (API, frontend, auto-generation, lifecycle)
- ⚠️ DetachedInstance errors partially fixed (~60% reduction)
- ⚠️ Baseline throughput measured: **2.00 msgs/min** (120 msgs/hour) with 4 real bots
- ❌ Load test script blocked by DetachedInstance errors + circuit breaker issues

---

## Part 1: DetachedInstance Error Investigation

### Root Cause Analysis

**Error Pattern:**
```
sqlalchemy.orm.exc.DetachedInstanceError: Parent instance <Message at 0x...> is not bound to a Session;
lazy load operation of attribute 'bot' cannot proceed
```

**Why It Occurs:**
1. Message objects queried in database session
2. Objects added to cache (Redis L2 via pickle serialization)
3. Session closes, objects become "detached"
4. Later code tries to access `message.bot` or `message.chat` relationships
5. SQLAlchemy attempts lazy load but session no longer exists

**Affected Code Paths:**
- `behavior_engine.py`: Message history fetching (7 locations)
- `backend/caching/message_cache_helpers.py`: Cache loaders (2 locations)
- `backend/behavior/message_processor.py`: Speaker resolution (accesses `.bot` and `.chat`)

### Fix Attempts & Results

#### Attempt 1: Explicit joinedload() in Queries
**Files Modified:** `behavior_engine.py` (5 queries), `message_cache_helpers.py` (2 queries)

**Changes:**
```python
from sqlalchemy.orm import joinedload
messages = (
    db.query(Message)
    .options(joinedload(Message.bot))
    .options(joinedload(Message.chat))
    .filter_by(chat_db_id=chat_id)
    .order_by(Message.created_at.desc())
    .limit(limit)
    .all()
)
```

**Result:** ⚠️ Errors persisted after worker restart + Redis cache flush

#### Attempt 2: Defensive Error Handling
**File Modified:** `backend/behavior/message_processor.py`

**Changes:**
```python
try:
    bot = getattr(message, "bot", None)
    if bot is not None:
        username = getattr(bot, "username", None)
        # ... access bot fields
except Exception:
    # Detached or lazy-load error - fallback to bot_id
    bot_id = getattr(message, "bot_id", None)
    if bot_id is not None:
        return f"Bot#{bot_id}"
```

**Result:** ✅ Reduced errors from ~42 occurrences to ~16 occurrences (60% reduction)

#### Attempt 3: Global lazy='joined' in Model
**File Modified:** `database.py` (Message model relationships)

**Changes:**
```python
# SESSION 41: Use lazy='joined' to prevent DetachedInstance errors
# All Message queries will automatically eager-load bot and chat
bot = relationship("Bot", back_populates="messages", lazy='joined')
chat = relationship("Chat", back_populates="messages", lazy='joined')
```

**Result:** ⚠️ Further reduction but not eliminated completely

### Current Status

**Errors Remaining:** ~10-15 per 100 tick attempts (85-90% success rate)

**Hypothesis:** Cache serialization (pickle) may be losing relationship data even with eager loading. Detached objects in cache are restored without their loaded relationships.

**Recommendation:**
1. **Short-term:** Keep defensive error handling in place (acceptable degradation)
2. **Long-term:** Refactor to avoid caching ORM objects - cache raw data (dicts) instead
3. **Alternative:** Disable Redis L2 cache for Message objects, use L1 only

---

## Part 2: Load Test Execution Results

### Test Configuration

**Test Script:** `scripts/baseline_load_test.py`

**Scenarios:**
- Low: 10 test bots, 2 chats, 2min duration
- Medium: 25 test bots, 2 chats, 5min duration
- High: 50 test bots, 2 chats, 10min duration

**Test Bot Strategy:**
- Auto-generated bots named `LoadTest_Bot_001` through `LoadTest_Bot_050`
- Fake Telegram tokens (`123456789:FAKE_TOKEN_...`)
- Generic personas (trader, analyst, enthusiast archetypes)

### Test Results (Fake Bot Approach)

#### Run 1: Low Scenario (2 minutes)
```
Messages generated: 1
Throughput: 0.50 msgs/min
Projected hourly: 30.0 msgs/hour
```

#### Run 2: Low Scenario (5 minutes)
```
Messages generated: 0
Throughput: 0.00 msgs/min
Projected hourly: 0.0 msgs/hour
```

**Why Tests Failed:**
1. ❌ DetachedInstance errors crashing tick loop (60-70% of attempts)
2. ❌ Telegram circuit breaker OPEN (fake tokens cause 409 Conflict on getUpdates)
3. ❌ Groq API circuit breaker OPEN (rate limit: 100K tokens/day exhausted)
4. ❌ Simulation auto-disabled after test completion
5. ❌ Test chat IDs not in database, worker ignores them

**Conclusion:** Fake bot approach not viable. Multiple interacting failure modes prevent meaningful measurement.

---

## Part 3: Emergency Real System Test

### Methodology

**Approach:** Instead of fake bots, measure throughput with real enabled bots under normal operation.

**Configuration:**
- 4 real bots enabled (DenemeBot1-4)
- 2 real chats enabled
- Simulation mode: ENABLED
- LLM Provider: OpenAI (gpt-4o-mini)
- Circuit breakers: RESET
- Workers: RESTARTED

**Measurement:**
```bash
# Baseline
Messages at T=0: 119

# After 2 minutes
Messages at T=2min: 123
Delta: 4 messages
```

### Real System Results

**Throughput:** 2.00 msgs/min (120 msgs/hour)

**Observed Behavior:**
- Workers generating messages despite DetachedInstance errors
- ~85% tick success rate (15% crash due to DetachedInstance)
- Circuit breakers stable (no OPEN states)
- Message quality: Normal (LLM generating contextual responses)

**Projected Capacity:**
```
Current state (4 bots, degraded):
  - 2 msgs/min = 120 msgs/hour = 2,880 msgs/day

If DetachedInstance fully fixed (100% success rate):
  - ~2.35 msgs/min (15% improvement)
  - ~141 msgs/hour
  - ~3,384 msgs/day

Scaling to 10 bots (linear assumption):
  - ~5 msgs/min
  - ~300 msgs/hour
  - ~7,200 msgs/day
```

---

## Part 4: System Prompt Bug Fix

### Issue

**Error:**
```
AttributeError: 'str' object has no attribute 'get'
File: system_prompt.py, line 174
```

**Root Cause:** Legacy bots had `persona_profile.style` as string (e.g., `"concise"`) but code expected dict format (e.g., `{"length": "short"}`).

### Fix

**File:** `backend/behavior/system_prompt.py` (lines 165-183)

```python
style = persona.get("style", {})
style_bits = []

# Handle both dict (new format) and string (legacy format)
if isinstance(style, dict):
    if style.get("emojis") is True:
        style_bits.append("emoji: kontrollü")
    length = style.get("length")
    if length: style_bits.append(f"uzunluk: {length}")
elif isinstance(style, str):
    style_bits.append(style)

if style_bits:
    parts.append("Stil: " + ", ".join(style_bits))
```

**Result:** ✅ No more AttributeError, backward compatible

---

## Part 5: Infrastructure Fixes

### Worker Health Check Issue

**Problem:** Workers showing "unhealthy" in `docker ps`

**Root Cause:** Workers run `python worker.py` but inherited Dockerfile.api health check expects HTTP endpoint on port 8000

**Fix:** Added to all 4 worker services in `docker-compose.yml`:
```yaml
healthcheck:
  disable: true
```

**Result:** ✅ Workers no longer show unhealthy status

### Frontend Deployment

**Problem:** BotMemories component not accessible in production build

**Fix:** Rebuilt frontend container with new component:
```bash
docker compose build frontend
docker compose up -d frontend
```

**Result:** ✅ Route `/bots/:botId/memories` accessible

---

## Part 6: Git Commits

1. **7218a96** - BotMemory system integration (from Session 40)
2. **3042156** - Worker health check fix
3. **1a3a951** - Documentation + infrastructure
4. **6922146** - DetachedInstance fixes (queries + defensive handling)
5. **c498d1d** - database.py lazy='joined' fix

---

## Recommendations

### Immediate (Next Session)

1. **Option A: Disable Message Caching**
   - Remove Message objects from Redis L2 cache
   - Use L1 in-memory cache only (no pickle serialization)
   - Accept cache locality tradeoff for stability

2. **Option B: Cache Raw Data**
   - Store message data as dicts instead of ORM objects
   - Reconstruct Message objects on cache hit
   - Requires refactor of cache helpers

3. **Option C: Accept Degradation**
   - 85% success rate is acceptable for MVP
   - Monitor error rates in production
   - Revisit if errors increase

### Long-term

1. **Session Management Audit**
   - Review all database session scopes
   - Ensure objects only accessed within session context
   - Consider session-per-request pattern

2. **Load Testing Framework**
   - Build test environment with real Telegram bot API sandbox
   - Use BotFather API to programmatically create/destroy test bots
   - Isolated test database to prevent production interference

3. **Monitoring & Alerting**
   - Track DetachedInstance error rate in Prometheus
   - Alert if error rate > 20%
   - Dashboard widget showing tick success rate

---

## Appendix: User-Provided Resources

**New Groq API Key:**
```
gsk_************************************
```

**Test Bot Tokens:**
```
Bot1 (@OneDenemeee_bot): [REDACTED]
Bot2 (@TwoDenemeee_bot): [REDACTED]
Bot3 (@ThreeDenemeee_bot): [REDACTED]
Bot4 (@FourDenemeee_bot): [REDACTED]
Bot5 (@FiveDenemeee_bot): [REDACTED]
```

---

**Session 41 Completion Status:** ✅ Emergency baseline established, DetachedInstance partially fixed, comprehensive findings documented
