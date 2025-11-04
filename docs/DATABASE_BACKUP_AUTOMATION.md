# Database Backup Automation Guide

**Created**: 2025-11-04 (Session 38)
**Status**: Production-Ready

## Overview

Automated database backup system with:
- **Daily backups**: Keep last 7 days
- **Weekly backups**: Keep last 4 weeks
- **Monthly backups**: Keep last 12 months
- **Compression**: Gzip compression (4-5x size reduction)
- **Kubernetes native**: CronJob + PersistentVolume

## Architecture

```
┌─────────────────────────────────────────────┐
│  K8s CronJob: database-backup               │
│  Schedule: 0 2 * * * (Daily 2 AM UTC)       │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │  Backup Logic       │
         │  - Determine type   │
         │  - pg_dump + gzip   │
         │  - Verify integrity │
         │  - Cleanup old      │
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────────┐
         │  PersistentVolume: 20Gi │
         │  /backups/              │
         │    ├── daily/           │
         │    ├── weekly/          │
         │    └── monthly/         │
         └─────────────────────────┘
```

## Backup Schedule Logic

```bash
# Daily at 2 AM UTC (5 AM Turkey time)
Schedule: "0 2 * * *"

# Backup type determination:
- Day of month = 1  → MONTHLY backup
- Day of week = 7   → WEEKLY backup
- Otherwise         → DAILY backup
```

## Retention Policy

| Type    | Retention | Directory         | Example Files |
|---------|-----------|-------------------|---------------|
| Daily   | 7 days    | `/backups/daily/` | backup_daily_20251104_020000.sql.gz |
| Weekly  | 4 weeks   | `/backups/weekly/` | backup_weekly_20251027_020000.sql.gz |
| Monthly | 12 months | `/backups/monthly/` | backup_monthly_20251101_020000.sql.gz |

## Deployment

### Prerequisites

1. **Database**: PostgreSQL running in K8s
2. **Secrets**: `piyasa-secrets` with DATABASE_URL and DB_PASSWORD
3. **Storage**: 20Gi PersistentVolume available

### Deploy to Dev

```bash
# 1. Verify backup CronJob in manifests
kubectl kustomize k8s/overlays/dev | grep -A 20 "kind: CronJob"

# 2. Deploy
kubectl apply -k k8s/overlays/dev

# 3. Verify CronJob created
kubectl get cronjob -n piyasa-chatbot-dev
# Expected output:
# NAME                   SCHEDULE    SUSPEND   ACTIVE   LAST SCHEDULE   AGE
# dev-database-backup    0 2 * * *   False     0        <none>          10s

# 4. Verify PVC created
kubectl get pvc -n piyasa-chatbot-dev | grep backup
# Expected output:
# dev-backup-pvc   Bound    pvc-xxx   20Gi       RWO            hostpath       5s
```

### Deploy to Production

```bash
# Production uses different storage class
kubectl apply -k k8s/overlays/prod

# Verify
kubectl get cronjob -n piyasa-chatbot
kubectl get pvc -n piyasa-chatbot | grep backup
```

## Manual Backup (On-Demand)

```bash
# Create job from CronJob template
kubectl create job --from=cronjob/dev-database-backup manual-backup-$(date +%Y%m%d) -n piyasa-chatbot-dev

# Monitor progress
kubectl logs -f job/manual-backup-20251104 -n piyasa-chatbot-dev

# Expected output:
# === Database Backup Starting ===
# Date: 2025-11-04_02:00:00
# Backup type: daily
# Backing up PostgreSQL database...
#   Host: dev-db-service
#   Port: 5432
#   Database: app
# Backup created: /backups/daily/backup_daily_20251104_020000.sql.gz
# Backup size: 45K
# Backup integrity: OK
# === Database Backup Completed Successfully ===
```

## Verification

### Check Backup Files

```bash
# Access backup pod
kubectl run -it --rm backup-shell --image=postgres:16-alpine --restart=Never -n piyasa-chatbot-dev \
  -- sh -c "mount | grep backups"

# Or use existing pod
kubectl exec -it deployment/dev-api -n piyasa-chatbot-dev -- ls -lh /backups/daily/
```

### Verify Backup Integrity

