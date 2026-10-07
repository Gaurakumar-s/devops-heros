# Session 15 – Helm (run on minikube)

Helm v3 on my local minikube cluster. Screenshots are my own terminal output. Image tags are pinned to ones already cached on the node (`nginx:1.24-alpine`, `1.25-alpine`, `1.27`) because Docker Hub was rate-limiting anonymous pulls from my laptop that evening.

## Task 1 – Helm commands

### create, lint, template, install, list, status
![helm create / lint / template / install / list / status](/assets/s15-commands-01.png)

| Command | What it does | What I saw |
|---|---|---|
| `helm version --short` | client version | v3.x |
| `helm create practice-chart` | scaffolds a chart: `Chart.yaml`, `values.yaml`, `templates/` (deployment, service, ingress, hpa, serviceaccount, `_helpers.tpl`, `NOTES.txt`, tests) | the whole tree in `ls -R` |
| `helm lint practice-chart` | static checks on the chart | `1 chart(s) linted, 0 chart(s) failed` |
| `helm template demo practice-chart` | renders the manifests locally without touching the cluster | the Deployment/Service YAML with my `--set image.tag=1.27` applied |
| `helm install demo practice-chart --set …` | creates release `demo`, revision 1 | `STATUS: deployed, REVISION: 1` and the `NOTES.txt` hints |
| `helm list` | releases in the namespace | `demo` plus two older releases of mine |
| `helm status demo` | current state of one release | status, revision, notes |

### get, upgrade, history, rollback, uninstall, repo, search
![helm get / upgrade / history / rollback / uninstall / repo / search](/assets/s15-commands-02.png)

| Command | What it does | What I saw |
|---|---|---|
| `helm get values demo` | the user-supplied values of the release | my `image.tag`/`pullPolicy` overrides |
| `helm get manifest demo` | the rendered YAML Helm applied | kind/replicas/image lines |
| `helm upgrade demo … --set replicaCount=3` | new revision with changed values | `REVISION: 2`, 3 Pods |
| `helm history demo` | revision table | 1 `superseded`, 2 `deployed` |
| `helm rollback demo 1` | re-applies revision 1 as a *new* revision | `Rollback was a success`; history now shows revision 3 `Rollback to 1` |
| `helm uninstall demo` | deletes every object of the release | `release "demo" uninstalled`, gone from `helm list` |
| `helm repo add bitnami …`, `helm repo list`, `helm repo update` | manage chart repositories | bitnami added and index refreshed |
| `helm search repo nginx` | search the added repos | bitnami/nginx and friends |
| `helm search hub wordpress` | search Artifact Hub | public wordpress charts |

The practice chart created by `helm create` is kept in [`practice-chart/`](practice-chart/).

## Task 2 – Rollback workflow (`07-install-upgrade/app-chart`)
Install → Upgrade → Verify → Upgrade again → Verify → Rollback → Verify

![install, upgrade, broken upgrade, rollback](/assets/s15-rollback.png)

1. `helm install rollback-demo ./app-chart --set image.tag=1.24-alpine` → revision 1, Pod running `nginx:1.24-alpine`.
2. `helm upgrade … --set image.tag=1.25-alpine` → revision 2, Pod rolled to `nginx:1.25-alpine`; `helm history` shows 1 superseded / 2 deployed.
3. `helm upgrade … --set image.tag=doesnotexist` → revision 3 is marked **deployed** even though the new Pod is `ImagePullBackOff`. Helm records "I applied it", not "it is healthy" (unless you use `--wait`/`--atomic`). The old 1.25 Pod keeps serving because the Deployment's rolling update never got a healthy replacement.
4. `helm rollback rollback-demo 2` → `Rollback was a success`; the broken ReplicaSet is scaled down, the Pod is back on `nginx:1.25-alpine`, and history gains revision 4 `Rollback to 2`. Rollback never rewrites history; it always adds a revision.
5. `helm get values` confirms the active values, `helm uninstall` cleans up.

## Task 3 – Mini project (`mini-project/notes-chart`)
Chart with `Chart.yaml`, `values.yaml`, `values-prod.yaml`, and templates for a ConfigMap, Deployment (envFrom the ConfigMap) and NodePort Service.

![notes chart: install dev, verify, upgrade with values-prod, rollback](/assets/s15-miniproject.png)

- `helm lint` clean; `helm install notes notes-chart` → `notes-config`, `notes-deploy`, `notes-svc` created; inside the Pod `APP_NAME=notes-app`, `ENVIRONMENT=development`; `wget http://notes-svc` from a busybox Pod returns the nginx page.
- `helm upgrade notes notes-chart -f notes-chart/values-prod.yaml` → 3 replicas on `nginx:1.25-alpine` and `ENVIRONMENT=production`. One `values-prod.yaml` switched replicas, image tag and config in a single command.
- `helm rollback notes 1` → back to 1 replica / `development`; history: 1 superseded, 2 superseded, 3 `Rollback to 1`.
- `helm uninstall notes` removes all three objects.

Things I learned the hard way: `minikube service <svc> --url` on macOS keeps a tunnel process open and blocks the terminal, so for scripted checks I curl from a Pod inside the cluster instead; and a release can be `deployed` in Helm while its Pods are broken, which is why `helm history` + `kubectl get pods` belong together.
