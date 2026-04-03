# Day 3 — Morning Planning Sheet

**Date:** _(fill in when you sit down)_  
**30-Day Plan Topic:** Files, environment variables, config, and runtime context  
**Time budget:** 45 min concept + 60 min hands-on + 20 min notes + 15 min explain out loud

---

## Today's topic
How running processes receive their configuration — through environment variables, mounted config files, and the Linux `/proc` filesystem — and how Kubernetes formalizes this through ConfigMaps and Secrets.

## Why it exists (first-principles reason)
A process needs more than just its binary to run. It needs to know: which database to connect to, which port to listen on, which environment (prod vs qa) it is running in. Hardcoding this is fatal for ops — you would need a different binary per environment. Instead, processes read config from their **runtime context**: environment variables, config files, and command-line flags. Every platform layer — Docker, Kubernetes, systemd — is really just a mechanism for injecting this runtime context into a process. Understanding this is the foundation for debugging "the app has the wrong config," "the secret isn't there," and "why did changing the ConfigMap do nothing?"

## Where I see this in my organization today

Look for one or two of these at work today and note what you observe:

- [ ] A Spring Boot service — find one `application.properties` or `application.yml` value that comes from an env var (look for `${ENV_VAR_NAME}` syntax)
- [ ] A Kubernetes ConfigMap in the `c-qa4` namespace — `kubectl get configmap -n c-qa4` — and note whether it is mounted as a volume or injected as env vars
- [ ] A Secret used by a pod — `kubectl describe pod <name> -n c-qa4` and look at the `Env:` and `Mounts:` sections
- [ ] Any pod that crashed because of a missing env var or missing secret — the error is usually visible in `kubectl logs` at startup

Write one real example from today's work context in the class notes.

## One real example I already know
The `configserver` runs with Spring Boot, which reads from `application.yml` + env var overrides. When it runs in Kubernetes, the cluster namespace (`c-qa4`) is passed as an env var so the app knows which config to serve. This is a direct example of runtime context changing application behavior without touching the binary.

## What I will build/test in my lab today
1. Run the FastAPI app and inspect its environment with `printenv` and `/proc/<PID>/environ`
2. Pass env vars explicitly (`APP_ENV=staging uvicorn main:app`) and have the app read them via `os.environ`
3. Write a config file (`config.json`) and have the app read it; swap the file out and observe behavior
4. Apply a Kubernetes ConfigMap and mount it both ways: as env vars and as a volume-mounted file
5. Update the ConfigMap and observe what happens to each mounting strategy
6. Use `kubectl exec -- env` to see the full runtime environment of a running pod

## How I will validate it
- I can explain why updating a ConfigMap does not immediately affect a pod that mounts it as env vars
- I can show the env of any running process using `/proc` without restarting it
- I can write a K8s manifest that reads DB credentials from a Secret (not hardcoded)
- I can explain the config precedence chain: binary default → file → env var → runtime flag

## End-of-day explanation target (say this out loud)

> "Every process starts with an inherited set of environment variables from its parent. In Kubernetes, the parent is the container runtime, and Kubernetes pre-loads that environment with values from ConfigMaps and Secrets before your app's first line of code runs. If the app reads `os.environ['DB_HOST']` and that env var is missing, the app crashes — not because of a K8s bug, but because the runtime context was not configured. This is the config layer: it fails silently if a key is missing and the app doesn't have a safe default, or loudly if the app validates at startup. On the platform side, my job is to ensure the right values are injected, that Secrets are not exposed in logs, and that I know how to verify what a running process actually sees."

---

## Today's doubts to track
Write any confusing thing in `doubts/day3-doubts.md` using the standard format.

## Tomorrow's topic
Day 4 — HTTP from first principles

---

*Fill in "What confused me" and "My final explanation" at end of day.*

**What confused me today:**  
_(fill in)_

**My final explanation in 3–5 lines:**  
_(fill in)_
