# Session Handover — DevOps Lifecycle

Read SESSION_HANDOVER.md first, then continue from the latest pending task
> **Start every new Cursor chat on any machine with:**
> `Read SESSION_HANDOVER.md first, then continue from the latest pending task.`

---

## Who I Am

- **Name:** Purnachandra Reddy Peddasura
- **GitHub:** [purnachandraredddy](https://github.com/purnachandraredddy)
- **Role context:** Moving from operator to architect — building mental models, diagnostic discipline, and hands-on fluency to own a production platform end-to-end.
- **Work environment:** Copart (uses external nginx VMs + BGP for routing, not Kubernetes Ingress objects directly).

---

## Project Overview

**DevOps-Lifecycle** — A structured 12-week learning repo for mastering production platform engineering through layered troubleshooting, Kubernetes operations, and systematic debugging.

**Current phase:** Month 1 — Platform Foundation (started 2026-03-25)

**Repo structure:**

| Folder | Purpose |
|--------|---------|
| `month1-platform-foundation/daily-notes/` | Raw class notes per session |
| `month1-platform-foundation/docs/` | Polished reference material (system-layers.md is the main doc) |
| `month1-platform-foundation/assessments/` | Self-assessment scores (baseline done, re-score at 2 weeks) |
| `month1-platform-foundation/doubts/` | Precise questions exposing real knowledge gaps |
| `month1-platform-foundation/app/` | Sample FastAPI app with `/`, `/health`, `/ready` endpoints |
| `month1-platform-foundation/k8s/` | Kubernetes manifests (not yet created) |
| `month1-platform-foundation/diagrams/` | Architecture diagrams (not yet created) |

---

## What Has Been Completed

### Day 2 (2026-03-30)
- Completed DNS deep-dive class notes (`daily-notes/day2-class2.md`):
  - ndots:5 resolution sequence (4 queries per short hostname)
  - CoreDNS Corefile anatomy (plugin chain, forward, cache 30s TTL)
  - DNS TTL failure scenarios: Service delete/recreate, StatefulSet pod IP change, JVM caching footgun, external DNS failover
  - DNS debugging commands: `nslookup`, `dig +search`, CoreDNS metrics, dns-debug pod
  - Full DNS record structure for Services, headless Services, and StatefulSet pods
- Wrote 5 precise doubts (`doubts/day2-doubts.md`): CoreDNS pod failure blast radius, ndots+FQDN interaction, split-horizon DNS, SERVFAIL vs NXDOMAIN, DNS+connection pooling during DB failover
- Created Kubernetes manifests (`k8s/`):
  - `deployment.yaml` — 2-replica Deployment with startup/liveness/readiness probes, resource limits, annotated
  - `service.yaml` — ClusterIP Service with selector explanation and iptables/IPVS notes
  - `ingress.yaml` — nginx Ingress with Exact/Prefix path rules + full nginx.conf generation explanation
  - `k8s/README.md` — full local deploy guide (minikube), layer-by-layer verification steps, probe behavior diagram
- Created `app/Dockerfile` and `app/requirements.txt` for building the FastAPI image

### Day 1 (2026-03-25)
- Established the 8-layer troubleshooting model (Client → DNS → Network → Ingress → Service → Pod → Application → Config)
- Wrote detailed class notes with 5 mandated questions answered (`daily-notes/day1-class1.md`)
- Created baseline self-assessment across 12 skills (average: 2.8/5)
- Documented 6 precise doubts with specific gaps identified (`doubts/day1-doubts.md`)
- Built full system-layers reference doc with decision tree, commands, and knowledge graphs (`docs/system-layers.md`)
- Created sample FastAPI app (`app/main.py`) with health/ready endpoints

### Real Incident Documented (2026-03-27)
- **Symptom:** `configserver.c-qa4.svc.rnq.k8s.copart.com` returning 404
- **Root cause:** nginx `server_name` mismatch — internal K8s DNS name used as public URL; nginx had no matching server block
- **Layer:** Layer 4 (Ingress/Proxy)
- **Key learning:** nginx routes by Host header, not just IP/port; 404 from nginx ≠ app broken

### Repo Setup
- Git initialized, `.gitignore` added
- GitHub repo created (public): https://github.com/purnachandraredddy/DevOps-Lifecycle
- Initial commit pushed to `main` branch
- GitHub CLI (`gh`) installed via winget, authenticated via browser

---

## Self-Assessment Snapshot (Baseline — 2026-03-25)

| Skill | Score | Primary Gap |
|-------|-------|-------------|
| Linux Process Understanding | 3 | cgroup v2, eBPF tooling |
| Ports & Connectivity | 3 | multi-namespace tcpdump, conntrack |
| HTTP Basics | 4 | HTTP/3, gRPC framing |
| DNS Clarity | 2 | CoreDNS internals, ndots, split-horizon |
| TLS / HTTPS Clarity | 2 | handshake tracing, mTLS, SNI + Ingress |
| Docker Basics | 3 | seccomp, buildkit, networking modes |
| K8s Pod & Deployment | 3 | scheduler internals, PDB, initContainers |
| K8s Service | 3 | iptables chain tracing, externalTrafficPolicy |
| K8s Ingress | 2 | path precedence, nginx config generation |
| K8s Probes | 2 | startup vs delay tuning, readiness gate |
| Troubleshooting Confidence | 3 | intermittent failures, time-pressure discipline |
| Ability to Explain Clearly | 3 | depth calibration, conciseness under stress |

**Average:** 2.8 / 5

**Priority focus areas (scored 2):** DNS, TLS, Ingress, Probes

---

## Open Doubts (Unresolved)

1. Why does a pod pass liveness but fail readiness? (probe mechanics, timing, what "not ready" blocks)
2. How does kube-proxy choose between endpoints? (iptables probability math, IPVS mode differences)
3. When does DNS TTL cause stale routing inside a cluster? (CoreDNS TTL, JVM caching footgun)
4. Precise difference between 502 and 504 from nginx Ingress perspective (log line distinction)
5. How does the startup probe interact with liveness and readiness? (gating mechanics, pod state during startup)
6. What happens to nginx config when a second Ingress resource is added? (merge vs conflict, location precedence)

---

## Key Conventions

- **Troubleshooting model:** Always narrow layer-by-layer, never guess. Symptom → evidence → hypothesis → eliminate.
- **Daily notes format:** 5 mandated questions per session (see `daily-notes/day1-class1.md` for template)
- **Doubts format:** Each doubt must be precise enough for a concrete answer, include "what I think I know" and "the specific gap"
- **Assessment cadence:** Re-score at 2-week mark and end of month
- **Git branch:** local `master` pushes to remote `main`

---

## Pending / Next Steps

- [x] Day 2 class notes and doubts *(completed 2026-03-30)*
- [x] Create `k8s/` manifests for the sample app (Deployment, Service, Ingress) *(completed 2026-03-30)*
- [x] Deep-dive into DNS (CoreDNS Corefile, ndots, search domains) *(completed in Day 2 notes)*
- [ ] **NEXT:** Hands-on exercise: deploy FastAPI app to local minikube cluster (follow `k8s/README.md`)
- [ ] Day 3 class notes — Deep-dive into Probes (startup probe gating, readiness gate vs readiness probe)
- [ ] Deep-dive into TLS (handshake tracing, mTLS, SNI + Ingress) — scored 2/5, priority gap
- [ ] 2-week self-assessment re-score (target date: ~2026-04-08)

---

## Environment Notes

- **OS:** Windows 10
- **Shell:** PowerShell (use PowerShell syntax, not bash `&&`/`||`)
- **Git:** v2.52.0
- **GitHub CLI:** v2.89.0 (installed at `C:\Program Files\GitHub CLI\gh.exe`)
- **Python:** FastAPI used for sample app
- **Credential helper:** `manager` (Windows Credential Manager) + `gh auth setup-git`

---

*Last updated: 2026-03-30 (Day 2 session)*
