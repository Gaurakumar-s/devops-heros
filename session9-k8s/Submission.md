# Session 9 – Kubernetes Fundamentals (minikube)

## 1–2. Install and configure Minikube, verify the cluster
Minikube runs with the Docker driver on my Mac (`minikube start --driver=docker`, with the `metrics-server` and `ingress` addons enabled for later sessions).

![minikube version/status, cluster-info, nodes, kube-system pods, readyz, api-resources, namespaces](/assets/s9-minikube-01.png)

Commands used:
```bash
minikube version
minikube status                       # host / kubelet / apiserver Running, kubeconfig Configured
kubectl version
kubectl cluster-info                  # control plane at https://127.0.0.1:<port>, CoreDNS
kubectl get nodes -o wide             # 1 node "minikube", Ready, control-plane, v1.37.0
kubectl get pods -n kube-system       # the control-plane components
kubectl get --raw='/readyz?verbose'   # API server health checks
kubectl api-resources --namespaced=true
kubectl get namespaces
```

## 3. Kubernetes architecture – short notes
`kubectl get pods -n kube-system` on minikube shows every architectural component as a Pod on the single node:

| Component | Pod on minikube | Role |
|---|---|---|
| **kube-apiserver** | `kube-apiserver-minikube` | Front door of the cluster. Every `kubectl` call, every controller and the kubelet talk to it; it validates objects and stores them in etcd. |
| **etcd** | `etcd-minikube` | Key-value store holding the whole cluster state (desired + observed). The only stateful part of the control plane. |
| **kube-scheduler** | `kube-scheduler-minikube` | Watches for Pods with no node and picks a node based on resources, selectors, affinities and taints. |
| **kube-controller-manager** | `kube-controller-manager-minikube` | Runs the control loops: Deployment, ReplicaSet, Node, Endpoint, ServiceAccount controllers… each compares desired vs actual and acts. |
| **kubelet** | runs on the node itself (`minikube ssh` → `systemctl status kubelet`) | Node agent. Receives Pod specs from the API server, starts containers through the container runtime (containerd), runs probes, reports status. |
| **kube-proxy** | `kube-proxy-xxxxx` (DaemonSet) | Programs iptables/IPVS so Service ClusterIPs reach Pod IPs. |
| **CoreDNS** | `coredns-xxxxx` | Cluster DNS: `service.namespace.svc.cluster.local`. |
| **CNI (kindnet)** | `kindnet-xxxxx` | Pod networking; every Pod gets an IP (`10.244.0.x`) routable inside the cluster. |
| **storage-provisioner** | `storage-provisioner` | minikube's dynamic volume provisioner behind the `standard` StorageClass. |

```text
kubectl ──▶ kube-apiserver ◀──▶ etcd
                 ▲   ▲
     scheduler ──┘   └── controller-manager
                 │
            kubelet (node) ──▶ containerd ──▶ Pods      kube-proxy / CNI handle networking
```

Control plane = API server + etcd + scheduler + controller-manager. Worker node = kubelet + kube-proxy + container runtime. On minikube both live on one node; on a real cluster the control plane runs on separate (often managed) machines.

## 4–5. Basic objects and commands, Kubernetes Basics tutorial hands-on
The official *Kubernetes Basics* tutorial (deploy an app → explore → expose → scale → update → roll back) executed on minikube:

![create deployment, pods, logs, expose, scale, update, rollback](/assets/s9-minikube-02.png)

| Step | Command | Observed |
|---|---|---|
| Deploy | `kubectl create deployment kubernetes-bootcamp --image=gcr.io/google-samples/kubernetes-bootcamp:v1` | Deployment → ReplicaSet → 1 Pod, `successfully rolled out` |
| Explore | `kubectl get pods -o wide`, `kubectl describe pod`, `kubectl logs` | Pod IP `10.244.0.x` on node minikube, image v1, logs show the server started |
| Expose | `kubectl expose deployment/kubernetes-bootcamp --type=NodePort --port=8080` | Service with a ClusterIP and a NodePort; a busybox Pod gets `Hello Kubernetes bootcamp! … v=1` through the Service name |
| Scale | `kubectl scale deployments/kubernetes-bootcamp --replicas=4` | 4 Pods, `kubectl get rs` shows DESIRED/CURRENT/READY 4 |
| Update | `kubectl set image deployments/kubernetes-bootcamp kubernetes-bootcamp=jocatalin/kubernetes-bootcamp:v2` | rolling update, new ReplicaSet, `rollout history` shows revision 2 |
| Roll back | `kubectl rollout undo deployments/kubernetes-bootcamp` | back to v1 image, revision 3 |
| Clean up | `kubectl delete deployment/service kubernetes-bootcamp` | |

Basic objects touched: **Pod** (smallest unit, one or more containers, one IP), **ReplicaSet** (keeps N Pods), **Deployment** (versions ReplicaSets, rolling updates and rollbacks), **Service** (stable name/IP in front of Pods), **Namespace** (logical partition), **Node**. The workload-controller comparison (Deployment, ReplicaSet, DaemonSet, StatefulSet) from the session notes is kept below.

---

## Workload controllers – notes
Notes on the four controllers that manage Pods, and when each one is the right choice.

### Deployment
- Used for stateless apps where any replica can serve any request.
- Keeps the requested number of Pods running via a ReplicaSet it owns.
- Supports rolling updates and `kubectl rollout undo` for instant rollback.
- Typical use: web frontends, REST APIs, workers that keep no local state.

### ReplicaSet
- Guarantees N identical Pods exist at all times; recreates any that die.
- Rarely created by hand – a Deployment creates and versions ReplicaSets for you.
- Typical use: the "keep 3 copies alive" layer underneath a Deployment.

### DaemonSet
- Runs exactly one Pod on every node (or every node matching a selector).
- New nodes automatically get the Pod; removed nodes lose it.
- Typical use: log shippers, metrics agents, CNI/network plugins, node monitoring.

### StatefulSet
- For apps that need a stable identity: fixed Pod names (`web-0`, `web-1`), stable DNS, and a PersistentVolume per Pod.
- Pods start and stop in order, so leader/follower setups work.
- Typical use: databases (PostgreSQL, MySQL, MongoDB), Kafka, ZooKeeper.

### Comparison

| Controller  | Guarantees                               | Scaling      | Storage            | Use for              |
| ----------- | ---------------------------------------- | ------------ | ------------------ | -------------------- |
| Deployment  | N replicas, rolling update + rollback    | Any count    | Shared / none      | Stateless services   |
| ReplicaSet  | N identical replicas                     | Any count    | Shared / none      | Building block       |
| DaemonSet   | One Pod per node                         | = node count | Usually hostPath   | Node-level agents    |
| StatefulSet | Ordered, named Pods with own volume each | Any count    | One PVC per Pod    | Databases, brokers   |
