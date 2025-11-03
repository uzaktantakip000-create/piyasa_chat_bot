# Kubernetes Manifests Validation Report

**Date**: 2025-11-03
**Reviewed By**: Claude Code (Session 36 - Detailed Validation)
**Files Reviewed**: 14 YAML files (base + overlays)
**Status**: ❌ **NOT READY FOR DEPLOYMENT**

---

## Executive Summary

A comprehensive review of all Kubernetes manifests revealed **26 issues** across 4 severity levels:

| Severity | Count | Description |
|----------|-------|-------------|
| **P0 - CRITICAL** | 4 | Application will not work |
| **P1 - HIGH** | 7 | Security vulnerabilities, data loss risk |
| **P2 - MEDIUM** | 13 | Best practice violations, stability issues |
| **P3 - LOW** | 2 | Minor improvements |

**❌ CRITICAL BLOCKERS**: Issues #17, #19, #20, #23/26 will cause deployment failure or broken functionality.

---

## P0 - CRITICAL Issues (Must Fix Before Deployment)

### Issue #17: WORKER_ID Logic Broken

**File**: `k8s/base/worker-statefulset.yaml:96-99`

**Problem**:
```yaml
- name: WORKER_ID
  valueFrom:
    fieldRef:
      fieldPath: metadata.name  # Returns "worker-0", "worker-1", etc.
```

Worker code expects integer `WORKER_ID` but receives string like `"worker-0"`:
```python
WORKER_ID = int(os.getenv("WORKER_ID"))  # ValueError: invalid literal for int()
```

**Impact**: **All worker pods crash immediately with ValueError**

**Fix**:
```yaml
# Option 1: Parse pod name in application
# Update worker.py to extract number from pod name

# Option 2: Use init container to calculate
initContainers:
- name: set-worker-id
  image: busybox
  command:
  - sh
  - -c
  - 'echo ${HOSTNAME##*-} > /shared/worker-id'
  volumeMounts:
  - name: shared
    mountPath: /shared

# Then read from file in main container
- name: WORKER_ID
  value: "$(cat /shared/worker-id)"
```

---

### Issue #19: Frontend API Connection Broken

**File**: `k8s/base/frontend-deployment.yaml:29-31`

**Problem**:
```yaml
env:
  - name: VITE_API_BASE_URL
    value: "http://api-service:8000"  # Runtime env var doesn't work!
```

Vite embeds `VITE_*` variables at **build time**, not runtime. Setting env var in pod has no effect.

**Impact**: **Frontend cannot connect to API, application unusable**

**Fix**:

Option 1 - Build-time configuration:
```dockerfile
# Dockerfile.frontend
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build
```

Option 2 - Runtime config with nginx:
```nginx
# Inject config at runtime
location / {
  sub_filter '</head>' '<script>window._env_={API_URL:"${API_URL}"}</script></head>';
  root /usr/share/nginx/html;
}
```

Option 3 - Environment-specific builds:
```bash
# Build dev image
docker build --build-arg VITE_API_BASE_URL=http://api.dev.example.com -t frontend:dev

# Build prod image
docker build --build-arg VITE_API_BASE_URL=https://api.example.com -t frontend:prod
```

---

### Issue #20: Infinite SSL Redirect Loop

**File**: `k8s/base/ingress.yaml:10-12, 49-54`

**Problem**:
```yaml
annotations:
  nginx.ingress.kubernetes.io/ssl-redirect: "true"
  nginx.ingress.kubernetes.io/force-ssl-redirect: "true"

spec:
  # tls:  # ← TLS configuration is commented out!
```

**Impact**: **Infinite redirect loop: HTTP → "redirect to HTTPS" → no TLS → error**

**Fix**:

Option 1 - Disable SSL redirect until TLS is configured:
```yaml
annotations:
  # nginx.ingress.kubernetes.io/ssl-redirect: "false"  # Disable until TLS ready
```

Option 2 - Enable TLS with cert-manager:
```yaml
spec:
  tls:
  - hosts:
    - api.piyasa-chatbot.example.com
    - piyasa-chatbot.example.com
    secretName: piyasa-tls-cert
```

---

### Issue #23 & #26: Worker HPA Breaks Coordination

**Files**:
- `k8s/base/hpa.yaml:47-90`
- `k8s/overlays/prod/kustomization.yaml:90-97, 104`

