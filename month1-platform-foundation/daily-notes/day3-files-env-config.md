# Day 3 — Files, Environment Variables, and Runtime Config

**Date:** _(fill in when you complete this)_  
**30-Day Plan Day:** 3  
**Topic:** How processes receive configuration — environment variables, config files, /proc, ConfigMaps, Secrets

---

## Question 1 — What is a file on Linux, and why does "everything is a file" matter for a platform engineer?

On Linux, **everything is a file** — or more precisely, everything is accessed through the same file-descriptor interface. This is not just a slogan; it shapes how every diagnostic tool works.

**What counts as a "file" in Linux:**

| Type | Example | Why it matters |
|------|---------|----------------|
| Regular file | `/etc/nginx/nginx.conf`, `app.py` | Config, code, data |
| Directory | `/proc/1234/` | Namespace for a PID |
| Device file | `/dev/null`, `/dev/sda` | Abstracts hardware |
| Socket | `/var/run/docker.sock` | IPC without a network port |
| Pipe | `ls \| grep foo` | Connects stdout of one process to stdin of another |
| Symlink | `/etc/resolv.conf → /run/systemd/resolve/stub-resolv.conf` | Points to real file |
| `/proc` virtual file | `/proc/1234/environ`, `/proc/1234/fd/` | Live kernel data about a process |

**The `/proc` filesystem — the most important for platform debugging:**

Every running process has a directory at `/proc/<PID>/`. The kernel creates this automatically. It is not on disk; it is live kernel data exposed as readable files.

Key files inside `/proc/<PID>/`:

| File | What it shows |
|------|--------------|
| `environ` | All env vars the process started with (null-byte separated) |
| `cmdline` | The exact command line used to start the process |
| `fd/` | Open file descriptors — sockets, log files, config files |
| `limits` | Resource limits (max open files, max memory) |
| `status` | Process state, memory usage, PID, PPID |
| `net/tcp` | Active TCP connections for this process's network namespace |

**Reading a live process's environment:**
```bash
# See env vars of PID 1234 (requires root or same user):
cat /proc/1234/environ | tr '\0' '\n'

# Same from inside a Kubernetes pod:
kubectl exec -it <pod> -- cat /proc/1/environ | tr '\0' '\n'

# See what files a process has open:
ls -la /proc/1234/fd/
lsof -p 1234
```

**Why "everything is a file" matters for ops:**

1. **Config is a file** — broken config path = process can't start = Layer 6 failure, not a K8s bug
2. **Sockets are files** — `/var/run/docker.sock` being missing means Docker CLI can't reach daemon
3. **`/proc` is readable** — you can inspect a live running process's exact environment without restarting it
4. **`kubectl exec`** works because it opens a pseudo-terminal file descriptor into the container's namespace

**Connection to troubleshooting:**
When a pod fails because "the config file isn't there," that is a file-layer failure:
- Container does not have the file mounted
- Volume mount path is wrong
- Secret/ConfigMap key name doesn't match what the app expects

---

## Question 2 — How do environment variables work: where do they live, how are they inherited, and how do you see a process's live env?

**What an environment variable is:**

An env var is a key=value string stored in the process's memory (specifically in the env block at the top of the process's stack). It is not a file. It is not in the kernel. It exists inside the process.

**How env vars are inherited:**

When a process forks (creates a child process), the child receives a **copy** of the parent's entire environment. This is the inheritance model:

```
init (PID 1) → bash (inherits init's env)
                 → uvicorn (inherits bash's env + anything you export)
                      → worker1 (inherits uvicorn's env)
                      → worker2 (inherits uvicorn's env)
```

**Key rule:** A child process cannot modify the parent's environment. The copy flows one way — down to children only.

**How to set env vars:**

```bash
# Set for the current shell session:
export DB_HOST=localhost

# Set for a single command only (does NOT affect the shell):
DB_HOST=localhost uvicorn main:app

# Set permanently for a user (write to ~/.bashrc or ~/.profile):
echo 'export DB_HOST=localhost' >> ~/.bashrc

# Unset:
unset DB_HOST
```

**Inspecting environment:**

```bash
printenv                     # all env vars of current shell
printenv DB_HOST             # single var
env                          # same as printenv
echo $DB_HOST                # single var (shell expansion)

# Live env of a running process by PID:
cat /proc/<PID>/environ | tr '\0' '\n'

# From inside a Kubernetes pod:
kubectl exec -it <pod> -- env
kubectl exec -it <pod> -- printenv DB_HOST
kubectl exec -it <pod> -- cat /proc/1/environ | tr '\0' '\n'
```

