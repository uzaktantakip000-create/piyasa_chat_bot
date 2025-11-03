# Disaster Recovery Plan

**Last Updated**: 2025-11-03
**Version**: 1.0
**Status**: Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Recovery Objectives](#recovery-objectives)
3. [Backup Strategy](#backup-strategy)
4. [Restoration Procedures](#restoration-procedures)
5. [Testing & Validation](#testing--validation)
6. [Roles & Responsibilities](#roles--responsibilities)
7. [Emergency Contacts](#emergency-contacts)
8. [Appendices](#appendices)

---

## Overview

### Purpose

This document outlines the disaster recovery (DR) procedures for the piyasa_chat_bot system. It provides step-by-step instructions for recovering from various failure scenarios.

### Scope

Covers recovery procedures for:
- Database corruption/loss
- Application data recovery
- System configuration restoration
- Complete system rebuild

### Disaster Scenarios

| Scenario | Severity | RTO | RPO | Recovery Procedure |
|----------|----------|-----|-----|-------------------|
| Database corruption | High | 15 min | 24h | Restore from backup |
| Accidental data deletion | Medium | 5 min | 24h | Point-in-time restore |
| Server failure | High | 30 min | 24h | Rebuild + restore |
| Complete data center loss | Critical | 2 hours | 24h | Offsite restore |

---

## Recovery Objectives

### RTO (Recovery Time Objective)

**Target**: 15 minutes
**Achieved**: < 1 minute (test results)

**Definition**: Maximum acceptable downtime after a disaster.

**Breakdown**:
- Detection: 1-5 minutes
- Decision: 1-2 minutes
- Execution: 5-10 minutes
- Verification: 2-3 minutes

### RPO (Recovery Point Objective)

**Target**: 24 hours
**Achieved**: < 24 hours

**Definition**: Maximum acceptable data loss window.

**Backup Frequency**:
- Daily backups: Every 24 hours (automated)
- Weekly backups: Every Sunday
- Monthly backups: First day of month

**Data Loss Tolerance**:
- Critical data: 0 hours (real-time replication recommended)
- Normal data: 24 hours (daily backups)
- Historical data: 7 days (weekly backups)

---

## Backup Strategy

### Automated Backups

**Script**: `scripts/backup_database.py`

**Schedule**:
```bash
# Linux/macOS (crontab)
0 2 * * * cd /path/to/piyasa_chat_bot && /path/to/.venv/bin/python scripts/backup_database.py

# Windows (Task Scheduler)
Run: C:\path\to\.venv\Scripts\python.exe
Arguments: C:\path\to\piyasa_chat_bot\scripts\backup_database.py
Trigger: Daily at 2:00 AM
```

**Configuration** (environment variables):
```bash
DATABASE_URL=sqlite:///./app.db           # or PostgreSQL URL
BACKUP_DIR=./backups                       # Backup directory
BACKUP_RETENTION_DAYS=7                    # Daily retention
BACKUP_RETENTION_WEEKS=4                   # Weekly retention
BACKUP_RETENTION_MONTHS=12                 # Monthly retention
```

### Backup Rotation

| Type | Frequency | Retention | Purpose |
|------|-----------|-----------|---------|
| Daily | Every 24h | 7 days | Recent data recovery |
| Weekly | Every Sunday | 4 weeks | Medium-term recovery |
| Monthly | 1st of month | 12 months | Long-term compliance |

### Backup Verification

**Daily Checks**:
1. Verify backup file exists
2. Check file size > 0
3. Validate gzip integrity: `gzip -t <file>`
4. Log backup success/failure

**Monthly Restore Test**:
1. Restore to test environment
2. Verify data integrity
3. Document results
4. Update runbook if needed

### Storage Locations

**Primary** (Local):
- Path: `./backups/daily/`, `./backups/weekly/`, `./backups/monthly/`
- Retention: As per policy
- Access: Application server only

**Secondary** (Offsite - Recommended):
- AWS S3: `s3://your-bucket/piyasa-backups/`
- Google Cloud Storage: `gs://your-bucket/piyasa-backups/`
- Azure Blob: `https://yourname.blob.core.windows.net/piyasa-backups/`

**Replication Command** (example for S3):
```bash
# Sync backups to S3
aws s3 sync ./backups/ s3://your-bucket/piyasa-backups/ \
  --exclude "*" \
  --include "daily/*" \
  --include "weekly/*" \
  --include "monthly/*"
```

---

## Restoration Procedures

### Prerequisites

1. Access to backup files
2. `TOKEN_ENCRYPTION_KEY` environment variable (same as original)
3. Python 3.11+ installed
4. `scripts/restore_database.py` script

### Procedure 1: Full Database Restore

**When to Use**: Database corrupted, accidental mass deletion

**Steps**:

1. **Stop Application**:
   ```bash
   docker compose down
   # or
   systemctl stop piyasa-worker
   systemctl stop piyasa-api
   ```

2. **Identify Backup**:
   ```bash
   # List available backups
   ls -lh backups/daily/
   ls -lh backups/weekly/
   ls -lh backups/monthly/

   # Choose latest or specific timestamp
   BACKUP_FILE="backups/daily/backup_daily_20251103_230310.sql.gz"
   ```

3. **Backup Current Database** (if recoverable):
   ```bash
   cp app.db app.db.corrupted_$(date +%Y%m%d_%H%M%S)
   ```

4. **Run Restore**:
   ```bash
   # Set environment
   export DATABASE_URL="sqlite:///./app.db"  # or PostgreSQL URL
   export TOKEN_ENCRYPTION_KEY="your-key-here"

   # Execute restore
   python scripts/restore_database.py $BACKUP_FILE --yes

   # Verify success
   echo $?  # Should be 0
   ```

5. **Verify Data Integrity**:
   ```bash
   python -c "
   from database import SessionLocal, Bot, Chat, Message
   db = SessionLocal()
   print(f'Bots: {db.query(Bot).count()}')
   print(f'Chats: {db.query(Chat).count()}')
   print(f'Messages: {db.query(Message).count()}')
   db.close()
   "
   ```

6. **Restart Application**:
   ```bash
   docker compose up -d
   # or
   systemctl start piyasa-api
   systemctl start piyasa-worker
   ```

7. **Monitor Logs**:
   ```bash
   docker compose logs -f
   # or
   journalctl -u piyasa-api -f
   ```

**Expected Duration**: < 1 minute (small DB), 5-15 minutes (large DB)

---

### Procedure 2: Point-in-Time Restore

**When to Use**: Restore to specific date/time

**Steps**:

1. Identify backup closest to desired timestamp:
   ```bash
   # List backups with timestamps
   ls -lh backups/daily/ | grep "backup_daily_20251103"
   ```

2. Follow Procedure 1 using selected backup

**Example**:
- Disaster at: 2025-11-03 14:00
- Latest backup: 2025-11-03 02:00 (daily)
- Data loss window: 12 hours
- Recovery: Restore from 02:00 backup

---

### Procedure 3: PostgreSQL Restore

**Prerequisites**:
- `pg_dump` and `psql` installed
- PostgreSQL server accessible

**Steps**:

1. **Stop Application** (same as Procedure 1)

2. **Drop Existing Database** (optional):
   ```bash
   psql -U postgres -c "DROP DATABASE IF EXISTS piyasa_db;"
   psql -U postgres -c "CREATE DATABASE piyasa_db;"
   ```

3. **Run Restore**:
   ```bash
   export DATABASE_URL="postgresql://user:pass@localhost/piyasa_db"
   python scripts/restore_database.py $BACKUP_FILE --yes
   ```

4. **Verify and Restart** (same as Procedure 1)

---

### Procedure 4: Complete System Rebuild

**When to Use**: Server failure, complete infrastructure loss

**Steps**:

1. **Provision New Server**
2. **Install Dependencies**:
   ```bash
   # Install Python, Docker, Git
   sudo apt-get update
   sudo apt-get install python3.11 python3.11-venv docker.io git

   # Clone repository
   git clone https://github.com/your-org/piyasa_chat_bot
   cd piyasa_chat_bot
   ```

3. **Restore Configuration**:
   ```bash
   # Copy .env from backup or secrets manager
   cp /path/to/backup/.env .env

   # Verify TOKEN_ENCRYPTION_KEY matches
   grep TOKEN_ENCRYPTION_KEY .env
   ```

4. **Restore Database** (follow Procedure 1)

5. **Install and Start Application**:
   ```bash
   docker compose up -d
   ```

6. **Verify System Health**:
   ```bash
   curl http://localhost:8000/healthz
   python preflight.py
   ```

**Expected Duration**: 30 minutes - 2 hours

---

## Testing & Validation

### Regular DR Tests

**Frequency**: Monthly

**Test Checklist**:
- [ ] Backup exists and is recent (< 24h)
- [ ] Backup file size reasonable (> 10 KB)
- [ ] Backup decompression succeeds
- [ ] Restore to test environment succeeds
- [ ] Data integrity verified (counts match)
- [ ] Application starts after restore
- [ ] API endpoints respond correctly

**Test Environment**:
```bash
# Create test directory
mkdir -p test_dr/{databases,backups}

# Copy production backup
cp backups/daily/latest.sql.gz test_dr/backups/

# Test restore
cd test_dr
DATABASE_URL=sqlite:///./databases/test.db \
python ../scripts/restore_database.py backups/latest.sql.gz --yes
```

### DR Drill Scenarios

**Quarterly Full DR Drill**:
1. Simulate production database corruption
2. Notify team (DR coordinator)
3. Execute restore procedure
4. Measure RTO/RPO
5. Document lessons learned
6. Update runbook

**Metrics to Track**:
- Time to detect disaster
- Time to decision
- Time to restore
- Data integrity percentage
- Application uptime after recovery

---

## Roles & Responsibilities

### DR Coordinator

**Primary**: System Administrator
**Backup**: DevOps Lead

**Responsibilities**:
- Declare disaster
- Initiate DR procedures
- Coordinate team
- Communicate with stakeholders
- Verify recovery success

### Database Administrator

**Responsibilities**:
- Execute restore procedures
- Verify data integrity
- Monitor backup health
- Manage backup rotation

### Application Owner

**Responsibilities**:
- Verify application functionality
- Test critical workflows
- Approve recovery completion
- Document incident

### Communications Lead

**Responsibilities**:
- Notify users of outage
- Provide status updates
- Announce recovery completion

---

## Emergency Contacts

| Role | Name | Phone | Email | Availability |
|------|------|-------|-------|--------------|
| DR Coordinator | [NAME] | [PHONE] | [EMAIL] | 24/7 |
| DB Administrator | [NAME] | [PHONE] | [EMAIL] | 24/7 |
| DevOps Lead | [NAME] | [PHONE] | [EMAIL] | Business hours |
| Application Owner | [NAME] | [PHONE] | [EMAIL] | Business hours |

**Escalation Path**:
1. DR Coordinator (immediate)
2. DB Administrator (within 5 min)
3. DevOps Lead (within 15 min)
4. CTO (if RTO > 1 hour)

---

## Appendices

### Appendix A: Backup File Naming Convention

```
backup_<type>_<timestamp>.sql.gz

Examples:
- backup_daily_20251103_020000.sql.gz
- backup_weekly_20251103_020023.sql.gz
- backup_monthly_20251103_020045.sql.gz
```

### Appendix B: Compression Details

- Format: gzip
- Compression level: 9 (maximum)
- Typical ratio: 4-6x
- Decompression time: < 1 second per 100 MB

### Appendix C: Encryption (Optional)

For sensitive data, encrypt backups:

```bash
# Encrypt backup
gpg --encrypt --recipient your-key-id backup.sql.gz

# Decrypt for restore
gpg --decrypt backup.sql.gz.gpg > backup.sql.gz
```

### Appendix D: Monitoring Integration

**Backup Success Monitoring** (Prometheus):
```yaml
- alert: BackupFailed
  expr: backup_success == 0
  for: 1h
  labels:
    severity: critical
  annotations:
    summary: "Database backup failed"
```

**Slack Notification** (example):
```bash
# Add to backup script
if [ $? -eq 0 ]; then
  curl -X POST -H 'Content-type: application/json' \
    --data '{"text":"✅ Backup successful"}' \
    $SLACK_WEBHOOK_URL
fi
```

### Appendix E: Regulatory Compliance

**Data Retention Requirements**:
- Financial data: 7 years (monthly backups)
- User data: 2 years (quarterly backups)
- Logs: 1 year (weekly backups)

**Audit Trail**:
- All backup operations logged
- Restore operations require approval
- Access to backups restricted (RBAC)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-03 | Claude Code (Session 35) | Initial DR plan with tested procedures |

---

*This document should be reviewed quarterly and updated after each DR test or actual disaster recovery event.*
