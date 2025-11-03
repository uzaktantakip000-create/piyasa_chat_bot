# 🚀 Production Deployment Guide

## Overview

This guide covers deploying **piyasa_chat_bot** to production with Docker Compose, including best practices for scalability, security, and monitoring.

**System Capacity**: 50-200 bots with 4-worker coordination

---

## Prerequisites

### System Requirements

**Minimum** (50 bots):
- CPU: 2 cores
- RAM: 4 GB
- Disk: 20 GB
- Network: 10 Mbps

**Recommended** (100-200 bots):
- CPU: 4 cores
- RAM: 8 GB
- Disk: 50 GB
- Network: 50 Mbps

### Software Requirements

- Docker Engine 20.10+
- Docker Compose 2.0+
- Git

---

## 🏗️ Deployment Steps

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_ORG/piyasa_chat_bot.git
cd piyasa_chat_bot
```

### 2. Configure Environment

Create `.env` file:

```bash
cp .env.example .env
```

**Critical Environment Variables**:

```bash
# ============================================================================
# SECURITY (REQUIRED)
# ============================================================================
API_KEY=<generate-secure-random-key>
TOKEN_ENCRYPTION_KEY=<generate-fernet-key>

# Default admin user
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=<strong-password>
DEFAULT_ADMIN_MFA_SECRET=<optional-totp-secret>
DEFAULT_ADMIN_API_KEY=<generate-secure-random-key>

# ============================================================================
# DATABASE (PRODUCTION)
# ============================================================================
DATABASE_URL=postgresql+psycopg://app:app@db:5432/app

# ============================================================================
# REDIS (PRODUCTION)
# ============================================================================
REDIS_URL=redis://redis:6379/0

# ============================================================================
# LLM PROVIDER (REQUIRED)
# ============================================================================
LLM_PROVIDER=openai  # or: groq, gemini
OPENAI_API_KEY=<your-openai-key>
LLM_MODEL=gpt-4o-mini

# Alternative providers
# GROQ_API_KEY=<your-groq-key>
# GROQ_MODEL=llama-3.3-70b-versatile
# GEMINI_API_KEY=<your-gemini-key>
# GEMINI_MODEL=gemini-1.5-flash

# ============================================================================
# TELEGRAM (REQUIRED)
# ============================================================================
TELEGRAM_API_BASE=https://api.telegram.org
TELEGRAM_TIMEOUT=20

# ============================================================================
# LOGGING
# ============================================================================
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR

# ============================================================================
# WORKER CONFIGURATION
# ============================================================================
WORKER_ID=0  # Managed by docker-compose
TOTAL_WORKERS=4  # 4 workers by default

# ============================================================================
# SHUTDOWN HANDLING
# ============================================================================
SHUTDOWN_TIMEOUT=15  # Graceful shutdown timeout (seconds)

# ============================================================================
# MONITORING
# ============================================================================
DASHBOARD_STREAM_INTERVAL=5  # WebSocket update interval
```

**Generate Secure Keys**:

```bash
# API Key (32 bytes hex)
python -c "import secrets; print(secrets.token_hex(32))"

# Fernet Encryption Key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# TOTP Secret (optional MFA)
python -c "import pyotp; print(pyotp.random_base32())"
```

### 3. Build Images

```bash
docker compose build
```

**Expected Output**:
- `piyasa_api` image (~350 MB with multi-stage build)
- `piyasa_frontend` image (~150 MB)

### 4. Start Services

```bash
docker compose up -d
```

**Services Started**:
- `api` - FastAPI REST API (port 8000)
- `worker-1` to `worker-4` - 4 behavior workers
- `db` - PostgreSQL 16
- `redis` - Redis 7
- `frontend` - React dashboard (port 5173)
- `prometheus` - Metrics collection (port 9090)
- `grafana` - Metrics visualization (port 3000)

### 5. Verify Health

```bash
curl http://localhost:8000/healthz
```

**Expected Response**:

```json
{
  "ok": true,
  "timestamp": "2025-11-03T...",
  "status": "healthy",
  "checks": {
    "database": {"status": "healthy", "message": "Connected"},
    "redis": {"status": "healthy", "message": "Connected"},
    "workers": {"status": "healthy", "message": "X messages in last 5 min"}
  }
}
```

**Status Codes**:
- `200` - System healthy
- `503` - System unhealthy or degraded

### 6. Access Dashboard

```
http://localhost:5173
```

**Default Credentials**:
- Username: `admin`
- Password: (from `.env` DEFAULT_ADMIN_PASSWORD)

---

## 📊 Monitoring

### Grafana Dashboard

```
http://localhost:3000
```

**Default Credentials**:
- Username: `admin`
- Password: `admin`

**Pre-configured Dashboards**:
- Message generation metrics
- Worker utilization
- Database query performance
- Redis cache hit rate
- Error rates

### Prometheus Metrics

```
http://localhost:9090
```

**Key Metrics**:
- `message_generation_total` - Total messages generated
- `message_generation_duration_seconds` - Generation latency
- `telegram_429_count` - Rate limit errors
- `telegram_5xx_count` - Telegram API errors

---

## 🧪 Load Testing

Before production deployment, run load tests to verify capacity:

```bash
# Test with 50 bots for 5 minutes
python scripts/production_load_test.py --bots 50 --duration 300

# Test with 100 bots for 10 minutes
python scripts/production_load_test.py --bots 100 --duration 600

