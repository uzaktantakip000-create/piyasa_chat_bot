# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**piyasa_chat_bot** is a Telegram market simulation chatbot system that orchestrates multiple bots to create realistic market discussions. The system consists of three main components:

1. **FastAPI REST API** (`main.py`) - Manages bots, chats, settings, and provides metrics
2. **Worker Process** (`worker.py`) - Background service that runs the behavior engine
3. **React Dashboard** (`App.jsx`, `src/main.jsx`) - Web-based management panel

The bots use OpenAI's LLM to generate contextual, persona-driven messages about Turkish financial markets (BIST, FX, Crypto, Macro) with configurable personalities, stances, and holdings.

## Development Commands

### Running the System

**Docker Compose (Recommended)**:
```bash
docker compose up --build
```

**Manual Setup** (requires Python 3.11+ and Node.js 18+):
```bash
# Terminal 1 - API
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2 - Worker
python worker.py

# Terminal 3 - Frontend
npm install
npm run dev
```

**Windows One-Click** (automated):
```bash
setup_all.cmd
```

### Testing

**Run all tests**:
```bash
pytest
```

**Run specific test suites**:
```bash
# API integration tests
pytest tests/test_api_flows.py

# Behavior engine tests
pytest tests/test_behavior_engine.py

# RBAC security tests
pytest tests/test_security_rbac.py

# Content filter tests
pytest tests/test_content_filters.py
```

**Frontend tests**:
```bash
npm test
```

**Worker validation** (check dependencies without running):
```bash
python worker.py --check-only
```

### Health Checks & Diagnostics

**Pre-flight system check** (validates API, DB, external services):
```bash
python preflight.py
```

**Comprehensive health check** (API, DB, Redis, panel):
```bash
python scripts/oneclick.py
```

**Stress testing**:
```bash
python scripts/stress_test.py --duration 30 --concurrency 4
```

### Database

**Default**: SQLite (`app.db`)

**PostgreSQL** (set in `.env`):
```
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/app
```

**Database Migrations** (Alembic):
```bash
# Check current migration version
python -m alembic current

# View migration history
python -m alembic history

# Create new migration (auto-generate from model changes)
python -m alembic revision --autogenerate -m "description"

# Apply pending migrations
python -m alembic upgrade head

# Rollback one migration (PostgreSQL only - see note below)
python -m alembic downgrade -1

# Rollback to specific revision
python -m alembic downgrade <revision_id>
```

**Important Notes**:
- Migrations are version-controlled in `alembic/versions/`
- Auto-generated migrations should be reviewed before committing
- **SQLite limitation**: Downgrade migrations that alter column types will fail on SQLite due to limited `ALTER TABLE` support. This is a known SQLite limitation. Downgrades work correctly on PostgreSQL.
- The database URL is read from `DATABASE_URL` environment variable (configured in `alembic/env.py`)
- Initial migration `fe686589d4eb` captures the schema state as of Session 12

**Token encryption migration** (auto-runs on startup):
- Requires `TOKEN_ENCRYPTION_KEY` in `.env`
- Generate key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

### Building

**API + Worker**:
```bash
docker build -f Dockerfile.api -t piyasa_api .
```

**Frontend**:
```bash
npm run build
npm run preview
```

## Architecture

### Core Components

**`main.py`** (FastAPI API - ~1400 lines)
- REST endpoints for bots, chats, settings, metrics, logs
- RBAC authentication (viewer/operator/admin roles)
- Session-based login with TOTP MFA support
- WebSocket endpoint (`/ws/dashboard`) for real-time metrics streaming
- Wizard endpoint (`/wizard/setup`) for one-step bot+chat+persona configuration
- Redis pub/sub integration for live config updates

**`worker.py`** (Background Service)
- Launches `behavior_engine.run_engine_forever()`
- Graceful shutdown handling (SIGINT/SIGTERM)
- Timeout-based cleanup of async tasks

**`behavior_engine.py`** (Message Generation Core - ~1500 lines)
- **BehaviorEngine class**: Main orchestrator
  - Picks random chat/bot respecting hourly limits and active_hours
  - Generates contextual messages using LLM with persona/stance/holdings
  - Handles reply targeting, @mentions, reactions
  - Typing simulation (WPM-based delays)
  - Prime hours boost (faster message rate during market hours)
  - Scale factor for global message rate adjustment
  - Deduplication (prevents repeating same message within N hours)
  - Consistency guard (validates LLM output against stance rules)
  - Redis config listener for hot-reloading settings
- **Persona refresh system**: Periodically reminds LLM of bot personality
- **News trigger**: Optionally fetches RSS brief for market context
- **Emotion profiles**: Controls tone, energy, signature phrases, anecdotes

