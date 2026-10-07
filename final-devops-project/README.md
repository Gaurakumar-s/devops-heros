# Final DevOps Project – TaskBoard

**Student:** Gaurav Kumar · Session 21 capstone for the DevOps course.

## 1. Project overview
TaskBoard is a small Flask REST API (create / list / update / delete tasks, SQLite on a persistent volume) that I took through the complete DevOps lifecycle learned in the course:

```text
Application ──▶ Git ──▶ GitHub ──▶ CI pipeline (build + unit test)
   ──▶ security scanning (SAST, SCA, secrets, image) ──▶ Docker image ──▶ GHCR
   ──▶ Kubernetes (Deployment, Service, ConfigMap, Secret, Ingress, HPA, probes, PVC)
   ──▶ Helm chart ──▶ Terraform infrastructure ──▶ Monitoring (Prometheus) ──▶ GitOps (Argo CD)
   ──▶ troubleshooting challenge
```

Everything in this folder was run for real: the pipeline on GitHub Actions, the cluster work on my local minikube, Terraform against a local AWS mock. Every screenshot is my own terminal output.

## 2. Architecture diagram

```text
                 developer git push
                        │
                        ▼
         ┌──────────────────────────────────────────────────────────────┐
         │ GitHub Actions – .github/workflows/final-project.yml         │
         │ build → unit-test → SAST → SCA → secret-scan → docker-build  │
         │ → image-scan → security-gate → push (GHCR) → helm deploy     │
         └──────────────┬───────────────────────────────┬───────────────┘
                        │ ghcr.io/gaurakumar-s/taskboard:<sha>          │ kind (in the runner)
                        ▼                                               ▼
          ┌──────────────────────────────────────────┐           smoke test
          │ Kubernetes namespace: taskboard          │
          │                                          │     ┌──────────────┐
  curl ──▶│ Ingress taskboard.local ─▶ Service :80   │◀────│ Argo CD      │ watches
          │        ─▶ Deployment taskboard (2 pods)  │     │ Application  │ final-devops-project/kubernetes
          │           ├─ ConfigMap  (APP_NAME, ENV…) │     └──────────────┘
          │           ├─ Secret     (ADMIN_TOKEN)    │
          │           ├─ probes: startup/ready/live  │     ┌──────────────┐
          │           ├─ PVC /data (SQLite)          │◀────│ Prometheus   │ scrapes /metrics,
          │           └─ HPA 2–5 on 60 % CPU         │     │ (in-cluster) │ alert rules
          └──────────────────────────────────────────┘     └──────────────┘

          Terraform (terraform/): VPC → subnet → IGW/route → security group → EC2 → S3
```

## 3. Technologies used
Python 3.12 / Flask / gunicorn / SQLite · pytest · Docker (multi-stage, non-root) · GitHub Actions · Bandit, Semgrep, pip-audit, Gitleaks, Trivy · GHCR · Kubernetes (minikube, kind) · Helm 3 · Terraform 1.16 + AWS provider 6 · Prometheus · Argo CD · Git/GitHub CLI.

## 4. Application setup (`application/`)
```bash
cd application
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q --cov=app            # 5 tests, 97 % coverage
ADMIN_TOKEN=dev python app/main.py   # http://127.0.0.1:8080
```
Endpoints: `/` (info), `/health` (liveness), `/ready` (readiness, checks the DB), `/metrics` (Prometheus), `/api/tasks` (GET/POST), `/api/tasks/<id>` (PUT, DELETE with `X-Admin-Token`). Configuration comes only from environment variables (`APP_NAME`, `ENVIRONMENT`, `DATA_DIR`, `PORT`, `ADMIN_TOKEN`), so the same image runs everywhere.

## 5. Docker setup (`docker/`)
Multi-stage `Dockerfile` (dependencies built in a builder stage, runtime copied into a clean `python:3.12-alpine`), non-root user, `HEALTHCHECK`, `gunicorn` with 2 workers. `docker-compose.yml` runs it locally with a named volume for `/data`.
```bash
docker compose -f docker/docker-compose.yml up --build
```
On my laptop the base image is pulled through `public.ecr.aws/docker/library/` because Docker Hub rate-limited anonymous pulls during this session.

## 6. Kubernetes deployment (`kubernetes/`)
Namespace, ConfigMap, Secret, PVC (500Mi), Deployment (2 replicas, `Recreate` because the PVC is RWO, startup/readiness/liveness probes, requests/limits, Prometheus scrape annotations), ClusterIP Service, NGINX Ingress (`taskboard.local`), HPA (2–5 replicas at 60 % CPU).

![kubectl apply, rollout, all objects](/assets/s21-deploy-01.png)

API exercised through the Ingress (port-forward of the minikube ingress controller): create two tasks, delete without token → 401, with token → 204, config/secret visible in the Pod env, Pods deleted and recreated → the task list survives on the PVC, metrics and logs.

