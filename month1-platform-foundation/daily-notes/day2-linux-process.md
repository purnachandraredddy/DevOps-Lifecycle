# Day 2 — Linux Process Model

**Date:** _(fill in when you complete this)_  
**30-Day Plan Day:** 2  
**Topic:** Process, PID, port binding, logs, and why failures start here before Kubernetes is relevant

---

## Question 1 — What is a process, and how does it relate to a running application?

A **process** is a running instance of a program. It is the fundamental unit of execution on Linux. When you start a Python script, a Java application, or a Go binary, the Linux kernel:

1. Allocates memory for the program's code and data
2. Assigns a unique **Process ID (PID)**
3. Creates a file descriptor table (so the process can read/write files, network sockets, pipes)
4. Schedules the process for CPU time

**Every application is a process.** This is true whether it runs:
- directly on a server (bare metal or VM)
- inside a Docker container (still a process, with namespace isolation applied)
- inside a Kubernetes pod (still a process — kubelet asks the container runtime, which asks the Linux kernel)

The container does not change what a process is. It only adds:
- **namespaces** (process sees its own PID namespace, network namespace, filesystem)
- **cgroups** (limits how much CPU/memory the process can use)

**Parent-child relationship:**
Every process has a parent. The init system (PID 1) is the ancestor of all processes. Inside a container, the CMD or ENTRYPOINT you define becomes PID 1. This matters because:
- If PID 1 exits → the container exits (regardless of what other processes are running in the same container)
- If a child process (spawned by your app) exits → the parent process may or may not notice, depending on signal handling

**Commands to find a process:**
```bash
ps aux | grep uvicorn          # all processes, show uvicorn
pgrep -a uvicorn               # PIDs matching "uvicorn"
ps -p <PID> -o pid,ppid,cmd    # specific PID: show its PID, parent PID, full command
top                            # live view of all processes
```

**Why this matters for troubleshooting:**
Before blaming Kubernetes, a Service, or the network — confirm the process exists. `ps aux | grep <app-name>` takes 2 seconds. If the process is not running, no higher-level component matters.

---

## Question 2 — How does an application bind to a port, and why does the binding address matter?

When your app calls `listen(port)`, the OS creates a **socket** — a kernel data structure representing "I am accepting connections on this port." The socket is tied to a specific **network interface** (or all interfaces).

**Two binding behaviors that engineers must distinguish:**

| Binding | Command/config | Who can reach the port |
|---------|---------------|------------------------|
| `0.0.0.0:8000` | "all interfaces" | Any IP — localhost, LAN, pod, external client |
| `127.0.0.1:8000` | "loopback only" | Only processes on the **same host** |

**The most common invisible failure:**
An app binds to `127.0.0.1` (loopback). From inside the container, `curl localhost:8000` works. But from outside the container — from another pod, a Service, or an Ingress — the port is unreachable. The error is `Connection refused` or a timeout, and nothing in the Kubernetes layer looks wrong.

This is a process-layer failure. It is not a Service bug, not an Ingress bug, not a network policy.

**How to check what a process is actually bound to:**
```bash
ss -tlnp                       # all listening TCP sockets, with PID
ss -tlnp | grep 8000           # filter by port
lsof -i :8000                  # which process has port 8000 open
lsof -i -P -n | grep LISTEN    # all listening ports, no DNS resolution
netstat -tlnp                  # older alternative to ss
```

**Reading `ss -tlnp` output:**
```
State   Recv-Q  Send-Q  Local Address:Port   Peer Address:Port  Process
LISTEN  0       128     0.0.0.0:8000         0.0.0.0:*          users:(("uvicorn",pid=1234,fd=5))
```
- `0.0.0.0:8000` → bound to all interfaces ✓ reachable from anywhere
- `127.0.0.1:8000` → bound to loopback only — NOT reachable from outside the host

**FastAPI / uvicorn behavior:**
```bash
# Default: binds to 127.0.0.1 — WRONG for containers
uvicorn main:app --port 8000

# Correct for containers and Kubernetes:
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Copart connection:**
When `curl http://10.148.14.190:8080` returned 401 on the configserver incident — that success confirmed the Spring Boot process was bound to `0.0.0.0:8080` and reachable from outside. If it had been bound to `127.0.0.1`, that curl would have timed out or been refused, and the failure would have been at the process layer, not the nginx layer.

---

## Question 3 — Where do logs come from, and how do they flow from process to operator?

**The fundamental log model:**
A process writes output to two file descriptors:
- **stdout (fd 1)** — standard output, normal operational messages
- **stderr (fd 2)** — error output, warnings, exceptions

That is it. Logs start here, as bytes written to these two file descriptors.

**How this flows in each environment:**

**Local (no container):**
```
Process stdout/stderr → terminal (or redirected to a file)
```
You see logs directly. `tail -f app.log` if redirected, or just in the terminal.

**Docker container:**
```
Process stdout/stderr → container runtime (Docker) → /var/lib/docker/containers/<id>/<id>-json.log
```
`docker logs <container>` reads that file and streams it back to you.

**Kubernetes pod:**
```
Process stdout/stderr → container runtime (containerd/CRI-O) → node-level log file
                                                               → kubelet API → kubectl logs
```
`kubectl logs <pod>` asks the kubelet on the node where the pod runs, which reads the container runtime's log file.

**Key operational implications:**

1. **Log format matters**: JSON structured logs are easier for log aggregation tools (Instana, Loki, Splunk) to parse. Plain text logs require regex parsing.