**Problem**:
```yaml
# HPA can scale to 24 workers
HorizontalPodAutoscaler:
  maxReplicas: 24

# But ConfigMap is static
ConfigMap:
  TOTAL_WORKERS: "6"  # Doesn't update when HPA scales!
```

**Impact**: **Worker coordination breaks when HPA scales**

Example scenario:
1. Start: 6 workers, TOTAL_WORKERS=6 ✓
2. HPA scales to 12 workers due to high CPU
3. All workers still see TOTAL_WORKERS=6
4. Result: Multiple workers process same messages, or some messages skipped

**Fix**:

Option 1 - Disable HPA for workers:
```yaml
# Remove worker-hpa from kustomization.yaml
resources:
  # - hpa.yaml  # Exclude worker HPA, keep only API and Frontend HPA
```

Option 2 - Dynamic TOTAL_WORKERS:
```python
# Update worker.py to count StatefulSet replicas dynamically
from kubernetes import client, config
config.load_incluster_config()
v1 = client.AppsV1Api()
statefulset = v1.read_namespaced_stateful_set("worker", "piyasa-chatbot")
TOTAL_WORKERS = statefulset.spec.replicas
```

Option 3 - Use ConfigMap dynamic update:
```yaml
# Use Kustomize replacement plugin (advanced)
# Or external controller to sync TOTAL_WORKERS with replica count
```

---

## P1 - HIGH Issues (Security/Data Risk)

### Issue #2: Database Password in Plain Text

**File**: `k8s/base/configmap.yaml:10`

**Problem**:
```yaml
DATABASE_URL: "postgresql://piyasa_user:piyasa_pass@db-service:5432/piyasa_db"
                                      ^^^^^^^^^^^
```

ConfigMaps are **not encrypted**. Anyone with namespace access can read the password.

**Impact**: **Security vulnerability - database credentials exposed**

**Fix**:
```yaml
# Option 1: Move to Secret
apiVersion: v1
kind: Secret
data:
  DATABASE_URL: <base64-encoded-full-url>

# Option 2: Construct URL from parts
env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: piyasa-secrets
        key: DATABASE_PASSWORD
  - name: DATABASE_URL
    value: "postgresql://piyasa_user:$(DB_PASSWORD)@db-service:5432/piyasa_db"
```

---

### Issue #4, #5, #6: Secret File Committed to Git

**Files**:
- `k8s/base/secret.yaml` (entire file)
- `k8s/base/kustomization.yaml:9`

**Problem**:
1. Secret file contains placeholder credentials
2. File is committed to Git repository
3. Referenced in kustomization.yaml

**Impact**:
- **Security best practice violation**
- Users may forget to change placeholders
- Git history exposes secret structure

**Fix**:
```bash
# 1. Remove from Git
git rm k8s/base/secret.yaml

# 2. Add to .gitignore
echo "k8s/base/secret.yaml" >> .gitignore

# 3. Create template
mv k8s/base/secret.yaml k8s/base/secret.yaml.template

# 4. Update kustomization.yaml
# Remove: - secret.yaml

# 5. Document manual secret creation
kubectl create secret generic piyasa-secrets \
  --from-literal=OPENAI_API_KEY='...' \
  --namespace=piyasa-chatbot
```

---

### Issue #12: Redis Has No Password

**File**: `k8s/base/redis-statefulset.yaml:44-50`

**Problem**:
```yaml
command:
  - redis-server
  - --appendonly
  - "yes"
  # Missing: --requirepass
```

Redis is accessible without authentication. Any pod can connect.

**Impact**: **Security vulnerability - unauthorized Redis access**

**Fix**:
```yaml
# 1. Add password to Secret
apiVersion: v1
kind: Secret
stringData:
  REDIS_PASSWORD: "strong-random-password"

# 2. Update Redis command
command:
  - redis-server
  - --appendonly
  - "yes"
  - --requirepass
  - "$(REDIS_PASSWORD)"

env:
  - name: REDIS_PASSWORD
    valueFrom:
      secretKeyRef:
        name: piyasa-secrets
        key: REDIS_PASSWORD

# 3. Update REDIS_URL in ConfigMap
REDIS_URL: "redis://:password@redis-service:6379/0"
```

---

### Issue #21: Ingress Rewrite Breaks API Paths

**File**: `k8s/base/ingress.yaml:10`

**Problem**:
```yaml
annotations:
  nginx.ingress.kubernetes.io/rewrite-target: /  # Global rewrite!
```

