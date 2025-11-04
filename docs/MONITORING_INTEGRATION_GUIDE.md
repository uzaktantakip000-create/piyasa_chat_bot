# Monitoring Integration Guide

**Created**: 2025-11-04 (Session 38 - P2.2)
**Status**: Production-Ready
**Stack**: Prometheus + AlertManager + Grafana

## Overview

This guide covers the complete monitoring stack integration for the Piyasa ChatBot system. The monitoring infrastructure provides comprehensive observability, alerting, and visualization for production operations.

### Architecture

```
┌─────────────────────────────────────────────────────┐
│              Application Services                    │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│   │   API    │  │  Worker  │  │ Frontend │        │
│   │  :8000   │  │  :8001   │  │  :3000   │        │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│        │             │              │               │
│        └─────────────┼──────────────┘               │
│                      │ /metrics                     │
│                      ▼                               │
│   ┌──────────────────────────────────────┐         │
│   │         Prometheus :9090             │         │
│   │  (Scrape metrics every 10-15s)       │         │
│   └──────────────┬───────────────────────┘         │
│                  │                                   │
│        ┌─────────┼─────────┐                       │
│        ▼         ▼         ▼                        │
│   ┌────────┐ ┌────────┐ ┌────────┐                │
│   │ Rules  │ │ Alerts │ │ Grafana│                │
│   │Evaluate│ │Manager │ │  :3001 │                │
│   │ (30s)  │ │ :9093  │ │ (Viz)  │                │
│   └────────┘ └───┬────┘ └────────┘                │
│                   │                                  │
│                   ▼                                  │
│   ┌────────────────────────────────────────┐       │
│   │  Notification Channels                 │       │
│   │  - Slack (#piyasa-alerts)              │       │
│   │  - Discord (webhook)                   │       │
│   │  - PagerDuty (optional)                │       │
│   └────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────┘
```

### Components

| Component | Port | Purpose | Configuration |
|-----------|------|---------|---------------|
| **Prometheus** | 9090 | Metrics collection & storage | `monitoring/prometheus.yml` |
| **AlertManager** | 9093 | Alert routing & notifications | `monitoring/alertmanager/alertmanager.yml` |
| **Grafana** | 3001 | Dashboard visualization | `monitoring/grafana/` |
| **API** | 8000 | Exposes `/metrics` endpoint | `backend/metrics/prometheus_exporter.py` |
| **Worker** | 8001 | Exposes `/metrics` endpoint | `worker.py` |

## Installation & Setup

### Docker Compose Deployment (Recommended)

```bash
# Start entire monitoring stack
docker compose up -d prometheus alertmanager grafana

# Verify services
docker ps | grep -E 'prometheus|alertmanager|grafana'

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check Grafana health
curl http://localhost:3001/api/health
```

### Kubernetes Deployment

```bash
# Deploy monitoring stack
kubectl apply -k k8s/overlays/prod

# Verify deployments
kubectl get pods -l app.kubernetes.io/component=monitoring

# Port-forward for local access
kubectl port-forward svc/prometheus 9090:9090
kubectl port-forward svc/alertmanager 9093:9093
kubectl port-forward svc/grafana 3001:3000
```

### Configuration Files

**1. `monitoring/prometheus.yml` (Prometheus Configuration)**
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'piyasa-chatbot'
    environment: 'production'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - '/etc/prometheus/rules/*.yml'

scrape_configs:
  - job_name: 'piyasa-chatbot-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s

  - job_name: 'piyasa-chatbot-worker'
    static_configs:
      - targets: ['worker:8001']
    metrics_path: '/metrics'
    scrape_interval: 10s
