# Baseline Self-Assessment — Month 1 Start

**Date:** 2026-03-25  
**Purpose:** Establish an honest starting point across 12 core skills before Month 1 (Platform Foundation) begins. Scores are calibrated against what "production-ready" looks like, not against a beginner baseline. Every score includes the reasoning and the evidence behind it — not aspirations.

**Scale:**
| Score | Meaning |
|-------|---------|
| 1 | I know the concept exists but cannot use it under pressure |
| 2 | I can follow a tutorial but get lost when something goes wrong |
| 3 | I can operate independently on familiar tasks; I slow down on edge cases |
| 4 | I can reason through unfamiliar problems and explain my decisions |
| 5 | I can design, teach, and debug any production scenario in this domain |

---

## Skill 1 — Linux Process Understanding

**Score: 3 / 5**

**Why I scored myself a 3:**  
I can use `ps`, `top`, `htop`, `kill`, `systemctl`, and read `/proc` entries for a known process. I understand file descriptors, signal semantics (SIGTERM vs SIGKILL), and can debug a zombie process. Where I slow down: tracing inter-process communication under load, interpreting `strace` output beyond the first few lines, and understanding cgroup v2 resource accounting precisely (which matters for containers).

**Evidence from real work:**  
Debugged a Node.js process that was consuming 100% CPU by using `top -H` to isolate the thread, then `strace -p` to confirm it was stuck in a tight loop calling `epoll_wait`. Fixed by identifying a misconfigured event listener that never de-registered. Also routinely use `lsof` to confirm port bindings before deployments.

**What a 5 looks like:**  
Can read `/proc/[pid]/maps`, `smaps`, `fdinfo` fluently to diagnose memory leaks, file descriptor leaks, or unexpected mmap regions. Understands eBPF tooling (bpftrace, perf) well enough to write custom probes. Can tune cgroup limits precisely for a containerized workload and explain the kernel scheduler impact. Can mentor someone through a production incident using only Linux built-ins.

---

## Skill 2 — Ports & Connectivity

**Score: 3 / 5**

**Why I scored myself a 3:**  
Comfortable with `curl`, `nc`, `telnet`, `ss`, `netstat`, `tcpdump` for basic reachability checks. I understand TCP three-way handshake, TIME_WAIT, and why half-open connections accumulate. I can trace a refused connection to a missing listener vs a firewall drop. Where I struggle: reading a multi-hop `tcpdump` trace across namespaces (host → container → pod), interpreting conntrack table state for NAT'd traffic, and diagnosing asymmetric routing issues.

**Evidence from real work:**  
Traced a "connection refused" error in a staging environment back to a containerized app binding to `127.0.0.1` instead of `0.0.0.0`. Used `ss -tlnp` inside the container to confirm, then compared with the Kubernetes Service targetPort. Also used `tcpdump` on a bridge interface to confirm traffic was reaching a container but the app was dropping it silently.

**What a 5 looks like:**  
Can capture and annotate a full TCP session across network namespaces. Understands iptables/nftables rule evaluation order deeply enough to trace why a packet is being DNAT'd unexpectedly. Can diagnose MTU black holes, TCP window scaling mismatches, and retransmit storms from a pcap. Can explain Kubernetes kube-proxy iptables vs IPVS modes and their failure signatures.

---

## Skill 3 — HTTP Basics

**Score: 4 / 5**

**Why I scored myself a 4:**  
Strong on status codes, headers, caching semantics, CORS, redirects, and HTTP/1.1 keep-alive vs HTTP/2 multiplexing. I can reason about what a 502 vs 504 means from a proxy perspective without guessing. I understand chunked transfer encoding, `Content-Length` mismatches, and how `Connection: close` interacts with upstream timeouts. The gap: HTTP/3 and QUIC internals, and gRPC framing over HTTP/2 at the protocol level.

**Evidence from real work:**  
Diagnosed a 504 in production by correlating nginx upstream timeout logs (`upstream timed out`) with application APM traces showing a DB query holding a connection for 45 seconds. Understood immediately that nginx had given up before the app responded — not that the app crashed. Also debugged CORS preflight failures by reading `Access-Control-Request-Headers` and comparing against the server's `Access-Control-Allow-Headers` response — found a missing `Authorization` header in the allow list.

**What a 5 looks like:**  
Can read a raw HTTP/2 frame dump and identify stream ID collisions or HPACK compression errors. Understands WebSocket upgrade handshake and why proxies drop connections without `Upgrade` header passthrough. Can design caching strategy for a distributed CDN. Can diagnose gRPC status codes (not HTTP codes) from a network trace and map them to application behavior.

---

## Skill 4 — DNS Clarity

**Score: 2 / 5**

