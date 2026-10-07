# Session 21 – TaskBoard capstone walkthrough (instructor project)

**Student:** Gaurav Kumar · **Enrollment:** 24BCS10066

This is the instructor's TaskBoard project (`session21-python/`: FastAPI backend + PostgreSQL + React/Vite frontend, Helm chart, Terraform, GitHub Actions) taken through every part of its README and the `GRADING.md` milestones on my laptop (Docker Desktop + minikube). My own end-to-end project built from scratch per the PDF deliverables is in [`../final-devops-project/`](../final-devops-project/README.md).

Fixes I had to make to the course files (all commented in place): a Postgres `healthcheck` + `depends_on: condition` in `docker-compose.yml` (the backend ran Alembic before the DB accepted connections and crashed), `TestClient` entering its context so the startup event creates the SQLite tables, a `backend` alias Service in the chart (the frontend's nginx proxies to `http://backend:8000`, the compose service name), the Ingress backend service name/port (`taskboard-taskboard-backend:8000`), and the Terraform files reformatted from invalid single-line HCL.

## M1/M4 – Run it locally (Docker Compose)
![docker compose up --build, compose ps, health, create/list task, metrics, frontend 200](/assets/s21p-compose.png)
![TaskBoard UI at http://localhost:3000](/assets/s21p-frontend-web.png)
![FastAPI Swagger at http://localhost:8000/docs](/assets/s21p-swagger-web.png)

Three containers (`postgres:16-alpine`, backend, frontend); Alembic migration `0001_create_tasks` runs on start; task created through the API shows up in the UI.

## M2 – Testing
![pytest -v: 3 passed](/assets/s21p-pytest.png)

## M3 – Git and GitHub
![git remote, commit count, recent history](/assets/s21p-git.png)

Repository: <https://github.com/Gaurakumar-s/devops-heros> (public, 49+ commits).

## M6 – Security scanning (Trivy)
![trivy image on backend and frontend images](/assets/s21p-trivy.png)

Trivy scans the OS packages (Debian 13 for the backend, Alpine for the nginx frontend) and the Python/npm packages inside each image against its vulnerability DB. **The first pipeline run was blocked by the gate**: `starlette 0.41.3` (pulled in by the pinned `fastapi==0.115.6`) had 3 HIGH CVEs (CVE-2025-62727, CVE-2026-48818, CVE-2026-54283), so `--exit-code 1` failed the job and nothing was pushed or deployed. Fix: bump `fastapi` to 0.142.2 and `prometheus-fastapi-instrumentator` to 8.1.0 (needed for Starlette ≥ 1.x), tests still pass, rebuilt image scans clean. A clean scan means no *known* vulnerable package versions; it is not proof the application code is secure, which is what SAST (Bandit/Semgrep in Session 17) covers.

## M5 – CI/CD (GitHub Actions)
Workflow: [`.github/workflows/session21-taskboard.yml`](../.github/workflows/session21-taskboard.yml) (repo-root copy of the project's `ci-cd.yml`, scoped to this folder): backend tests → build both images → Trivy gate → push `ghcr.io/gaurakumar-s/taskboard-backend` and `taskboard-frontend` with the git SHA and `latest` → deploy with Helm into a kind cluster and smoke-test the API.

![pipeline run and GHCR packages](/assets/s21p-pipeline-cli.png)

Runs: <https://github.com/Gaurakumar-s/devops-heros/actions/workflows/session21-taskboard.yml>

## M7 – Terraform (VPC + EKS)
![terraform init / fmt / validate / plan for the VPC + EKS modules](/assets/s21p-terraform.png)

`init` downloads the `terraform-aws-modules/vpc` and `eks` modules and the AWS provider; `validate` passes. There is no AWS account on this machine, so `plan`/`apply` against real AWS (and the console/`destroy` screenshots the rubric asks for) are not possible here; the identical workflow was exercised end to end against a local AWS mock in Session 18/19 (`../session19-cloud-terraform/terraform-project/README.md`).

## M8 – Kubernetes + Helm (minikube)
![helm lint/install, helm list, pods, services, ingress/hpa/pvc/secret, migration log](/assets/s21p-helm-k8s.png)

`helm upgrade --install taskboard ./helm/taskboard -n taskboard-capstone -f values-dev.yaml` with the images built inside minikube (`minikube image build`). Backend ×2, frontend ×2, Postgres with PVC, Secret, Services, Ingress `capstone.local`, HPA (2–6 on 60 % CPU).

![ingress: /api/health, /api/tasks, frontend title, /api/metrics; HPA; helm history](/assets/s21p-ingress-hpa.png)
![TaskBoard through the Ingress hostname (capstone.local via the minikube ingress controller)](/assets/s21p-ingress-web.png)

## M9 – Monitoring (Prometheus + Grafana)
kube-prometheus-stack installed with `monitoring/prometheus-values.yaml`; the chart's `ServiceMonitor` registers the backend's `/metrics` with the Prometheus Operator.

![backend /metrics, Prometheus targets (taskboard UP), Grafana datasource](/assets/s21p-monitoring.png)
![Prometheus targets page](/assets/s21p-prom-targets-web.png)
![Grafana dashboard with populated panels](/assets/s21p-grafana-web.png)

## Troubleshooting lab
![broken image (ImagePullBackOff → fixed) and broken service (no endpoints → selector fixed)](/assets/s21p-troubleshooting.png)

| Lab | Symptom | Root cause | Fix |
|---|---|---|---|
| `broken-image.yaml` | `ErrImagePull` / `ImagePullBackOff` | `ghcr.io/example/taskboard-backend:does-not-exist` | `kubectl set image` to a real image (+ the DB URL env) → rolled out |
| `broken-service.yaml` | Service exists, `endpoints: <none>` | selector `app: label-that-does-not-exist` | patch selector to `app: taskboard-backend` → endpoints appear |

## M10 – Documentation
This file plus the project README. Lessons: compose start-up ordering needs health checks, not just `depends_on`; a Service name must match what the proxy inside the image expects; one-line HCL is not valid Terraform; and every "it works on compose" assumption (service names, ports) has to be re-checked in Kubernetes.
