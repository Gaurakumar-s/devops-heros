# GitOps for the final project

`argocd-application.yaml` tells Argo CD to keep the `taskboard` namespace equal to `final-devops-project/kubernetes/` on `main` of this repository, with automated sync, pruning and self-heal.

Flow: CI pushes `ghcr.io/gaurakumar-s/taskboard:<sha>` → a commit updates the image tag in `kubernetes/04-deployment.yaml` → Argo CD notices the new commit, shows OutOfSync, syncs, and reports Healthy once the rollout finishes. Manual `kubectl` changes are reverted (self-heal); resources deleted from Git are deleted from the cluster (prune).

```bash
kubectl apply -f gitops/argocd-application.yaml
kubectl -n argocd get applications
```