**Why I scored myself a 2:**  
I can use `dig`, `nslookup`, and `host`. I know A, CNAME, MX, TXT, NS record types and can query them. I understand that Kubernetes uses CoreDNS and that service names resolve to cluster-internal IPs. Where I get lost: understanding the full DNS resolution chain inside a cluster (search domains, ndots threshold), how CoreDNS plugin chain works, when a CNAME chain causes unexpected latency, and why TTL-based caching can cause stale routing after a failover. I could not confidently debug a split-horizon DNS setup without reference material.

**Evidence from real work:**  
Fixed a broken internal service call in Kubernetes by realizing the application was using a short hostname (`db`) that wasn't resolving because the pod's `resolv.conf` search domain list didn't include the correct namespace suffix. Ran `kubectl exec` into the pod and used `cat /etc/resolv.conf` + `dig db.default.svc.cluster.local` to confirm. That was a learner's debug, not an expert's.

**What a 5 looks like:**  
Can read a CoreDNS Corefile and predict exactly what queries will hit upstream resolvers vs be served locally. Understands DNSSEC chain of trust. Can diagnose split-horizon DNS inconsistencies where internal and external resolution return different answers. Can trace a DNS query through CoreDNS plugin chain (cache → forward → errors) using CoreDNS logs. Can explain ndots and how it interacts with search domain list to cause N+1 lookup overhead.

---

## Skill 5 — TLS / HTTPS Clarity

**Score: 2 / 5**

**Why I scored myself a 2:**  
I know what TLS does conceptually: certificate exchange, handshake, symmetric session keys. I can use `openssl s_client` to inspect a certificate chain and check expiry. I can configure cert-manager in Kubernetes for basic Let's Encrypt issuance. The gaps are significant: I cannot confidently trace a TLS handshake failure from a packet capture, I confuse myself on mTLS vs regular TLS client auth, I don't fully understand SNI and how it interacts with Ingress TLS termination, and I've never debugged a cipher suite negotiation failure.

**Evidence from real work:**  
Configured cert-manager `Certificate` and `ClusterIssuer` resources for an HTTPS Ingress and got it working, but only after following documentation closely. When the certificate wasn't issuing, I could see the cert-manager logs showed an ACME challenge failure — but I needed to look up what an HTTP-01 challenge required (publicly reachable `/.well-known/acme-challenge/` path) rather than knowing it from memory.

**What a 5 looks like:**  
Can trace a TLS handshake failure in Wireshark (alert code, record layer). Understands mTLS certificate rotation without downtime. Can configure Istio mTLS mode (STRICT vs PERMISSIVE) and explain the SPIFFE identity model. Knows exactly how SNI is used by nginx Ingress to route to different backends before TLS termination. Can explain certificate pinning, HPKP, and OCSP stapling trade-offs.

---

## Skill 6 — Docker Basics

**Score: 3 / 5**

**Why I scored myself a 3:**  
Comfortable writing Dockerfiles (multi-stage builds, layer caching, non-root users), running containers with volume mounts, port bindings, and environment variables. I understand image layers, the union filesystem concept, and why `docker build --no-cache` costs more. I know how to inspect a container (`docker inspect`, `docker logs`, `docker exec`). The gaps: I don't fully understand `buildkit` advanced features, I've never debugged a `seccomp` or `AppArmor` profile blocking a syscall, and I have surface-level understanding of Docker networking modes beyond bridge and host.

**Evidence from real work:**  
Debugged a container that was building successfully but failing at runtime because the base image had changed its default user from `root` to a non-root user — file permissions on a mounted volume were blocking writes. Identified by running `docker exec` and checking `id` and `ls -la` on the mount path. Also wrote a multi-stage Dockerfile for a Go service that reduced image size from 800MB to 22MB.

**What a 5 looks like:**  
Can write a secure Dockerfile with minimal attack surface (distroless, read-only filesystem, dropped capabilities) and explain each decision. Can diagnose a container failing due to seccomp profile syscall blocking using `strace` + profile comparison. Understands OCI image spec well enough to explain layer deduplication in a registry. Can debug Docker overlay2 storage driver issues at the filesystem level.

---

## Skill 7 — Kubernetes: Pod & Deployment

**Score: 3 / 5**

**Why I scored myself a 3:**  
I can write Pod and Deployment manifests, understand resource requests/limits, and reason about pod scheduling (node selector, affinity, taints/tolerations at a basic level). I know the pod lifecycle states (Pending → Running → Succeeded/Failed) and can use `kubectl describe pod` and `kubectl logs` to diagnose CrashLoopBackOff and ImagePullBackOff. The gaps: I don't have deep intuition for the scheduler's bin-packing algorithm, I get uncertain around `PodDisruptionBudget` semantics during rolling updates, and I haven't worked with `initContainers` enough to debug ordering issues confidently.

