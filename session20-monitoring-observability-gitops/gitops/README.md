# GitOps with Argo CD

## What is GitOps?
GitOps is a way of operating infrastructure and applications where **a Git repository is the single source of truth for the desired state**, and an automated agent continuously makes the live system match it. You do not run `kubectl apply` by hand or from a CI job with cluster credentials; you merge a commit, and the agent inside the cluster pulls the change.

Four principles (OpenGitOps):
1. **Declarative** – the desired state is described (YAML/Helm/Kustomize), not scripted.
2. **Versioned and immutable** – it lives in Git: history, review, rollback = `git revert`.
3. **Pulled automatically** – an agent in the cluster fetches the state; the cluster does not receive pushes.
4. **Continuously reconciled** – the agent keeps comparing live vs desired and fixes drift.

## Git as the source of truth
```text
developer ──PR──▶ Git repo (manifests)  ◀──polls/webhook── Argo CD (in cluster)
                                                                │ diff live vs Git
                                                                ▼
                                                           kubectl apply (by the agent)
                                                                │
                                                                ▼
                                                           Kubernetes objects
```
- Who changed what, when and why is the Git log. Access to the cluster is reduced to the agent.
- Environments are branches/folders/overlays (`envs/dev`, `envs/prod`), promotion is a merge.
- Secrets still must not be committed in plain text (Session 12): use Sealed Secrets, SOPS or External Secrets, which are themselves declared in Git.

## Declarative configuration
Imperative: "run these commands in this order". Declarative: "this is what should exist". Kubernetes is already declarative (`kubectl apply -f`), GitOps simply moves the `apply` to an agent and the files to Git. The repo for this demo holds exactly:

```text
08-mini-project/app/
├── namespace.yaml      Namespace session20
├── deployment.yaml     Deployment, replicas: 2
├── service.yaml        Service
└── argocd-application.yaml   the Argo CD Application that points at this folder
```

## Continuous reconciliation
Argo CD's application controller runs a loop: fetch Git → render manifests → compare with the cluster → report **Synced/OutOfSync** and **Healthy/Degraded** → if `automated` sync is on, apply the diff. With `selfHeal: true` a manual change in the cluster (someone scales the Deployment to 5 with `kubectl`) is reverted within minutes; with `prune: true` a resource deleted from Git is deleted from the cluster. This is what makes drift impossible to keep.

## GitOps workflow
```text
1. git clone  →  edit deployment.yaml (image tag, replicas, config)
2. git commit / push / PR review / merge to main
3. Argo CD detects the new commit (poll every 3 min, or a GitHub webhook for instant)
4. Argo CD shows OutOfSync → auto-sync applies it → Healthy
5. Rollback = git revert <commit> → Argo CD syncs the previous state
```
CI (Session 16/17) still builds, tests, scans and pushes the image; its last step becomes "commit the new image tag to the GitOps repo" instead of "kubectl apply to prod". That separates *build* credentials from *deploy* credentials.

## Kubernetes + GitOps
- **Argo CD** (used here) and **Flux** are the two CNCF-graduated agents. Both support plain YAML, Helm charts and Kustomize, multiple clusters, and RBAC/SSO.
- Argo CD objects: `Application` (one app = one repo path → one destination namespace), `AppProject` (grouping/permissions), `ApplicationSet` (generate many Applications from a template).
- Health is evaluated per Kubernetes kind (Deployment: all replicas available; Service: exists; Ingress: has an address), so the UI tells you whether the *rollout* worked, not just whether `apply` succeeded.
- Works together with everything from earlier sessions: Helm charts (15) are an Argo CD source type, HPA/probes (13) make the health checks meaningful, Ingress (12) is just another manifest in the repo.

## The demo (see `../Submission.md` for screenshots)
1. Install Argo CD on minikube: `kubectl create ns argocd && kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml`.
2. Get the initial admin password: `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d`.
3. Apply `08-mini-project/app/argocd-application.yaml` pointing at **this GitHub repository**, path `session20-monitoring-observability-gitops/08-mini-project/app`, with automated sync + prune + selfHeal.
4. Argo CD creates the namespace, Deployment (2 replicas) and Service from Git.
5. Change `replicas: 2 → 3` in Git, push, watch Argo CD go OutOfSync → Synced with 3 Pods.
6. Drift test: `kubectl scale deploy … --replicas=1` by hand; selfHeal puts it back to what Git says.