2. **If the process crashes before writing logs**: You may see no log output for a crash. The container exits, but `kubectl logs <pod> --previous` retrieves the logs from the last run.

3. **If logs are written to a file instead of stdout**: `kubectl logs` shows nothing. This is a common mistake with legacy Java apps that write to `/var/log/app.log` inside the container. You need to either `kubectl exec` into the container, use a sidecar log shipper, or configure the app to write to stdout.

4. **Log rotation**: Docker and containerd rotate container logs automatically. `kubectl logs --tail=100` to avoid reading gigabytes of history.

**Commands:**
```bash
kubectl logs <pod>                        # current container stdout/stderr
kubectl logs <pod> --previous             # previous container (after crash)
kubectl logs <pod> -f                     # follow (stream live)
kubectl logs <pod> -c <container>         # multi-container pod — specify which
kubectl logs <pod> --tail=50              # last 50 lines only
kubectl logs <pod> --since=10m            # last 10 minutes
```

**Local process log commands:**
```bash
tail -f /var/log/app.log                  # follow file-based log
journalctl -u myservice -f                # systemd-managed process
dmesg | tail                              # kernel messages (OOM kills appear here)
```

---

## Question 4 — What layers can fail before Kubernetes is even involved?

This is the key calibration for an operator moving to systems thinking.

When something "doesn't work," there is a temptation to start with `kubectl describe` or check the Ingress. But Kubernetes cannot fix a broken process.

**Failures that happen at the process layer (below Kubernetes):**

| Failure | What you see in K8s | Root cause |
|---------|--------------------|----|
| App bound to `127.0.0.1` | Pods Running, Endpoints exist, 503 from Service | Wrong bind address in app |
| App crashes at startup | CrashLoopBackOff | Missing dependency, bad env var, OOM at startup |
| App starts but hangs after init | Pod shows Running 0/1, readiness probe fails | App deadlock, DB connection wait, slow init |
| Wrong port in app code | Endpoints exist but requests time out | App listens on 8080, container/probe/service expects 8000 |
| App writes to file, not stdout | Pod Running, `kubectl logs` shows nothing | Legacy logging config |
| OOMKilled | Pod restarts with Reason: OOMKilled | Process exceeded memory cgroup limit |

**Why does `Connection refused` vs `Connection timed out` tell you something different?**

- `Connection refused` → the port is actively rejecting connections. The OS is sending a TCP RST. This means either: no process is listening on that port, or a firewall rule explicitly rejected it.
- `Connection timed out` → no response at all. Packets are being dropped. This means: firewall silently dropping, wrong IP, or the machine is not reachable.

When you see `Connection refused` on a pod's containerPort — the process layer is the first suspect. Check `ss -tlnp` inside the container.

**The 2-second process check before anything else:**
```bash
# From inside the container/pod:
kubectl exec -it <pod> -- ss -tlnp
kubectl exec -it <pod> -- ps aux

# If these show the app is listening on the right port → process layer is healthy, look up
# If these show nothing listening → process layer is broken, look at startup logs
```

---

## Question 5 — One real Copart observation, classified at the process layer

**Observation: Spring Boot services during startup in `c-qa4` namespace**

When Spring Boot applications (like `configserver`) start inside a Kubernetes pod, they go through a multi-second initialization before they bind to port 8080. During this window:

- The pod shows `Running 0/1` (container started, process is alive, but it has not bound the port yet)
- The readiness probe (`/actuator/health`) returns connection refused or 503 because the port is not open yet
- The pod is excluded from Service endpoints — traffic correctly does not reach it

This is the process-layer explaining the Kubernetes-level behavior. The sequence is:
```
Container starts → JVM starts → Spring Boot starts autoconfigure → DB migrations → Port binds → App healthy
```

If the readiness probe fires before port binds → `Connection refused` → probe fails → correct behavior.

**What I would check to confirm this:**
```bash
kubectl exec -it <pod> -- ss -tlnp    # is port 8080 bound yet?
kubectl logs <pod> -f                  # is Spring Boot still initializing?
kubectl describe pod <pod>             # readiness probe failure messages in events
```

**The process-layer signal that tells me "app is still starting":**
`kubectl logs` shows Spring Boot startup lines (autoconfigure, bean loading, datasource init) but no `Started configserver in X seconds` line yet.
That is the process not yet ready — and readiness failing is the correct behavior, not a bug.

**Layer classification:**
- Layer 6 (Pod/Container) appears broken — pod shows 0/1 Ready
- Root cause is at the process layer — the JVM has not finished initialization
- Fix: tune `initialDelaySeconds` or use a `startupProbe` with enough budget for the JVM startup time

---

## My Definition of a Process Layer Failure — Day 2

A process layer failure is any failure caused by the application process itself: it is not running, not bound to the expected port/interface, crashing at startup, or not producing logs to stdout. No amount of Kubernetes configuration fixes a process layer failure. The fix is always in the application binary, its startup command, its runtime dependencies, or its resource allocation.

**When I see a broken pod, I eliminate the process layer in 3 commands:**
1. `kubectl exec -it <pod> -- ss -tlnp` → is the port bound?
2. `kubectl logs <pod>` → is the process healthy/starting/crashing?
3. `kubectl describe pod <pod>` → what is the probe/event saying?

If all three point elsewhere, the process layer is healthy — look up.

---

**Date written:** _(fill in)_
