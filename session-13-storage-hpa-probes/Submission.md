# Session 13 – Storage, HPA and Probes (run on minikube)

All exercises were run on my local minikube cluster (`metrics-server` and `default-storageclass` addons enabled). Screenshots are my own terminal output.

## Task 1 – Kubernetes Volumes
The write-up is in [`01-kubernetes-volumes/README.md`](01-kubernetes-volumes/README.md) (emptyDir, hostPath, PV, PVC, StorageClass, dynamic provisioning). The hands-on that the notes are based on:

### emptyDir and hostPath (`01-volumes/`)
![emptyDir survives a container restart but not Pod deletion; hostPath survives Pod deletion](/assets/s13-volumes.png)

- `emptyDir`: wrote `/data/note.txt`, killed PID 1 → container restarted (RESTARTS 1) and the file was still there. Deleted and re-created the Pod → `/data` empty.
- `hostPath`: the file written by the first Pod was read by the second Pod and is visible on the node with `minikube ssh`.

### PersistentVolume / PersistentVolumeClaim and StorageClass (`02-persistent-storage/`, `03-storageclass/`)
![pv, pvc, pod with claim, storageclass, dynamic pv](/assets/s13-pv-pvc.png)

- `student-pv` (1Gi, Retain) created → `Available`. `student-pvc` (500Mi) created → `Bound`.
- Wrote `Student: Gaurav Kumar` to `/data/student-data.txt`, deleted the Pod, re-created it → the file is still there.
- Surprise: the PVC bound to a *dynamically provisioned* `pvc-…` volume of StorageClass `standard`, not to my hand-made `student-pv` (which stayed `Available`). Because minikube has a default StorageClass, a PVC without `storageClassName` goes to the provisioner. To use the manual PV I would set `storageClassName: ""` (or a matching custom class) on both.
- `kubectl get storageclass` → `standard (default)`, provisioner `k8s.io/minikube-hostpath`, reclaim `Delete`. Applying `dynamic-pvc` created a PV automatically within 5 s with hostPath `/tmp/hostpath-provisioner/default/dynamic-pvc`; deleting the PVC deleted the PV too (`Delete` policy).

## Task 2 – HPA hands-on

### `04-hpa/` – the session's `hpa.yaml` on the nginx Deployment
![hpa demo: unknown -> 118% -> 3 replicas -> load removed](/assets/s13-hpa-demo.png)

1. Deployed `hpa-demo` (1 replica, `requests.cpu: 100m`) + Service, applied `hpa.yaml` (min 1 / max 5 / 50 % CPU).
2. `TARGETS` is `<unknown>/50%` for the first ~1–2 minutes while metrics-server collects its first samples (`FailedGetResourceMetric` events are normal here).
3. Two busybox load generators running `wget` in a loop pushed CPU to **118 %** (`kubectl top pods` → 118m of a 100m request). HPA event: `New size: 3; reason: cpu resource utilization above target`. Replicas: 1 → 3 and the average dropped to 41 %.
4. After deleting the load generators CPU fell to 0 % but replicas stayed at 3: the downscale stabilisation window is 5 minutes by default, so scaling down is deliberately slow.

### `hpa/` – `yatri-backend` load test (PDF steps 1–9)
![hpa load test: 2 -> 4 -> 8 -> 10 replicas](/assets/s13-hpa-loadtest.png)

- `backend-deployment.yaml` is a tiny Python HTTP server; every request to `/healthz` does 12,000 SHA-256 rounds so each hit costs real CPU (nginx alone barely moves the needle).
- `hpa-backend.yaml`: min 2 / max 10 / 50 % CPU. Load: `load-generator.yaml` (6 busybox Pods hammering the Service from inside the cluster). I also tried the provided `load_generator.sh`, which goes through `kubectl port-forward`; on macOS that only reached ~15 % because the port-forward itself is the bottleneck, so the in-cluster generator is what the screenshot uses.
- Observed: `<unknown>` → **269 %/50 %** with 4 replicas → **292 %** with 10 replicas (events `New size: 4`, `New size: 8`, then max 10) → load removed, CPU falls, replicas stay at 10 until the stabilisation window passes.
- Useful commands used throughout: `kubectl get hpa`, `kubectl get pods -l app=…`, `kubectl top pods`, `kubectl describe hpa`.

Formula check: 2 replicas at ~269 % against a 50 % target → `ceil(2 × 269/50) = 11`, capped by `maxReplicas: 10`; the controller gets there in steps (4 → 8 → 10) because it limits how much it scales per period.

## Probes (`05-probes/`)
![liveness restart, readiness removes the pod from endpoints, startup probe](/assets/s13-probes.png)

- `liveness-demo`: deleting `index.html` makes `GET /` return 403 → after 3 failures the kubelet restarted the container (RESTARTS 1).
- `readiness-demo`: same trick → the Pod stays `Running` but goes `0/1`, `Ready=False`, event `Readiness probe failed: HTTP probe failed with statuscode: 403`. No restart; it is just taken out of the Service endpoints.
- `startup-demo`: `failureThreshold: 30 × periodSeconds: 2` gives a slow app 60 s to come up before liveness/readiness even start.

## Task 3 – Mini project (`mini-project/`)
Namespace `production-webapp`, PVC `web-data` (500Mi), Deployment `web-app` (2 replicas, all three probes, CPU/memory requests, `/data` on the PVC), ClusterIP Service `web-service`, HPA `web-app-hpa` (2–5, 50 % CPU).

![mini project: deploy, pvc bound, persistence across pod deletion, probes, service](/assets/s13-miniproject-01.png)

- PVC `Bound` immediately (dynamic provisioning), both Pods `Running`.
- Persistence test: wrote `Student: Gaurav Kumar` to `/data/student.txt`, deleted that Pod, read the file from the replacement Pod → identical. (The Deployment uses `strategy: Recreate` because the PVC is `ReadWriteOnce`.)
- Service check: `web-service` endpoints list the two Pod IPs; `wget http://web-service` from a busybox Pod returns the nginx page.

![mini project: HPA scales 2 -> 3 under load](/assets/s13-miniproject-02.png)

- Three busybox load generators → CPU 64 % → HPA scaled 2 → 3 replicas (`SuccessfulRescale`), then settled at 44 % → 36 % as the extra Pod absorbed traffic. Removed the load, cleaned up with `kubectl delete namespace production-webapp`.

Probe cheat-sheet I keep from this session: **startup** = "has it finished booting?", **readiness** = "can it take traffic right now?" (fail → out of endpoints), **liveness** = "is it stuck?" (fail → restart).