```

**2. `monitoring/prometheus_rules/alert_rules.yml` (Alert Rules)**
- 25+ alert rules across 6 groups
- Coverage: API health, worker health, LLM services, database, Telegram API, system resources
- See file for complete rule definitions

**3. `monitoring/alertmanager/alertmanager.yml` (Alert Routing)**
```yaml
route:
  receiver: 'default'
  group_by: ['alertname', 'severity', 'service']
  routes:
    - match: {severity: critical}
      receiver: 'critical-alerts'
      repeat_interval: 5m
    - match: {severity: high}
      receiver: 'high-priority'
      repeat_interval: 15m
    - match: {severity: warning}
      receiver: 'warnings'
      repeat_interval: 1h
```

## Metrics Exposed

### API Metrics (`/metrics` on port 8000)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_requests_total` | Counter | method, endpoint, status | Total HTTP requests |
| `http_request_duration_seconds` | Histogram | method, endpoint | Request latency distribution |
| `database_connection_pool_size` | Gauge | - | Max DB connections |
| `database_connection_pool_in_use` | Gauge | - | Active DB connections |
| `database_query_duration_seconds` | Histogram | operation | Query latency distribution |
| `cache_hits_total` | Counter | cache_type | Cache hits |
| `cache_misses_total` | Counter | cache_type | Cache misses |

### Worker Metrics (`/metrics` on port 8001)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `messages_generated_total` | Counter | bot_id, chat_id | Successful messages generated |
| `messages_failed_total` | Counter | bot_id, chat_id, error_type | Failed message attempts |
| `message_generation_duration_seconds` | Histogram | bot_id | Message generation latency |
| `llm_requests_total` | Counter | provider, model | Total LLM API requests |
| `llm_requests_failed_total` | Counter | provider, error_type | Failed LLM requests |
| `llm_tokens_used_total` | Counter | provider, token_type | Tokens consumed (prompt/completion) |
| `circuit_breaker_state` | Gauge | service | Circuit breaker state (0=closed, 1=half-open, 2=open) |
| `telegram_requests_total` | Counter | method | Telegram API requests |
| `telegram_errors_total` | Counter | error_code | Telegram API errors |
| `telegram_429_count` | Counter | - | Telegram rate limit hits |
| `simulation_active` | Gauge | - | Simulation on/off state |

### System Metrics (Auto-collected)

| Metric | Type | Description |
|--------|------|-------------|
| `process_cpu_seconds_total` | Counter | Total CPU time used |
| `process_resident_memory_bytes` | Gauge | Resident memory (RSS) |
| `process_virtual_memory_max_bytes` | Gauge | Maximum virtual memory |
| `up` | Gauge | Service availability (1=up, 0=down) |

## Alert Rules

### Alert Severity Levels

| Severity | Repeat Interval | Notification | Example Alerts |
|----------|----------------|--------------|----------------|
| **critical** | 5 minutes | Slack + PagerDuty | APIDown, WorkerDown, CircuitBreakerOpen |
| **high** | 15 minutes | Slack | WorkerNoMessages, HighAPIErrorRate, DatabaseConnectionPoolExhausted |
| **warning** | 1 hour | Slack | HighAPILatency, SlowDatabaseQueries, LowCacheHitRate |
| **info** | 12 hours | Slack (info channel) | LowMessageThroughput, HighDeduplicationRate |

### Key Alert Rules

#### 1. Service Health Alerts

**APIDown**
```yaml
alert: APIDown
expr: up{job="piyasa-chatbot-api"} == 0
for: 1m
severity: critical
```
Fires when API service is unreachable for 1 minute.

**WorkerDown**
```yaml
alert: WorkerDown
expr: up{job="piyasa-chatbot-worker"} == 0
for: 2m
severity: critical
```
Fires when Worker service is unreachable for 2 minutes.

#### 2. Performance Alerts

**HighAPIErrorRate**
```yaml
alert: HighAPIErrorRate
expr: |
  (
    sum(rate(http_requests_total{job="piyasa-chatbot-api", status=~"5.."}[5m]))
    /
    sum(rate(http_requests_total{job="piyasa-chatbot-api"}[5m]))
  ) > 0.05
for: 5m
severity: high
```
Fires when API error rate exceeds 5% for 5 minutes.