This rewrites **all paths** to `/`:
- Request: `GET api.example.com/api/bots`
- Rewritten: `GET api-service/` (path lost!)

**Impact**: **All API endpoints except root path return 404**

**Fix**:
```yaml
annotations:
  # Remove rewrite-target for host-based routing
  # nginx.ingress.kubernetes.io/rewrite-target: /  # DELETE THIS LINE
```

---

### Issue #22: CORS Allows All Origins

**File**: `k8s/base/ingress.yaml:19`

**Problem**:
```yaml
nginx.ingress.kubernetes.io/cors-allow-origin: "*"
```

Any website can make requests to your API (CSRF risk).

**Impact**: **Security vulnerability - CORS misconfiguration**

**Fix**:
```yaml
# Production: Whitelist specific origins
nginx.ingress.kubernetes.io/cors-allow-origin: "https://piyasa-chatbot.example.com"

# Or multiple:
nginx.ingress.kubernetes.io/cors-allow-origin: "https://piyasa-chatbot.example.com,https://admin.piyasa-chatbot.example.com"
```

---

## P2 - MEDIUM Issues (Best Practices)

### Issue #7 & #11: Missing storageClassName

**Files**:
- `k8s/base/postgres-deployment.yaml:8-13`
- `k8s/base/redis-statefulset.yaml:75-83`

**Problem**:
```yaml
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  # storageClassName: ???  # Missing!
```

Different clusters have different default storage classes. If no default exists, PVC stays "Pending".

**Impact**: **Database pods fail to start (PVC pending)**

**Fix**:
```yaml
spec:
  storageClassName: standard  # or gp2, gp3, premium-ssd, etc.
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

---

### Issue #8: PostgreSQL Using Deployment Instead of StatefulSet

**File**: `k8s/base/postgres-deployment.yaml:16-23`

**Problem**:
```yaml
kind: Deployment  # Wrong for stateful database!
```

Deployments are for stateless apps. Databases need:
- Stable network identity
- Ordered deployment/scaling
- Persistent volume affinity

**Impact**: **Potential data corruption during restarts/scaling**

**Fix**:
```yaml
apiVersion: apps/v1
kind: StatefulSet  # Changed from Deployment
metadata:
  name: postgres
spec:
  serviceName: db-service
  replicas: 1
  volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```

---

### Issue #9 & #10: Missing Security Context and fsGroup

**File**: `k8s/base/postgres-deployment.yaml:32-54`

**Problem**:
```yaml
spec:
  containers:
  - name: postgres
    # No securityContext!
```

Postgres may run as root, and volume permissions may fail.

**Impact**: **Security risk, potential permission errors**

**Fix**:
```yaml
spec:
  securityContext:
    fsGroup: 999  # PostgreSQL GID
    runAsUser: 999
    runAsNonRoot: true
  containers:
  - name: postgres
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop:
        - ALL
      readOnlyRootFilesystem: false  # Postgres needs write
```

---

### Issue #13: Missing MFA_SECRET Environment Variable

**File**: `k8s/base/api-deployment.yaml:82-121`

**Problem**:
```yaml
# Secret has DEFAULT_ADMIN_MFA_SECRET
# But API deployment doesn't inject it!
env:
  - name: DEFAULT_ADMIN_USERNAME  # ✓
  - name: DEFAULT_ADMIN_PASSWORD  # ✓
  - name: DEFAULT_ADMIN_API_KEY   # ✓
  # DEFAULT_ADMIN_MFA_SECRET ???   # ✗ Missing!
```

**Impact**: **TOTP MFA feature won't work**

**Fix**:
```yaml
- name: DEFAULT_ADMIN_MFA_SECRET
  valueFrom:
    secretKeyRef:
      name: piyasa-secrets
      key: DEFAULT_ADMIN_MFA_SECRET
```

---

### Issue #14: Using :latest Image Tag

**Files**: All deployments use `:latest`

**Problem**:
```yaml
image: ghcr.io/uzaktantakip000-create/piyasa_chat_bot/api:latest
```

**Impact**:
- Can't identify which version is deployed
- Different pods may run different versions
- Rollback is difficult

**Fix**:
```yaml
image: ghcr.io/uzaktantakip000-create/piyasa_chat_bot/api:v1.0.0
```

Use semantic versioning: `v1.0.0`, `v1.0.1`, `v1.1.0`

---

### Issue #15: Unclear imagePullSecrets

**Files**: All deployments have commented `imagePullSecrets`

**Problem**:
```yaml
# imagePullSecrets:
# - name: ghcr-secret
```

Is ghcr.io public or private? If private, pods will fail with `ImagePullBackOff`.

**Impact**: **Deployment may fail if registry is private**

**Fix**:

If public (no authentication needed):
```yaml
# Remove commented section, no imagePullSecrets needed
```

If private:
```yaml
imagePullSecrets:
- name: ghcr-secret