```bash
# List backups with sizes
kubectl exec -it deployment/dev-api -n piyasa-chatbot-dev -- sh -c '
  echo "=== Daily Backups ==="
  ls -lh /backups/daily/ 2>/dev/null || echo "No daily backups"

  echo -e "\n=== Weekly Backups ==="
  ls -lh /backups/weekly/ 2>/dev/null || echo "No weekly backups"

  echo -e "\n=== Monthly Backups ==="
  ls -lh /backups/monthly/ 2>/dev/null || echo "No monthly backups"
'

# Test gzip integrity
kubectl exec -it deployment/dev-api -n piyasa-chatbot-dev -- \
  gzip -t /backups/daily/backup_daily_*.sql.gz && echo "OK"
```

## Restore Procedure

### Quick Restore (Latest Backup)

```bash
# 1. Find latest backup
LATEST_BACKUP=$(kubectl exec deployment/dev-api -n piyasa-chatbot-dev -- \
  ls -t /backups/daily/backup_daily_*.sql.gz | head -n 1)

echo "Restoring from: $LATEST_BACKUP"

# 2. Extract and restore
kubectl exec -it deployment/dev-api -n piyasa-chatbot-dev -- sh -c "
  gunzip -c $LATEST_BACKUP | psql -h dev-db-service -U app -d app
"
```

### Point-in-Time Restore

```bash
# 1. List available backups
kubectl exec deployment/dev-api -n piyasa-chatbot-dev -- \
  find /backups -name "backup_*.sql.gz" -type f | sort

# 2. Choose backup (example: weekly from Oct 27)
BACKUP_FILE="/backups/weekly/backup_weekly_20251027_020000.sql.gz"

# 3. Restore
kubectl exec -it deployment/dev-api -n piyasa-chatbot-dev -- sh -c "
  gunzip -c $BACKUP_FILE | psql -h dev-db-service -U app -d app
"
```

### Full Disaster Recovery

See `docs/DISASTER_RECOVERY.md` for complete recovery procedures.

## Monitoring

### Check CronJob Status

```bash
# List recent jobs
kubectl get jobs -n piyasa-chatbot-dev | grep backup

# Check last job logs
LAST_JOB=$(kubectl get jobs -n piyasa-chatbot-dev --sort-by=.metadata.creationTimestamp | grep backup | tail -n 1 | awk '{print $1}')
kubectl logs job/$LAST_JOB -n piyasa-chatbot-dev
```

### Monitor Storage Usage

```bash
# Check PVC size
kubectl get pvc dev-backup-pvc -n piyasa-chatbot-dev

# Check actual usage
kubectl exec deployment/dev-api -n piyasa-chatbot-dev -- \
  du -sh /backups/*
```

### Set Up Alerts

```yaml
# Prometheus alert example
- alert: BackupJobFailed
  expr: kube_job_status_failed{job_name=~".*database-backup.*"} > 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Database backup job failed"
    description: "Backup job {{ $labels.job_name }} failed"
```

## Troubleshooting

### CronJob Not Running

```bash
# Check CronJob configuration
kubectl describe cronjob dev-database-backup -n piyasa-chatbot-dev

# Check for suspended state
kubectl get cronjob dev-database-backup -n piyasa-chatbot-dev -o yaml | grep suspend

# Unsuspend if needed
kubectl patch cronjob dev-database-backup -n piyasa-chatbot-dev -p '{"spec":{"suspend":false}}'
```

### Backup Job Failed

```bash
# Get failed job logs
kubectl get jobs -n piyasa-chatbot-dev | grep backup | grep -v Complete

# View logs
kubectl logs job/<failed-job-name> -n piyasa-chatbot-dev

# Common issues:
# 1. Secret not found → Check piyasa-secrets exists
# 2. PVC not mounted → Check PVC bound state
# 3. Database unreachable → Check database service
# 4. Permission denied → Check securityContext settings
```

### Storage Full

```bash
# Check storage usage
kubectl exec deployment/dev-api -n piyasa-chatbot-dev -- df -h /backups

# Manual cleanup (older backups)
kubectl exec deployment/dev-api -n piyasa-chatbot-dev -- sh -c '
  find /backups/daily -name "backup_daily_*.sql.gz" -mtime +7 -delete
  find /backups/weekly -name "backup_weekly_*.sql.gz" -mtime +28 -delete
  find /backups/monthly -name "backup_monthly_*.sql.gz" -mtime +365 -delete
'

# Expand PVC (if storage class supports)
kubectl patch pvc dev-backup-pvc -n piyasa-chatbot-dev \
  -p '{"spec":{"resources":{"requests":{"storage":"50Gi"}}}}'
```

