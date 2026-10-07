# Kubernetes Object Comparison

Notes written while doing Session 11 on minikube. Three comparisons: Deployment vs ReplicaSet, Deployment vs DaemonSet vs StatefulSet, and ReplicaSet vs Service.

---

## 1. Deployment vs ReplicaSet

| | ReplicaSet | Deployment |
|---|---|---|
| **Purpose** | Keep N identical Pods running at all times | Manage *versions* of an application by owning ReplicaSets |
| **Pod management** | Watches Pods that match its `selector`; creates or deletes Pods until `replicas` is met | Does not touch Pods directly; it creates a ReplicaSet and lets that ReplicaSet manage the Pods |
| **Scaling** | `kubectl scale rs <name> --replicas=5` – works, but a Deployment above it will overwrite the number | `kubectl scale deploy <name> --replicas=5` – the Deployment updates its current ReplicaSet |
| **Rolling updates** | None. Changing the Pod template of a ReplicaSet does nothing to existing Pods | Yes. A template change creates a *new* ReplicaSet and shifts Pods from old to new (`maxSurge` / `maxUnavailable`), with `rollout history`, `rollout undo`, `rollout pause` |
| **Who creates it** | Almost always created by a Deployment, rarely by hand | Created by you |

### Relationship

```text
Deployment  (desired version + strategy)
   │
   ├── ReplicaSet  rev 1  (nginx:1.24)  replicas: 0   ← kept for rollback
   └── ReplicaSet  rev 2  (nginx:1.25)  replicas: 3   ← current
            │
            ├── Pod
            ├── Pod
            └── Pod
```

- A Deployment is a controller *of* ReplicaSets. Every time the Pod template changes, a new ReplicaSet with a new pod-template-hash is created.
- Old ReplicaSets are scaled to 0 but kept (`revisionHistoryLimit`, default 10) so `kubectl rollout undo` can scale them back up.
- `kubectl get rs` on a Deployment that has been updated twice shows three ReplicaSets; only one has a non-zero DESIRED count.

### Why we never write ReplicaSets by hand
If I edit a ReplicaSet's image, the running Pods keep the old image until they die. A Deployment gives me the rollout behaviour, history and rollback for free, so in practice the ReplicaSet is an implementation detail.

---

## 2. Deployment vs DaemonSet vs StatefulSet

| | Deployment | DaemonSet | StatefulSet |
|---|---|---|---|
| **Use cases** | Stateless apps: web servers, APIs, workers | One Pod on *every* node: log shippers (Fluent Bit), node monitoring (node-exporter), CNI/kube-proxy, storage agents | Stateful apps that need stable identity: databases (MySQL, PostgreSQL), Kafka, ZooKeeper, Elasticsearch |
| **Pod creation** | `replicas: N` Pods with random names (`web-7d9f8-x2k9q`), scheduled anywhere | Exactly one Pod per node (or per node matching a `nodeSelector`/tolerations). No `replicas` field; adding a node adds a Pod automatically | Ordered, numbered Pods: `db-0`, `db-1`, `db-2`. Created one at a time, `db-1` only after `db-0` is Ready; deleted in reverse order |
| **Scaling** | `kubectl scale`, HPA | Scales with the number of nodes, not with a replica count | `kubectl scale` works but Pods are added/removed in order; each new Pod gets its own PVC |
| **Networking** | Pods are interchangeable; reached through a normal Service (ClusterIP) that load-balances | Usually reached on the node itself (hostPort / hostNetwork) or via a Service | Needs a **Headless Service**; each Pod gets a stable DNS name `db-0.db.default.svc.cluster.local` so clients can talk to a *specific* replica (e.g. the primary) |
| **Storage** | Normally none, or a shared PVC; all replicas see the same volume definition | Often `hostPath` to read node logs/metrics | `volumeClaimTemplates`: a separate PVC per Pod (`data-db-0`, `data-db-1`), re-attached to the same Pod name after restart |
| **Update** | RollingUpdate / Recreate | RollingUpdate node by node | RollingUpdate in reverse ordinal order, or `partition` for canary-style |

