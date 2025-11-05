# Load Test Findings - Session 41

## Summary

Baseline load test implementation attempted but encountered multiple technical blockers that prevent accurate performance measurement. Test script created but requires significant refactoring of behavior engine session management.

## Test Script Created

**File**: `scripts/baseline_load_test.py`

**Features**:
- Three scenarios: low (10 bots), medium (25 bots), high (50 bots)
- Configurable duration via `--duration` parameter
- Automated test bot creation/cleanup
- Metrics collection (throughput, message count)
- Results saved to JSON

**Usage**:
```bash
python scripts/baseline_load_test.py --scenario low --duration 2
python scripts/baseline_load_test.py --all  # Run all scenarios
```

## Blockers Identified

### 1. SQLAlchemy DetachedInstance Error ❌
**Location**: `behavior_engine.py:2128` (`_prepare_context_data`)

**Error**:
```
sqlalchemy.orm.exc.DetachedInstanceError: Parent instance <Message> is not bound to a Session
```

**Cause**: Message objects from history query are accessed outside their session context, causing lazy-load failures when accessing relationships (e.g., `message.bot_id`).

**Impact**: Workers crash on every tick_once attempt, preventing any message generation.

**Fix Required**: Refactor `_prepare_context_data` to eagerly load all required relationships within session scope.

### 2. system_prompt.py Style Type Bug ✅ FIXED
**Location**: `system_prompt.py:174`

**Error**:
```
AttributeError: 'str' object has no attribute 'get'
```

**Cause**: Legacy bots have `persona_profile.style` as string (e.g., `"concise"`), but code expects dict format (e.g., `{"length": "short", "emojis": false}`).

**Fix Applied**: Added `isinstance(style, dict)` check with fallback for string format.

**Commit**: Included in Session 41 commit 7218a96

### 3. Circuit Breaker Issues
**Groq API**: Circuit breaker OPEN due to rate limit or invalid key
**Telegram API**: Circuit breaker OPEN (expected - test bots use fake tokens)

**Mitigation**: Switched LLM_PROVIDER from `groq` to `openai` in `.env` for testing.

### 4. Test Chat Strategy Problem
**Test Chat ID**: `-1001234567890_LOADTEST` (fake)
**Issue**: Workers may not select fake chat IDs, or bot selection logic filters test bots.

**Observation**: Even with simulation enabled, zero messages generated during 2-minute test windows.

## Test Results (Incomplete)

| Scenario | Bots | Duration | Messages | Throughput | Status |
|----------|------|----------|----------|------------|--------|
| Low      | 10   | 5 min    | 2        | 0.40 msgs/min | ⚠️ Before fixes |
| Low      | 10   | 2 min    | 1        | 0.50 msgs/min | ⚠️ Groq API blocked |
| Low      | 10   | 2 min    | 0        | 0.00 msgs/min | ❌ DetachedInstance error |

**Note**: Results are not representative of actual system capacity due to blockers.

## Current System State

- **Real Bots**: 4 active
- **Enabled Chats**: 2
- **Total Messages**: 116 in database
- **Workers**: 4 running (healthy after health check fix)
- **Simulation**: Disabled (by design when not testing)

## Recommendations

### Short Term (Next Session)
1. **Fix DetachedInstance Error**: Add `joinedload()` to message queries in `_prepare_context_data`
2. **Use Real Chat for Testing**: Instead of fake chat ID, use existing enabled chat with test bots
3. **Add Test Mode Flag**: Environment variable `LOAD_TEST_MODE=true` to bypass Telegram API calls

### Medium Term
4. **Mock Telegram Client**: Create test double for Telegram API to avoid circuit breaker issues
5. **Dedicated Test Database**: Use separate SQLite database for load tests to avoid polluting production data
6. **Continuous Load Testing**: Add to CI/CD pipeline once blockers resolved

### Long Term
7. **Grafana Dashboard**: Integrate Prometheus metrics into load test report
8. **Stress Testing**: Add scenarios for 100, 250, 500 bots
9. **Distributed Testing**: Test multi-worker coordination under load

## Session 38 Production Targets (Reference)

From ROADMAP Task 0.2:
- **Low**: 10 bots (baseline)
- **Medium**: 25 bots (target)
- **High**: 50 bots (stretch goal)

**Note**: These targets remain untested due to technical blockers.

## Files Modified/Created

### Created
- `scripts/baseline_load_test.py` - Load test script (258 lines)
- `docs/load_test_findings.md` - This document

### Modified
- `system_prompt.py` - Fixed style type handling (defensive coding)
- `.env` - Switched LLM_PROVIDER from groq to openai

### Needs Work
- `behavior_engine.py` - Fix DetachedInstance error in `_prepare_context_data`
- `telegram_client.py` - Add test mode bypass

## Next Steps

Load testing is **blocked** until DetachedInstance error is resolved. Proceeding with other P1 tasks:
1. ✅ System_prompt.py bug fix (completed)
2. ⏸️ Load testing (blocked - requires engine refactor)
3. ⏭️ Memory system documentation
4. ⏭️ Automated cleanup cron job
5. ⏭️ ROADMAP update

**Priority**: Fix DetachedInstance bug in next session before attempting load tests again.
