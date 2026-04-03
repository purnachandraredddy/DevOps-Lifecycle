# Linux Process Model — Reference Document

**30-Day Plan:** Day 2  
**Purpose:** Polished reference — command cheatsheet, mental models, troubleshooting patterns

---

## Core mental model

```
Application code
       │
       ▼
  Linux Process (PID assigned, memory allocated, fd table created)
       │
       ├── binds to a port on an interface (0.0.0.0 or 127.0.0.1)
       ├── reads from stdin / writes to stdout + stderr
       ├── reads environment variables
       └── may open files, sockets, pipes

  Container = Process + namespace isolation + cgroup limits
  Kubernetes pod = Container + lifecycle management by kubelet
```

The container and the pod do not change what a process is. They add management and isolation around it.

---

## Inspecting a running process

### Find it

```bash
ps aux | grep <name>           # all processes, filter by name
ps aux                         # all processes (a=all users, u=user format, x=no-tty)
pgrep -a <name>                # PIDs matching name + full command
pgrep -la <name>               # same, with long format
pidof <name>                   # PIDs of exact binary name
top                            # live CPU/memory view
htop                           # interactive version of top (if installed)
```

### Understand a specific PID

```bash
ps -p <PID> -o pid,ppid,cmd,rss,vsz,%cpu,%mem
# pid    = process ID
# ppid   = parent PID
# cmd    = full command including arguments
# rss    = resident set size (physical memory in KB, actual RAM used)
# vsz    = virtual size (includes mapped but not loaded memory)
# %cpu   = CPU usage
# %mem   = memory as % of total system RAM

cat /proc/<PID>/cmdline        # exact command that started the process (null-delimited)
cat /proc/<PID>/environ        # environment variables of the process
cat /proc/<PID>/status         # detailed state: VmRSS, VmSize, Threads, State
ls -la /proc/<PID>/fd          # open file descriptors (files, sockets, pipes)
```

### Process states (in `ps` output)

| State | Meaning |
|-------|---------|
| `R` | Running or runnable (on CPU or waiting for CPU) |
| `S` | Sleeping (interruptible) — waiting for I/O, timer, signal |
| `D` | Sleeping (uninterruptible) — waiting for disk I/O, cannot be killed |
| `Z` | Zombie — process exited but parent hasn't called wait() |
| `T` | Stopped — suspended by signal (SIGSTOP) |

A process stuck in `D` state is often a symptom of disk I/O hang or NFS mount issue. A large number of `Z` processes means the parent is not reaping children.

---

## Port binding

### Check what is listening

```bash
ss -tlnp                       # TCP listening, numeric, show process
ss -tlnp | grep :8000          # filter by port
ss -tulnp                      # TCP + UDP listening
lsof -i :8000                  # process holding port 8000 open
lsof -i -P -n | grep LISTEN    # all listening sockets, no reverse DNS
netstat -tlnp                  # older command, same output (may not be installed)
```

### Reading `ss -tlnp` output

```
State   Recv-Q  Send-Q  Local Address:Port  Peer Address:Port  Process
LISTEN  0       128     0.0.0.0:8000        0.0.0.0:*          users:(("uvicorn",pid=1,fd=5))
LISTEN  0       128     127.0.0.1:6379      0.0.0.0:*          users:(("redis-server",pid=8,fd=6))
```

| Local Address | Reachable from |
|--------------|----------------|
| `0.0.0.0:8000` | Any IP — pods, services, external |
| `127.0.0.1:8000` | Loopback only — same host/container only |
| `:::8000` | All IPv6 interfaces (and often IPv4 too) |
| `::1:8000` | IPv6 loopback only |

### The 0.0.0.0 vs 127.0.0.1 failure pattern

```
App bound to 127.0.0.1:8000
    └── curl localhost:8000  →  200 OK  (works from inside container)
    └── curl <pod-ip>:8000   →  Connection refused  (fails from another pod)
    └── kubectl logs          shows no error
    └── kubectl describe pod  shows readiness probe failing
    └── Service endpoints     may exist but requests are refused

Root cause: bind address. Fix: --host 0.0.0.0 in the start command.
```

---

## Logs

### Where logs come from

```
Process writes to stdout (fd 1) and stderr (fd 2)
    │
    ├── Local: terminal or file redirect (> app.log 2>&1)
    ├── Docker: /var/lib/docker/containers/<id>/<id>-json.log
    └── Kubernetes: container runtime log file on node → kubelet API → kubectl logs
```

### kubectl log commands

```bash
kubectl logs <pod>                         # stdout + stderr
kubectl logs <pod> --previous              # previous container (after crash/restart)
kubectl logs <pod> -f                      # follow (stream live)
kubectl logs <pod> -c <container>          # multi-container pod
kubectl logs <pod> --tail=50               # last 50 lines
kubectl logs <pod> --since=10m             # last 10 minutes
kubectl logs -l app=fastapi-app            # all pods matching label
```

### Local process log commands