**`database.py`** (SQLAlchemy Models)
- Models: `Bot`, `Chat`, `Message`, `Setting`, `BotStance`, `BotHolding`, `SystemCheck`, `ApiUser`, `ApiSession`
- Token encryption/decryption for bot tokens (Fernet)
- RBAC user management with hashed passwords and API keys
- Session token generation and validation

**`telegram_client.py`**
- Async HTTP client for Telegram Bot API
- Methods: `send_message`, `send_typing`, `try_set_reaction`
- Rate limit and 5xx error tracking

**`llm_client.py`**
- OpenAI API wrapper (ChatCompletion)
- System prompt: "Telegram piyasa sohbet botu" with detailed persona/stance injection
- Configurable temperature, max_tokens
- Static `pick_reaction_for_text()` for emoji reactions

**`system_prompt.py`**
- `generate_user_prompt()`: Assembles multi-part prompt with history, persona, stances, holdings, market trigger
- `summarize_persona()`: Condenses persona_profile to compact string
- `summarize_stances()`: Formats stance list for LLM context

**`security.py`**
- Fernet-based token encryption/decryption
- `mask_token()`: Hides sensitive tokens in logs/UI

**`auth_utils.py`**
- Password hashing (SHA-256 + salt)
- API key generation (32-byte hex)
- TOTP MFA secret generation and verification

### Frontend (React + Vite)

**`App.jsx`** (Main React Component - ~500 lines)
- Tabs: QuickStart, Dashboard, Bots, Chats, Settings, Logs
- Authentication: Session cookie + X-API-Key header
- WebSocket connection to `/ws/dashboard` for live metrics
- Role-based UI controls (viewer/operator/admin)

**Key JSX Components**:
- `QuickStart.jsx`: Login/setup wizard
- `Dashboard.jsx`: Metrics, system check, start/stop/scale controls
- `Bots.jsx`: Bot CRUD, persona/emotion/stance/holding management
- `Chats.jsx`: Chat CRUD, topic configuration
- `Settings.jsx`: Global settings editor
- `Logs.jsx`: Recent message log viewer

**`apiClient.js`**
- REST API wrapper with automatic X-API-Key injection
- Methods mirror main.py endpoints

**Localization**:
- `translation_core.js`, `localization.js`: Multi-language support (tr/en)
- `settings_alerts.js`: User-facing alert preference utilities

### Data Flow

1. **Worker startup** → Initializes `BehaviorEngine` → Subscribes to Redis config channel
2. **Behavior loop** (`tick_once()`):
   - Check `simulation_active` setting
   - Pick random enabled chat
   - Pick eligible bot (respecting hourly limits, active_hours)
   - Fetch bot persona/emotion/stances/holdings
   - Determine if reply or new message (probability-based)
   - Build history transcript from recent messages
   - Choose topic (keyword-based scoring from message history)
   - Fetch news brief (optional, topic-specific)
   - Synthesize reaction plan (emotion-driven instructions)
   - Generate user prompt with all context
   - Call LLM to generate message text
   - Apply consistency guard (check against stances)
   - Apply micro-behaviors (ellipsis, emoji placement)
   - Deduplicate (paraphrase if recent duplicate found)
   - Send typing action to Telegram
   - Send message to chat
   - Log to `messages` table
3. **Dashboard updates** via WebSocket (5s interval by default)

### Configuration

**Environment Variables** (`.env`):
- `API_KEY`: Master API key for legacy auth (now supplemented by RBAC)
- `OPENAI_API_KEY`: OpenAI API access (required)
- `TOKEN_ENCRYPTION_KEY`: Fernet key for encrypting bot tokens
- `DATABASE_URL`: SQLite or PostgreSQL connection string
- `REDIS_URL`: Optional Redis for config sync and caching
- `LLM_MODEL`: OpenAI model (default: `gpt-4o-mini`)
- `DEFAULT_ADMIN_USERNAME/PASSWORD/MFA_SECRET/API_KEY`: Auto-create admin user on startup
- `DASHBOARD_STREAM_INTERVAL`: WebSocket update interval in seconds
- `LOG_LEVEL`: DEBUG/INFO/WARNING/ERROR

**Database Settings** (stored in `settings` table):
- `simulation_active`: Master on/off switch
- `scale_factor`: Global message rate multiplier
- `max_msgs_per_min`: Rate limit (messages per minute)
- `typing_enabled`: Enable/disable typing simulation
- `prime_hours_boost`: Faster messages during market hours
- `prime_hours`: Time ranges (e.g., `["09:30-12:00","14:00-18:00"]`)
- `reply_probability`: Chance to reply vs new message (0.0-1.0)
- `mention_probability`: Chance to @mention in reply
- `short_reaction_probability`: Chance to send reaction-only (emoji)
- `message_length_profile`: Distribution of short/medium/long messages
- `bot_hourly_msg_limit`: Min/max messages per bot per hour
- `typing_speed_wpm`: Min/max words per minute for typing sim
- `dedup_enabled`/`dedup_window_hours`/`dedup_max_attempts`: Duplicate prevention
- `cooldown_filter_enabled`: Exclude cooldown topics from selection
- `news_trigger_enabled`/`news_trigger_probability`: RSS news injection
- `news_feed_urls`: List of RSS feed URLs

