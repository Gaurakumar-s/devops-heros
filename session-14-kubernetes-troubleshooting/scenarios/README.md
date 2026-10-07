# Triage Gauntlet – five broken Pods, five fixes

`bash triage_all.sh` deploys all five `broken.yaml` files with the label `tier=triage-gauntlet`. Each folder also has a `fixed.yaml` that I wrote after finding the root cause. Screenshots and the write-up are in `../Submission.md`.

```bash
bash triage_all.sh
kubectl get pods -l tier=triage-gauntlet
# ... investigate ...
kubectl delete pods -l tier=triage-gauntlet
kubectl create namespace production          # needed by scenario 4's fix
kubectl apply -f scenario-1-crashloop/fixed.yaml -f scenario-2-imagepull/fixed.yaml \
              -f scenario-3-pending/fixed.yaml -f scenario-4-dns-failure/fixed.yaml \
              -f scenario-5-oomkilled/fixed.yaml
```

| # | Pod | Status seen | Command that found it | Root cause | Fix |
|---|---|---|---|---|---|
| 1 | `fail-1-crashloop-pod` | `Error` → `CrashLoopBackOff`, RESTARTS 3 | `kubectl logs --previous` | app exits 1 because `DATABASE_URL` is unset | set the env var; keep the process running |
| 2 | `fail-2-imagepull-pod` | `ErrImagePull` → `ImagePullBackOff` | `kubectl describe pod` (Events) | image `yatri-api-service:v999-invalid-tag-does-not-exist` does not exist | use `nginx:1.27-alpine` |
| 3 | `fail-3-pending-pod` | `Pending` | `kubectl describe pod` → `FailedScheduling` | requests `cpu: 500`, `memory: 1000Gi`; node has 8 CPU / ~7.7Gi | request 100m / 64Mi |
| 4 | `fail-4-dns-failure-pod` | `Running` (but useless) | `kubectl logs`, `nslookup` of the hostname | `postgres-db-wrong-name.production.svc.cluster.local` has no Service behind it | correct hostname + create the `postgres-db` Service/Pod in `production` |
| 5 | `fail-5-oomkilled-pod` | `OOMKilled`, RESTARTS climbing | `kubectl get pod -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'` | allocates ~200 MiB with a `20Mi` limit | allocate less and set a realistic limit (256Mi) |

Scenario 4 is the sneaky one: Kubernetes thinks the Pod is perfectly healthy. Only the application log (or a readiness probe that checks the DB) reveals the problem.

Image note: the original files used `python:3.11-alpine`; Docker Hub answered `429 Too Many Requests` on my machine, so both scenario 1 and 5 now use the locally cached `python:3.12-alpine`.
