# Files, Environment Variables & Runtime Config — Reference Notes

**Topic:** Day 3 — Config layer mechanics  
**Covers:** /proc filesystem, env var inheritance, ConfigMaps, Secrets, volume mounts, config precedence

---

## Core Mental Model

```
Process runtime context = env vars + mounted files + command-line flags
                          ↑           ↑                  ↑
                    From K8s     From K8s            From K8s
                  ConfigMap/    ConfigMap/           Deployment
                   Secret        Secret              spec.args
```

Before your app's first line of code runs, Kubernetes has already injected everything into the process's environment. If the value is wrong or missing there, no app-level logic fixes it.

---

## Section 1: The /proc Filesystem

### Structure
```
/proc/
  <PID>/
    environ     ← env vars at process start (null-byte delimited)
    cmdline     ← exact startup command (null-byte delimited)
    fd/         ← open file descriptors (symlinks to actual files/sockets)
    status      ← process state, memory, PID, PPID
    limits      ← ulimits in effect
    cgroup      ← which cgroup this process belongs to
    net/
      tcp       ← TCP connections (hex IPs)
      tcp6      ← IPv6 TCP connections
  meminfo       ← system-wide memory
  cpuinfo       ← CPU info
  loadavg       ← system load
```

### Key /proc Commands
```bash
# See a process's environment at startup:
cat /proc/<PID>/environ | tr '\0' '\n'

# See exact startup command:
cat /proc/<PID>/cmdline | tr '\0' ' '

# List open file descriptors:
ls -la /proc/<PID>/fd/

# See memory usage:
cat /proc/<PID>/status | grep -E "VmRSS|VmSize|VmPeak"

# See cgroup membership:
cat /proc/<PID>/cgroup

# From inside a Kubernetes pod (PID 1 = your app):
kubectl exec -it <pod> -- cat /proc/1/environ | tr '\0' '\n'
kubectl exec -it <pod> -- cat /proc/1/cmdline | tr '\0' ' '
```

### /proc/1 Inside a Container
Inside a container, PID 1 is whatever your `CMD` or `ENTRYPOINT` specifies. In our FastAPI case:
```
/proc/1/cmdline → uvicorn main:app --host 0.0.0.0 --port 8000
/proc/1/environ → all K8s-injected env vars
```

---

## Section 2: Environment Variables

### Inheritance Model
```
Kernel (PID 0 conceptual)
  └─ systemd (PID 1, bare metal)
       └─ kubelet (inherits node env)
            └─ containerd
                 └─ container (K8s injects env here via spec.containers.env)
                      └─ your app process (copies K8s-injected env)
                           └─ worker threads (share process env, not separate copies)
```

**Rule:** Each fork creates a copy. Child cannot modify parent's env. Copy flows down only.

### Setting Env Vars — All Methods
```bash
# Current shell only (not exported to children):
DB_HOST=localhost

# Current shell + all children spawned from this shell:
export DB_HOST=localhost

# Single command only (cleanest for testing):
DB_HOST=localhost APP_ENV=staging uvicorn main:app

# Permanent for user (requires new shell or `source`):
echo 'export DB_HOST=localhost' >> ~/.bashrc
source ~/.bashrc

# Permanent system-wide:
echo 'DB_HOST=localhost' >> /etc/environment

# Via .env file (not automatic — app must load it):
# Python: pip install python-dotenv → from dotenv import load_dotenv; load_dotenv()
```

### Inspecting Env Vars
```bash
printenv                          # all env vars
printenv DB_HOST                  # specific key
env                               # same as printenv
env | sort                        # sorted alphabetically
echo $DB_HOST                     # shell variable expansion

# Running process (by PID):
cat /proc/<PID>/environ | tr '\0' '\n'
cat /proc/<PID>/environ | tr '\0' '\n' | grep DB_HOST

# Kubernetes pod:
kubectl exec -it <pod> -- env
kubectl exec -it <pod> -- env | sort
kubectl exec -it <pod> -- printenv DB_HOST
kubectl exec -it <pod> -- cat /proc/1/environ | tr '\0' '\n'
```

### Reading Env Vars in Python
```python
import os

# With default (safe — never crashes):
db_host = os.environ.get("DB_HOST", "localhost")

# Required (crashes with KeyError if missing — good for fail-fast):
db_host = os.environ["DB_HOST"]

# With type conversion:
port = int(os.environ.get("PORT", "8000"))
debug = os.environ.get("DEBUG", "false").lower() == "true"

# Using pydantic-settings (validates and documents all config):
from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    db_host: str = "localhost"
    port: int = 8000
    class Config:
        env_file = ".env"
```

---

## Section 3: Kubernetes ConfigMaps

### Creating ConfigMaps
```bash
# From literal values:
kubectl create configmap app-config \
  --from-literal=db_host=postgres.c-qa4.svc.cluster.local \
  --from-literal=app_env=qa4

# From a file (key = filename, value = file content):
kubectl create configmap nginx-config --from-file=nginx.conf

# From a directory (one key per file):
kubectl create configmap app-configs --from-file=./config/

# From a YAML manifest (preferred for GitOps):
kubectl apply -f configmap.yaml
```

