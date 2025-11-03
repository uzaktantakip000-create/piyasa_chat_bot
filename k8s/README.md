# Kubernetes Manifests

Bu dizin piyasa_chat_bot uygulamasının Kubernetes deployment dosyalarını içerir.

## Dizin Yapısı

```
k8s/
├── base/                    # Temel Kubernetes kaynakları
│   ├── namespace.yaml       # Namespace tanımı
│   ├── configmap.yaml       # Yapılandırma değişkenleri
│   ├── secret.yaml          # Hassas veriler (API anahtarları)
│   ├── postgres-deployment.yaml  # PostgreSQL veritabanı
│   ├── redis-statefulset.yaml    # Redis cache
│   ├── api-deployment.yaml       # FastAPI uygulaması
│   ├── worker-statefulset.yaml   # Background worker'lar
│   ├── frontend-deployment.yaml  # React dashboard
│   ├── ingress.yaml              # Dış erişim routing
│   ├── hpa.yaml                  # Otomatik ölçeklendirme
│   └── kustomization.yaml        # Kustomize yapılandırması
├── overlays/
│   ├── dev/                 # Development ortamı
│   │   └── kustomization.yaml
│   └── prod/                # Production ortamı
│       ├── kustomization.yaml
│       └── ingress-tls.yaml
└── README.md

```

## Hızlı Başlangıç

### Prerequisites

1. Kubernetes cluster (1.24+)
2. kubectl CLI tool
3. (Opsiyonel) Kustomize 4.0+
4. NGINX Ingress Controller
5. (Opsiyonel) cert-manager (TLS sertifikaları için)

### Development Ortamında Deploy

```bash
# Namespace oluştur ve kaynakları deploy et
kubectl apply -k k8s/overlays/dev/

# Deploy durumunu kontrol et
kubectl get pods -n piyasa-chatbot-dev
kubectl get services -n piyasa-chatbot-dev
kubectl get ingress -n piyasa-chatbot-dev

# Log'ları görüntüle
kubectl logs -f deployment/dev-api -n piyasa-chatbot-dev
kubectl logs -f statefulset/dev-worker -n piyasa-chatbot-dev
```

### Production Ortamında Deploy

```bash
# Secret'ları oluştur (önce!)
kubectl create secret generic piyasa-secrets \
  --from-literal=OPENAI_API_KEY='your-openai-key' \
  --from-literal=API_KEY='your-master-api-key' \
  --from-literal=TOKEN_ENCRYPTION_KEY='your-encryption-key' \
  --namespace=piyasa-chatbot

# Deploy et
kubectl apply -k k8s/overlays/prod/

# Durumu kontrol et
kubectl get all -n piyasa-chatbot
```

## Secret'ları Yapılandırma

**ÖNEMLI**: `k8s/base/secret.yaml` dosyasındaki placeholder değerler production'da kullanılmamalı!

### Yöntem 1: kubectl ile oluştur

```bash
kubectl create secret generic piyasa-secrets \
  --from-literal=OPENAI_API_KEY='sk-...' \
  --from-literal=GROQ_API_KEY='gsk_...' \
  --from-literal=GEMINI_API_KEY='AIza...' \
  --from-literal=API_KEY='your-master-key' \
  --from-literal=TOKEN_ENCRYPTION_KEY='your-fernet-key' \
  --from-literal=DATABASE_PASSWORD='strong-password' \
  --from-literal=DEFAULT_ADMIN_USERNAME='admin' \
  --from-literal=DEFAULT_ADMIN_PASSWORD='strong-password' \
  --from-literal=DEFAULT_ADMIN_API_KEY='api-key' \
  --namespace=piyasa-chatbot
```

### Yöntem 2: .env dosyasından oluştur

```bash
kubectl create secret generic piyasa-secrets \
  --from-env-file=.env \
  --namespace=piyasa-chatbot
```

## Kaynaklar

| Kaynak | Tip | Replicas | Açıklama |
|--------|-----|----------|----------|
| api | Deployment | 2-10 | FastAPI REST API |
| worker | StatefulSet | 4-12 | Background message generator |
| frontend | Deployment | 2-6 | React dashboard |
| postgres | Deployment | 1 | PostgreSQL database |
| redis | StatefulSet | 1 | Redis cache |

## Auto-scaling

HorizontalPodAutoscaler (HPA) aktif:

- **API**: CPU %70, Memory %80 → 2-10 replicas
- **Worker**: CPU %75, Memory %85 → 4-12 replicas
- **Frontend**: CPU %70, Memory %75 → 2-6 replicas

## Storage

- **PostgreSQL**: 10Gi PersistentVolume
- **Redis**: 5Gi PersistentVolume (StatefulSet)

## Ingress & External Access

### Development
- Frontend: `http://dev.piyasa-chatbot.example.com`
- API: `http://api.dev.piyasa-chatbot.example.com`

### Production
- Frontend: `https://piyasa-chatbot.example.com`
- API: `https://api.piyasa-chatbot.example.com`

**TLS**: cert-manager ile Let's Encrypt sertifikası otomatik oluşturulur.

## Monitoring

```bash
# Pod durumunu izle
kubectl get pods -n piyasa-chatbot -w

# HPA ölçeklendirmeyi izle
kubectl get hpa -n piyasa-chatbot -w

# Resource kullanımını görüntüle
kubectl top pods -n piyasa-chatbot
kubectl top nodes
```

## Troubleshooting

### Pod başlamıyor

```bash
# Pod detaylarını kontrol et
kubectl describe pod <pod-name> -n piyasa-chatbot

# Log'ları kontrol et
kubectl logs <pod-name> -n piyasa-chatbot --previous

# Events'i kontrol et
kubectl get events -n piyasa-chatbot --sort-by='.lastTimestamp'
```

### Secret'lar yüklenmiyor

```bash
# Secret'ları listele
kubectl get secrets -n piyasa-chatbot

# Secret içeriğini görüntüle (base64 encoded)
kubectl get secret piyasa-secrets -n piyasa-chatbot -o yaml

# Secret'ı decode et
kubectl get secret piyasa-secrets -n piyasa-chatbot -o jsonpath='{.data.OPENAI_API_KEY}' | base64 -d
```

### Ingress çalışmıyor

```bash
# Ingress detaylarını kontrol et
kubectl describe ingress piyasa-ingress -n piyasa-chatbot

# NGINX Ingress Controller log'larını kontrol et
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx
```

## Upgrade & Rollback

```bash
# Yeni image ile deploy et
kubectl set image deployment/api api=ghcr.io/.../api:v2.0.0 -n piyasa-chatbot

# Rollout durumunu kontrol et
kubectl rollout status deployment/api -n piyasa-chatbot

# Rollback yap
kubectl rollout undo deployment/api -n piyasa-chatbot

# Rollout history'i görüntüle
kubectl rollout history deployment/api -n piyasa-chatbot
```

## Cleanup

```bash
# Development ortamını temizle
kubectl delete -k k8s/overlays/dev/

# Production ortamını temizle
kubectl delete -k k8s/overlays/prod/

# Namespace'i tamamen sil (tüm kaynakları siler)
kubectl delete namespace piyasa-chatbot
kubectl delete namespace piyasa-chatbot-dev
```

## Daha Fazla Bilgi

Detaylı deployment kılavuzu için `docs/K8S_DEPLOYMENT.md` dosyasına bakın.
