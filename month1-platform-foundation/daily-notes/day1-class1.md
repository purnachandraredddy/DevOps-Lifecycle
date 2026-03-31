# Day 1 — Class 1: Systems Thinking & Layered Troubleshooting

**Date:** 2026-03-25  
**Topic:** Systems thinking, the 8-layer troubleshooting model, symptom vs root cause

---

## Question 1 — What is my personal definition of troubleshooting?

Troubleshooting is **evidence-driven narrowing**: the systematic process of eliminating possible layers until only one remains as the source of a failure, using observable signals rather than intuition.

The key word is *narrowing*. A guess is not a hypothesis. A hypothesis is a statement tied to evidence — "the service has no endpoints because the label selector doesn't match" is a hypothesis. "It might be a networking issue" is a guess. Troubleshooting done well produces a ranked list of hypotheses, and each check either eliminates a layer or confirms it.

The deeper principle: in a complex layered system, symptoms always appear at a layer above the root cause. A `504 Gateway Timeout` appears at Layer 4 (Ingress) but the cause is at Layer 7 (slow DB query) or Layer 8 (connection pool exhausted). The error code is the smoke; the root cause is the fire. Every troubleshooting action moves you closer to the fire by eliminating the smoke.

**Operating model I hold:**
1. Observe the symptom — precisely (status code, error message, layer it surfaced at)
2. Identify the highest layer that is confirmed healthy
3. Identify the lowest layer that is confirmed broken
4. Narrow the gap with evidence until they converge on the same layer
5. Fix at the root cause layer, not the symptom layer

This is the same model surgeons use (differentials), detectives use (eliminate suspects), and scientists use (falsify hypotheses). It is not specific to engineering — but engineering gives it a concrete layer stack to work through.

---

## Question 2 — What is the difference between a symptom and a root cause?

A **symptom** is the observable signal: what the user sees, what the monitoring alert fires on, what the HTTP response code is. A **root cause** is the underlying system state that caused that signal to appear.

The same symptom can have multiple root causes at different layers. That is why symptoms are not debugging targets — they are debugging starting points.

**Concrete example: 504 → DB connection pool exhaustion**

```
Symptom (Layer 4):
  nginx logs: "upstream timed out (110: Connection timed out) while reading response header from upstream"
  User sees: HTTP 504 Gateway Timeout

Surface hypothesis (wrong):
  "The app is slow — scale it up"

Actual chain:
  Layer 7: Application received the request, started processing
  Layer 7: Application attempted to acquire a DB connection from the pool
  Layer 8: All 20 connection pool slots were occupied by long-running queries
  Layer 7: Application hung waiting for a free connection slot
  Layer 4: nginx proxy-read-timeout (60s) fired before app responded
  Layer 4: nginx returned 504 to the user

Root cause (Layer 8):
  A slow analytics query (unindexed full-table scan) was holding DB connections open for 45+ seconds.
  Pool exhausted. New requests waited. nginx timed out.

Fix at root cause layer (Layer 8):
  Add index on the queried column.
  Set a query timeout in the application to fail fast rather than hold a slot.
  Optionally: increase pool size as a temporary mitigation (not a fix).
```

If you fix at the symptom layer (scale up app replicas), you have more processes all waiting on the same exhausted pool. The 504s continue. Only fixing at Layer 8 resolves the problem.

**The general pattern:**
- `5xx` errors → the cause is almost always below Layer 4
- `4xx` errors from a proxy → usually Layer 4 (routing) or Layer 5 (no endpoints)
- `4xx` errors from the app itself → Layer 7 (business logic) or Layer 8 (auth/config)
- Connection errors → Layer 2 (DNS) or Layer 3 (network)

---

## Question 3 — Layers I understand well

**Layer 3 — Network / Connection (confident)**

I have direct production experience with this layer. I understand the difference between `Connection refused` (RST sent — something is there, port is wrong or app binding is wrong) and `Connection timed out` (no RST, packet dropped — firewall or Security Group). I can use `nc -zv`, `curl -v`, `ss -tlnp`, and `tcpdump` effectively. I have debugged the "app binds to 127.0.0.1 instead of 0.0.0.0" failure mode and can catch it quickly.

**Layer 7 — Application (confident)**

Strong on reading application logs, understanding `500 vs 504 vs 502` from the application's perspective, using APM traces to find internal latency, and reasoning about timeout chains (DB query timeout → app request timeout → proxy timeout → client timeout). I have debugged the DB query blocking the connection pool scenario from real production experience.

**Layer 5 — Service / Endpoints (functional)**

