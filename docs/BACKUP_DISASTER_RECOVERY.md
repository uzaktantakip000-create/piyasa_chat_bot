# Database Backup & Disaster Recovery

**Version**: 1.0
**Last Updated**: 2025-11-03
**Status**: Production Ready ✅

---

## Table of Contents

1. [Overview](#overview)
2. [Backup Strategy](#backup-strategy)
3. [Automated Backups](#automated-backups)
4. [Manual Backups](#manual-backups)
5. [Restore Procedures](#restore-procedures)
6. [Disaster Recovery](#disaster-recovery)
7. [Monitoring & Verification](#monitoring--verification)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Piyasa Chat Bot backup system provides **automated, encrypted, and versioned** database backups with intelligent rotation policies. Backups are compressed (gzip) and organized by frequency:

- **Daily**: Last 7 days
- **Weekly**: Last 4 weeks (Sundays)
- **Monthly**: Last 12 months (1st of month)

**Supported Databases**:
- ✅ SQLite (development/small deployments)
- ✅ PostgreSQL (production)

---

## Backup Strategy

### Backup Types

| Type | Schedule | Retention | Trigger | Size Est. |
|------|----------|-----------|---------|-----------|
| **Daily** | 2:00 AM | 7 days | Every day | ~50-500 KB |
| **Weekly** | 2:00 AM Sunday | 4 weeks | Sundays | ~50-500 KB |
| **Monthly** | 2:00 AM 1st | 12 months | 1st of month | ~50-500 KB |

### Storage Requirements

**Estimated storage** (with default retention):
- Daily: 7 backups × 500 KB = **3.5 MB**
- Weekly: 4 backups × 500 KB = **2 MB**
- Monthly: 12 backups × 500 KB = **6 MB**
- **Total**: ~12 MB (for 50 bots, ~500 messages)

**At scale** (200 bots, 10,000 messages):
- Per backup: ~2-5 MB compressed
- Total storage: ~50-100 MB

---

## Automated Backups

### Linux/macOS Setup (Cron)

**One-command setup**:
```bash
bash scripts/setup_backup_cron.sh
```

**Manual setup**:
```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 2 AM):
0 2 * * * cd /path/to/piyasa_chat_bot && python scripts/backup_database.py >> logs/backup.log 2>&1
```

**Verify cron job**:
```bash
crontab -l | grep backup
```

---

### Windows Setup (Task Scheduler)

**One-command setup** (Run PowerShell as Administrator):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_backup_windows.ps1
```

**Manual setup**:
1. Open **Task Scheduler**
2. Create Basic Task: `PiyasaChatBot-DatabaseBackup`
3. Trigger: Daily at 2:00 AM
4. Action: Run `python scripts\backup_database.py`
5. Working directory: Project root

**Verify task**:
```powershell
Get-ScheduledTask -TaskName "PiyasaChatBot-DatabaseBackup"
```

---

### Docker Setup

**Add to docker-compose.yml**:
```yaml
services:
  backup:
    image: piyasa_chat_bot-api
    command: python scripts/backup_database.py --backup-dir /backups
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/piyasa
    volumes:
      - ./backups:/backups
      - ./app.db:/app/app.db  # If using SQLite
    restart: "no"
```

**Schedule with cron** (on host):
```bash
# Run backup container daily at 2 AM
0 2 * * * docker compose run --rm backup >> logs/backup.log 2>&1
```

**Or use bash script**:
```bash
bash scripts/docker_backup.sh daily
```

---

## Manual Backups

### Basic Usage

```bash
# Auto-detect backup type (daily/weekly/monthly)
python scripts/backup_database.py

# Force specific type
python scripts/backup_database.py --type daily
python scripts/backup_database.py --type weekly
python scripts/backup_database.py --type monthly

# Custom backup directory
python scripts/backup_database.py --backup-dir /mnt/backups

# Dry run (simulate without changes)
python scripts/backup_database.py --dry-run
```

### Environment Variables

```bash
# Database connection
export DATABASE_URL="postgresql://user:password@localhost:5432/piyasa"
# or
export DATABASE_URL="sqlite:///./app.db"

# Backup configuration
export BACKUP_DIR="./backups"
export BACKUP_RETENTION_DAYS=7
export BACKUP_RETENTION_WEEKS=4
export BACKUP_RETENTION_MONTHS=12
```

### Backup Output

```
backups/
├── daily/
│   ├── backup_daily_20251103_020000.sql.gz
│   ├── backup_daily_20251104_020000.sql.gz
│   └── ...
├── weekly/
│   ├── backup_weekly_20251027_020000.sql.gz
│   └── ...
└── monthly/
    ├── backup_monthly_20251001_020000.sql.gz
    └── ...
```

---

## Restore Procedures

### ⚠️ WARNING

**Database restore will OVERWRITE existing data!**
Always create a backup before restoring.

### Basic Restore

```bash
# Dry run (test without changes)
python scripts/restore_database.py backups/daily/backup_daily_20251103_020000.sql.gz --dry-run

# Actual restore (interactive confirmation)
python scripts/restore_database.py backups/daily/backup_daily_20251103_020000.sql.gz

# Skip confirmation (use with caution!)
python scripts/restore_database.py backups/daily/backup_daily_20251103_020000.sql.gz --yes
```

### Restore to Different Database

```bash
# Restore to staging database
python scripts/restore_database.py \
    backups/daily/backup_daily_20251103_020000.sql.gz \
    --database-url "postgresql://user:pass@staging-db:5432/piyasa_staging"
```

### Restore Process

1. **Validation**: Script checks if backup file exists
2. **Decompression**: Extracts `.sql.gz` to `.sql` (temporary)
3. **Safety Backup**: Existing database backed up to `.db.bak` (SQLite) or equivalent
4. **Restore**: SQL dump executed against target database
5. **Cleanup**: Temporary files removed
6. **Verification**: Connection test

---

## Disaster Recovery

### Scenario 1: Database Corruption

**Symptoms**:
- Database file corrupted
- "database disk image is malformed"
- Unable to query data

**Recovery Steps**:
```bash
# 1. Stop all services
docker compose down
# or
systemctl stop piyasa_worker piyasa_api

# 2. Move corrupted database
mv app.db app.db.corrupted

# 3. Restore from most recent backup
python scripts/restore_database.py backups/daily/backup_daily_YYYYMMDD_HHMMSS.sql.gz --yes

# 4. Restart services
docker compose up -d
# or
systemctl start piyasa_api piyasa_worker

# 5. Verify system health
curl http://localhost:8000/healthz
```

---

### Scenario 2: Accidental Data Deletion

**Symptoms**:
- Bots/chats/messages accidentally deleted
- Need to recover specific data

**Recovery Steps**:
```bash
# 1. Identify when deletion occurred
ls -lht backups/daily/

# 2. Restore to separate database for recovery
python scripts/restore_database.py \
    backups/daily/backup_daily_YYYYMMDD_HHMMSS.sql.gz \
    --database-url "sqlite:///./recovery.db" \
    --yes

# 3. Extract specific data using SQL
sqlite3 recovery.db "SELECT * FROM bots WHERE id = 123;"

# 4. Manually re-add data via API or SQL
curl -X POST http://localhost:8000/bots -d '...'

# 5. Cleanup
rm recovery.db
```

---

### Scenario 3: Complete System Loss

**Recovery Steps**:
```bash
# 1. Clone repository
git clone https://github.com/your-org/piyasa_chat_bot.git
cd piyasa_chat_bot

# 2. Install dependencies
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 3. Copy .env from backup
# (Ensure TOKEN_ENCRYPTION_KEY matches original!)

# 4. Restore database from offsite backup
python scripts/restore_database.py /mnt/offsite-backup/backup_daily_YYYYMMDD.sql.gz --yes

# 5. Start services
docker compose up -d

# 6. Verify
curl http://localhost:8000/healthz
```

**Critical**: `TOKEN_ENCRYPTION_KEY` must match original, or bot tokens cannot be decrypted!

---

## Monitoring & Verification

### Backup Logs

```bash
# View backup logs
tail -f logs/backup.log

# Check for errors
grep ERROR logs/backup.log

# Check backup sizes
du -sh backups/*/*.sql.gz
```

### Automated Verification

```bash
# Test backup integrity (decompress + check)
gunzip -t backups/daily/backup_daily_20251103_020000.sql.gz

# Verify SQL dump structure
gunzip -c backups/daily/backup_daily_20251103_020000.sql.gz | head -50
```

### Health Check Integration

**Add to healthz endpoint** (optional):
```python
# Check if recent backup exists
latest_backup = max(Path("backups/daily").glob("*.sql.gz"), default=None)
if latest_backup:
    age_hours = (datetime.now() - datetime.fromtimestamp(latest_backup.stat().st_mtime)).total_seconds() / 3600
    if age_hours > 26:  # No backup in last 26 hours
        return {"status": "degraded", "backup": "stale"}
```

---

### Alerting

**Email on backup failure** (add to script):
```bash
#!/bin/bash
python scripts/backup_database.py || {
    echo "Backup failed at $(date)" | mail -s "Piyasa Backup FAILED" admin@example.com
    exit 1
}
```

**Prometheus metric**:
```python
# In backup_database.py
backup_last_success_timestamp = Gauge('backup_last_success', 'Last successful backup timestamp')
backup_last_success_timestamp.set(time.time())
```

---

## Troubleshooting

### Issue: "sqlite3 command not found" (Linux)

**Solution**: Script uses Python's sqlite3 module, no external command needed.

If issues persist:
```bash
# Verify Python has sqlite3
python -c "import sqlite3; print(sqlite3.version)"
```

---

### Issue: "Permission denied" writing backups

**Solution**:
```bash
# Check backup directory permissions
ls -ld backups/

# Fix permissions
chmod 755 backups/
chmod 755 backups/{daily,weekly,monthly}
```

---

### Issue: Backup size too large

**Solutions**:
1. **Vacuum database** (SQLite):
   ```bash
   sqlite3 app.db "VACUUM;"
   ```

2. **Truncate old messages**:
   ```sql
   DELETE FROM messages WHERE created_at < datetime('now', '-90 days');
   ```

3. **Increase retention** only for critical backups:
   ```bash
   python scripts/backup_database.py --retention-days 3
   ```

---

### Issue: Restore fails with "table already exists"

**Solution**: Database must be empty before restore.

**SQLite**:
```bash
mv app.db app.db.old
python scripts/restore_database.py backup.sql.gz --yes
```

**PostgreSQL**:
```bash
psql -U postgres -c "DROP DATABASE piyasa; CREATE DATABASE piyasa;"
python scripts/restore_database.py backup.sql.gz --yes
```

---

### Issue: Disk space full

**Emergency cleanup**:
```bash
# Remove old daily backups (keep last 3)
cd backups/daily/
ls -t | tail -n +4 | xargs rm

# Remove weekly backups older than 2 weeks
find backups/weekly/ -mtime +14 -delete

# Check space
df -h backups/
```

---

## Best Practices

### 1. **Offsite Backups**

**Upload to cloud storage**:
```bash
# AWS S3
aws s3 sync backups/ s3://your-bucket/piyasa-backups/

# Google Cloud Storage
gsutil -m rsync -r backups/ gs://your-bucket/piyasa-backups/

# Backblaze B2
b2 sync --replaceNewer backups/ b2://your-bucket/piyasa-backups/
```

**Schedule offsite sync**:
```bash
# Daily at 3 AM (after local backup)
0 3 * * * aws s3 sync backups/ s3://your-bucket/piyasa-backups/ >> logs/sync.log 2>&1
```

---

### 2. **Test Restores Regularly**

```bash
# Monthly test restore to staging
0 0 1 * * python scripts/restore_database.py \
    backups/monthly/latest.sql.gz \
    --database-url "postgresql://user:pass@staging-db/piyasa_test" \
    --yes >> logs/test-restore.log 2>&1
```

---

### 3. **Encrypt Backups**

**GPG encryption**:
```bash
# Encrypt backup
gpg --symmetric --cipher-algo AES256 backup.sql.gz

# Decrypt
gpg backup.sql.gz.gpg
```

---

### 4. **Monitor Backup Size Trends**

```bash
# Track backup size over time
echo "$(date),$(du -sb backups/ | cut -f1)" >> backup_size_history.csv
```

---

### 5. **Document Recovery RTO/RPO**

**Recovery Time Objective (RTO)**: 15 minutes
**Recovery Point Objective (RPO)**: 24 hours (daily backup)

**Faster RPO** (6 hours):
```bash
# Run backup every 6 hours
0 */6 * * * python scripts/backup_database.py --type daily
```

---

## Security Considerations

1. **Backup Encryption**:
   - Backups contain bot tokens (encrypted with TOKEN_ENCRYPTION_KEY)
   - Use encrypted storage or encrypt backups with GPG

2. **Access Control**:
   - Restrict backup directory: `chmod 700 backups/`
   - Use separate service account for backups

3. **KEY MANAGEMENT**:
   - `TOKEN_ENCRYPTION_KEY` must be backed up separately
   - Store in password manager (1Password, LastPass, etc.)
   - Never commit to Git

4. **Offsite Backups**:
   - Use encrypted transport (S3 with SSE, HTTPS)
   - Enable versioning on cloud storage

---

## Appendix: File Sizes

**Typical Backup Sizes**:
| Database Content | Uncompressed | Compressed (gzip) | Ratio |
|------------------|--------------|-------------------|-------|
| 10 bots, 100 msgs | 50 KB | 8 KB | 6.25:1 |
| 50 bots, 1K msgs | 500 KB | 80 KB | 6.25:1 |
| 200 bots, 10K msgs | 5 MB | 800 KB | 6.25:1 |

**Compression**: gzip achieves ~6-7x compression on SQL dumps.

---

## Support & Contact

For backup/restore issues:
1. Check logs: `logs/backup.log`
2. Review this document
3. File issue: https://github.com/your-org/piyasa_chat_bot/issues

---

**Last Updated**: 2025-11-03
**Version**: 1.0
**Status**: Production Ready ✅
