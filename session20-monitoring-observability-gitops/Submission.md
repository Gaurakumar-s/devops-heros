# Session 20 – Monitoring, Observability and GitOps

## Task 1 – Monitoring demo (`monitoring-demo/`)
Stack (docker compose): **Prometheus** (quay.io v3.5.0), **node-exporter** (host CPU/memory), a small **demo-app** that exposes `/metrics`, `/health`, `/work` (CPU burn), `/break` and `/fix`, and **Grafana 12.2** provisioned with the Prometheus datasource and a dashboard. Alert rules in `alert-rules.yml`: `TargetDown`, `HighCpuUsage`, `HighMemoryUsage`, `DemoAppUnhealthy`.

```bash
cd monitoring-demo && docker compose up -d --build
# Prometheus http://localhost:9090   Grafana http://localhost:3000 (admin/admin, anonymous viewer on)
```

### Metrics, CPU, memory, application health
![targets up, up{}, CPU %, memory %, app health, load, req/s, p95](/assets/s20-monitoring-01.png)

- `/api/v1/targets` → prometheus, node-exporter and demo-app all `up`.
- PromQL used: CPU `100 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))*100`, memory `(1 - node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)*100`, request rate `sum by (path)(rate(demo_app_requests_total[1m]))`, p95 `histogram_quantile(0.95, …_bucket)`.
- 30 calls to `/work` show up as req/s on `/work` and a p95 latency of ~70 ms.

### Alerts and logs
![alert rules inactive -> firing after /break and stopping node-exporter -> resolved](/assets/s20-monitoring-02.png)

- `curl /break` flips `demo_app_healthy` to 0 and `/health` to 503; `docker compose stop node-exporter` removes a target.
- 40 s later `/api/v1/alerts` shows **`TargetDown` firing** (node-exporter) and **`DemoAppUnhealthy` firing**. The demo-app log line `health switched to UNHEALTHY by request` explains the alert (logs answer "why", the metric answered "what").
- `/fix` + restarting node-exporter → 0 active alerts.
- Grafana API confirms the provisioned datasource and the dashboard.

### Grafana dashboard
![Grafana: CPU %, memory %, app health stat, targets up, req/s by path, p95](/assets/s20-grafana-dashboard.png)

The health stat and "targets up" panels show the dip during the alert test. Prometheus UI during the test:

![Prometheus targets page](/assets/s20-prometheus-targets.png)
![Prometheus alerts page](/assets/s20-prometheus-alerts.png)

## Task 2 – Observability
Documented in [`observability/README.md`](observability/README.md): what metrics, logs and traces each mean, why observability is required, common tools (Prometheus/Grafana/Loki/Tempo/OpenTelemetry and managed equivalents), Kubernetes observability layer by layer, and how the demo maps onto the pillars.

## Task 3 – GitOps with Argo CD
Concepts in [`gitops/README.md`](gitops/README.md). Hands-on on minikube with Argo CD v3.5 installed from the official manifest:

![Argo CD pods, Application manifest, Synced/Healthy, resources created from Git](/assets/s20-gitops-01.png)

- `gitops/argocd-application.yaml` points at **this repository**, path `08-mini-project/app` (Namespace, Deployment with 2 replicas, Service), with `automated: prune + selfHeal`.
- Argo CD created the namespace and the objects and reports `Synced / Healthy` at the current commit.

![replicas changed only in Git -> synced; manual scale reverted by selfHeal; history; final project Application](/assets/s20-gitops-02.png)

- Changed `replicas` in `deployment.yaml`, committed and pushed → after a refresh the Application went `OutOfSync` → `Synced` and the Deployment matched Git. No `kubectl apply` by me.
- Drift test: `kubectl scale … --replicas=5` by hand → within ~1 minute self-heal put it back to the value in Git. Git is the source of truth; the cluster is not allowed to disagree.
- The final project's Application (`final-devops-project/gitops/argocd-application.yaml`) was registered the same way.

**Bug I hit and fixed:** the instructor's `app/argocd-application.yaml` (with placeholder `YOUR_USERNAME`) lived inside the synced path, so on the first sync Argo CD applied it onto *itself* and overwrote the Application's `repoURL`, after which every refresh failed with `Repository not found`. Moving the template out of `app/` (now `08-mini-project/argocd-application.example.yaml`) fixed it. Lesson: never keep the Application CR in the path it syncs.

## Files
```text
monitoring-demo/   docker-compose.yml, prometheus.yml, alert-rules.yml, demo-app/, grafana/ (provisioning + dashboard JSON)
observability/README.md
gitops/README.md, gitops/argocd-application.yaml
08-mini-project/app/   namespace.yaml, deployment.yaml, service.yaml   (the GitOps source path)
```