### ConfigMap Manifest
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: c-qa4
data:
  db_host: "postgres.c-qa4.svc.cluster.local"
  db_port: "5432"
  app_env: "qa4"
  # Multi-line value (config file content):
  app.yaml: |
    server:
      port: 8000
    database:
      host: postgres.c-qa4.svc.cluster.local
```

### Injecting ConfigMap as Env Vars
```yaml
spec:
  containers:
  - name: app
    # Method 1: specific keys:
    env:
    - name: DB_HOST
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: db_host
    - name: APP_ENV
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: app_env

    # Method 2: all keys at once:
    envFrom:
    - configMapRef:
        name: app-config
```

### Injecting ConfigMap as Volume-Mounted Files
```yaml
spec:
  volumes:
  - name: config-vol
    configMap:
      name: app-config
      # Optional: only mount specific keys:
      items:
      - key: app.yaml
        path: app.yaml

  containers:
  - name: app
    volumeMounts:
    - name: config-vol
      mountPath: /app/config
      readOnly: true
```

Result: `/app/config/app.yaml` exists inside the container with the ConfigMap's `app.yaml` value as content.

### ConfigMap Update Behavior

| Mount method | Pod sees update | Without restart? |
|-------------|----------------|-----------------|
| `env:` or `envFrom:` | No | Requires `kubectl rollout restart` |
| Volume mount | Yes | K8s refreshes files within ~30–60s (controlled by `syncPeriod`) |

```bash
# Force all pods in a deployment to pick up new ConfigMap:
kubectl rollout restart deployment/app-deployment

# Watch the rollout:
kubectl rollout status deployment/app-deployment

# Verify new pod has new value:
kubectl exec -it <new-pod> -- printenv DB_HOST
```

---

## Section 4: Kubernetes Secrets

### What Secrets Are
Secrets store sensitive data (passwords, API keys, TLS certs). They are base64-encoded, not encrypted by default (encryption at rest requires etcd encryption config or a KMS plugin).

**Base64 is NOT encryption.** Anyone with `kubectl get secret -o yaml` can decode it.

### Creating Secrets
```bash
# From literal values:
kubectl create secret generic app-secret \
  --from-literal=db_password=supersecret \
  --from-literal=api_key=abc123

# From files (e.g., TLS cert):
kubectl create secret tls tls-secret \
  --cert=tls.crt --key=tls.key

# From a YAML manifest (encode values first):
echo -n "supersecret" | base64
# → c3VwZXJzZWNyZXQ=
```

### Secret Manifest
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secret
  namespace: c-qa4
type: Opaque
data:
  db_password: c3VwZXJzZWNyZXQ=   # base64 of "supersecret"
  api_key: YWJjMTIz               # base64 of "abc123"
```

### Injecting Secrets
```yaml
# As env var:
env:
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: app-secret
      key: db_password

# As volume-mounted file (preferred for certs, longer values):
volumes:
- name: secret-vol
  secret:
    secretName: app-secret

containers:
- name: app
  volumeMounts:
  - name: secret-vol
    mountPath: /app/secrets
    readOnly: true
```

### Reading/Debugging Secrets
```bash
# See what secrets exist:
kubectl get secrets -n c-qa4

# See secret data (base64 encoded):
kubectl get secret app-secret -o yaml

# Decode a specific key:
kubectl get secret app-secret -o jsonpath='{.data.db_password}' | base64 -d

# Check what a pod received (value is still base64 in env var):
kubectl exec -it <pod> -- printenv DB_PASSWORD
```

---

## Section 5: Config Precedence Chain

### From Lowest to Highest Priority
```
1. Binary default       → hardcoded fallback in source code
2. Config file          → /etc/app/config.yaml, ./config/app.yaml
3. Environment variable → DB_HOST=x (injected by K8s ConfigMap/Secret)
4. Command-line flag    → --db-host=x (in Deployment spec.containers.args)
5. Runtime store        → Vault, AWS Parameter Store (fetched at runtime)
```

Higher number always wins when the same key appears in multiple sources.

### Spring Boot Precedence (most relevant for Copart)
```
1. application.properties inside the .jar
2. application.yml inside the .jar
3. application-{profile}.yml
4. OS environment variables
5. SPRING_ prefixed environment variables  ← K8s ConfigMap injection lands here
6. Command-line arguments
```

Example: K8s ConfigMap sets `SPRING_DATASOURCE_URL=jdbc:postgresql://...`
This overrides `spring.datasource.url` in the bundled `application.yml` without changing the image.

### Config Precedence Failure Patterns