**HighMessageGenerationLatency**
```yaml
alert: HighMessageGenerationLatency
expr: |
  histogram_quantile(0.95,
    sum(rate(message_generation_duration_seconds_bucket[5m])) by (le)
  ) > 10.0
for: 10m
severity: warning
```
Fires when p95 message generation latency exceeds 10 seconds.

#### 3. LLM Circuit Breaker Alerts

**CircuitBreakerOpen**
```yaml
alert: CircuitBreakerOpen
expr: circuit_breaker_state{service=~"openai_api|gemini_api|groq_api"} == 2
for: 1m
severity: high
```
Fires when any LLM provider circuit breaker opens (state=2).

**HighLLMErrorRate**
```yaml
alert: HighLLMErrorRate
expr: |
  (
    sum(rate(llm_requests_failed_total[5m])) by (provider)
    /
    sum(rate(llm_requests_total[5m])) by (provider)
  ) > 0.15
for: 5m
severity: warning
```
Fires when LLM error rate exceeds 15% for 5 minutes.

#### 4. Database Alerts

**DatabaseConnectionPoolExhausted**
```yaml
alert: DatabaseConnectionPoolExhausted
expr: |
  (
    database_connection_pool_in_use
    /
    database_connection_pool_size
  ) > 0.90
for: 5m
severity: high
```
Fires when connection pool usage exceeds 90%.

**SlowDatabaseQueries**
```yaml
alert: SlowDatabaseQueries
expr: |
  histogram_quantile(0.95,
    sum(rate(database_query_duration_seconds_bucket[5m])) by (le)
  ) > 1.0
for: 10m
severity: warning
```
Fires when p95 query latency exceeds 1 second.

#### 5. Telegram API Alerts

**TelegramRateLimitHit**
```yaml
alert: TelegramRateLimitHit
expr: rate(telegram_429_count[5m]) > 0.1
for: 5m
severity: warning
```
Fires when Telegram 429 errors exceed 0.1 per second.

### Alert Inhibition Rules

**Inhibition** prevents duplicate notifications when related alerts fire together.

**Example 1**: If API is down, suppress high latency alerts
```yaml
- source_match:
    alertname: 'APIDown'
  target_match:
    alertname: 'HighAPILatency'
  equal: ['service']
```

**Example 2**: If circuit breaker is open, suppress failure alerts
```yaml
- source_match:
    alertname: 'CircuitBreakerOpen'
  target_match_re:
    alertname: '.*Failure'
  equal: ['service']
```

## Grafana Dashboards

### Production Overview Dashboard

**UID**: `piyasa-chatbot-overview`
**Refresh**: 10 seconds
**Panels**: 18 panels across 7 sections

#### Dashboard Sections

**1. System Health & Alerts** (4 stat panels)
- Service Health: Count of down services
- Active Alerts: Number of firing alerts
- LLM Circuit Breaker: Current state (closed/half-open/open)
- Cache Hit Rate: Current cache effectiveness

**2. Message Generation & Worker** (2 panels)
- Message Generation Rate: Success/failure rate over time
- Message Generation Duration: p50/p95/p99 latency gauges

**3. API Performance** (2 panels)
- API Request Rate: Requests per second by status code
- API Request Duration: p50/p95 latency by endpoint

**4. LLM & AI Services** (2 panels)
- LLM Token Usage: Tokens per second by provider (stacked area)
- LLM Error Rate: Error rate by provider over time

**5. Database & Cache** (3 panels)
- DB Connection Pool Usage: Current pool utilization (gauge)
- Database Query Duration: p95 query latency
- Cache Hit/Miss Rate: Hit/miss distribution (stacked percent)

**6. Telegram API** (2 panels)
- Telegram Rate Limit Hits: 429 errors over time
- Telegram API Error Rate: Overall error rate

