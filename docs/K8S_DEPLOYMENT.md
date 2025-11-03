# Kubernetes Deployment Guide

**Last Updated**: 2025-11-03
**Version**: 1.0
**Status**: Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Architecture](#architecture)
4. [Deployment Procedures](#deployment-procedures)
5. [Configuration](#configuration)
6. [Scaling & Auto-scaling](#scaling--auto-scaling)
7. [Monitoring & Observability](#monitoring--observability)
8. [Maintenance](#maintenance)
9. [Troubleshooting](#troubleshooting)
10. [Security](#security)
11. [Disaster Recovery](#disaster-recovery)
12. [Appendices](#appendices)

---

## Overview

### Purpose

This document provides comprehensive instructions for deploying the **piyasa_chat_bot** application to Kubernetes. It covers everything from initial setup to production operations.

### Benefits of Kubernetes Deployment

| Feature | Docker Compose | Kubernetes |
|---------|---------------|------------|
| Auto-scaling | ❌ Manual | ✅ HPA (CPU/Memory based) |
| Self-healing | ❌ Limited | ✅ Automatic pod restart |
| Rolling updates | ❌ Manual | ✅ Zero-downtime updates |
| Load balancing | ❌ External | ✅ Built-in Service LB |
| Secret management | ❌ .env files | ✅ Native Secrets |
| Multi-environment | ❌ Multiple files | ✅ Kustomize overlays |
| Resource limits | ✅ Basic | ✅ Advanced QoS |
| Health checks | ✅ Basic | ✅ Liveness + Readiness |

### Deployment Models

1. **Development** (`k8s/overlays/dev/`):
   - Minimal resources
   - 1 API, 2 Workers, 1 Frontend
   - Debug logging
   - Local storage

2. **Production** (`k8s/overlays/prod/`):
   - High availability
   - 3+ API, 6+ Workers, 3+ Frontend
   - Auto-scaling enabled
   - TLS/HTTPS enforced
   - Persistent storage with backups

---

## Prerequisites

### Required Tools

| Tool | Version | Purpose | Installation |
|------|---------|---------|--------------|
| kubectl | 1.24+ | Kubernetes CLI | [Install kubectl](https://kubernetes.io/docs/tasks/tools/) |
| Kubernetes | 1.24+ | Container orchestration | Minikube / K3s / Cloud provider |
| Kustomize | 4.0+ | Configuration management | Built into kubectl 1.14+ |
| Docker | 20.10+ | Container images | [Install Docker](https://docs.docker.com/get-docker/) |

### Optional Tools

- **Helm** (3.0+): Alternative to Kustomize
- **k9s**: Terminal UI for Kubernetes
- **kubectx/kubens**: Context and namespace switching
- **stern**: Multi-pod log tailing

### Kubernetes Cluster Requirements

**Minimum Specifications**:
- 3 worker nodes (recommended)
- 8 GB RAM per node
- 4 CPU cores per node
- 50 GB storage

**Cloud Providers** (tested):
- ✅ AWS EKS (Elastic Kubernetes Service)
- ✅ Google GKE (Google Kubernetes Engine)
- ✅ Azure AKS (Azure Kubernetes Service)
- ✅ DigitalOcean DOKS
- ✅ Local: Minikube, Kind, K3s

### Required Add-ons

1. **NGINX Ingress Controller**:
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml
   ```

2. **Metrics Server** (for HPA):
   ```bash
   kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
   ```

3. **cert-manager** (optional, for TLS):
   ```bash
   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
   ```

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                │
│                                                       │
│  ┌─────────────┐        ┌─────────────┐             │
│  │   Ingress   │────────│   Frontend  │ (2-6 pods)  │
│  │  Controller │        │  Deployment │             │
│  └─────────────┘        └─────────────┘             │
│         │                                            │
│         │               ┌─────────────┐             │
│         └───────────────│     API     │ (2-10 pods) │
│                         │  Deployment │             │
│                         └─────────────┘             │
│                                │                     │
│         ┌──────────────────────┼──────────────────┐ │
│         │                      │                  │ │
│  ┌──────▼─────┐       ┌────────▼────┐   ┌────────▼───┐
│  │  Worker-0  │       │  Worker-1   │   │  Worker-N  │
│  │ StatefulSet│       │StatefulSet  │   │StatefulSet │
│  └────────────┘       └─────────────┘   └────────────┘
│         │                      │                  │    │
│         └──────────────────────┼──────────────────┘    │
│                                │                        │
│         ┌──────────────────────┼──────────────────┐    │
│         │                      │                  │    │
│  ┌──────▼─────┐       ┌────────▼────┐   ┌────────▼───┐
│  │ PostgreSQL │       │    Redis    │   │    PVC     │
│  │ Deployment │       │ StatefulSet │   │  Storage   │
│  └────────────┘       └─────────────┘   └────────────┘
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Kubernetes Resources

| Resource Type | Name | Purpose | Replicas |
|--------------|------|---------|----------|
| Namespace | piyasa-chatbot | Isolation | 1 |
| ConfigMap | piyasa-config | Non-sensitive config | 1 |
| Secret | piyasa-secrets | API keys, passwords | 1 |
| Deployment | api | FastAPI REST API | 2-10 |
| StatefulSet | worker | Background workers | 4-12 |
| Deployment | frontend | React dashboard | 2-6 |
| Deployment | postgres | PostgreSQL DB | 1 |
| StatefulSet | redis | Redis cache | 1 |
| Service | api-service | API load balancer | 1 |
| Service | frontend-service | Frontend LB | 1 |
| Service | db-service | DB internal access | 1 |
| Service | redis-service | Redis access | 1 |
| Ingress | piyasa-ingress | External routing | 1 |
| HPA | api-hpa | API auto-scaling | 1 |
| HPA | worker-hpa | Worker auto-scaling | 1 |
| HPA | frontend-hpa | Frontend auto-scaling | 1 |
| PVC | postgres-pvc | DB storage | 10Gi |
| PVC | redis-data-N | Redis storage | 5Gi |

---

## Deployment Procedures

### Procedure 1: Initial Setup (First-Time Deployment)

**Target Environment**: Development or Production

**Steps**:

#### 1. Clone Repository

```bash
git clone https://github.com/uzaktantakip000-create/piyasa_chat_bot.git
cd piyasa_chat_bot
```

#### 2. Configure Secrets

Create a `.env` file with your credentials:

```bash
# .env
OPENAI_API_KEY=sk-your-openai-key-here
GROQ_API_KEY=gsk_your-groq-key-here
GEMINI_API_KEY=AIza_your-gemini-key-here
API_KEY=your-master-api-key
TOKEN_ENCRYPTION_KEY=your-fernet-encryption-key
DATABASE_PASSWORD=strong-postgres-password
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=change-me-in-production
DEFAULT_ADMIN_API_KEY=admin-api-key-here
DEFAULT_ADMIN_MFA_SECRET=your-totp-secret
```

**Generate Encryption Key**:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

#### 3. Create Kubernetes Secret

```bash
# Development
kubectl create namespace piyasa-chatbot-dev
kubectl create secret generic piyasa-secrets \
  --from-env-file=.env \
  --namespace=piyasa-chatbot-dev

# Production
kubectl create namespace piyasa-chatbot
kubectl create secret generic piyasa-secrets \
  --from-env-file=.env \
  --namespace=piyasa-chatbot
```

#### 4. Update ConfigMap (Optional)

Edit `k8s/base/configmap.yaml` to customize:
- Database URL pattern
- LLM model selection
- Log level
- Total workers

#### 5. Deploy Application

**Development**:
```bash
kubectl apply -k k8s/overlays/dev/
```

**Production**:
```bash
kubectl apply -k k8s/overlays/prod/
```

#### 6. Verify Deployment

```bash
# Check pod status
kubectl get pods -n piyasa-chatbot-dev -w

# Expected output (dev):
# NAME                           READY   STATUS    RESTARTS   AGE
# dev-api-7b8f9d5c6d-abcde       1/1     Running   0          2m
# dev-frontend-6c4d8e7f9g-xyz12  1/1     Running   0          2m
# dev-postgres-5a7b9c8d6e-123ab  1/1     Running   0          2m
# dev-redis-0                    1/1     Running   0          2m
# dev-worker-0                   1/1     Running   0          2m
# dev-worker-1                   1/1     Running   0          2m

# Check services
kubectl get svc -n piyasa-chatbot-dev

# Check ingress
kubectl get ingress -n piyasa-chatbot-dev
```

#### 7. Access Application

**Development** (if using port-forward):
```bash
# API
kubectl port-forward -n piyasa-chatbot-dev svc/dev-api-service 8000:8000

# Frontend
kubectl port-forward -n piyasa-chatbot-dev svc/dev-frontend-service 5173:5173
```

Visit:
- Frontend: `http://localhost:5173`
- API Docs: `http://localhost:8000/docs`

**Production** (via Ingress):
- Frontend: `https://piyasa-chatbot.example.com`
- API: `https://api.piyasa-chatbot.example.com`

**Expected Duration**: 5-10 minutes

---

### Procedure 2: Update Existing Deployment

**When to Use**: Deploy new version, update configuration

**Steps**:

#### 1. Update Docker Images

```bash
# Build and push new images
docker build -f Dockerfile.api -t ghcr.io/uzaktantakip000-create/piyasa_chat_bot/api:v2.0.0 .
docker push ghcr.io/uzaktantakip000-create/piyasa_chat_bot/api:v2.0.0
```

#### 2. Update Deployment with New Image

```bash
# Update API
kubectl set image deployment/api \
  api=ghcr.io/uzaktantakip000-create/piyasa_chat_bot/api:v2.0.0 \
  -n piyasa-chatbot

# Update Worker
kubectl set image statefulset/worker \
  worker=ghcr.io/uzaktantakip000-create/piyasa_chat_bot/api:v2.0.0 \
  -n piyasa-chatbot
```

#### 3. Monitor Rollout

```bash
# Watch rollout status
kubectl rollout status deployment/api -n piyasa-chatbot
kubectl rollout status statefulset/worker -n piyasa-chatbot

# Check pod health
kubectl get pods -n piyasa-chatbot -w
```

#### 4. Verify Update Success

```bash
# Check new version
kubectl describe pod <api-pod-name> -n piyasa-chatbot | grep Image:

# Test API health
curl https://api.piyasa-chatbot.example.com/healthz
```

#### 5. Rollback (if needed)

```bash
# Rollback to previous version
kubectl rollout undo deployment/api -n piyasa-chatbot

# Check rollback status
kubectl rollout status deployment/api -n piyasa-chatbot
```

**Expected Duration**: 2-5 minutes (zero downtime)

---

### Procedure 3: Scale Application

**When to Use**: Handle increased load, reduce costs

**Manual Scaling**:

```bash
# Scale API
kubectl scale deployment/api --replicas=5 -n piyasa-chatbot

# Scale Workers
kubectl scale statefulset/worker --replicas=8 -n piyasa-chatbot

# Scale Frontend
kubectl scale deployment/frontend --replicas=4 -n piyasa-chatbot
```

**Auto-scaling (HPA)**:

HPA is pre-configured in `k8s/base/hpa.yaml`:

```yaml
# API: 2-10 replicas based on 70% CPU, 80% Memory
# Worker: 4-12 replicas based on 75% CPU, 85% Memory
# Frontend: 2-6 replicas based on 70% CPU, 75% Memory
```

Monitor HPA:
```bash
kubectl get hpa -n piyasa-chatbot -w
```

**Expected Duration**: Instant (manual), 1-5 min (HPA)

---

## Configuration

### ConfigMap Configuration

Edit `k8s/base/configmap.yaml` or use Kustomize patches:

**Common Settings**:
```yaml
DATABASE_URL: "postgresql://user:pass@db-service:5432/db"
REDIS_URL: "redis://redis-service:6379/0"
LLM_PROVIDER: "openai"
LLM_MODEL: "gpt-4o-mini"
LOG_LEVEL: "INFO"
TOTAL_WORKERS: "4"
```

**Apply Changes**:
```bash
kubectl apply -k k8s/overlays/prod/
kubectl rollout restart deployment/api -n piyasa-chatbot
```

### Secret Management

**Best Practices**:
1. ❌ Never commit secrets to Git
2. ✅ Use `kubectl create secret` from `.env`
3. ✅ Use external secret managers (AWS Secrets Manager, Vault)
4. ✅ Rotate secrets regularly
5. ✅ Encrypt secrets at rest (enable in cluster config)

**Rotate Secrets**:
```bash
# Delete old secret
kubectl delete secret piyasa-secrets -n piyasa-chatbot

# Create new secret
kubectl create secret generic piyasa-secrets --from-env-file=.env.new -n piyasa-chatbot

# Restart pods to pick up new secret
kubectl rollout restart deployment/api -n piyasa-chatbot
kubectl rollout restart statefulset/worker -n piyasa-chatbot
```

### Environment-Specific Configuration

**Development** (`k8s/overlays/dev/kustomization.yaml`):
- LOG_LEVEL=DEBUG
- TOTAL_WORKERS=2
- Reduced replicas and resource limits

**Production** (`k8s/overlays/prod/kustomization.yaml`):
- LOG_LEVEL=INFO
- TOTAL_WORKERS=6
- Increased replicas and resource limits
- TLS enabled

---

## Scaling & Auto-scaling

### Horizontal Pod Autoscaler (HPA)

**Configuration** (`k8s/base/hpa.yaml`):

| Component | Min | Max | CPU Target | Memory Target |
|-----------|-----|-----|------------|---------------|
| API | 2 | 10 | 70% | 80% |
| Worker | 4 | 12 | 75% | 85% |
| Frontend | 2 | 6 | 70% | 75% |

**Scale-Up Policy**:
- 100% increase or +2 pods per 30 seconds (whichever is higher)
- Stabilization: 60 seconds

**Scale-Down Policy**:
- 50% decrease per 60 seconds
- Stabilization: 300 seconds (API/Frontend), 600 seconds (Worker)

**Monitor Scaling**:
```bash
# Watch HPA in real-time
kubectl get hpa -n piyasa-chatbot -w

# Example output:
# NAME         REFERENCE        TARGETS          MINPODS   MAXPODS   REPLICAS
# api-hpa      Deployment/api   45%/70%, 60%/80% 2         10        3
# worker-hpa   StatefulSet/...  80%/75%, 70%/85% 4         12        6
```

**Load Testing** (trigger auto-scaling):
```bash
# Install hey (HTTP load generator)
go install github.com/rakyll/hey@latest

# Generate load on API
hey -z 5m -c 50 -q 10 https://api.piyasa-chatbot.example.com/healthz

# Watch HPA scale up
kubectl get hpa -n piyasa-chatbot -w
```

### Vertical Pod Autoscaler (VPA) - Optional

For automatic resource request/limit tuning:

```bash
# Install VPA
git clone https://github.com/kubernetes/autoscaler.git
cd autoscaler/vertical-pod-autoscaler
./hack/vpa-up.sh
```

**VPA Example** (create `api-vpa.yaml`):
```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: api-vpa
  namespace: piyasa-chatbot
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  updatePolicy:
    updateMode: "Auto"
```

---

## Monitoring & Observability

### Pod Monitoring

```bash
# Get all pods
kubectl get pods -n piyasa-chatbot

# Watch pod status in real-time
kubectl get pods -n piyasa-chatbot -w

# Get pod details
kubectl describe pod <pod-name> -n piyasa-chatbot

# View pod logs
kubectl logs -f <pod-name> -n piyasa-chatbot

# View previous pod logs (if crashed)
kubectl logs <pod-name> -n piyasa-chatbot --previous

# Tail logs from multiple pods
kubectl logs -f -l app=piyasa-api -n piyasa-chatbot --tail=100
```

### Resource Usage

```bash
# Install metrics-server first
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# View pod resource usage
kubectl top pods -n piyasa-chatbot

# View node resource usage
kubectl top nodes

# Example output:
# NAME              CPU(cores)   MEMORY(bytes)
# api-abc123        150m         512Mi
# worker-0          800m         1.5Gi
# worker-1          750m         1.4Gi
```

### Events & Debugging

```bash
# Get recent events
kubectl get events -n piyasa-chatbot --sort-by='.lastTimestamp'

# Describe resource for events
kubectl describe pod <pod-name> -n piyasa-chatbot
kubectl describe deployment api -n piyasa-chatbot
kubectl describe hpa api-hpa -n piyasa-chatbot

# Execute command inside pod
kubectl exec -it <pod-name> -n piyasa-chatbot -- /bin/sh
kubectl exec -it <pod-name> -n piyasa-chatbot -- python preflight.py
```

### Prometheus & Grafana Integration

The application exposes Prometheus metrics at `/metrics`.

**Deploy Prometheus Stack** (recommended):
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace
```

**ServiceMonitor** for API (create `api-servicemonitor.yaml`):
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: piyasa-api-metrics
  namespace: piyasa-chatbot
spec:
  selector:
    matchLabels:
      app: piyasa-api
  endpoints:
  - port: http
    path: /metrics
```

---

## Maintenance

### Database Migrations

**Run Alembic Migrations**:

```bash
# Create migration job
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration
  namespace: piyasa-chatbot
spec:
  template:
    spec:
      containers:
      - name: migration
        image: ghcr.io/uzaktantakip000-create/piyasa_chat_bot/api:latest
        command: ["python", "-m", "alembic", "upgrade", "head"]
        envFrom:
        - configMapRef:
            name: piyasa-config
        - secretRef:
            name: piyasa-secrets
      restartPolicy: Never
  backoffLimit: 3
EOF

# Watch job status
kubectl get job db-migration -n piyasa-chatbot -w

# View migration logs
kubectl logs job/db-migration -n piyasa-chatbot
```

### Database Backups

**Automated Backups via CronJob**:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: db-backup
  namespace: piyasa-chatbot
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: ghcr.io/uzaktantakip000-create/piyasa_chat_bot/api:latest
            command: ["python", "scripts/backup_database.py"]
            envFrom:
            - configMapRef:
                name: piyasa-config
            - secretRef:
                name: piyasa-secrets
            volumeMounts:
            - name: backup-storage
              mountPath: /backups
          volumes:
          - name: backup-storage
            persistentVolumeClaim:
              claimName: backup-pvc
          restartPolicy: OnFailure
```

**Manual Backup**:
```bash
kubectl exec -it <postgres-pod> -n piyasa-chatbot -- \
  pg_dump -U piyasa_user piyasa_db | gzip > backup-$(date +%Y%m%d).sql.gz
```

### Certificate Renewal (TLS)

If using cert-manager:

```bash
# Check certificate status
kubectl get certificate -n piyasa-chatbot

# Force renewal
kubectl delete certificate piyasa-tls-cert -n piyasa-chatbot
kubectl apply -k k8s/overlays/prod/
```

### Cleanup Old Resources

```bash
# Delete completed jobs (older than 7 days)
kubectl delete job -n piyasa-chatbot --field-selector status.successful=1 \
  --ignore-not-found=true

# Delete failed pods (older than 1 day)
kubectl delete pod -n piyasa-chatbot --field-selector status.phase=Failed \
  --ignore-not-found=true
```

---

## Troubleshooting

### Pod CrashLoopBackOff

**Symptoms**: Pod keeps restarting

**Diagnosis**:
```bash
kubectl describe pod <pod-name> -n piyasa-chatbot
kubectl logs <pod-name> -n piyasa-chatbot --previous
```

**Common Causes**:
1. Missing environment variables (check Secret/ConfigMap)
2. Database connection failure (check DATABASE_URL)
3. Invalid API keys (check Secret values)
4. OOMKilled (increase memory limits)

**Fix**:
```bash
# Increase memory limits
kubectl patch deployment api -n piyasa-chatbot -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"2Gi"}}}]}}}}'
```

### Ingress Not Working

**Symptoms**: Cannot access application via domain

**Diagnosis**:
```bash
kubectl describe ingress piyasa-ingress -n piyasa-chatbot
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx
```

**Common Causes**:
1. Ingress controller not installed
2. DNS not configured
3. TLS certificate issue

**Fix**:
```bash
# Install NGINX Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/cloud/deploy.yaml

# Check DNS propagation
nslookup api.piyasa-chatbot.example.com
```

### Database Connection Failures

**Symptoms**: API logs show `OperationalError: could not connect to server`

**Diagnosis**:
```bash
# Check DB pod status
kubectl get pod -n piyasa-chatbot -l app=postgres

# Check DB service
kubectl get svc db-service -n piyasa-chatbot

# Test connection from API pod
kubectl exec -it <api-pod> -n piyasa-chatbot -- \
  python -c "from database import engine; engine.connect()"
```

**Common Causes**:
1. DB pod not running
2. Wrong DATABASE_URL in ConfigMap
3. Wrong password in Secret

**Fix**:
```bash
# Restart DB pod
kubectl rollout restart deployment/postgres -n piyasa-chatbot

# Verify DATABASE_URL
kubectl get configmap piyasa-config -n piyasa-chatbot -o yaml
```

### HPA Not Scaling

**Symptoms**: HPA shows `<unknown>` for metrics

**Diagnosis**:
```bash
kubectl describe hpa api-hpa -n piyasa-chatbot
kubectl top pods -n piyasa-chatbot
```

**Common Causes**:
1. Metrics server not installed
2. Resource requests not set
3. Insufficient load

**Fix**:
```bash
# Install metrics-server
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Verify metrics available
kubectl top nodes
kubectl top pods -n piyasa-chatbot
```

### Out of Disk Space

**Symptoms**: Pods evicted, PVCs full

**Diagnosis**:
```bash
# Check PVC usage
kubectl exec -it <postgres-pod> -n piyasa-chatbot -- df -h

# Check node disk usage
kubectl describe node <node-name>
```

**Fix**:
```bash
# Resize PVC (if StorageClass supports it)
kubectl patch pvc postgres-pvc -n piyasa-chatbot -p \
  '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'

# Or create new larger PVC and migrate
```

---

## Security

### Network Policies

Restrict inter-pod communication:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-network-policy
  namespace: piyasa-chatbot
spec:
  podSelector:
    matchLabels:
      app: piyasa-api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: piyasa-frontend
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
```

### Pod Security Standards

Apply security context:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: api
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 2000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: api
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop:
        - ALL
      readOnlyRootFilesystem: true
```

### RBAC Configuration

Create service account with minimal permissions:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: piyasa-api-sa
  namespace: piyasa-chatbot
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: piyasa-api-role
  namespace: piyasa-chatbot
rules:
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: piyasa-api-rolebinding
  namespace: piyasa-chatbot
subjects:
- kind: ServiceAccount
  name: piyasa-api-sa
roleRef:
  kind: Role
  name: piyasa-api-role
  apiGroup: rbac.authorization.k8s.io
```

---

## Disaster Recovery

### Backup Strategy

**What to Backup**:
1. Database (PostgreSQL)
2. Redis persistent data
3. Kubernetes manifests (Git)
4. Secrets (external vault)

**Automated Backups**:
- CronJob for database backups (see Maintenance section)
- Velero for cluster-level backups
- Git for manifest version control

**Install Velero**:
```bash
velero install \
  --provider aws \
  --bucket piyasa-k8s-backups \
  --backup-location-config region=us-east-1 \
  --snapshot-location-config region=us-east-1
```

**Create Backup**:
```bash
# Backup entire namespace
velero backup create piyasa-backup --include-namespaces piyasa-chatbot

# Verify backup
velero backup describe piyasa-backup
```

**Restore from Backup**:
```bash
# Restore namespace
velero restore create --from-backup piyasa-backup

# Monitor restore
velero restore describe <restore-name>
```

### Multi-Region Deployment

For high availability across regions:

1. Deploy to multiple Kubernetes clusters (different regions)
2. Use external DNS for multi-region routing
3. Replicate PostgreSQL using streaming replication
4. Use cloud provider's global load balancer

---

## Appendices

### Appendix A: Resource Requirements

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-----------|-------------|-----------|----------------|--------------|
| API (dev) | 250m | 500m | 256Mi | 512Mi |
| API (prod) | 500m | 2000m | 512Mi | 2Gi |
| Worker (dev) | 500m | 1000m | 512Mi | 1Gi |
| Worker (prod) | 1000m | 4000m | 1Gi | 4Gi |
| Frontend | 100m | 500m | 128Mi | 512Mi |
| PostgreSQL | 250m | 1000m | 256Mi | 1Gi |
| Redis | 100m | 500m | 128Mi | 512Mi |

### Appendix B: Port Mapping

| Service | Internal Port | External Port | Protocol |
|---------|--------------|---------------|----------|
| API | 8000 | 80/443 (via Ingress) | HTTP/HTTPS |
| Frontend | 5173 | 80/443 (via Ingress) | HTTP/HTTPS |
| PostgreSQL | 5432 | - (internal only) | TCP |
| Redis | 6379 | - (internal only) | TCP |

### Appendix C: Useful kubectl Commands

```bash
# Get all resources in namespace
kubectl get all -n piyasa-chatbot

# Get resource usage
kubectl top pods -n piyasa-chatbot
kubectl top nodes

# Port forward to pod
kubectl port-forward <pod-name> 8000:8000 -n piyasa-chatbot

# Execute command in pod
kubectl exec -it <pod-name> -n piyasa-chatbot -- /bin/bash

# Copy files to/from pod
kubectl cp <pod-name>:/path/to/file ./local-file -n piyasa-chatbot
kubectl cp ./local-file <pod-name>:/path/to/file -n piyasa-chatbot

# Restart deployment
kubectl rollout restart deployment/api -n piyasa-chatbot

# View rollout history
kubectl rollout history deployment/api -n piyasa-chatbot

# Scale deployment
kubectl scale deployment/api --replicas=5 -n piyasa-chatbot

# Delete pod (will be recreated by Deployment)
kubectl delete pod <pod-name> -n piyasa-chatbot
```

### Appendix D: Kustomize Commands

```bash
# Preview generated manifests (dev)
kubectl kustomize k8s/overlays/dev/

# Apply with kustomize (dev)
kubectl apply -k k8s/overlays/dev/

# Delete with kustomize (dev)
kubectl delete -k k8s/overlays/dev/

# Diff before applying
kubectl diff -k k8s/overlays/prod/
```

### Appendix E: Health Check Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| GET /healthz | Liveness probe | 200 OK |
| GET /readyz | Readiness probe | 200 OK (when DB connected) |
| GET /metrics | Prometheus metrics | 200 OK (Prometheus format) |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-03 | Claude Code (Session 36) | Initial K8s deployment guide |

---

*This document should be reviewed quarterly and updated after each major Kubernetes version upgrade or architecture change.*
