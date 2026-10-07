# Monitoring for the final project

- `prometheus-config.yaml` – scrape config using Kubernetes pod service discovery (`prometheus.io/scrape|port|path` annotations, which the Deployment/Helm chart set) plus three alert rules: pod down, 5xx error rate > 5 %, p95 latency > 500 ms.
- `prometheus.yaml` – ServiceAccount/Role/RoleBinding (read pods, services, endpoints in the namespace), a single-replica Prometheus Deployment and a ClusterIP Service.
- Application metrics come from `/metrics` in the app itself: `taskboard_requests_total{method,endpoint,status}`, `taskboard_request_seconds` histogram, `taskboard_tasks{state}` gauge.
- Logs: gunicorn access log + app log on stdout → `kubectl logs -n taskboard deploy/taskboard`.

```bash
kubectl apply -f monitoring/
kubectl -n taskboard port-forward svc/prometheus 9090:9090
# http://localhost:9090/targets  → taskboard-pods (2/2 up)
```

For a full stack, the Session 20 `monitoring-demo` Grafana dashboard JSON works unchanged against this Prometheus (same metric names).