**7. System Resources** (2 panels)
- CPU Usage: CPU utilization by instance
- Memory Usage: Memory utilization by instance

### Accessing Dashboards

**Local Development**:
```
http://localhost:3001/d/piyasa-chatbot-overview
```

**Kubernetes (port-forward)**:
```bash
kubectl port-forward svc/grafana 3001:3000
# Open: http://localhost:3001/d/piyasa-chatbot-overview
```

**Default Credentials** (Change after first login!):
- Username: `admin`
- Password: `admin`

### Dashboard Customization

**Add New Panel**:
1. Edit dashboard (pencil icon top-right)
2. Add Panel → Add new panel
3. Select data source: Prometheus
4. Enter PromQL query
5. Configure visualization (graph, gauge, stat, etc.)
6. Save dashboard

**Example Custom Panel - Bot-Specific Message Rate**:
```promql
rate(messages_generated_total{bot_id="123"}[5m])
```

## Notification Configuration

### Slack Integration

**1. Create Slack Incoming Webhook**:
1. Go to https://api.slack.com/apps
2. Create New App → From scratch
3. Enable Incoming Webhooks
4. Add New Webhook to Workspace
5. Select channel (e.g., `#piyasa-alerts`)
6. Copy webhook URL

**2. Update AlertManager Configuration**:
```yaml
# monitoring/alertmanager/alertmanager.yml
global:
  slack_api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'

receivers:
  - name: 'critical-alerts'
    slack_configs:
      - channel: '#piyasa-alerts-critical'
        username: 'Prometheus'
        title: '🚨 CRITICAL: {{ .GroupLabels.alertname }}'
        text: |
          {{ range .Alerts }}
          *Alert:* {{ .Labels.alertname }}
          *Severity:* {{ .Labels.severity }}
          *Service:* {{ .Labels.service }}
          *Summary:* {{ .Annotations.summary }}
          *Description:* {{ .Annotations.description }}
          {{ end }}
        send_resolved: true
```

**3. Restart AlertManager**:
```bash
docker compose restart alertmanager
# OR
kubectl rollout restart deployment/alertmanager
```

### Discord Integration

**1. Create Discord Webhook**:
1. Open Discord → Server Settings → Integrations
2. Create Webhook
3. Copy webhook URL

**2. Update AlertManager Configuration**:
```yaml
# monitoring/alertmanager/alertmanager.yml
receivers:
  - name: 'critical-alerts'
    webhook_configs:
      - url: 'https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN/slack'
        send_resolved: true
        http_config:
          follow_redirects: true
```

Note: Add `/slack` suffix to Discord webhook URL for Slack-compatible format.

### PagerDuty Integration (Production)

**1. Create PagerDuty Integration Key**:
1. Go to PagerDuty → Services
2. Select service → Integrations → Add Integration
3. Select "Prometheus" integration type
4. Copy Integration Key

**2. Update AlertManager Configuration**:
```yaml
# monitoring/alertmanager/alertmanager.yml
receivers:
  - name: 'critical-alerts'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_INTEGRATION_KEY'
        description: '{{ .GroupLabels.alertname }}: {{ .Annotations.summary }}'
        severity: '{{ .Labels.severity }}'
```

## Testing & Validation

### Test Prometheus Scraping

**Check Targets Status**:
```bash
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

**Expected Output**:
```json
{
  "job": "piyasa-chatbot-api",
  "health": "up"
}
{
  "job": "piyasa-chatbot-worker",
  "health": "up"
}
```

**Verify Metrics Collection**:
```bash
# Check API metrics
curl http://localhost:9090/api/v1/query?query=up{job=\"piyasa-chatbot-api\"}

# Check worker metrics
curl http://localhost:9090/api/v1/query?query=messages_generated_total
```

### Test Alert Rules

**Validate Alert Rules Syntax**:
```bash
promtool check rules monitoring/prometheus_rules/alert_rules.yml
```

**Expected Output**:
```
Checking monitoring/prometheus_rules/alert_rules.yml
  SUCCESS: 25 rules found