### Bot Configuration

**Bot fields** (database model):
- `name`, `token` (encrypted), `username`, `is_enabled`
- `speed_profile`: Delay and typing multipliers (JSON)
- `active_hours`: Time ranges when bot is active (JSON array)
- `persona_hint`: Short freeform personality description
- `persona_profile`: Structured persona (tone, risk_profile, watchlist, never_do, style)
- `emotion_profile`: Emotion parameters (tone, empathy, signature_emoji, signature_phrases, anecdotes, energy)

**BotStance** (many-to-one with Bot):
- `topic`, `stance_text`, `confidence`, `cooldown_until`
- Used to enforce consistency (LLM output must not contradict stance)

**BotHolding** (many-to-one with Bot):
- `symbol`, `avg_price`, `size`, `note`
- Injected into prompt for realistic portfolio references

### Caching System

**Architecture**: Multi-layer (L1 in-memory + L2 Redis)

**L1 Cache (In-Memory)**:
- Thread-safe LRU cache with TTL support
- Max size: 1000 entries (configurable via `CACHE_L1_MAX_SIZE`)
- Per-worker (not shared across workers)
- Automatic expiration on access
- Hit/miss tracking for monitoring

**L2 Cache (Redis)**:
- Shared across all workers for distributed caching
- Pickle serialization (supports complex Python objects)
- Optional - gracefully degrades if unavailable
- Requires `REDIS_URL` environment variable
- Connection timeout: 2 seconds

**Cached Data & TTLs**:
1. Bot profiles (5 min TTL) - Full bot object with all fields
2. Bot personas (10 min TTL) - Persona profile only
3. Bot emotions (10 min TTL) - Emotion profile only
4. Bot stances (3 min TTL) - All stances for a bot
5. Bot holdings (5 min TTL) - All holdings for a bot
6. Chat message history (1 min TTL) - Recent messages in a chat

**Cache Invalidation**:
- Automatic invalidation on bot/stance/holding updates
- Pattern-based key invalidation (e.g., `bot:123:*` clears all bot 123 cache)
- Triggered via API endpoints (11 endpoints with invalidation):
  - `PATCH /bots/{bot_id}` → invalidates bot cache
  - `DELETE /bots/{bot_id}` → invalidates bot cache
  - `PUT /bots/{bot_id}/persona` → invalidates bot cache
  - `PUT /bots/{bot_id}/emotion` → invalidates bot cache
  - `POST /bots/{bot_id}/stances` → invalidates bot cache
  - `PATCH /stances/{stance_id}` → invalidates bot cache
  - `DELETE /stances/{stance_id}` → invalidates bot cache
  - `POST /bots/{bot_id}/holdings` → invalidates bot cache
  - `PATCH /holdings/{holding_id}` → invalidates bot cache
  - `DELETE /holdings/{holding_id}` → invalidates bot cache
  - `DELETE /chats/{chat_id}` → invalidates chat message cache