![API through ingress, secret/config injection, persistence across pod restart](/assets/s21-deploy-02.png)

## 7. Helm deployment (`helm/taskboard/`)
Chart with values for image, config, secret, service, ingress, persistence, resources and autoscaling, plus `values-dev.yaml`. Install → upgrade (2 replicas, `ENVIRONMENT=staging`) → history → rollback → uninstall, all on minikube; the pipeline deploys with the same chart (`helm upgrade --install … --set image.tag=<sha>`).

![helm lint / install / upgrade / history / rollback](/assets/s21-helm.png)

## 8. Terraform infrastructure (`terraform/`)
VPC, public subnet, internet gateway, route table, security group (22/80/443), EC2 `t3.small` with nginx user data, versioned private S3 bucket. Same code and workflow as Session 19 (init → fmt → validate → plan → apply → output → destroy), run against a local AWS mock because no AWS credentials exist on this machine; see `terraform/README.md` and the Session 19 screenshots.

## 9. CI/CD pipeline (`.github/workflows/final-project.yml`)
Ten jobs chained with `needs:`; artifacts for the test report and the image tarball; the image that was scanned is the exact one pushed (`:<git-sha>` + `:latest`); the deploy job spins up a kind cluster in the runner, installs the chart with the new tag, waits for the rollout and smoke-tests `/health`, `/ready`, `POST /api/tasks`, `GET /api/tasks`, `/metrics`.

![final project pipeline – all ten jobs green, GHCR package](/assets/s21-pipeline-cli.png)

Run: <https://github.com/Gaurakumar-s/devops-heros/actions/workflows/final-project.yml>

## 10. DevSecOps implementation (`security/`)
| Stage | Tool | Gate |
|---|---|---|
| SAST | Bandit + Semgrep (python, flask rules) | HIGH / any blocking finding |
| SCA | pip-audit | any known CVE in dependencies |
| Secret scanning | Gitleaks over git history | any leaked credential (lab placeholders allow-listed) |
| Container image scanning | Trivy on the built tarball | fixable CRITICAL |
| Security gate | `security-gate` job | all four must pass before push/deploy |

The pipeline is green on the first run; in Session 17 the same gates caught a real `debug=True` and a `0.0.0.0` binding, which is why this app reads host/port/debug from the environment.

## 11. Monitoring (`monitoring/`)
In-cluster Prometheus (ServiceAccount + Role, pod service discovery on `prometheus.io/*` annotations, 2h retention) with three alert rules (pod down, 5xx rate > 5 %, p95 > 500 ms). Application metrics `taskboard_requests_total`, `taskboard_request_seconds`, `taskboard_tasks`; logs on stdout via `kubectl logs`; `kubectl top` via metrics-server.

![prometheus targets, request rates, task gauge, alert rules, top, logs](/assets/s21-monitoring.png)

## 12. GitOps (`gitops/`)
Argo CD `Application` pointing at `final-devops-project/kubernetes` on `main` with automated sync, prune and self-heal. The hands-on (Application creation, a replica change made only in Git, drift reverted by self-heal) is in `../session20-monitoring-observability-gitops/Submission.md`; the final project Application is registered next to it.

## 13. Troubleshooting
Five faults injected and fixed, documented in [`troubleshooting/README.md`](troubleshooting/README.md): wrong image tag (`ImagePullBackOff`), Service selector typo (empty endpoints, 503), missing ConfigMap/Secret keys (`CreateContainerConfigError`), wrong probe paths (`CrashLoopBackOff`, `0/1`), impossible resource requests (`Pending`).

## 14. Screenshots
All in `/assets/s21-*.png` and referenced above; Session 20 adds the Grafana dashboard and Argo CD screenshots.

## 15. Lessons learned
- **Config from the environment** is what makes one image work in compose, kind, minikube and the pipeline; the Session 12 newline bug and the Session 17 SAST findings both came back to "do not hard-code".
- **Gates must have thresholds.** Failing on every LOW finding would block delivery; failing on HIGH/CRITICAL caught real problems and still let the pipeline run in 4 minutes.
- **Immutable tags.** Deploying `:<git-sha>` means the scanned image is the deployed image; `:latest` is only a convenience for the local cluster.
- **`Recreate` + RWO storage is a trade-off**, and it made the troubleshooting challenge's first issue an outage instead of a failed rollout.
- **Most outages are not the code**: registry, selectors, config keys, probes and scheduling caused four of five faults.
- **GitOps needs discipline about what lives in the synced path** – an Application manifest inside its own source path overwrote itself (found and fixed in Session 20).
- **Infrastructure limits are real:** Docker Hub rate limits, a full disk and a broken minikube node cost more time than any YAML. Mirrors (`mirror.gcr.io`, ECR Public), cache cleanup and `minikube delete` were the fixes.
