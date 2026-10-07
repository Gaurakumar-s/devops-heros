# Observability – the three pillars

## Monitoring vs observability
**Monitoring** asks questions you already know to ask: *is CPU above 80 %? is the Pod up? did the request rate drop?* You pick metrics in advance, draw dashboards and set alerts.

**Observability** is the property of a system that lets you answer questions you did **not** know you would need to ask, from the data it emits: *why is checkout slow only for users in one region since the last deploy?* It is built from three kinds of telemetry, correlated with each other.

```text
            metrics  ──  "something is wrong"      (cheap, aggregated, alertable)
               │
            logs     ──  "what exactly happened"   (detailed events, searchable)
               │
            traces   ──  "where in the request path" (per-request timing across services)
```

## Pillar 1 – Metrics
Numeric measurements sampled over time, stored as time series with labels: `demo_app_requests_total{path="/work",status="200"}`.

- Types: **counter** (only goes up: requests, errors), **gauge** (goes up and down: memory, queue depth, `demo_app_healthy`), **histogram** (distribution: request latency buckets → p95), summary.
- Cheap to store, easy to aggregate (`rate()`, `sum by (path)`), ideal for dashboards and alerts.
- Weakness: no context about *one* request; high-cardinality labels (user id) blow up storage.
- In the demo: Prometheus scrapes `/metrics` every 5 s from itself, node-exporter (host CPU/RAM) and `demo-app`; PromQL `100 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))*100` is the CPU panel.

## Pillar 2 – Logs
Timestamped text (ideally structured JSON) emitted by the application and the platform: `2026-10-07 16:10:01 INFO GET /work 0.412s`.

- Richest detail, answer "what happened at 16:10:01 on Pod X".
- Expensive at volume; need shipping (Fluent Bit, Promtail, Vector), storage/indexing (Loki, Elasticsearch/OpenSearch, CloudWatch Logs) and good structure (level, request id, trace id) to be searchable.
- In Kubernetes: `kubectl logs`, `kubectl logs --previous`, container stdout/stderr collected by a DaemonSet from `/var/log/containers`.
- In the demo: `docker compose logs demo-app` shows every request and the `health switched to UNHEALTHY` error line that explains the alert.

## Pillar 3 – Traces
A trace follows **one request** across services: a tree of spans (`frontend → api → db query`) with timing. Shows *where* latency or errors come from in a distributed system; metrics tell you p95 is 2 s, the trace tells you 1.8 s of it was one SQL query.

- Needs instrumentation: OpenTelemetry SDK/auto-instrumentation, propagation of `traceparent` headers between services.
- Backends: Jaeger, Tempo, Zipkin, AWS X-Ray, Datadog APM.
- Best value when the trace id is also printed in logs and exemplars link metrics → traces.
- Not implemented in the demo (single service); the Session 21 project notes where OpenTelemetry would be added.

## Why observability is required
1. **Microservices and Kubernetes hide failures**: a request crosses 5 services and 3 Pods that may be replaced at any time; `ssh` and `top` no longer work.
2. **Unknown unknowns**: dashboards only show the failures you predicted; new deploys produce new failure modes.
3. **MTTR**: with correlated metrics → logs → traces an on-call engineer goes from "alert fired" to root cause in minutes instead of hours.
4. **Feedback for CI/CD**: canary and rollback decisions (Session 10) need error rate and latency per version.
5. **Capacity and cost**: HPA (Session 13) scales on metrics; right-sizing requests/limits needs utilisation history.
6. **SLOs**: you cannot promise 99.9 % availability without measuring it.

## Common tools

| Need | Open source / CNCF | Managed / SaaS |
|---|---|---|
| Metrics | **Prometheus**, Thanos/Mimir (long-term), node-exporter, kube-state-metrics, metrics-server | CloudWatch, Datadog, New Relic, Grafana Cloud |
| Logs | **Loki** + Promtail/Fluent Bit, OpenSearch/ELK, Vector | CloudWatch Logs, Datadog Logs, Splunk |
| Traces | **Jaeger**, Tempo, Zipkin, OpenTelemetry Collector | AWS X-Ray, Datadog APM, Honeycomb |
| Dashboards | **Grafana** | same vendors |
| Alerting | Prometheus Alertmanager, Grafana Alerting | PagerDuty/Opsgenie for routing |
| Instrumentation standard | **OpenTelemetry** (metrics + logs + traces, vendor-neutral) | – |
| Kubernetes bundle | kube-prometheus-stack Helm chart (Prometheus + Alertmanager + Grafana + exporters + dashboards) | EKS add-ons, GKE Managed Prometheus |

## Kubernetes observability
What to collect at each layer:

```text
Cluster   kube-state-metrics (object states: Deployments ready, Pods pending, HPA replicas)
Node      node-exporter (CPU, memory, disk, network of each node)   ← same thing the demo scrapes
Pod       cAdvisor via kubelet (container_cpu_usage_seconds_total, container_memory_working_set_bytes)
          metrics-server → `kubectl top pods/nodes`, HPA
App       /metrics endpoint (prometheus_client), logs on stdout, OpenTelemetry traces
Control   API server, etcd, CoreDNS, kube-proxy metrics
Events    `kubectl events` / `kubectl get events --sort-by=.lastTimestamp` (Session 14)
```

- **Prometheus Operator** (`ServiceMonitor`, `PodMonitor`, `PrometheusRule` CRDs) turns scrape targets and alert rules into Kubernetes objects next to the app.
- **Probes** (Session 13) are the kubelet's own health signal; export the same check as a metric (`demo_app_healthy`) so dashboards and alerts see it too.
- Standard alerts to start with: `KubePodCrashLooping`, `KubePodNotReady`, `KubeDeploymentReplicasMismatch`, `NodeMemoryPressure`, `TargetDown`, `CPUThrottlingHigh`.
- Logs: one Fluent Bit/Promtail DaemonSet ships every container's stdout with Pod/namespace labels, so `{namespace="prod", app="api"} |= "error"` works in Loki without the app knowing anything about it.
- Golden signals per service (SRE book): **latency, traffic, errors, saturation** – the demo dashboard has one panel for each (p95 latency, req/s by path, status labels, CPU/memory).

## How the demo maps to the pillars
| Pillar | In `../monitoring-demo` |
|---|---|
| Metrics | Prometheus scraping prometheus, node-exporter, demo-app; Grafana dashboard with CPU %, memory %, health, req/s, p95 |
| Logs | demo-app structured log lines (`docker compose logs`), including the error that explains the health alert |
| Alerts | `alert-rules.yml`: TargetDown, HighCpuUsage, HighMemoryUsage, DemoAppUnhealthy – fired on purpose with `/break` and by stopping a container |
| Traces | not implemented; next step would be OpenTelemetry auto-instrumentation + Tempo |
