# Kubernetes Manifests — FastAPI App

These manifests deploy the sample FastAPI app from `../app/` to a local Kubernetes cluster (minikube).

## Files

| File | What it creates |
|------|----------------|
| `deployment.yaml` | 2-replica Deployment with startup, liveness, and readiness probes |
| `service.yaml` | ClusterIP Service exposing port 80 → pod port 8000 |
| `ingress.yaml` | nginx Ingress routing `fastapi-app.local` to the Service |

---

## Local Deploy Steps (minikube)

### 1. Start minikube with nginx Ingress enabled

```bash
minikube start
minikube addons enable ingress
```

### 2. Build the Docker image inside minikube's Docker daemon

```bash
# Point Docker CLI to minikube's daemon (fish shell: eval (minikube docker-env))
eval $(minikube docker-env)

# Build the image (from the app/ directory)
docker build -t fastapi-app:dev ../app/
```

### 3. Apply the manifests

```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml
```

### 4. Verify each layer

```bash
# Layer 6 — Pod is Running and Ready
kubectl get pods -l app=fastapi-app

# Layer 5 — Service has endpoints (pod IPs listed here)
kubectl get endpoints fastapi-app

# Layer 4 — Ingress has an Address assigned
kubectl get ingress fastapi-app

# See the nginx.conf the controller generated
kubectl exec -n ingress-nginx \
  $(kubectl get pods -n ingress-nginx -o name | head -1) \
  -- cat /etc/nginx/nginx.conf | grep -A 20 "fastapi-app.local"
```

### 5. Test via Ingress

```bash
# Add to /etc/hosts (or C:\Windows\System32\drivers\etc\hosts on Windows):
# <minikube ip>   fastapi-app.local

minikube ip   # get the IP to add to hosts

curl http://fastapi-app.local/
curl http://fastapi-app.local/health
curl http://fastapi-app.local/ready
```

---

## Troubleshooting Reference (8-layer model)

| Symptom | First check | Layer |
|---------|-------------|-------|
| `curl` connection refused | `minikube ip`, `kubectl get ingress` (address assigned?) | 4 |
| `curl` returns 404 | `kubectl get ingress` host matches `curl` Host header? | 4 |
| `curl` returns 503 | `kubectl get endpoints fastapi-app` — is list empty? | 5 |
| Endpoints empty | `kubectl get pods --show-labels` — does `app=fastapi-app` match? | 6 |
| Pods show 0/1 Ready | `kubectl describe pod <name>` → readiness/startup probe events | 6 |
| Pods CrashLoopBackOff | `kubectl logs <pod> --previous` | 7 |

---

## Probe Behavior Summary

```
Pod starts
    │
    ▼
startupProbe runs (/health every 5s, up to 60s)
    │ fails → container KILLED and restarted
    │ passes ↓
    ▼
livenessProbe starts (/health every 10s)   ←── fail 3× → container KILLED
readinessProbe starts (/ready every 5s)    ←── fail → removed from endpoints (NOT killed)
    │ readiness passes ↓
    ▼
Pod IP added to Service endpoints → traffic can flow
```

Key distinction:
- **Liveness failure** → container is killed and restarted (same pod, new container)
- **Readiness failure** → pod stays running, removed from traffic rotation
- **Startup probe running** → pod shows `0/1 Ready`, no traffic, NOT restarted yet