```bash
tail -f /var/log/app.log                   # follow file-based log
journalctl -u <service> -f                 # systemd service logs
journalctl -u <service> --since "10 min ago"
dmesg | tail -20                           # kernel ring buffer (OOM kills appear here)
dmesg | grep -i oom                        # filter for OOM killer events
```

### OOM kill signature in kernel logs

```
dmesg output:
[12345.678] Out of memory: Killed process 1234 (java) total-vm:4096kB, anon-rss:2048kB
```

In Kubernetes, this surfaces as:
- `kubectl describe pod` → `Last State: Terminated, Reason: OOMKilled, Exit Code: 137`
- The container exits with code 137 (128 + signal 9 = SIGKILL)

Exit code 137 = OOMKilled. Always check this when a pod restarts unexpectedly.

---

## Signals and process control

```bash
kill -0 <PID>       # test if process exists (no actual signal sent, exit code 0 = exists)
kill <PID>          # send SIGTERM (15) — ask process to shut down gracefully
kill -9 <PID>       # send SIGKILL — force kill, cannot be caught or ignored
pkill <name>        # send SIGTERM to processes matching name
```

**SIGTERM vs SIGKILL:**
- SIGTERM (15): process receives it, can run cleanup code, close connections, flush buffers, then exit. This is the graceful path.
- SIGKILL (9): kernel terminates the process immediately. No cleanup. Use this only when SIGTERM is ignored.

In Kubernetes, when a pod is deleted or evicted:
1. K8s sends SIGTERM to PID 1 in the container
2. Waits `terminationGracePeriodSeconds` (default 30s)
3. If process still running → sends SIGKILL

If your app doesn't handle SIGTERM → it ignores the graceful shutdown signal → Kubernetes kills it hard after 30s. This causes connection resets on in-flight requests.

---

## CPU and memory

```bash
top                            # live view, sorted by CPU
top -o %MEM                    # sort by memory
free -h                        # total, used, free, available memory (human readable)
free -h -s 2                   # refresh every 2 seconds
vmstat 1 5                     # CPU/memory/disk stats, 5 samples, 1s interval
cat /proc/meminfo              # detailed memory breakdown
```

**What RSS vs VSZ means:**
- **RSS** (Resident Set Size) = physical RAM actually in use. This is what you care about for cgroup memory limits.
- **VSZ** (Virtual Size) = all memory mapped by the process including shared libraries, memory-mapped files. Always larger than RSS.

Kubernetes memory limits are enforced against RSS. If RSS exceeds the container's `resources.limits.memory`, the container is OOMKilled.

---

## Inside a Kubernetes container

```bash
# Get a shell inside the container
kubectl exec -it <pod> -- /bin/sh       # if sh exists
kubectl exec -it <pod> -- /bin/bash     # if bash exists

# Once inside, run these to check the process:
ps aux
ss -tlnp
cat /etc/resolv.conf
env | sort                              # all environment variables
ls /proc/1/fd                           # file descriptors of PID 1
cat /proc/1/cmdline | tr '\0' ' '      # full command of PID 1

# Memory limits visible inside the container:
cat /sys/fs/cgroup/memory/memory.limit_in_bytes    # cgroup v1
cat /sys/fs/cgroup/memory.max                       # cgroup v2
```

---

## Troubleshooting decision tree — process layer

```
Pod is Running but something is wrong
         │
         ▼
Is the process listening on the expected port?
kubectl exec <pod> -- ss -tlnp
         │
    No ──┤──── Check: kubectl logs <pod>
         │           Is the app still starting?
         │           Is it crashing before binding?
         │
   Yes ──┤
         ▼
Is the process bound to 0.0.0.0 (not 127.0.0.1)?
         │
    No ──┤──── Fix: change --host to 0.0.0.0 in start command
         │
   Yes ──┤
         ▼
Process layer is healthy. Look up to Service/Ingress layer.
```

---

## Common process-layer failures and their signatures

| Failure | `kubectl get pods` | `kubectl describe pod` | `kubectl logs` | Fix |
|---------|-------------------|----------------------|----------------|-----|
| Process not started / crash | `CrashLoopBackOff` | Events: Exit code 1/2 | App error at startup | Fix startup dependency / config |
| OOMKilled | Pod restarts | `OOMKilled`, Exit Code 137 | Logs cut off mid-output | Increase memory limit or fix memory leak |
| Wrong bind address | Running 0/1 | Readiness probe: `Connection refused` | App healthy in logs | Add `--host 0.0.0.0` |
| Wrong port in app | Running 0/1 | Readiness probe: `Connection refused` | App listening on different port | Match port in app, Dockerfile, probe, service |
| App writes to file not stdout | Running 1/1 | Normal | No output | Configure app to write to stdout/stderr |
| Slow startup, probe fires too early | Running 0/1 | Probe failures in events | Spring Boot/JVM still starting | Add `startupProbe` with sufficient budget |

---

*Part of Month 1 — Platform Foundation*  
*30-Day Plan: Day 2*  
*Created: 2026-03-30*