**How an application reads env vars in Python (FastAPI):**

```python
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")   # with default
DB_HOST = os.environ["DB_HOST"]                     # raises KeyError if missing
```

The `KeyError` case is important: if the required env var is missing, the app crashes at startup — not a K8s bug. Check `kubectl logs` for `KeyError: 'DB_HOST'`.

**Critical operational fact: env vars are snapshotted at process start**

When the process starts, it copies the env block. After that, env vars do not change for that process unless the process re-reads them. This means:
- Updating a Kubernetes ConfigMap injected as env vars → the running pod does NOT see the new values
- You must restart the pod to pick up env var changes
- This is one of the most common "I updated the config but nothing changed" situations

---

## Question 3 — How does Kubernetes inject configuration into pods, and when do you use env vars vs volume-mounted files?

Kubernetes provides two mechanisms to push config into a running container. Both read from ConfigMaps or Secrets.

**Mechanism 1: Environment variable injection**

```yaml
env:
  - name: DB_HOST
    valueFrom:
      configMapKeyRef:
        name: app-config
        key: db_host
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: app-secret
        key: db_password
```

Or inject all keys at once:
```yaml
envFrom:
  - configMapRef:
      name: app-config
  - secretRef:
      name: app-secret
```

**Mechanism 2: Volume-mounted files**

```yaml
volumes:
  - name: config-volume
    configMap:
      name: app-config

containers:
  - name: app
    volumeMounts:
      - name: config-volume
        mountPath: /app/config
```

This mounts each key in the ConfigMap as a separate file inside `/app/config/`. If the ConfigMap has key `nginx.conf`, the file appears at `/app/config/nginx.conf`.

**When to use which:**

| Situation | Use env vars | Use volume mount |
|-----------|-------------|-----------------|
| Simple key=value config (URLs, flags, ports) | ✓ | |
| Large structured config file (nginx.conf, application.yml) | | ✓ |
| Config that changes at runtime without pod restart | | ✓ (K8s updates mounted files) |
| Secrets | Acceptable for simple values | ✓ preferred (files can have stricter permissions) |
| Config the app expects as a file on disk | | ✓ |
| Config the app reads via `os.environ` | ✓ | |

**The critical difference on updates:**

| Update to ConfigMap | Env var injection | Volume mount |
|--------------------|-------------------|--------------|
| Pod sees new value immediately? | **No** — pod must restart | **Yes** — K8s updates the file within ~30–60s |
| Requires pod restart? | **Yes** | No (but app must re-read the file) |

**How to force a pod restart when a ConfigMap changes (env var injection):**

```bash
# Rollout restart — creates new pods with updated env:
kubectl rollout restart deployment/<name>

# Watch the rollout:
kubectl rollout status deployment/<name>
```

**Verifying what a pod actually received:**

```bash
# See all env vars:
kubectl exec -it <pod> -- env

# See mounted config files:
kubectl exec -it <pod> -- ls /app/config/
kubectl exec -it <pod> -- cat /app/config/nginx.conf

# Check what volumes are mounted:
kubectl describe pod <pod> | grep -A5 "Mounts:"
```

---

## Question 4 — What is the config precedence chain, and where does Kubernetes fit in it?

Applications typically read config from multiple sources. When the same key exists in multiple sources, precedence determines which value wins.

**Standard config precedence (lowest to highest):**

```
1. Binary default         (hardcoded fallback in source code)
2. Config file            (/etc/app/config.yaml or ./config.json)
3. Environment variable   (DB_HOST=x)
4. Command-line flag      (--db-host=x)
5. Runtime API / secret store  (Vault, AWS Parameter Store)
```

Higher number wins. This is how most well-designed apps work (Spring Boot, Django, FastAPI with pydantic-settings, nginx).

**Spring Boot specifically:**
Spring Boot's config precedence is well-documented. Key ordering:
```
application.properties in jar → application.yml in jar
→ application-{profile}.yml → OS env vars → SPRING_ prefixed env vars
→ command-line args
```

So `SPRING_DATASOURCE_URL=jdbc:postgresql://...` (env var) overrides `spring.datasource.url` in the bundled `application.yml`. This is exactly how Kubernetes ConfigMap values override the defaults baked into the Docker image.

**Kubernetes position in the chain:**