**Evidence from real work:**  
Debugged a Deployment that was stuck in `Pending` — used `kubectl describe pod` and saw `Insufficient memory` in the events. Confirmed by running `kubectl describe nodes` and seeing the node allocatable vs requested delta. Fixed by adjusting resource requests to accurate measured values rather than over-provisioned guesses. Also fixed a CrashLoopBackOff caused by a missing `ConfigMap` reference — `kubectl logs` showed the app panicking on startup with a missing env var.

**What a 5 looks like:**  
Can read scheduler logs and explain exactly why a pod was placed on a specific node. Understands Vertical Pod Autoscaler and HPA interaction edge cases (both scaling simultaneously). Can write a rolling update strategy with `maxUnavailable` and `maxSurge` tuned to a specific SLA requirement. Can debug `initContainer` deadlock (A waits for B, B waits for A) and explain readiness gate blocking. Understands `PodDisruptionBudget` enforcement during cluster upgrades.

---

## Skill 8 — Kubernetes: Service

**Score: 3 / 5**

**Why I scored myself a 3:**  
I understand ClusterIP, NodePort, and LoadBalancer Service types and can write their manifests. I know that a Service selects pods via label selectors and that `kubectl get endpoints` shows the backing pod IPs. I can trace a "no endpoints" error to a label mismatch. Where I get uncertain: kube-proxy iptables rule chain for a Service (I can explain it conceptually but not trace it live), how `externalTrafficPolicy: Local` vs `Cluster` affects source IP preservation, and how Headless Services interact with StatefulSet pod DNS.

**Evidence from real work:**  
Fixed a service that had no traffic by discovering the Deployment template labels didn't match the Service selector — a copy-paste error had left `app: frontend` in the Service but `app: frontend-v2` in the Deployment. Caught it by comparing `kubectl get svc -o yaml` selector against `kubectl get pods --show-labels`. Also set up a Headless Service for a StatefulSet and confirmed individual pod DNS entries resolved correctly using `dig` inside the cluster.

**What a 5 looks like:**  
Can trace the full iptables DNAT chain for a ClusterIP Service and explain why a specific packet hits endpoint A vs B. Understands `externalTrafficPolicy` impact on health checks with cloud load balancers. Can configure and debug topology-aware routing (zone-aware hints). Understands the implications of `sessionAffinity: ClientIP` and when it breaks under NAT. Can explain why Headless Service changes DNS TTL behavior and how StatefulSets rely on it.

---

## Skill 9 — Kubernetes: Ingress

**Score: 2 / 5**

**Why I scored myself a 2:**  
I can write basic Ingress manifests with host and path routing rules and have deployed the nginx Ingress controller. I understand that Ingress is a Layer 7 proxy sitting in front of Services. Where I consistently get uncertain: path matching precedence when multiple rules exist, how the nginx Ingress controller maps Ingress resources to nginx `server` and `location` blocks, the difference between a 502 and 504 from the nginx Ingress perspective, and `rewrite-target` annotation behavior with regex capture groups.

**Evidence from real work:**  
Set up an Ingress to route `/api/*` to one Service and `/` to another. It worked until I added a second host rule — the routing became unpredictable because I didn't understand that `pathType: Prefix` vs `pathType: Exact` have different precedence semantics. Had to read the nginx Ingress controller source to understand the ordering. That level of "had to read source to understand" is a 2, not a 3.

**What a 5 looks like:**  
Can read an nginx Ingress controller generated `nginx.conf` and predict exactly how a request will be routed. Understands `pathType: ImplementationSpecific` risks across controllers. Can configure canary Ingress annotations for traffic splitting with header-based routing. Understands how `ingress.class` and `IngressClass` resources interact in multi-controller clusters. Can diagnose TLS passthrough vs termination at the Ingress level.

---

## Skill 10 — Kubernetes: Probes (Liveness, Readiness, Startup)

**Score: 2 / 5**

**Why I scored myself a 2:**  
I know what liveness, readiness, and startup probes are and can configure them in a manifest. I understand that a failing readiness probe removes a pod from Service endpoints and a failing liveness probe triggers a restart. The conceptual gap: I am not confident about when to use a startup probe vs a high `initialDelaySeconds`, or why a pod can pass liveness but fail readiness (different paths, different conditions, different dependencies being checked). I've never tuned probe parameters (`failureThreshold`, `periodSeconds`, `successThreshold`) based on actual application SLA requirements — I've copied defaults.

**Evidence from real work:**  
Configured readiness and liveness probes for a Node.js app. The liveness probe hit `/healthz` (always returned 200) and the readiness probe hit `/ready` (checked DB connection). In one incident the pod was "running" but receiving no traffic — I didn't immediately understand why until I checked `kubectl describe pod` and saw readiness probe failures, meaning the DB connection was down but the process was alive. Understanding that after the fact is a 2.

