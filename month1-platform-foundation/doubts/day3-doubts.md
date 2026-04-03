# Day 3 — Doubts & Open Questions

**Date:** _(fill in when you complete Day 3)_  
**Session topic:** Files, environment variables, config, and runtime context  
**Rule:** Every question here must be precise enough that a concrete answer can be given. Each doubt must expose a specific gap that, if filled, would change how I debug something.

---

## Doubt 1 — If I update a volume-mounted ConfigMap, how long until the pod sees the new file, and is the update atomic?

**What I think I know:**
Kubernetes updates volume-mounted ConfigMaps within approximately 30–60 seconds (controlled by the kubelet's `syncPeriod`). The env var injection method requires a pod restart to pick up changes.

**The specific gap:**
When the kubelet refreshes a mounted ConfigMap, does it happen atomically? Meaning: is there a window where the app could open the file and see it half-written? Or does Kubernetes swap the file using a symlink so the old file is fully visible until the new file is fully written?

**What I need to understand:**
- How exactly does Kubernetes update mounted ConfigMap files — atomic symlink swap or in-place write?
- If my app is reading the config file in a tight loop (live reload), can it ever see a partial write?
- What happens if the app holds the file open when the ConfigMap is updated? Does it see the new content on the next read?
- What is the exact timing: is it 30s, 60s, or "up to syncPeriod + jitter"?

**Why this matters in production:**
If the file update is not atomic, a config reload could read corrupted partial content. For nginx, reloading with a half-written config would crash the process. I need to know whether I can trust the mounted file integrity.

---

## Doubt 2 — Where exactly do Kubernetes Secrets live, and what does "base64 is not encryption" mean operationally?

**What I think I know:**
Secrets are stored in etcd. Base64 is just an encoding, not encryption. Anyone with `kubectl get secret -o yaml` and cluster access can decode the value trivially.

**The specific gap:**
I know the theory. I don't know: (1) what "encryption at rest" actually means in the context of etcd and how to tell if it's enabled, (2) whether the Secret value is ever exposed in plain text anywhere automatically — in logs, in /proc, in kubelet state files on the node, etc.

**What I need to understand:**
- Is the Secret value in `kubectl exec -- env` stored as plain text in `/proc/<PID>/environ` on the node's filesystem? (Can a node-level compromise expose all Secrets?)
- What is the difference between `encryption at rest` (etcd EncryptionConfig) and mounting a Secret as a volume vs env var — do both have the same confidentiality properties at rest?
- How does a malicious pod (or a compromised process) typically extract a Secret it's been injected with?
- Is there a way to tell without cluster-admin access whether encryption at rest is enabled?

**Why this matters in production:**
At Copart, DB passwords are likely injected as Secrets. If a container is compromised, I need to know exactly what an attacker can read. If etcd encryption is not enabled, then all Secrets are plain text on disk on the control plane nodes — that's a different risk model.

---

## Doubt 3 — What exactly happens when two different ConfigMaps have the same key name and both are injected with `envFrom`?

**What I think I know:**
If you use `envFrom:` to inject two ConfigMaps and both contain a key named `DB_HOST`, one value wins. I think the one listed first wins, but I'm not certain.

**The specific gap:**
I don't know the precise precedence rule when multiple `envFrom:` sources conflict on the same key name.

**What I need to understand:**
- Is there a defined precedence order for `envFrom:` — first one wins, or last one wins?
- Does Kubernetes emit a warning or event when a key collision occurs?
- What happens with `env:` (explicit key injection) vs `envFrom:` if both define the same key — which wins?
- If I use both `envFrom: [configMapRef, secretRef]` and also `env: [- name: DB_HOST valueFrom: ...]`, which wins?

**Why this matters in production:**
Complex deployments often inject both a shared global ConfigMap and a service-specific ConfigMap. If both have overlapping keys and the precedence is wrong, the service silently gets the wrong config. This is the kind of bug that only surfaces in production when the shared ConfigMap changes.

---

## Doubt 4 — When the app reads `os.environ` in Python, is it reading the value at process start, or is it a live lookup into the kernel's env?

**What I think I know:**
`os.environ` in Python is a mapping object. I believe it reads env vars at module import time and caches them. But I'm not sure if subsequent `os.environ.get()` calls re-read from the process's env block or use a cached dict.

**The specific gap:**
I don't know whether the env block in a Linux process (`/proc/<PID>/environ`) can ever change after the process starts, or if it is immutable. If it is immutable, `os.environ` is effectively a snapshot. If it can change (e.g., via `putenv()` in C code called via ctypes), then Python's view might be stale.

**What I need to understand:**
- Is `/proc/<PID>/environ` a live view or a snapshot of the process's env at start time?
- In Python, is `os.environ` a cached dict or does it call `getenv()` (which reads live memory) on each access?
- Can a running Python process change its own env vars with `os.environ['DB_HOST'] = 'newvalue'`? If yes, does that change persist to child processes?
- If a Kubernetes ConfigMap is updated and the pod does NOT restart, can the Python process ever see the new value without a restart?

**Why this matters in production:**
If I tell an on-call engineer "just update the ConfigMap, no restart needed," I need to be confident that is only safe for volume-mounted files, not env vars. And I need to understand whether any live-reload mechanism in Python could theoretically pick up new env values without a restart.

---

## Doubt 5 — What is the difference between `kubectl describe pod` showing `<set to the key 'db_password' in secret 'app-secret'>` and the actual value being visible to the process?

**What I think I know:**
`kubectl describe pod` deliberately redacts Secret values, showing the reference rather than the value. The actual value is injected at pod creation time and visible only inside the running container.

**The specific gap:**
I don't fully understand at what point in the pod lifecycle the Secret value is resolved. Is it resolved by the API server when the pod spec is created? By the kubelet when it creates the container? Or lazily when the container reads the env var?

**What I need to understand:**
- At what point does the kubelet fetch the Secret value and inject it into the container's environment? Is it before container start, during container start, or lazily?
- If the Secret is deleted after the pod is running, does the running pod lose access to the value? (I think no — the env var is already in the process. But what about volume-mounted Secrets?)
- What happens if a Secret referenced in a pod spec does not exist at pod creation time? Does the pod fail to start with a clear error? What is the exact error message?
- Does the kubelet cache Secret values locally on the node, and if yes, how does that interact with Secret rotation?

**Why this matters in production:**
If a Secret is deleted while pods are running (mistake, security rotation, emergency), I need to know immediately: do running pods lose access, and do new pods fail to start? Getting this wrong means misdiagnosing an incident as a network problem when it's actually a missing Secret.

---

*Last updated: _(fill in)_*