Kubernetes injects config before the app starts. By the time the first line of your Python or Java code runs, `os.environ` already contains everything injected from ConfigMaps and Secrets. K8s is operating at the "environment variable" level of the precedence chain.

**The failure modes at each level:**

| Level | What breaks | What you see |
|-------|------------|--------------|
| Binary default | Wrong hardcoded value | App connects to wrong DB in prod — works "locally" |
| Config file | File not mounted / wrong path | App crashes: `FileNotFoundError` at startup |
| Env var | Missing required key | App crashes: `KeyError` or `NullPointerException` at startup |
| Env var | Wrong value (typo, stale) | App starts but behaves wrong — DB connection refused |
| Command-line flag | Wrong flag or missing | App starts with wrong behavior or crashes |

**How to debug config layer failures:**

```bash
# 1. What env does the pod actually have?
kubectl exec -it <pod> -- env | sort

# 2. Does the expected file exist at the expected path?
kubectl exec -it <pod> -- ls -la /app/config/
kubectl exec -it <pod> -- cat /app/config/app.yaml

# 3. What does the ConfigMap actually contain?
kubectl get configmap app-config -o yaml

# 4. What does the Secret contain (base64 decoded)?
kubectl get secret app-secret -o jsonpath='{.data.db_password}' | base64 -d

# 5. What did the app log at startup about config?
kubectl logs <pod> | head -50
```

---

## Question 5 — One real Copart observation, classified at the config/environment layer

**Observation: `configserver` in `c-qa4` namespace — it IS the config server**

The `configserver` service in Copart's `c-qa4` namespace is a **Spring Cloud Config Server** — its job is to serve configuration to other microservices. When I observed it returning 404 via the nginx route, the actual root cause was at Layer 4 (nginx routing), but the *reason* any of this matters is the config layer.

Here is what `configserver` does at the config layer:

1. It reads its own startup config from a ConfigMap or env vars: which Git repo to read from, which branch to use per profile
2. Other services (like `auth-service`, `payment-service`) call `configserver` at startup to receive their own `application.yml`
3. If `configserver` is unreachable (404 at the nginx layer), the calling service **fails its own startup** — because it cannot read its required config

**The cascade this creates:**

```
configserver unreachable (404 from nginx)
   → auth-service calls configserver at startup
   → Spring Boot config fetch fails
   → auth-service throws: "Could not locate PropertySource" 
   → auth-service crashes → CrashLoopBackOff
   → all services depending on auth-service are unreachable
```

This is a config-layer failure masked as a networking failure. The symptom (services down) is far from the root cause (nginx server_name mismatch blocking the config server).

**Commands to confirm the config layer is healthy:**

```bash
# 1. From inside a service that depends on configserver:
kubectl exec -it <dependent-pod> -- env | grep SPRING_CLOUD_CONFIG

# 2. Can the pod reach configserver?
kubectl exec -it <dependent-pod> -- curl http://configserver.c-qa4.svc.cluster.local:8080/actuator/health

# 3. What config is configserver actually serving?
curl http://configserver.c-qa4.svc.cluster.local:8080/<service-name>/default

# 4. Check configserver's own env for its git repo config:
kubectl exec -it <configserver-pod> -- env | grep GIT
```

**Layer classification:**
- Visible symptom: multiple services in CrashLoopBackOff
- Layer 4 (Ingress/nginx): the 404 blocking external access to configserver
- Config layer: the dependency chain — services cannot start without their config
- Fix priority: restore configserver access first (nginx fix), then verify downstream services recover

---

## My Definition of a Config Layer Failure — Day 3

A config layer failure is any failure caused by wrong, missing, or stale configuration reaching a process. The process itself may be healthy — it starts, binds the right port, and is reachable. But it behaves incorrectly or crashes during initialization because the runtime context is wrong. Config layer failures are diagnosed by examining what the process actually received, not what you intended to pass. The command `kubectl exec -- env` is the entry point. If the wrong value is there, find where it is being set. If it is absent, find where it should be set.

**When I see startup crashes or wrong behavior, I check the config layer in 4 commands:**
1. `kubectl exec -it <pod> -- env | sort` → what does the process actually have?
2. `kubectl exec -it <pod> -- cat /path/to/config` → what does the mounted file contain?
3. `kubectl get configmap <name> -o yaml` → what is the source of truth in K8s?
4. `kubectl logs <pod> | head -50` → did the app log a config error at startup?

---

**Date written:** _(fill in)_
