# Day 2 — Class 2: DNS Inside Kubernetes

**Date:** 2026-03-30  
**Topic:** CoreDNS internals, ndots, search domains, DNS TTLs, and the JVM caching footgun  
**Priority gap addressed:** DNS (scored 2/5 in baseline assessment)

---

## Question 1 — What exactly happens when a pod queries a short hostname like `db`?

When a pod in namespace `default` runs `curl http://db`, the OS does NOT send a query for `db` directly. Instead it follows the rules in `/etc/resolv.conf`, which CoreDNS injects into every pod at creation time.

**A typical pod's `/etc/resolv.conf`:**
```
nameserver 10.96.0.10          # ClusterIP of the kube-dns Service
search default.svc.cluster.local svc.cluster.local cluster.local
options ndots:5
```

**The resolution sequence for `db` (4 DNS queries, not 1):**

Because `db` has **0 dots**, and `ndots:5` means "treat as relative if the name has fewer than 5 dots", the resolver runs through the search list before trying the bare name:

1. `db.default.svc.cluster.local` → CoreDNS responds with an A record if a Service named `db` exists in namespace `default`. ✓ Stop here.
2. `db.svc.cluster.local` → (only reached if step 1 fails)
3. `db.cluster.local` → (only reached if step 2 fails)
4. `db` → (absolute query, reached only if all above fail)

**For a name with 5+ dots** (e.g., `a.b.c.d.e.f`), `ndots:5` treats it as already fully qualified — the search list is skipped entirely and only one query is sent.

**The performance implication:**
Every time a pod calls `db.default.svc.cluster.local` correctly (fully qualified), CoreDNS answers it in one round trip. But when apps use short hostnames, they burn 1–4 DNS queries per connection setup. At high request rate (thousands of connections/second), this creates measurable DNS amplification load on CoreDNS.

**Production pattern to know:**
Some teams configure `ndots:2` in their pod spec to reduce unnecessary lookups for apps that only query internal Services:
```yaml
spec:
  dnsConfig:
    options:
      - name: ndots
        value: "2"
```
This means a name like `db.default` (1 dot) still goes through the search list, but `db.default.svc` (2 dots) is treated as absolute. Trade-off: external names with fewer than 2 dots would also skip the search list.

---

## Question 2 — How does CoreDNS actually work internally? What is the Corefile?

CoreDNS is a DNS server built as a **plugin chain**. Every DNS query passes through a configured list of plugins in order. The configuration lives in the **Corefile** (a ConfigMap in the `kube-system` namespace).

**Default Corefile in a standard cluster:**
```
.:53 {
    errors
    health {
       lameduck 5s
    }
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa {
       pods insecure
       fallthrough in-addr.arpa ip6.arpa
       ttl 30
    }
    prometheus :9153
    forward . /etc/resolv.conf {
       max_concurrent 1000
    }
    cache 30
    loop
    reload
    loadbalance
}
```

**What each relevant plugin does:**