# Test with 200 bots for 15 minutes
python scripts/production_load_test.py --bots 200 --duration 900
```

**Success Criteria**:
- ✅ Throughput >= 0.5 msg/sec
- ✅ Error rate < 1%
- ✅ Average latency < 10s
- ✅ No worker crashes

---

## 🔒 Security Best Practices

### 1. API Security

- ✅ **Authentication**: RBAC with viewer/operator/admin roles
- ✅ **MFA**: TOTP 2FA support (optional)
- ✅ **Session Management**: 12-hour TTL with secure cookies
- ✅ **API Key Rotation**: Automatic on login

### 2. Network Security

```yaml
# docker-compose.override.yml
services:
  api:
    networks:
      - internal
    ports:
      - "127.0.0.1:8000:8000"  # Bind to localhost only

  frontend:
    networks:
      - internal
    ports:
      - "127.0.0.1:5173:5173"  # Bind to localhost only

networks:
  internal:
    driver: bridge
```

### 3. Token Encryption

- ✅ All bot tokens encrypted with Fernet (AES-128)
- ✅ Encryption key stored in `.env` (never commit!)
- ✅ Automatic migration on startup

### 4. Database Security

```bash
# Use strong PostgreSQL password in production
POSTGRES_PASSWORD=<generate-strong-password>
```

---

## 📈 Scaling

### Horizontal Scaling (Workers)

To scale beyond 4 workers, edit `docker-compose.yml`:

```yaml
worker-5:
  build:
    context: .
    dockerfile: Dockerfile.api
  environment:
    - WORKER_ID=4
    - TOTAL_WORKERS=8  # Update all workers
```

**Worker Coordination**:
- Each worker handles `bot_id % TOTAL_WORKERS == WORKER_ID`
- Redis pub/sub for config updates
- Independent failure isolation

### Vertical Scaling (Resources)

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

---

## 🛠️ Maintenance

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f worker-1

# Last 100 lines
docker compose logs --tail=100 api
```

### Restarting Services

```bash
# Restart all workers
docker compose restart worker-1 worker-2 worker-3 worker-4

# Restart API only
docker compose restart api

# Rolling restart (zero downtime)
for worker in worker-1 worker-2 worker-3 worker-4; do
  docker compose restart $worker
  sleep 10
done
```

### Database Backups

```bash
# Backup database
docker compose exec db pg_dump -U app app > backup_$(date +%Y%m%d).sql

# Restore database
docker compose exec -T db psql -U app app < backup_20251103.sql
```

### Database Migrations

```bash
# Check current version
docker compose exec api python -m alembic current

# Apply pending migrations
docker compose exec api python -m alembic upgrade head

# Rollback one migration
docker compose exec api python -m alembic downgrade -1
```

---

## 🚨 Troubleshooting

### Workers Not Generating Messages

**Symptoms**: No new messages in database

**Checks**:
1. Verify `simulation_active` setting is `true`
2. Check at least one bot and chat are enabled
3. Verify bot `active_hours` matches current time
4. Check worker logs for errors

```bash
docker compose logs worker-1 --tail=50
```

### High Error Rate (429 Rate Limits)

**Symptoms**: Telegram 429 errors in logs

**Solution**: Reduce `max_msgs_per_min` setting

```bash
# Via API
curl -X PATCH http://localhost:8000/settings \
  -H "X-API-Key: $API_KEY" \
  -d '{"max_msgs_per_min": 3}'

# Or via dashboard Settings tab
```

### Database Connection Errors

**Symptoms**: "could not connect to server" errors

**Checks**:
1. Verify PostgreSQL is running: `docker compose ps db`
2. Check PostgreSQL logs: `docker compose logs db`
3. Verify health: `docker compose exec db pg_isready -U app`

**Fix**: Restart database

```bash
docker compose restart db
```

### Redis Connection Errors

**Symptoms**: "Error connecting to Redis" warnings

**Checks**:
1. Verify Redis is running: `docker compose ps redis`
2. Test connection: `docker compose exec redis redis-cli ping`

**Fix**: Restart Redis (safe - L2 cache only)

```bash
docker compose restart redis
```

---

## 🔄 Updates & Rollbacks

### Update to Latest Version

```bash
# Pull latest code
git pull origin main

# Rebuild images
docker compose build

# Rolling update (zero downtime)
docker compose up -d --no-deps --build api
for worker in worker-1 worker-2 worker-3 worker-4; do
  docker compose up -d --no-deps --build $worker
  sleep 10
done
```

### Rollback

```bash
# Checkout previous version
git checkout <previous-commit>

# Rebuild and restart
docker compose build
docker compose up -d
```

---

## 📋 Production Checklist

Before going live:

- [ ] ✅ Strong passwords in `.env`
- [ ] ✅ TOKEN_ENCRYPTION_KEY generated
- [ ] ✅ MFA enabled for admin user
- [ ] ✅ Health check passing (200 OK)
- [ ] ✅ Load test completed successfully
- [ ] ✅ Monitoring dashboards configured
- [ ] ✅ Database backups automated
- [ ] ✅ Log aggregation configured
- [ ] ✅ Alerting rules configured
- [ ] ✅ Disaster recovery plan documented
- [ ] ✅ Telegram bot tokens encrypted
- [ ] ✅ API bound to internal network only
- [ ] ✅ SSL/TLS termination configured (if exposed)

---

## 📞 Support

**Documentation**:
- [CLAUDE.md](../CLAUDE.md) - Development guide
- [ROADMAP_MEMORY.md](../ROADMAP_MEMORY.md) - Project roadmap
- [README.md](../README.md) - User guide

**Issues**: https://github.com/YOUR_ORG/piyasa_chat_bot/issues

---

*Last Updated: 2025-11-03 | Session 26: Production Readiness*