```

**Trigger Test Alert Manually**:
```bash
# Stop API to trigger APIDown alert
docker compose stop api

# Wait 1 minute for alert to fire
sleep 60

# Check pending/firing alerts
curl http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | {alertname: .labels.alertname, state: .state}'
```

### Test AlertManager Routing

**Send Test Alert**:
```bash
curl -X POST http://localhost:9093/api/v1/alerts -H "Content-Type: application/json" -d '[
  {
    "labels": {
      "alertname": "TestAlert",
      "severity": "warning",
      "service": "test"
    },
    "annotations": {
      "summary": "This is a test alert",
      "description": "Testing AlertManager routing"
    }
  }
]'
```

**Check AlertManager UI**:
```
http://localhost:9093/#/alerts
```

**Verify Notification Delivery**:
- Check Slack channel for test alert
- Verify alert appears in AlertManager UI
- Confirm alert formatting is correct

### Test Grafana Dashboard

**1. Generate Test Load**:
```bash
# Run load test
python scripts/stress_test.py --duration 60 --concurrency 4
```

**2. Observe Metrics in Grafana**:
- Open dashboard: http://localhost:3001/d/piyasa-chatbot-overview
- Verify panels populate with data
- Check metric updates in real-time (10s refresh)
- Validate alert annotations appear on graphs

**3. Validate Panel Queries**:
- Edit panel → View query
- Click "Query inspector" → Refresh
- Check for query errors

## Troubleshooting

### Issue: Prometheus Not Scraping Targets

**Symptoms**:
- Targets show as "DOWN" in Prometheus UI
- No metrics available in Grafana

**Diagnosis**:
```bash
# Check Prometheus logs
docker logs prometheus

# Check API /metrics endpoint
curl http://localhost:8000/metrics

# Test connectivity from Prometheus container
docker exec prometheus wget -O- http://api:8000/metrics
```

**Solutions**:
1. Verify services are running: `docker ps`
2. Check scrape_configs in prometheus.yml
3. Ensure metrics endpoint is exposed: `METRICS_ENABLED=true` in .env
4. Restart Prometheus: `docker compose restart prometheus`

### Issue: Alerts Not Firing

**Symptoms**:
- Expected alerts don't appear in AlertManager
- No notifications received

**Diagnosis**:
```bash
# Check alert rules are loaded
curl http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[] | {alert: .name, state: .state}'

# Check evaluation errors
docker logs prometheus | grep "error evaluating rule"

# Verify AlertManager connection
curl http://localhost:9090/api/v1/alertmanagers
```

**Solutions**:
1. Validate rule syntax: `promtool check rules monitoring/prometheus_rules/alert_rules.yml`
2. Check `for` duration (alert must be true for entire duration)
3. Verify alerting configuration in prometheus.yml
4. Check AlertManager is reachable from Prometheus
5. Review alert inhibition rules (may be suppressing alerts)

### Issue: Notifications Not Delivered

**Symptoms**:
- Alerts firing in AlertManager
- No messages in Slack/Discord

**Diagnosis**:
```bash
# Check AlertManager logs
docker logs alertmanager

# Test webhook directly
curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
  -H "Content-Type: application/json" \
  -d '{"text": "Test notification"}'

# Check AlertManager silences
curl http://localhost:9093/api/v1/silences
```

**Solutions**:
1. Verify webhook URL is correct in alertmanager.yml
2. Check receiver routing (alerts must match route)
3. Ensure repeat_interval hasn't suppressed notification
4. Test webhook outside of AlertManager (curl)
5. Check Slack/Discord webhook permissions

### Issue: Grafana Panels Show No Data

**Symptoms**:
- Dashboard loads but panels are empty
- "No data" message displayed

**Diagnosis**:
```bash
# Test Prometheus data source from Grafana
curl http://localhost:3001/api/datasources/proxy/1/api/v1/query?query=up