## Offsite Replication (Recommended for Production)

### AWS S3 Integration

```yaml
# Add sidecar container to CronJob
- name: s3-sync
  image: amazon/aws-cli
  command:
  - sh
  - -c
  - |
    aws s3 sync /backups s3://my-backup-bucket/piyasa-chatbot/ \
      --storage-class GLACIER_IR \
      --exclude "*" \
      --include "backup_*.sql.gz"
  env:
  - name: AWS_ACCESS_KEY_ID
    valueFrom:
      secretKeyRef:
        name: aws-credentials
        key: access_key_id
  - name: AWS_SECRET_ACCESS_KEY
    valueFrom:
      secretKeyRef:
        name: aws-credentials
        key: secret_access_key
  volumeMounts:
  - name: backup-storage
    mountPath: /backups
    readOnly: true
```

### Google Cloud Storage Integration

```yaml
# Add sidecar container
- name: gcs-sync
  image: google/cloud-sdk:alpine
  command:
  - sh
  - -c
  - |
    gsutil -m rsync -r /backups gs://my-backup-bucket/piyasa-chatbot/
  env:
  - name: GOOGLE_APPLICATION_CREDENTIALS
    value: /var/secrets/google/key.json
  volumeMounts:
  - name: backup-storage
    mountPath: /backups
    readOnly: true
  - name: gcp-key
    mountPath: /var/secrets/google
```

## Security Best Practices

1. **Encryption at Rest**: Use encrypted storage class
   ```yaml
   storageClassName: encrypted-ssd
   ```

2. **Encryption in Transit**: Enable SSL for pg_dump
   ```bash
   pg_dump "sslmode=require host=..."
   ```

3. **Access Control**: Restrict PVC access
   ```yaml
   accessModes:
     - ReadWriteOnce  # Single node only
   ```

4. **Secret Rotation**: Regularly rotate DATABASE_URL password

5. **Offsite Backups**: Always replicate to offsite storage (S3/GCS)

## Maintenance

### Monthly Backup Test

```bash
# 1. Restore latest monthly backup to test database
MONTHLY_BACKUP=$(kubectl exec deployment/dev-api -n piyasa-chatbot-dev -- \
  ls -t /backups/monthly/backup_monthly_*.sql.gz | head -n 1)

# 2. Create test database
kubectl exec -it deployment/dev-db -n piyasa-chatbot-dev -- \
  psql -U postgres -c "CREATE DATABASE backup_test;"

# 3. Restore
kubectl exec -it deployment/dev-api -n piyasa-chatbot-dev -- sh -c "
  gunzip -c $MONTHLY_BACKUP | psql -h dev-db-service -U app -d backup_test
"

# 4. Verify data
kubectl exec -it deployment/dev-db -n piyasa-chatbot-dev -- \
  psql -U app -d backup_test -c "SELECT COUNT(*) FROM bots;"

# 5. Cleanup
kubectl exec -it deployment/dev-db -n piyasa-chatbot-dev -- \
  psql -U postgres -c "DROP DATABASE backup_test;"
```

### Backup Rotation Verification

```bash
# Check that old backups are being deleted
kubectl exec deployment/dev-api -n piyasa-chatbot-dev -- sh -c '
  echo "Daily backups (should be <= 7):"
  find /backups/daily -name "*.sql.gz" | wc -l

  echo "Weekly backups (should be <= 4):"
  find /backups/weekly -name "*.sql.gz" | wc -l

  echo "Monthly backups (should be <= 12):"
  find /backups/monthly -name "*.sql.gz" | wc -l
'
```

## Success Metrics

- ✅ Backup success rate: > 99%
- ✅ RTO (Recovery Time Objective): < 15 minutes
- ✅ RPO (Recovery Point Objective): < 24 hours
- ✅ Compression ratio: 4-5x
- ✅ Storage usage: < 10Gi for 1 year retention

## References

- Backup script: `scripts/backup_database.py`
- Restore script: `scripts/restore_database.py`
- K8s manifest: `k8s/base/backup-cronjob.yaml`
- DR runbook: `docs/DISASTER_RECOVERY.md`
- DR test results: `test_dr/DR_TEST_RESULTS.md` (Session 35)

---

*Generated with Claude Code - Session 38*
*Status: Production-Ready*