I can trace the label selector → endpoint mapping and catch mismatches quickly. My gap is the deeper iptables/IPVS mechanics behind `kube-proxy`, but I don't need them for 80% of Service issues.

**Layer 6 — Pod / Container (functional)**

Comfortable reading `kubectl describe pod` events, distinguishing `CrashLoopBackOff` vs `OOMKilled`, and checking `--previous` logs. The probe layer is where I start to slow down — specifically when a pod passes liveness but fails readiness (different endpoints, different conditions being checked).

---

## Question 4 — Layers that are still blurry

**DNS — specifically inside Kubernetes:**

I understand *what* DNS does but not *how* CoreDNS resolves queries step by step inside a cluster. The part I cannot reason through confidently: when a pod queries `db`, what is the exact resolution sequence? The search domain list in `/etc/resolv.conf` (`default.svc.cluster.local`, `svc.cluster.local`, `cluster.local`) is appended in order before the bare name is tried — but the interaction with `ndots: 5` means that any name with fewer than 5 dots triggers the search list first. This creates N+1 DNS lookups for every short hostname, which I have read about but never traced live in a cluster under load.

The CoreDNS plugin chain (`cache` → `forward` → `errors` → `health`) is also opaque to me. I don't know how to read a CoreDNS Corefile and predict exactly which queries hit the cache, which go upstream, and which get served from the in-cluster zone.

**Ingress — path/host matching precedence:**

When multiple Ingress resources exist, and some have the same host with overlapping paths, I cannot confidently predict which rule wins. I understand `pathType: Prefix` vs `pathType: Exact` at a definition level but not at the "how nginx implements this" level. The nginx Ingress controller merges all Ingress resources into a single `nginx.conf` — the precedence of `location` blocks in that generated config is what actually matters, and I've only read about it, not traced it.

**Readiness gate vs readiness probe:**

I know what a readiness probe is. I do not have a clear mental model of readiness gates (pod condition gates used by Argo Rollouts, progressive delivery systems). The distinction between "probe succeeds" and "readiness gate is open" is something I have not internalized from production experience.

---

## Question 5 — One real incident, classified by layer

**Incident: 503 on all requests after a deployment**

**Symptom (what the user/monitor saw):**
All requests to the `api.internal` service returned `503 Service Unavailable` for approximately 8 minutes after a deployment. nginx Ingress logs showed `no live upstreams while connecting to upstream`.

**Evidence gathered:**

1. `kubectl get pods -n production` → new pods were `Running` but `0/1 Ready`
2. `kubectl describe pod <new-pod>` → events showed readiness probe failing: `HTTP probe failed with statuscode: 503`
3. The application's `/ready` endpoint was returning `503` because it checked the database connection on startup, and the DB was still processing schema migration from the previous deployment step
4. `kubectl get endpoints api-svc -n production` → endpoint list was empty
5. `kubectl logs <new-pod>` → app logs showed: `Waiting for database migrations to complete... DB not accepting application connections`

**Layer identified:** Layer 6 (Pod / Container) — readiness probe failing because the pod was genuinely not ready

**Root cause:** The readiness probe was correct. The application was waiting for a DB migration job to complete before accepting traffic. The migration job had not completed before the new pods started probing. This was a sequencing problem in the deployment pipeline — the migration job should have been verified as complete before the Deployment rollout began.

**What I missed initially:** I assumed the 503 meant the Ingress was misconfigured (Layer 4 assumption). I spent 4 minutes checking `kubectl describe ingress` and nginx logs before I looked at endpoints. If I had followed the narrowing model, `kubectl get endpoints` at minute 1 would have shown empty endpoints → immediately pointed to Layer 5/6 → then Layer 6 → the pod not being ready.

**What I would check first next time:**
1. `kubectl get endpoints <svc>` — immediately tells me if the service has backing pods
2. If empty: `kubectl get pods --show-labels` + compare to service selector
3. If pods exist but not Ready: `kubectl describe pod` → readiness probe failure section

**Knowledge graph from this incident:**
- `readiness_probe_failure removes_pod_from endpoints`
- `empty_endpoints causes 503_at_ingress`
- `migration_dependency causes_readiness_probe_failure`
- `deployment_sequencing must_ensure migration_complete_before_pod_start`
- `503_symptom masked Layer_5_root_cause`

---

## My Definition of Troubleshooting — Day 1

Troubleshooting is observing the symptom, identifying which layer it surfaced at, then collecting evidence layer by layer until only one cause remains. You follow the signal — status code, log line, probe state — not your gut.

**Date written:** 2026-03-25
