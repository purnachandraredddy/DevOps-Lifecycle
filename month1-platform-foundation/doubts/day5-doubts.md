# Day 2 — Doubts & Open Questions

**Date:** 2026-03-30  
**Session topic:** DNS inside Kubernetes — CoreDNS, ndots, search domains, TTLs  
**Rule:** Every question here must be precise enough that a concrete answer can be given. No vague questions. Every doubt must expose a specific gap that, if filled, would change how I debug something.

---

## Doubt 1 — What happens to DNS resolution when CoreDNS itself is down or overloaded?

**What I think I know:**
Every pod has `nameserver 10.96.0.10` (or similar ClusterIP for the `kube-dns` Service) in its `/etc/resolv.conf`. If CoreDNS is unreachable, DNS queries time out. The `options timeout:1` and `options attempts:2` defaults in resolv.conf mean each query waits up to 1 second and retries 2 times before failing.

**The specific gap:**
If CoreDNS has 2 replicas and one crashes:
- Does the kube-dns Service ClusterIP automatically route only to the healthy replica? (Yes, because the endpoint is removed when the pod fails readiness — but how fast?)
- Is there a window where in-flight queries are dropped while kube-proxy updates its iptables rules?
- What does an app experience during that window? A single 1-second timeout? Multiple retries?

**What I need to understand:**
- What is the CoreDNS readiness probe and what triggers it? Is it purely HTTP health check or does it test actual DNS resolution?
- In a cluster under load, how long does it take from CoreDNS pod failure → kube-proxy updates iptables → pod DNS queries stop hitting the dead pod?
- What is the practical blast radius of one CoreDNS pod crashing (in a 2-replica setup)?

**Why this matters in production:**
I have seen "random" DNS timeouts that lasted 1–3 seconds, appearing intermittently. I blamed the app. These could have been CoreDNS pod restarts causing a brief window where some queries hit a terminating pod. I want to be able to confirm or rule this out from `kubectl logs` and metrics.

---

## Doubt 2 — How does ndots interact with fully qualified domain names in practice?

**What I think I know:**
A name ending with `.` is treated as fully qualified by the resolver and skips the search list entirely, regardless of ndots. A name without a trailing dot with 5+ dots is also treated as absolute by the `ndots:5` rule.

**The specific gap:**
In practice, app configs rarely include trailing dots. When I see a connection string like `my-svc.default.svc.cluster.local` in a config file, does that have 4 dots or 5? Let me count: `my-svc` → `.` → `default` → `.` → `svc` → `.` → `cluster` → `.` → `local` = 4 dots. With `ndots:5`, this is fewer than 5 dots, so the search list fires first.

That means even a "fully qualified" in-cluster name without a trailing dot still triggers unnecessary search list lookups? Is that right?

**What I need to understand:**
- Confirm: `my-svc.default.svc.cluster.local` (4 dots, no trailing dot) → goes through search list with ndots:5?
- If so, the first query would be `my-svc.default.svc.cluster.local.default.svc.cluster.local` — which is obviously wrong and returns NXDOMAIN quickly — but is this visible in CoreDNS logs?
- What is the precise query sequence CoreDNS sees when an app queries `my-svc.default.svc.cluster.local`?
- Is there a way to force all in-cluster queries to be treated as absolute without adding a trailing dot everywhere? (Perhaps reducing ndots?)

**Why this matters in production:**
If I'm debugging high DNS query volume and the metrics show many NXDOMAIN responses, I need to know whether these are real failures or just the search list exhausting itself normally. The number of "expected" NXDOMAIN queries per successful resolution depends on the query format.

---

## Doubt 3 — How does CoreDNS handle split-horizon DNS?

**What I think I know:**
Split-horizon DNS means the same name resolves differently depending on who is asking (internal vs external). Inside a cluster, `api.example.com` might resolve to a ClusterIP. Outside, it resolves to a public load balancer IP.

**The specific gap:**
I don't understand how CoreDNS handles this concretely. The `forward` plugin sends unresolved queries (non-`.cluster.local`) to the node's upstream DNS. That upstream is usually the corporate DNS server or cloud provider's DNS. If corporate DNS knows about internal service names, does CoreDNS just forward those transparently?

