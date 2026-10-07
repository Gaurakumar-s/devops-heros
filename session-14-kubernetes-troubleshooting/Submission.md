# Session 14 – Kubernetes Troubleshooting (run on minikube)

Everything below was run on my local minikube cluster; the screenshots are my own terminal output.

## Task 1 – Troubleshooting commands

`kubectl get` (pods, `-o wide`, `-o yaml`, nodes), `kubectl explain` for a field I was unsure about (`livenessProbe`, `restartPolicy`).

![kubectl get, get -o wide, explain](/assets/s14-commands-01.png)

`kubectl describe` (events at the bottom are the useful part), `kubectl logs` (`--tail`, `--timestamps`), `kubectl exec` (listing nginx files, curl from inside the container, `nginx -v`), `kubectl events --for pod/…`, `kubectl get events --sort-by=.lastTimestamp`, `kubectl top nodes/pods` (needs metrics-server).

![describe, logs, exec, events, top](/assets/s14-commands-02.png)

How I think about them now:

| Command | Question it answers |
|---|---|
| `kubectl get` | What exists and what state is it in? |
| `kubectl describe` | Why is it in that state? (conditions + events) |
| `kubectl logs` | What did my application say? |
| `kubectl events` | What did Kubernetes do to my resource? |
| `kubectl exec` | What does the world look like from inside the container? |
| `kubectl explain` | What does this field mean and what values does it take? |
| `kubectl top` | Is it CPU/memory bound right now? |
| `kubectl get -o wide` | Which node/IP, and is the Pod ready? |

## Task 2 – Common issues

### CrashLoopBackOff, ImagePullBackOff, Pending (`06-`, `07-`, `08-`)
![crashloop, imagepull, pending – broken then fixed](/assets/s14-issues-01.png)

| Issue | Identify | Investigate | Root cause | Fix | Verify |
|---|---|---|---|---|---|
| CrashLoopBackOff | `crash-demo` shows `Error` / `CrashLoopBackOff`, RESTARTS climbing | `describe` → `Back-off restarting failed container`; `logs --previous` | the script runs `exit 1` | `fixed-pod.yaml` keeps the process alive | `1/1 Running`, RESTARTS 0 |
| ImagePullBackOff | `image-demo` stuck `ErrImagePull` → `ImagePullBackOff` | `describe` → `Failed to pull image "nginx:this-image-does-not-exist"` | tag does not exist | use `nginx:1.27` | `1/1 Running` |
| Pending | `pending-demo` never leaves `Pending` | `describe` → `FailedScheduling … didn't match Pod's node affinity/selector`; `describe node` for allocatable | `nodeSelector: kubernetes.io/hostname: node-that-does-not-exist` | remove the selector | scheduled and `Running` |

`ContainerCreating` showed up for a few seconds on every Pod whose image was not cached yet; it only becomes a problem when it lasts (volume mount failure, CNI, or a slow pull, all visible in `describe`).

### Service connectivity, DNS and Pod networking (`09-service-dns-troubleshooting/`)
![service with wrong selector, DNS checks](/assets/s14-service-dns.png)

- First surprise: the provided `dns-test-pod.yaml` itself went `ImagePullBackOff` because `registry.k8s.io/e2e-test-images/dnsutils:1.3` no longer exists (`describe` → `NotFound`). I replaced it with `dns-test-pod-fixed.yaml` (busybox, which has `nslookup` and `wget`).
- **Service connectivity:** `web-service` resolved fine (`nslookup` → `10.109.79.120`) but `wget` failed. `kubectl get endpoints web-service` → `<none>`. `describe svc` showed `Selector: app=web-ahsgdf` while the Pods carry `app=web`. Patched the selector, endpoints filled with the two Pod IPs, request returned the nginx page.
- **DNS issue:** `nslookup web-service-typo` → `NXDOMAIN`. DNS is healthy (CoreDNS answered from `10.96.0.10`); the name is simply wrong. Rule: NXDOMAIN = name problem, timeout = CoreDNS/network problem, resolves-but-hangs = endpoints/selector/readiness problem.
- **Pod networking:** `get pods -o wide` gave the Pod IPs (`10.244.0.x`), and the fixed endpoints list matched them exactly; `wget` by Service name from another Pod proves Pod-to-Pod traffic through kube-proxy works.

### Triage gauntlet (`scenarios/`)
Five intentionally broken workloads deployed with `triage_all.sh`:

![five broken pods – investigation](/assets/s14-scenarios-01.png)

| Scenario | Symptom | Root cause (from describe/logs) | Fix (`fixed.yaml`) |
|---|---|---|---|
| 1 crashloop | `Error` / `CrashLoopBackOff`, restarts | `logs --previous` → `[FATAL ERROR]: DATABASE_URL environment variable is MISSING!` | add the `DATABASE_URL` env var (configuration issue) |
| 2 imagepull | `ErrImagePull` → `ImagePullBackOff` | `Failed to pull image "yatri-api-service:v999-invalid-tag-does-not-exist"` | a real image/tag |
| 3 pending | `Pending` forever | `0/1 nodes are available: 1 Insufficient cpu, 1 Insufficient memory` (asked for 500 CPU / 1000Gi) | realistic requests (100m / 64Mi) |
| 4 dns-failure | `Running` but the app never reaches its DB | curl to `postgres-db-wrong-name.production.svc.cluster.local` fails, no such Service | correct hostname + the `postgres-db` Service it should point at |
| 5 oomkilled | `OOMKilled`, restarts | `lastState.terminated.reason: OOMKilled`, limit `20Mi` vs ~200 MiB allocated | fix the allocation and give a sane limit (256Mi) |

All five after applying the fixes:

![five pods fixed](/assets/s14-scenarios-02.png)

Note: `python:3.11-alpine` from the original scenario files could not be pulled on my laptop (`429 Too Many Requests` from Docker Hub, a rate-limit on anonymous pulls) so I switched scenarios 1 and 5 to the already-cached `python:3.12-alpine`. That was its own small troubleshooting exercise: the Pod showed `ErrImagePull`, `describe` showed the 429, and `minikube image ls` showed which tags were available locally.

## Task 3 – Mini project (`mini-project/`)
![mini project – deploy, inspect service, break, fix](/assets/s14-miniproject.png)

- Deployed `troubleshooting-app` (2 nginx Pods) and `troubleshooting-service`; `describe service` showed the selector `app=troubleshooting-app`, TargetPort 80 and two endpoints; `curl localhost` from inside a Pod returned the nginx page.
- Applied `broken-pod.yaml`.

**Question 1 – What is the Pod status?** `ImagePullBackOff` (after a first `ErrImagePull`).

**Question 2 – What is the actual error?** `Failed to pull image "nginx:this-tag-does-not-exist": … not found` – the tag does not exist in the registry.

**Question 3 – Which command helped you find the reason?** `kubectl describe pod project-broken-pod` – the Events section at the bottom. `kubectl get pod` only says *that* it is failing; `describe` says *why*.

- Fix: `fixed-pod.yaml` with `nginx:1.27` → Pod `1/1 Running` in a few seconds. Cleanup with `kubectl delete`.

## Logs vs events, in one line
Logs = what my application said. Events = what Kubernetes did to my resource. When a Pod never starts, logs are empty and events have the answer; when a Pod starts and misbehaves, events are quiet and logs have the answer.