| Symptom | Root cause | Diagnostic |
|---------|-----------|------------|
| App connects to wrong DB | Env var missing, falling back to hardcoded default | `kubectl exec -- printenv DB_HOST` |
| App crashes: KeyError / NPE | Required env var not injected | `kubectl logs <pod> \| head -20` |
| App crashes: FileNotFoundError | Config file not mounted at expected path | `kubectl exec -- ls /app/config/` |
| Config change has no effect | ConfigMap updated but pod not restarted | `kubectl rollout restart deployment/<name>` |
| Config change has no effect | Wrong ConfigMap name referenced in manifest | `kubectl describe pod <pod> \| grep ConfigMap` |
| Secret value wrong | YAML had wrong base64 encoding | `kubectl get secret -o yaml` then `base64 -d` |

---

## Section 6: Troubleshooting Decision Tree — Config Layer

```
Pod is running but behaving wrong, OR crashes at startup
│
├─ Step 1: What does the process actually have?
│  └─ kubectl exec -it <pod> -- env | sort
│     ├─ Wrong value → find the ConfigMap/Secret and fix the value
│     ├─ Missing key → ConfigMap/Secret not injected → check manifest env: / envFrom:
│     └─ Correct value → config layer is healthy, look at app logic
│
├─ Step 2: Does the expected config file exist?
│  └─ kubectl exec -it <pod> -- ls -la /expected/path/
│     ├─ File missing → volume mount not applied → check volumes: and volumeMounts: in manifest
│     ├─ File exists but wrong content → kubectl get configmap <name> -o yaml
│     └─ File exists, correct content → app is not reading the file it should be reading
│
├─ Step 3: What did the app log at startup about config?
│  └─ kubectl logs <pod> | head -50
│     ├─ "Could not locate PropertySource" → Spring Boot cannot reach configserver
│     ├─ "KeyError: 'DB_HOST'" → Python app, env var missing
│     ├─ "FileNotFoundError" → config file not at expected path
│     └─ No config error → config loaded OK, problem is elsewhere
│
└─ Step 4: Is the ConfigMap/Secret the correct version?
   └─ kubectl get configmap <name> -o yaml
   └─ kubectl describe pod <pod> | grep -A10 "Environment:"
```

---

## Section 7: Quick Reference Commands

### Inspect running process config
```bash
# See all env vars of PID:
cat /proc/<PID>/environ | tr '\0' '\n'

# See config files open by PID:
lsof -p <PID> | grep -E "\.conf|\.yaml|\.yml|\.json|\.properties"

# Inside a Kubernetes pod:
kubectl exec -it <pod> -- env | sort
kubectl exec -it <pod> -- cat /proc/1/environ | tr '\0' '\n'
kubectl exec -it <pod> -- cat /app/config/app.yaml
```

### Manage ConfigMaps and Secrets
```bash
kubectl get configmap -n <ns>
kubectl get configmap <name> -o yaml -n <ns>
kubectl describe configmap <name> -n <ns>
kubectl edit configmap <name> -n <ns>
kubectl delete configmap <name> -n <ns>

kubectl get secrets -n <ns>
kubectl get secret <name> -o jsonpath='{.data.<key>}' | base64 -d
kubectl describe secret <name> -n <ns>
```

### Apply config changes
```bash
# Update ConfigMap:
kubectl apply -f configmap.yaml

# Restart deployment to pick up new env vars:
kubectl rollout restart deployment/<name> -n <ns>
kubectl rollout status deployment/<name> -n <ns>

# Force pod recreation (delete → scheduler recreates):
kubectl delete pod <pod> -n <ns>
```

### Verify pod received correct config
```bash
kubectl describe pod <pod> -n <ns>     # shows Env: and Mounts: sections
kubectl exec -it <pod> -- env | grep DB_HOST
kubectl exec -it <pod> -- cat /app/config/app.yaml
kubectl get pod <pod> -o yaml | grep -A20 "env:"
```

---

## Section 8: Failure Signature Table

| Error | Layer | Root cause | Fix |
|-------|-------|-----------|-----|
| `KeyError: 'DB_HOST'` (Python) | Config | Env var not injected | Add to ConfigMap + reference in Deployment env: |
| `Could not locate PropertySource` (Spring) | Config | configserver unreachable | Fix configserver route, check SPRING_CLOUD_CONFIG_URI |
| `FileNotFoundError: /app/config/app.yaml` | Config/File | Volume not mounted | Add volumes: + volumeMounts: to Deployment |
| App connects to `localhost` DB instead of prod | Config | Hardcoded default, env var missing | Set DB_HOST env var in ConfigMap |
| Config change has no effect after kubectl apply | Config | Pod not restarted (env var injection) | kubectl rollout restart deployment/<name> |
| `base64: invalid input` | Config | Secret YAML not properly base64-encoded | Re-encode: `echo -n "value" \| base64` |
| Pod CrashLoopBackOff, logs show `NullPointerException` on DB connect | Config | DB_HOST or DB_PASSWORD missing/wrong | Check kubectl exec -- env for DB_ vars |

---

*Created: Day 3 — 2026-04-01*
