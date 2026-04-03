# Day 2 — Doubts & Open Questions

**Date:** _(fill in when you complete Day 2)_  
**Session topic:** Linux process model — PID, port binding, logs, process-layer failures  
**Rule:** Every question here must be precise enough that a concrete answer can be given. Each doubt must expose a specific gap that, if filled, would change how I debug something.

---

## Doubt 1 — What exactly happens at the kernel level when a process calls bind() on a port?

**What I think I know:**
A process calls `bind(socket, address, port)` and the OS starts accepting connections on that port. After bind, the process calls `listen()` to start the accept queue, then `accept()` in a loop to handle individual connections.

**The specific gap:**
I understand the sequence at a high level but not what actually prevents two processes from binding to the same port. Is it enforced purely in kernel memory? Is there a per-namespace table? And how does `SO_REUSEADDR` / `SO_REUSEPORT` change this?

**What I need to understand:**
- Where does the kernel store the "this port is in use" state? Is it per-network namespace?
- In a Kubernetes pod, each pod has its own network namespace. Does that mean two pods can both bind to port 8080 without conflict?
- What does `SO_REUSEPORT` actually allow? I've seen nginx and some web servers use it — what problem does it solve?
- If a process crashes without calling `close()`, does the port get freed immediately or does it enter TIME_WAIT?

**Why this matters in production:**
If I see two containers in the same pod both trying to bind to port 8080, I need to know whether that's a conflict or allowed. And if a pod crashes and restarts quickly, I need to know whether the port can be reused immediately or if there's a delay.

---

## Doubt 2 — What is the exact difference between RSS and the memory that triggers OOMKill?

**What I think I know:**
OOMKill happens when a container's memory use exceeds `resources.limits.memory`. RSS is the physical RAM in use by the process. But I've read that the OOM killer considers more than just RSS — anonymous memory, page cache, shared memory.

**The specific gap:**
The `resources.limits.memory` in Kubernetes maps to a cgroup memory limit. But which memory counter does the cgroup use? Is it RSS? Is it RSS + page cache? If my app is reading a lot of files, does that cached file data count toward the cgroup limit?

**What I need to understand:**
- Exactly which memory counter is checked against `memory.limit_in_bytes` in cgroup v1? (`rss`? `rss + cache`? `usage_in_bytes`?)
- In cgroup v2, does this change? (The counter is `memory.current` — but what does it include?)
- If I set `limits.memory: 256Mi` and my app's RSS is 200Mi but it's also caching 100Mi of files, will it OOMKill?
- What is the difference between `kubectl top pod` memory number and the RSS in `ps aux`?

**Why this matters in production:**
I've seen pods OOMKilled when their `kubectl top pod` memory looked fine. This confusion between RSS, page cache, and cgroup accounting could explain that. I need to know which number to watch.

---

## Doubt 3 — What happens to in-flight HTTP connections when a pod receives SIGTERM?

**What I think I know:**
When Kubernetes terminates a pod (delete, eviction, rolling update), it sends SIGTERM to PID 1 in the container, waits `terminationGracePeriodSeconds` (default 30s), then sends SIGKILL if the process hasn't exited.

**The specific gap:**
If my FastAPI/uvicorn process receives SIGTERM while it is actively processing an HTTP request — what happens to that in-flight request? Does uvicorn:
- Immediately stop accepting new connections but finish in-flight ones (graceful drain)?
- Close all connections immediately (abrupt)?
- Crash and return a 502 to the client?

I don't know what uvicorn does by default on SIGTERM vs what I need to configure.

**What I need to understand:**
- Does uvicorn handle SIGTERM gracefully by default, or do I need to configure it?
- What is the exact sequence: Kubernetes removes pod from endpoints BEFORE or AFTER sending SIGTERM? (If after, there's a window where traffic is still being sent to a pod that's shutting down.)
- What does `preStop` hook do and when would I use it?
- If the grace period is 30s but a request takes 45s to complete, what happens?

**Why this matters in production:**
Rolling deployments at Copart will cause SIGTERM on old pods. If those pods drop in-flight requests, users see errors during deploys. Understanding the SIGTERM sequence determines whether we need a preStop sleep, a longer grace period, or application-level drain logic.

---

## Doubt 4 — When a Spring Boot app starts inside a container, what exactly is PID 1?

**What I think I know:**
The CMD/ENTRYPOINT in the Dockerfile becomes PID 1. In the JVM case, the java binary is PID 1. PID 1 has special signal-handling behavior in Linux — it does not get default SIGTERM handling unless explicitly coded for it.

**The specific gap:**
Spring Boot apps are often started with a shell script (`entrypoint.sh`) that calls `java -jar app.jar`. In that case, the shell script is PID 1, and java is a child process. SIGTERM sent by Kubernetes goes to the shell (PID 1), which may or may not forward it to the java child process.

**What I need to understand:**
- If the Dockerfile is `CMD ["sh", "-c", "java -jar app.jar"]`, what is PID 1? (`sh`). Does `sh` forward SIGTERM to java?
- What is the `exec` form vs `shell` form of CMD, and which one makes java PID 1?
- What does `exec java -jar app.jar` do inside a shell script, and why is it the correct way?
- Does Spring Boot have built-in graceful shutdown? If yes, does it only work when java is PID 1?

**Why this matters in production:**
Many Spring Boot pods at Copart may be started with shell scripts. If the shell is PID 1 and doesn't forward SIGTERM, Spring Boot never receives the shutdown signal, and the JVM is killed hard after 30 seconds — breaking in-flight requests and skipping graceful connection drain.

---

## Doubt 5 — Why does `kubectl exec` work even when the app is unhealthy?

**What I think I know:**
`kubectl exec` opens a connection to the kubelet on the node, which then runs `exec` in the container's process namespace. It doesn't go through the Service or Ingress. So it should work independently of app health.

**The specific gap:**
I understand why exec is independent of Service routing. But I don't fully understand what `kubectl exec` is actually doing at the system level inside the container. It's not SSH. There's no SSH daemon in most containers.

**What I need to understand:**
- What mechanism does `kubectl exec` actually use? (nsenter? The container runtime's exec API? Something else?)
- When I run `kubectl exec -it <pod> -- /bin/sh`, what namespaces does that shell join?
- If the container doesn't have `/bin/sh` or `/bin/bash`, why does exec fail? Is there an alternative?
- Does `kubectl exec` work on a pod that is in `CrashLoopBackOff`? (It shouldn't — the container isn't running — but I want to confirm the exact condition.)
- What is `kubectl debug` and when would I use it instead of `kubectl exec`?

**Why this matters in production:**
When a pod is crashing, I need to know immediately whether `kubectl exec` is available to me or not — and what to do instead when it isn't. Getting this wrong wastes time during an incident.

---

*Last updated: _(fill in)_*
