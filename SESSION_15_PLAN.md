# Session 15 - Planning Document

**Status**: READY TO START
**Prepared**: 2025-11-01
**Estimated Duration**: 2-3 hours

---

## 🎯 RECOMMENDED FOCUS: Database Query Optimization (P0)

### Why This Task?

**Priority**: P0 (Highest Impact)
**Expected Outcome**: 50%+ latency reduction
**Complexity**: Medium-High
**Prerequisites**: ✅ All met (caching operational, system stable)

**Rationale**:
1. **Foundation Ready**: Cache system operational, benefits compound with DB optimization
2. **High Impact**: Database queries often the biggest bottleneck
3. **Measurable**: Clear before/after metrics
4. **Roadmap Priority**: P0 task from original plan

---

## 📋 SESSION 15 TASK BREAKDOWN

### Phase 1: Query Profiling (30-45 min)

**Objectives**:
- Identify slow queries in behavior_engine.py
- Profile database access patterns
- Measure current baseline latencies

**Actions**:
1. Add query timing instrumentation
2. Run 10-minute profiling session
3. Identify top 5 slowest queries
4. Document N+1 query patterns

**Expected Findings**:
- Message history queries (likely slow)
- Bot profile queries (multiple calls)
- Stance/holding lookups
- Chat selection queries

---

### Phase 2: Index Optimization (30-45 min)

**Objectives**:
- Add missing database indexes
- Optimize existing indexes
- Verify index usage

**Actions**:
1. Analyze query patterns from Phase 1
2. Design optimal indexes:
   - `messages(chat_db_id, created_at)` - History queries
   - `messages(bot_id, created_at)` - Bot message tracking
   - `bot_stances(bot_id)` - Stance lookups
   - `bot_holdings(bot_id)` - Holding lookups
3. Create Alembic migration
4. Apply migration
5. Verify performance improvement

**Expected Impact**: 30-50% query time reduction

---

### Phase 3: N+1 Query Elimination (45-60 min)

**Objectives**:
- Eliminate repeated queries in loops
- Implement query batching
- Use eager loading where appropriate

**Common Patterns to Fix**:
```python
# BEFORE (N+1 problem)
for bot in bots:
    stances = db.query(BotStance).filter_by(bot_id=bot.id).all()  # N queries

# AFTER (Single query)
bot_ids = [b.id for b in bots]
all_stances = db.query(BotStance).filter(BotStance.bot_id.in_(bot_ids)).all()
stances_by_bot = group_by(all_stances, lambda s: s.bot_id)
```

**Target Areas**:
- Bot selection logic
- Message history fetching
- Stance/holding data loading

**Expected Impact**: 20-40% fewer database calls

---

### Phase 4: Validation & Measurement (15-30 min)

**Objectives**:
- Measure performance improvements
- Compare before/after metrics
- Document findings

**Actions**:
1. Run 10-minute load test
2. Compare with baseline (if available)
3. Generate performance report
4. Commit optimizations

**Success Criteria**:
- ✅ 50%+ latency reduction
- ✅ Fewer total queries
- ✅ Zero new errors
- ✅ System stable

---

## 🔧 TECHNICAL APPROACH

### Tools & Methods

1. **Query Profiling**:
   ```python
   import time
   start = time.time()
   result = db.query(...)
   duration = time.time() - start
   logger.info(f"Query took {duration:.3f}s")
   ```

2. **Index Creation** (Alembic):
   ```python
   def upgrade():
       op.create_index(
           'ix_messages_chat_created',
           'messages',
           ['chat_db_id', 'created_at']
       )
   ```

3. **N+1 Detection**:
   - Enable SQLAlchemy query logging
   - Count queries per operation
   - Identify repeated patterns

---

## 📊 EXPECTED METRICS

### Before Optimization (Current)
- Average message generation: ~10-15s
- Database queries per message: 15-20
- Cache hit rate: Unknown (need measurement)

### After Optimization (Target)
- Average message generation: ~5-8s (50% reduction)
- Database queries per message: 8-12 (40% reduction)
- Cache hit rate: Measured and documented

---

## 🚨 RISK MITIGATION

### Potential Issues

1. **Index Size**: Too many indexes slow writes
   - **Mitigation**: Only essential indexes, measure impact

2. **Complex Query Refactoring**: Breaking changes
   - **Mitigation**: Test thoroughly, git commit after each change

3. **SQLite Limitations**: Limited concurrent writes
   - **Mitigation**: Document as PostgreSQL migration motivation

4. **Cache Coherency**: Stale data after writes
   - **Mitigation**: Use existing cache invalidation (already working)

---

## 📝 DELIVERABLES

**Code**:
- Query profiling instrumentation
- New database indexes (via Alembic migration)
- N+1 query eliminations
- Performance measurement script

**Documentation**:
- Query profiling results
- Before/after comparison
- Index design rationale
- Performance report

**Commits**:
- Profiling infrastructure
- Index migration
- Query optimizations
- Performance validation

---

## 🔄 ALTERNATIVE OPTIONS

### If Time Constrained (1 hour available)

**Quick Win Path**:
1. Add only critical indexes (15 min)
2. Quick validation (10 min)
3. Commit and document (5 min)
4. Defer deep optimization to next session

### If Blocked by Issues

**Fallback Options**:
- **Option A**: Redis L2 Cache Setup (30-45 min)
- **Option B**: Long Performance Test (30-45 min)
- **Option D**: Telegram Reaction API Fix (45-60 min)

---

## ✅ PRE-SESSION CHECKLIST

Before starting Session 15, ensure:
- [ ] Git status clean (current: clean ✅)
- [ ] Latest code pulled (current: up to date ✅)
- [ ] System stable (current: stable ✅)
- [ ] Cache operational (current: L1 active ✅)
- [ ] Documentation reviewed (this doc ✅)

---

## 🎬 SUGGESTED START SEQUENCE

1. **Read SESSION_15_PLAN.md** (this document)
2. **Create TodoList** with Phase 1-4 tasks
3. **Start Phase 1**: Query profiling
4. **Proceed systematically** through phases
5. **Document & commit** after each phase

---

## 💡 SUCCESS DEFINITION

**Session 15 Success Criteria**:
- ✅ 50%+ latency reduction achieved
- ✅ Clear before/after metrics documented
- ✅ No regression in functionality
- ✅ System remains stable
- ✅ Changes committed with explanation

---

**Status**: READY TO START
**Next Action**: Begin Phase 1 (Query Profiling)

---

*Generated: 2025-11-01 18:00 UTC*
*Session 14 completed, Session 15 planned*
*System Status: PRODUCTION READY, optimizations ready to apply*