What if I want `api.internal.example.com` to resolve differently inside the cluster than outside — pointing to a ClusterIP instead of a public IP?

**What I need to understand:**
- Can I add a `stub zone` to the CoreDNS Corefile to handle specific domains locally while forwarding everything else upstream?
- What does a stub zone Corefile entry look like for `internal.example.com`?
- In the `forward` plugin, what happens if the upstream DNS returns a private IP for a name — does CoreDNS return it as-is? Or does it filter/rewrite?
- How do I verify that a specific query is being handled by the `kubernetes` plugin vs being forwarded upstream?

**Why this matters in production:**
Your org (`copart.com`) likely uses split-horizon DNS. Services have `*.k8s.copart.com` internal names and separate public names. Understanding how CoreDNS routes those queries determines whether you need to modify the Corefile or whether the existing forwarding handles it correctly.

---

## Doubt 4 — What does a SERVFAIL from CoreDNS actually mean vs NXDOMAIN?

**What I think I know:**
- `NXDOMAIN` (Non-Existent Domain) = the DNS name does not exist. The authoritative server confirmed it.
- `SERVFAIL` = the DNS server encountered an internal error and could not process the query.

**The specific gap:**
From CoreDNS logs, when I see a SERVFAIL — what is the most common cause inside a cluster?

I've read that SERVFAIL can happen when:
1. CoreDNS cannot reach the upstream forwarder (network issue, upstream down)
2. The upstream returns a SERVFAIL itself (upstream DNS is broken)
3. A bug in a CoreDNS plugin causes a panic/recovery
4. A malformed query or response triggers an error path

But I cannot confidently distinguish these from a CoreDNS log line alone.

**What I need to understand:**
- What does a CoreDNS log line look like for case 1 (upstream unreachable) vs case 2 (upstream returns SERVFAIL)?
- In the `errors` plugin output, what text appears for each failure mode?
- If I see `SERVFAIL` spikes in CoreDNS metrics — what is my first diagnostic step?
- Can a SERVFAIL from the cluster's DNS cause a pod to fall back to something, or does it just fail with a timeout/error?

**Why this matters in production:**
SERVFAIL is the most disruptive DNS error because apps typically don't distinguish it from a network error — they just see "hostname resolution failed" and crash or circuit-break. Being able to read CoreDNS logs and immediately identify the cause determines how fast I can remediate a cluster-wide DNS outage.

---

## Doubt 5 — How does DNS resolution interact with connection pooling in services like databases?

**What I think I know:**
When an application opens a database connection, it resolves the hostname once and establishes a TCP connection to that IP. If the connection is pooled (reused across requests), the DNS resolution only happens when a new connection is opened, not for every query.

**The specific gap:**
If the DB's DNS entry changes (e.g., a primary-to-replica failover), and the application has 20 pooled connections all pointing to the old IP:
- The old connections do not break immediately — they remain open until the old server closes them (RST/FIN) or the application's TCP keepalive fires
- New connections opened after the DNS change will get the new IP
- But if the app's connection pool always reuses existing connections (max pool size reached), no new connections are ever opened, so no new DNS lookups happen

Is this correct? And if so, what actually triggers the app to open new connections and pick up the new DNS entry?

**What I need to understand:**
- What is the exact sequence of events during a DNS-based DB failover for a connection-pooled Java application?
- If the old DB server goes down (RST), how quickly does HikariCP (common Java connection pool) detect the dead connection and open a new one? Does it test connections before use, or only after a query fails?
- For Redis (often used without a connection pool, with single persistent connection): is Redis's reconnect logic DNS-aware? After a reconnect, does it re-resolve the hostname?
- Does any of this behavior change if using a Service mesh (Envoy/Istio) where the sidecar handles connection management?

**Why this matters in production:**
Database failover events often cause application errors for longer than necessary because the app doesn't drop and re-establish connections fast enough. Understanding the exact mechanism determines whether the fix is DNS TTL, connection pool configuration, or a healthcheck-driven reconnect policy.

---

*Last updated: 2026-03-30*