**What a 5 looks like:**  
Can design a probe strategy for a slow-starting JVM app that avoids false-positive restarts during startup while still detecting deadlocks in steady state. Understands readiness gate (pod condition gate) as distinct from readiness probe and when Argo Rollouts or canary deployments depend on it. Can explain the cascading failure scenario where a failing readiness probe + HPA interaction causes a thundering herd. Knows `successThreshold` > 1 use cases.

---

## Skill 11 — Troubleshooting Confidence

**Score: 3 / 5**

**Why I scored myself a 3:**  
I follow a layered narrowing model and don't immediately jump to assumptions. I reach for evidence first (logs, events, metrics) before forming a hypothesis. I can hold a structured hypothesis in my head and eliminate layers systematically. Where my confidence breaks: under time pressure in production, I sometimes shortcut to "it's probably the app" without fully eliminating network. I also struggle when the symptom is intermittent — I don't have a solid methodology for capturing transient failures reliably.

**Evidence from real work:**  
Led debugging on a 503 incident that lasted 35 minutes. Started with nginx logs (upstream errors), moved to pod events (OOMKilled container — correct layer identified at minute 5), adjusted memory limits and deployed. The remaining 30 minutes were spent on the wrong layer (assuming the app had a memory leak) when the real cause was a dependency injecting large payloads that should have been rejected at the API gateway. Layer misidentification under pressure.

**What a 5 looks like:**  
Maintains composure and systematic methodology under P1 pressure. Has runbook-level instincts: given a symptom, can generate a ranked hypothesis list with specific evidence commands for each. Can conduct blameless retrospectives that identify systemic causes, not just immediate causes. Can debug intermittent issues by instrumenting with targeted metrics or tracing before the next occurrence rather than waiting to catch it live. Writes runbooks that someone else can follow to the same resolution.

---

## Skill 12 — Ability to Explain Clearly

**Score: 3 / 5**

**Why I scored myself a 3:**  
I can explain technical concepts accurately to engineers at my level or slightly below. I use analogies effectively for things I deeply understand (e.g., TCP handshake as a phone call). The gap: when I explain concepts I only partially understand (TLS internals, DNS delegation), my explanations become accurate-but-vague — I cover the concept without giving the listener anything actionable. I also tend to over-explain background before getting to the point when under stress.

**Evidence from real work:**  
Successfully onboarded two junior engineers to Kubernetes basics — both could write and debug simple Deployments and Services independently within a week. However, when a senior engineer asked me to explain why a particular routing decision was made in a multi-cluster setup, I gave a technically correct but unhelpfully abstract answer. The senior had to ask three follow-up questions to get to the actual root of the decision.

**What a 5 looks like:**  
Can explain any concept in the 12-skill list to a non-technical stakeholder, a junior engineer, and a principal engineer — calibrating depth and vocabulary in real time. Can write documentation that someone can follow without asking follow-up questions. Can give a concise, structured incident post-mortem to an executive audience in under 3 minutes. Explanations make the listener feel more capable, not more confused.

---

## Summary Snapshot

| # | Skill | Score | Primary Gap |
|---|-------|-------|-------------|
| 1 | Linux Process Understanding | 3 | cgroup v2, eBPF tooling |
| 2 | Ports & Connectivity | 3 | multi-namespace tcpdump, conntrack |
| 3 | HTTP Basics | 4 | HTTP/3, gRPC framing |
| 4 | DNS Clarity | 2 | CoreDNS internals, ndots, split-horizon |
| 5 | TLS / HTTPS Clarity | 2 | handshake tracing, mTLS, SNI + Ingress |
| 6 | Docker Basics | 3 | seccomp, buildkit, networking modes |
| 7 | K8s Pod & Deployment | 3 | scheduler internals, PDB, initContainers |
| 8 | K8s Service | 3 | iptables chain tracing, externalTrafficPolicy |
| 9 | K8s Ingress | 2 | path precedence, nginx config generation |
| 10 | K8s Probes | 2 | startup vs delay tuning, readiness gate |
| 11 | Troubleshooting Confidence | 3 | intermittent failures, time-pressure discipline |
| 12 | Ability to Explain Clearly | 3 | depth calibration, conciseness under stress |

**Average: 2.8 / 5**

### Priority Focus Areas for Month 1

Skills scored 2 are the highest-leverage targets — they represent gaps where I can get stuck in production without a clear path forward:

1. **DNS Clarity (2)** — CoreDNS plugin chain, ndots, search domain behavior
2. **TLS / HTTPS (2)** — Handshake tracing, SNI, cert-manager edge cases
3. **K8s Ingress (2)** — nginx config generation, path matching, 502 vs 504 semantics
4. **K8s Probes (2)** — Probe parameter tuning, readiness gate, startup probe design

Skills at 3 are "functional but not expert" — the goal is to move at least two of them to 4 by end of Month 1 through deliberate practice and incident simulation.