# Check Grafana logs
docker logs grafana

# Verify time range
# (Data might be outside selected time window)
```

**Solutions**:
1. Verify Prometheus data source is configured in Grafana
2. Test query in Prometheus UI first: http://localhost:9090/graph
3. Check time range selector (top-right of dashboard)
4. Verify metrics exist: `curl http://localhost:9090/api/v1/label/__name__/values`
5. Check panel query syntax (Edit panel → Query tab)

### Issue: High Memory Usage by Prometheus

**Symptoms**:
- Prometheus container using excessive memory
- OOMKilled errors in Kubernetes

**Diagnosis**:
```bash
# Check storage size
docker exec prometheus du -sh /prometheus

# Check active series count
curl http://localhost:9090/api/v1/status/tsdb | jq '.data.numSeries'

# Check retention settings
docker exec prometheus cat /etc/prometheus/prometheus.yml | grep retention
```

**Solutions**:
1. Reduce retention period: `--storage.tsdb.retention.time=15d` (default: 30d)
2. Limit memory: `--storage.tsdb.wal-compression` (enable WAL compression)
3. Reduce scrape frequency for non-critical metrics
4. Add recording rules for expensive queries
5. Increase memory limit in docker-compose.yml or k8s deployment

## Performance Tuning

### Prometheus Optimization

**1. Recording Rules** (Pre-compute expensive queries)
```yaml
# monitoring/prometheus_rules/recording_rules.yml
groups:
  - name: recording_rules
    interval: 30s
    rules:
      - record: job:http_requests:rate5m
        expr: sum(rate(http_requests_total[5m])) by (job)

      - record: job:message_generation:rate5m
        expr: sum(rate(messages_generated_total[5m])) by (job)
```

**2. Retention Configuration**
```yaml
# docker-compose.yml
prometheus:
  command:
    - '--storage.tsdb.retention.time=30d'
    - '--storage.tsdb.retention.size=10GB'
```

**3. Remote Write (Long-term Storage)**
```yaml
# prometheus.yml
remote_write:
  - url: "https://prometheus-remote-storage.example.com/write"
    queue_config:
      capacity: 10000
      max_shards: 50
```

### AlertManager Optimization

**1. Group Alerts** (Reduce notification spam)
```yaml
route:
  group_by: ['alertname', 'severity', 'service']
  group_wait: 30s       # Wait for more alerts before first notification
  group_interval: 5m    # Wait before sending batch of new alerts
  repeat_interval: 12h  # Resend interval for unresolved alerts
```

**2. Alert Deduplication**
```yaml
# Alerts with same fingerprint within group_interval are deduplicated automatically
```

### Grafana Optimization

**1. Dashboard Variables** (Dynamic filtering)
```yaml
# Add template variable for bot selection
Name: bot_id
Type: Query
Query: label_values(messages_generated_total, bot_id)
```

**2. Panel Query Optimization**
- Use recording rules for complex queries
- Limit time range: 1h default, max 24h
- Use rate() instead of irate() for smoother graphs
- Aggregate before histogram_quantile()

## Security Best Practices

### 1. Network Security

**Restrict Prometheus Access**:
```yaml
# docker-compose.yml
prometheus:
  networks:
    - monitoring_internal
  # Don't expose :9090 publicly!
```

**Use Authentication**:
```yaml
# prometheus.yml
basic_auth_users:
  admin: $2y$10$HashedPasswordHere
```

### 2. AlertManager Security

**Secure Webhook URLs**:
- Store webhook URLs in environment variables
- Use secrets management (Vault, K8s secrets)
- Rotate webhook keys periodically

**Example with K8s Secrets**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: alertmanager-secrets
type: Opaque
stringData:
  slack_webhook_url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### 3. Grafana Security

**Change Default Credentials**:
```bash
# First login: admin/admin
# Immediately change password!
```

