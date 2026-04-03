# Day 2 — Morning Planning Sheet

**Date:** _(fill in when you sit down)_  
**30-Day Plan Topic:** Linux process model — Process, PID, ports, logs  
**Time budget:** 45 min concept + 60 min hands-on + 20 min notes + 15 min explain out loud

---

## Today's topic
Linux process model — how an application exists on a Linux system before containers or Kubernetes are involved.

## Why it exists (first-principles reason)
Every application — whether it runs on bare metal, in a VM, in a Docker container, or in a Kubernetes pod — is **a process on Linux**. Understanding how processes start, bind to ports, produce logs, and consume memory/CPU is the foundation that makes all container and Kubernetes debugging make sense.

When something is "down," the question is always: is there a running process? Is it on the right port? Is it outputting errors? Kubernetes layers on top of these answers, but it cannot answer them for you.

## Where I see this in my organization today

Look for one or two of these at work today and note what you observe:

- [ ] A Spring Boot service (e.g., `configserver`, `auth-service`) — what port does it bind to? Is it `0.0.0.0` or `127.0.0.1`?
- [ ] A pod in `kubectl describe pod` — look at the container's stdout logs and see how they surface in `kubectl logs`
- [ ] A pod that is `CrashLoopBackOff` or recently restarted — what process exited? What was the exit code?
- [ ] A memory-related OOMKilled event in your cluster — that starts at the Linux memory limit on the container process
- [ ] Any startup log that says `Started X on port YYYY` — that is the process binding the port

Write one real example from today's work context in the class notes.

## One real example I already know
The `configserver` incident (2026-03-27):  
- Direct IP `curl http://10.148.14.190:8080` → 401 → the **process** was alive, bound to port 8080, handling requests  
- The failure was not at the process layer — it was at the nginx routing layer (Layer 4)  
- Key signal: `curl` with IP+port succeeded → process layer was healthy. This is exactly how you use process-layer knowledge to eliminate a layer in troubleshooting.

## What I will build/test in my lab today
1. Run the FastAPI app **locally without Docker** and inspect it as a Linux process
2. Practice the 6 core commands: `ps`, `ss -tlnp`, `lsof -i`, `pgrep`, `top`, `kill -0`
3. Observe what happens when the app binds to `127.0.0.1` vs `0.0.0.0`
4. Check process logs via stdout vs via a file
5. Intentionally kill the process and observe what "the app is down" looks like from the process level

## How I will validate it
- I can answer: "is this app running?" using only process-level commands
- I can find which port a process is using without looking at the source code
- I can explain why `curl localhost:8000` works but `curl <machine-ip>:8000` fails when the app binds to `127.0.0.1`

## End-of-day explanation target (say this out loud)

> "An application on Linux is a process with a PID. It binds to a port on a specific interface — either all interfaces (0.0.0.0) or loopback only (127.0.0.1). Its output goes to stdout/stderr. When a container runs, it is still just a Linux process with namespace isolation applied. When Kubernetes runs a container, it is still just that process — but now kubelet, cgroups, and the container runtime are managing its lifecycle. Before I look at Kubernetes events or service endpoints, the first question is always: is the process running, on the right port, producing healthy output?"

---

## Today's doubts to track
Write any confusing thing in `doubts/day2-doubts.md` using the standard format.

## Tomorrow's topic
Day 3 — Files, environment variables, config, and runtime context

---

*Fill in "What confused me" and "My final explanation" at end of day.*

**What confused me today:**  
_(fill in)_

**My final explanation in 3–5 lines:**  
_(fill in)_