| Plugin | What it does |
|--------|-------------|
| `errors` | Logs DNS errors to stdout |
| `kubernetes` | Resolves in-cluster names: `svc.cluster.local`, `pod.cluster.local` |
| `forward` | Forwards unresolved queries upstream (to node's resolv.conf → your corporate DNS or 8.8.8.8) |
| `cache 30` | Caches all responses for up to 30 seconds (TTL cap) |
| `loadbalance` | Round-robins A records returned to pods (for multi-endpoint headless Services) |

**Resolution flow for an in-cluster query (`my-svc.default.svc.cluster.local`):**
1. Query arrives at CoreDNS on port 53
2. `errors` plugin passes it through
3. `kubernetes` plugin checks its in-memory cache of Services/Endpoints → finds a match → returns the ClusterIP as an A record with TTL=30
4. `cache` plugin stores this response for 30 seconds
5. Response returned to the pod

**Resolution flow for an external query (`google.com`):**
1. `kubernetes` plugin: no match (not `.cluster.local`) → `fallthrough`
2. `forward` plugin: sends query to the node's upstream DNS resolver
3. Response returned and cached

**Key insight — TTL is 30 seconds by default:**
The `ttl 30` in the `kubernetes` stanza and `cache 30` mean that a pod gets a cached DNS answer for up to 30 seconds. If a Service's ClusterIP changes (rare, but possible on delete+recreate), pods can use stale IPs for up to 30 seconds.

---

## Question 3 — When does DNS TTL actually cause stale routing in production?

This was Doubt 3. Here is the concrete answer:

**Scenario 1: Delete and recreate a Service with the same name (different ClusterIP)**

Kubernetes does NOT guarantee a Service gets the same ClusterIP on recreation. If:
1. Service `my-svc` has ClusterIP `10.96.100.50`
2. You delete it and recreate it → new ClusterIP might be `10.96.100.51`
3. Pods that queried `my-svc` in the last 30 seconds have `10.96.100.50` in their CoreDNS cache
4. Those pods' requests go to a dead IP for up to 30 seconds

**Scenario 2: StatefulSet pod replacement**

StatefulSet pods have stable DNS names: `pod-0.my-svc.default.svc.cluster.local`. But when a pod is replaced (restarts, reschedule), its pod IP **changes**. The DNS record in CoreDNS updates immediately (kube-dns watches the pod), but the `cache` plugin means pods querying that name can have the old IP cached for up to 30 seconds.

For a StatefulSet (e.g., Kafka, Zookeeper, etcd), this 30-second stale window can cause connection failures if the app reconnects after a pod restarts.

**Scenario 3: JVM DNS caching (the footgun)**

JVM caches DNS resolution results **indefinitely** by default (`networkaddress.cache.ttl = -1` means forever). This means:
- A Java app that starts and resolves `my-svc` at startup will **never re-query** CoreDNS
- If the Service is deleted and recreated (new ClusterIP), the Java app continues sending traffic to the old (now dead) IP
- The app appears broken while non-JVM apps on the same pod recover after 30 seconds

**Fix:** Set `networkaddress.cache.ttl=30` in the JVM's `java.security` file, or in the application's startup arguments via `-Dsun.net.inetaddr.ttl=30`. This forces re-resolution after 30 seconds, aligning with CoreDNS's cache TTL.

**Scenario 4: External DNS failover**

If your app queries an external name (e.g., `db.prod.mycompany.com` for an RDS endpoint) and that DNS record changes during a failover (e.g., RDS primary switches to a replica), the `forward` plugin passes this to the upstream DNS. The upstream TTL might be 60–300 seconds. Pods will use the stale DB IP for that duration.

---

## Question 4 — How do I debug DNS issues in a live cluster?

**Step 1: Check what the pod sees**

```bash
kubectl exec -it <pod-name> -- cat /etc/resolv.conf
```
Tells you: what nameserver the pod is using, what search domains are configured, and what ndots value is set.

**Step 2: Run a DNS query from inside the pod**

```bash
kubectl exec -it <pod-name> -- nslookup my-svc
kubectl exec -it <pod-name> -- nslookup my-svc.default.svc.cluster.local
kubectl exec -it <pod-name> -- dig my-svc +search +all
```

`nslookup my-svc` will show you exactly which name got queried and what response came back. If you see 4 queries before resolution, that's the ndots search list being exhausted.

**Step 3: Check if CoreDNS is healthy**

```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns
```

Look for repeated error lines like `SERVFAIL` (CoreDNS is forwarding but upstream is broken) or `NXDOMAIN` (the name doesn't exist in the zone).

**Step 4: Check CoreDNS metrics (if Prometheus is available)**

The `prometheus :9153` plugin in the Corefile exposes:
- `coredns_dns_requests_total` — total queries by type
- `coredns_dns_responses_total` — responses by rcode (NOERROR, NXDOMAIN, SERVFAIL)
- `coredns_cache_hits_total` / `coredns_cache_misses_total` — cache hit ratio

A sudden spike in `SERVFAIL` or a drop in cache hit ratio is a leading indicator of DNS layer problems.

**Step 5: Run a DNS debug pod if the original pod has no tools**

```bash
kubectl run dns-debug --image=busybox:1.28 --rm -it --restart=Never -- nslookup my-svc.default.svc.cluster.local
```

Note: use `busybox:1.28` specifically — newer versions of busybox changed `nslookup` behavior.

---

## Question 5 — What is the DNS record structure for different Kubernetes objects?

Understanding what DNS records exist — and for which objects — is essential for knowing what to query when debugging.

**Services:**

| Type | DNS name | Record | Resolves to |
|------|----------|--------|-------------|
| ClusterIP | `<svc>.<ns>.svc.cluster.local` | A | ClusterIP |
| ClusterIP | `<svc>.<ns>.svc.cluster.local` | SRV | port + protocol info |
| Headless (`clusterIP: None`) | `<svc>.<ns>.svc.cluster.local` | A | All pod IPs (multiple A records) |
| ExternalName | `<svc>.<ns>.svc.cluster.local` | CNAME | External hostname |
| NodePort / LoadBalancer | Same as ClusterIP | A | ClusterIP (not the node IP) |

**Pods:**

| Condition | DNS name | Record |
|-----------|----------|--------|
| Default | `<pod-ip-dashes>.<ns>.pod.cluster.local` | A |
| StatefulSet pod | `<pod-name>.<headless-svc>.<ns>.svc.cluster.local` | A |

**Key insight — StatefulSet DNS:**
StatefulSet pods get stable DNS names **only if you also create a headless Service** (the `serviceName` field in the StatefulSet spec). Without the headless Service, the pod DNS name does not exist. This is why StatefulSets always specify `serviceName`.

**What "headless" means for routing:**
A headless Service (`clusterIP: None`) returns multiple A records — one per ready pod IP. The client's DNS resolver typically uses the first one (or whichever one the OS returns). There is no load balancing at the Service level — the app is responsible for handling multiple addresses or connecting to a specific pod by index.

This is why databases like Kafka and Cassandra use headless Services: each client needs to connect to specific nodes (by partition/replica role), not a random one.

---

## Real-World Connection (Copart Environment)

Your org uses external nginx VMs + BGP, not K8s Ingress. But CoreDNS still governs all pod-to-pod and pod-to-service resolution **within** the cluster. The nginx VMs resolve the backend pods by querying `<svc>.<ns>.svc.cluster.local` or directly by pod IP via BGP-advertised routes.

This means DNS debugging is still essential even in your org's architecture — the path from nginx to the K8s backend goes through ClusterIP, which requires DNS resolution inside the cluster if you're using service names in the nginx `upstream` block.

---

**Date written:** 2026-03-30