### Examples

Deployment – stateless API:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: api }
spec:
  replicas: 3
  selector: { matchLabels: { app: api } }
  template:
    metadata: { labels: { app: api } }
    spec:
      containers:
        - name: api
          image: ghcr.io/example/api:1.4
```

DaemonSet – node-exporter on every node:
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata: { name: node-exporter, namespace: monitoring }
spec:
  selector: { matchLabels: { app: node-exporter } }
  template:
    metadata: { labels: { app: node-exporter } }
    spec:
      hostNetwork: true
      tolerations:
        - key: node-role.kubernetes.io/control-plane
          effect: NoSchedule
      containers:
        - name: node-exporter
          image: prom/node-exporter:v1.8.2
```

StatefulSet – 3-node database with its own disk per Pod:
```yaml
apiVersion: v1
kind: Service
metadata: { name: db }
spec:
  clusterIP: None          # headless -> db-0.db, db-1.db, db-2.db
  selector: { app: db }
  ports: [{ port: 5432 }]
---
apiVersion: apps/v1
kind: StatefulSet
metadata: { name: db }
spec:
  serviceName: db
  replicas: 3
  selector: { matchLabels: { app: db } }
  template:
    metadata: { labels: { app: db } }
    spec:
      containers:
        - name: postgres
          image: postgres:16
          volumeMounts:
            - { name: data, mountPath: /var/lib/postgresql/data }
  volumeClaimTemplates:
    - metadata: { name: data }
      spec:
        accessModes: [ReadWriteOnce]
        resources: { requests: { storage: 1Gi } }
```

Rule of thumb I use: *interchangeable Pods → Deployment; one per node → DaemonSet; Pods with a name and a disk → StatefulSet.*

---

## 3. ReplicaSet vs Service

| | ReplicaSet | Service |
|---|---|---|
| **Responsibility** | Availability: "there must always be 3 Pods with label `app=web`" | Reachability: "there must always be one stable address that reaches whichever `app=web` Pods are Ready" |
| **Works on** | Pod *count* | Pod *network* |
| **Owns Pods?** | Yes (ownerReference) | No, it only selects them |

### Why a Service is required
- Pods are ephemeral. The ReplicaSet replaces a dead Pod with a *new* one that has a *new* IP. Anything that remembered the old IP breaks.
- A Service gets a virtual IP (ClusterIP) and a DNS name (`web.default.svc.cluster.local`) that never change for the life of the Service.
- The ReplicaSet makes sure Pods exist; the Service makes sure clients can find them. Neither one does the other's job.

### How traffic reaches Pods

```text
client Pod ──> DNS: web.default.svc.cluster.local  (CoreDNS answers 10.96.45.12)
          ──> ClusterIP 10.96.45.12:80             (virtual IP, no process listens here)
          ──> kube-proxy iptables/IPVS rule on the node
          ──> picks one endpoint from the EndpointSlice: 10.244.0.17:80 | 10.244.0.18:80 | 10.244.0.19:80
          ──> Pod container port 80
```

1. The Service `selector` (`app: web`) is matched against Pod labels; the endpoints controller writes the matching **Ready** Pod IPs into an EndpointSlice.
2. kube-proxy on every node programs iptables/IPVS so that packets to the ClusterIP are DNAT-ed to one of those Pod IPs.
3. When the ReplicaSet replaces a Pod, the EndpointSlice is updated within seconds; the ClusterIP stays the same, so clients never notice.
4. A Pod that fails its readiness probe is removed from the EndpointSlice but **not** deleted, which is why readiness probes and Services belong together.

What I saw in the drill (`troubleshooting/empty-endpoints.yaml`): a Service whose selector has a typo (`app: wrong-backend-name`) is created fine and gets a ClusterIP, but `kubectl get endpoints` shows `<none>` and every request times out. The ReplicaSet was healthy the whole time; the problem was purely on the Service side. `kubectl describe svc` + `kubectl get pods --show-labels` is the fastest way to catch this.