# And create secret:
# kubectl create secret docker-registry ghcr-secret \
#   --docker-server=ghcr.io \
#   --docker-username=<username> \
#   --docker-password=<token> \
#   --namespace=piyasa-chatbot
```

---

### Issue #16 & #18: Missing Security Context & Health Checks

**Files**:
- `k8s/base/api-deployment.yaml:21-44`
- `k8s/base/worker-statefulset.yaml:22-106`

**Problem**:
- No `securityContext` (runs as root)
- Worker has no liveness/readiness probes

**Impact**: **Security risk, worker failures undetected**

**Fix**:
```yaml
# Security context
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
  containers:
  - securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop:
        - ALL
      readOnlyRootFilesystem: true

# Worker health check
livenessProbe:
  exec:
    command:
    - python
    - -c
    - "import sys; sys.exit(0)"  # Simple check
  initialDelaySeconds: 60
  periodSeconds: 30
```

---

### Issue #24: Secret.yaml in Kustomization

**File**: `k8s/base/kustomization.yaml:9`

**Problem**:
```yaml
resources:
  - secret.yaml  # Should not be in production kustomization
```

**Impact**: **Encourages bad security practices**

**Fix**:
```yaml
resources:
  # - secret.yaml  # Users should create secrets manually
```

---

### Issue #25: Incorrect Comment (HPA Not Disabled)

**File**: `k8s/overlays/dev/kustomization.yaml:53-62`

**Problem**:
```yaml
# Disable HPA in dev  ← This comment is WRONG!
- target:
    kind: HorizontalPodAutoscaler
  patch: |-
    - op: replace
      path: /spec/minReplicas
      value: 1
```

HPA is still active, just with lower limits.

**Impact**: **Misleading documentation**

**Fix**:
```yaml
# Reduce HPA limits for dev  ← Corrected comment
```

---

## P3 - LOW Issues (Minor Improvements)

### Issue #1: Environment Label in Base Namespace

**File**: `k8s/base/namespace.yaml:7`

**Problem**:
```yaml
labels:
  environment: production  # Base file shouldn't have env-specific labels
```

**Fix**:
```yaml
# Remove from base, add in overlays
labels:
  app: piyasa-chatbot
  # environment: production  # Remove this
```

---

### Issue #3: Redis Service Name for Headless Service

**File**: `k8s/base/configmap.yaml:13`

**Problem**:
```yaml
REDIS_URL: "redis://redis-service:6379/0"
```

For headless service with StatefulSet, format may need to be:
```yaml
REDIS_URL: "redis://redis-0.redis-service:6379/0"
```

**Fix**: Test both formats, verify which works.

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Total Issues | 26 |
| Critical (P0) | 4 |
| High (P1) | 7 |
| Medium (P2) | 13 |
| Low (P3) | 2 |

**Files with Issues**:
- namespace.yaml: 1 issue
- configmap.yaml: 2 issues
- secret.yaml: 3 issues
- postgres-deployment.yaml: 5 issues
- redis-statefulset.yaml: 3 issues
- api-deployment.yaml: 4 issues
- worker-statefulset.yaml: 3 issues
- frontend-deployment.yaml: 2 issues
- ingress.yaml: 3 issues
- hpa.yaml: 2 issues
- kustomization.yaml: 2 issues

---

## Recommendation

**DO NOT DEPLOY** until P0 and P1 issues are fixed.

**Next Steps**:
1. Fix all P0 issues (4 critical blockers)
2. Fix all P1 issues (7 security/data risks)
3. Consider fixing P2 issues (13 best practices)
4. Test deployment in local Kubernetes cluster
5. Validate all fixes work correctly
6. Update documentation with known limitations

**Estimated Fix Time**:
- P0 fixes: 4-6 hours
- P1 fixes: 3-4 hours
- P2 fixes: 4-6 hours
- Testing: 4-8 hours
- **Total**: 15-24 hours of work

---

*Generated: 2025-11-03 by Claude Code (Session 36)*