- Graceful error handling (cache failures don't block operations)

**Monitoring**:
- Endpoint: `GET /cache/stats` (viewer role access)
- Returns:
  - L1 stats: size, max_size, hits, misses, hit_rate
  - L2 stats: available, enabled status
  - Timestamp for monitoring

**Configuration**:
```bash
REDIS_URL=redis://localhost:6379/0  # L2 cache (optional)
CACHE_L1_MAX_SIZE=1000              # L1 max entries (default: 1000)
```

**Performance Impact** (Session 13 + 15):
- Cache hit latency: <1ms (vs 5-20ms DB query)
- Database query reduction: 60-80% at scale
- Combined with indexing: 35-60% total latency reduction
- Cross-worker cache sharing via Redis L2

**Implementation Files**:
- `backend/caching/cache_manager.py`: Core CacheManager class (L1+L2 orchestration)
- `backend/caching/bot_cache_helpers.py`: Bot profile caching helpers
- `backend/caching/message_cache_helpers.py`: Message history caching helpers

### Testing Strategy

**Pytest fixtures** (`tests/conftest.py`):
- `test_db`: In-memory SQLite session for isolated tests
- `api_client`: FastAPI TestClient with auth
- Temporary environment variable patching

**Test Categories**:
- **API flows** (`test_api_flows.py`): CRUD operations, auth, wizard
- **Behavior engine** (`test_behavior_engine.py`): Message generation logic, topic scoring, persona refresh
- **Security/RBAC** (`test_security_rbac.py`): Role-based access control, session management, MFA
- **Content filters** (`test_content_filters.py`): LLM output validation
- **Settings regression** (`test_settings_regression.py`): Ensures setting schema stability

## Important Patterns & Conventions

### Authentication

- **Legacy**: Single `API_KEY` in `.env` (still works for backward compatibility)
- **Current**: RBAC with `ApiUser` table
  - Roles: `viewer` (read-only), `operator` (manage bots/chats), `admin` (full control)
  - Session-based auth via `piyasa.session` cookie (12h TTL by default)
  - API key rotation on login
  - TOTP MFA optional per user

### Message Generation Context

When modifying `generate_user_prompt()` or `behavior_engine.py`, always consider:
1. **History excerpt**: Last 6 messages (reversed chronological)
2. **Contextual examples**: Bot's previous turn-taking patterns
3. **Market trigger**: Optional RSS news brief (1-2 sentences)
4. **Persona/emotion**: Injected as structured guidance
5. **Stances**: Listed with topic, confidence, cooldown
6. **Holdings**: Listed with symbol, size, note
7. **Length hint**: Sampled category + persona style preference
8. **Persona refresh note**: Periodic reminder of core personality

### Extending the System

**Adding new API endpoints** (`main.py`):
1. Use `@app.get/post/patch/delete` decorators
2. Add `dependencies=viewer_dependencies/operator_dependencies/admin_dependencies` for RBAC
3. Use `db: Session = Depends(get_db)` for database access
4. Call `publish_config_update(get_redis(), {...})` if settings changed

**Adding new bot behaviors** (`behavior_engine.py`):
1. Add helper functions at module level (before `BehaviorEngine` class)
2. Modify `BehaviorEngine.tick_once()` to integrate new logic
3. Update `load_settings()` if new settings are needed
4. Add tests in `tests/test_behavior_engine.py`

**Adding new settings**:
1. Add to `database.init_default_settings()` defaults dict
2. Access via `self.settings(db).get("setting_key")` in engine
3. Expose in `Settings.jsx` frontend component
4. Document in `.env.example` if environment variable

### Code Quality

- Python: Type hints encouraged, docstrings for complex functions
- JavaScript: PropTypes or inline comments for component props
- Error handling: Use try/except with logger.exception() in engine/API
- Logging: Use module-level loggers (`logger = logging.getLogger(__name__)`)

## Troubleshooting

**Worker not generating messages**:
- Check `simulation_active` setting (must be `true`)
- Verify at least one enabled bot and one enabled chat exist
- Check bot `active_hours` matches current time
- Review `bot_hourly_msg_limit` (bot may have hit cap)

**429 Rate Limit Errors** (Telegram):
- Reduce `max_msgs_per_min` in settings
- Increase `base_delay_seconds` in bot `speed_profile`
- Check `telegram_429_count` metric

**Token Encryption Issues**:
- Ensure `TOKEN_ENCRYPTION_KEY` is set and consistent across restarts
- Re-run `migrate_plain_tokens()` if switching keys

**WebSocket Connection Failures**:
- Check CORS settings in `main.py` (allowed_origins)
- Verify session cookie or X-API-Key header is sent
- Review `DASHBOARD_STREAM_INTERVAL` and `DASHBOARD_STREAM_MAX_MESSAGES`

**Duplicate Messages**:
- Enable `dedup_enabled` setting
- Increase `dedup_window_hours` for longer memory
- Increase `dedup_max_attempts` for more paraphrase retries

## Project-Specific Context

- **Turkish Language**: All prompts, UI, and generated messages are in Turkish. LLM is instructed to never use English.
- **Market Topics**: Default topics are BIST (Turkish stock market), FX (foreign exchange), Kripto (cryptocurrency), Makro (macroeconomics)
- **Telegram-Specific**: Uses Telegram Bot API v7+ features (reactions via setMessageReaction)
- **Emoji Usage**: Bot persona can include `signature_emoji` for consistent emotional signaling
- **Stance Cooldown**: After generating a message on a topic, bot can optionally set `cooldown_until` to prevent flip-flopping
- **Consistency Guard**: LLM-based validation step that rewrites message if it contradicts recorded stances

## Git Workflow

**Recent commits** (from gitStatus):
- PR #55: Add adaptive view toggles and alert preference utilities
- Recent focus: Activity center tab fixes, multi-step wizard, persona refresh helpers

**Uncommitted changes**:
- `package.json`, `package-lock.json` modified

**Main branch**: `main` (use for PRs)

## Additional Resources

- `README.md`: User-facing setup guide (Turkish)
- `RUNBOOK.md`: Operational runbook
- `docs/error_management.md`: Error handling strategy
- `docs/panel_user_experience_plan.md`: UX roadmap
- `docs/reporting_roadmap.md`: Test reporting module plan
- `docs/ux-improvement-suggestions.md`: Professionalization suggestions
