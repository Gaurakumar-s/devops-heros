# Final troubleshooting challenge

Five issues were introduced on purpose into the running TaskBoard deployment (namespace `taskboard` on minikube). For each one: identify → investigate (logs/resources) → root cause → fix → verify → document. The healthy manifests in `../kubernetes/` are the "fix" in every case; the broken versions are the files in this folder.

![issues 1 and 2: wrong image tag, service selector typo](/assets/s21-troubleshooting-01.png)
![issues 3, 4 and 5: missing config, wrong probe paths, impossible resources](/assets/s21-troubleshooting-02.png)
![event evidence and final verification](/assets/s21-troubleshooting-03.png)

| # | File | Symptom (`kubectl get pods`) | Investigation | Root cause | Fix | Verified by |
|---|---|---|---|---|---|---|
| 1 | `01-wrong-image-tag.yaml` | both new Pods `ImagePullBackOff`; old Pods gone because of `Recreate` → outage | `kubectl describe pod` → `Failed to pull image "ghcr.io/gaurakumar-s/taskboard:v9.9.9-does-not-exist"` | tag was never built/pushed by the pipeline | re-apply `kubernetes/04-deployment.yaml` (`:latest`, loaded with `minikube image build`) | `rollout status` → `successfully rolled out`, 2/2 Running |
| 2 | `02-service-selector-typo.yaml` | Pods healthy but every request through the Ingress fails (503) | `kubectl get endpoints taskboard` → `<none>`; `describe svc` → `Selector: app=taskbaord`; `get pods --show-labels` → `app=taskboard` | one-letter typo in the Service selector | re-apply `kubernetes/05-service.yaml` | endpoints show the two Pod IPs; `curl /health` → `{"status":"ok"}` |
| 3 | `03-missing-config-key.yaml` | `CreateContainerConfigError` | `describe pod` → `couldn't find key ADMIN_PASSWORD in Secret taskboard/taskboard-secret`; ConfigMap data lost `DATA_DIR`/`PORT` | Deployment references a Secret key that does not exist, and the ConfigMap was edited | re-apply `01-configmap.yaml` + `04-deployment.yaml` | rollout OK, `env` inside the Pod shows all keys |
| 4 | `04-wrong-probe-path.yaml` | `Running` then `CrashLoopBackOff`, READY `0/1`, restarts climbing | `describe pod` → `Readiness probe failed: HTTP probe failed with statuscode: 404` (`/healthz`) and `Liveness probe failed … 404` (`/status`) → `Killing`; endpoints empty | probes point at paths the app does not serve (`/health`, `/ready` are the real ones); liveness `failureThreshold: 1` kills on the first miss | re-apply `04-deployment.yaml` | 2/2 Running, 0 restarts, endpoints populated |
| 5 | `05-resource-limits-too-low.yaml` | `Pending` forever | `describe pod` → `0/1 nodes are available: 1 Insufficient cpu` (request `cpu: 64`); had it scheduled, `memory: 16Mi` would have `OOMKilled` gunicorn | impossible CPU request / unrealistic memory limit | re-apply `04-deployment.yaml` (100m/64Mi requests, 500m/256Mi limits) | scheduled and Running |

## Commands that did the work
```bash
kubectl -n taskboard get pods                      # what state is it in
kubectl -n taskboard describe pod -l app=taskboard # why (Events at the bottom)
kubectl -n taskboard logs deploy/taskboard         # what the app said
kubectl -n taskboard get endpoints taskboard       # does the Service see any Pods
kubectl -n taskboard describe svc taskboard        # selector vs labels
kubectl -n taskboard get pods --show-labels
kubectl -n taskboard get configmap taskboard-config -o jsonpath='{.data}'
kubectl -n taskboard get events --sort-by=.lastTimestamp
kubectl apply -f kubernetes/ && kubectl -n taskboard rollout status deploy/taskboard
```

## Lessons
- `Recreate` strategy + a bad image = immediate outage; `RollingUpdate` with `maxUnavailable: 0` would have kept the old Pods serving. The trade-off here is the `ReadWriteOnce` PVC.
- Most "the app is down" tickets were not the app: 1 was the registry, 2 the Service, 3 the config, 5 the scheduler. Only 4 was about the app's HTTP behaviour, and even then the app was fine, the probe was wrong.
- `kubectl get endpoints` is the fastest single check for "Pods are Running but nothing answers".
- Argo CD with `selfHeal` would have reverted issues 2–5 automatically because they are drift from Git; issue 1 would surface as a Degraded Application instead.