**Enable HTTPS**:
```yaml
# grafana.ini
[server]
protocol = https
cert_file = /etc/grafana/ssl/grafana.crt
cert_key = /etc/grafana/ssl/grafana.key
```

**RBAC Roles**:
- Viewer: Read-only dashboard access
- Editor: Create/edit dashboards
- Admin: Full access including data sources

## Integration Checklist

Use this checklist when deploying monitoring to a new environment:

### Initial Setup
- [ ] Deploy Prometheus, AlertManager, Grafana
- [ ] Verify all services are running
- [ ] Check Prometheus targets are "UP"
- [ ] Import Grafana dashboards
- [ ] Configure Prometheus data source in Grafana

### Alert Configuration
- [ ] Load alert rules into Prometheus
- [ ] Configure AlertManager receivers (Slack/Discord/PagerDuty)
- [ ] Test alert routing with manual alert
- [ ] Verify notification delivery
- [ ] Set up alert inhibition rules

### Dashboard Validation
- [ ] Open Production Overview dashboard
- [ ] Verify all panels show data
- [ ] Check metric update frequency (10s refresh)
- [ ] Validate alert annotations appear
- [ ] Test dashboard variables (if added)

### Testing
- [ ] Run load test to generate metrics
- [ ] Trigger test alerts (stop services temporarily)
- [ ] Verify notifications in all channels
- [ ] Check alert inhibition works correctly
- [ ] Validate dashboard updates during load

### Security
- [ ] Change Grafana default password
- [ ] Restrict Prometheus/AlertManager access
- [ ] Secure webhook URLs (use secrets)
- [ ] Enable HTTPS for Grafana (production)
- [ ] Set up RBAC roles in Grafana

### Documentation
- [ ] Document webhook URLs (securely)
- [ ] Create runbook for common alerts
- [ ] Share dashboard URLs with team
- [ ] Train team on alert response procedures
- [ ] Document custom alert thresholds

## Maintenance

### Daily Tasks
- Monitor active alerts: http://localhost:9093
- Check service health in Grafana
- Review critical alert notifications

### Weekly Tasks
- Review alert trends (false positives/negatives)
- Check Prometheus storage usage
- Validate backup retention policies
- Review dashboard usage (Grafana analytics)

### Monthly Tasks
- Audit alert rules (add/remove/tune thresholds)
- Review notification channels (add/remove team members)
- Update dashboards based on feedback
- Check for Prometheus/Grafana updates
- Test disaster recovery procedures

### Quarterly Tasks
- Comprehensive monitoring stack review
- Alert rule effectiveness analysis
- Dashboard redesign based on usage patterns
- Performance tuning (retention, query optimization)
- Security audit (rotate keys, review access)

## References

### Official Documentation
- Prometheus: https://prometheus.io/docs/
- AlertManager: https://prometheus.io/docs/alerting/latest/alertmanager/
- Grafana: https://grafana.com/docs/grafana/latest/
- PromQL: https://prometheus.io/docs/prometheus/latest/querying/basics/

### Internal Documentation
- Metrics Exporter: `backend/metrics/prometheus_exporter.py`
- Alert Rules: `monitoring/prometheus_rules/alert_rules.yml`
- AlertManager Config: `monitoring/alertmanager/alertmanager.yml`
- Grafana Dashboard: `monitoring/grafana/provisioning/dashboards/piyasa_chatbot_overview.json`

### Related Guides
- LLM Batch Generation: `docs/LLM_BATCH_GENERATION_GUIDE.md`
- Database Backup: `docs/DATABASE_BACKUP_AUTOMATION.md`
- PostgreSQL Migration: `docs/POSTGRESQL_MIGRATION_GUIDE.md`

---

*Generated with Claude Code - Session 38 (P2.2)*
*Status: Production-Ready*
*Stack: Prometheus 2.x + AlertManager 0.26+ + Grafana 10.x*
