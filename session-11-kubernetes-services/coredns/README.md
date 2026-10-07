# CoreDNS in Kubernetes

## What is CoreDNS?
CoreDNS is a DNS server written in Go that is built as a chain of **plugins**. Each plugin does one thing (answer from Kubernetes objects, forward upstream, cache, log, …) and a request flows through the chain in order. It has been the default cluster DNS since Kubernetes 1.13, replacing kube-dns.

In the cluster it runs as a Deployment in `kube-system` and is exposed through the `kube-dns` Service (name kept for compatibility):

```bash
kubectl get deploy,svc -n kube-system -l k8s-app=kube-dns
```

On my minikube: 1 replica (`coredns-559f6c778d-…`), Service `kube-dns` with ClusterIP `10.96.0.10` on UDP/TCP 53 and 9153 for metrics.

## Why Kubernetes uses CoreDNS
- **Single binary, plugin based** – the `kubernetes` plugin turns Services and Pods into DNS records; the `forward` plugin sends everything else upstream. No sidecars (kube-dns needed 3 containers: kubedns, dnsmasq, sidecar).
- **Watches the API server** – it keeps an informer cache of Services and EndpointSlices, so a new Service is resolvable within a second or two without any restart.
- **Configurable with one file** – the Corefile in a ConfigMap. Stub domains, rewrites, custom upstreams and extra zones are a few lines each.
- **Observable** – `/metrics` for Prometheus, `/health` and `/ready` endpoints, and a `log` plugin for per-query debugging.
- CNCF graduated, actively maintained, and what kubeadm, minikube, kind, EKS, GKE and AKS all ship.

## How Service discovery works
1. You create a Service `yatri-backend-service` in `default`.
2. The API server stores it; the endpoints controller writes the matching Ready Pod IPs into an EndpointSlice.
3. CoreDNS's `kubernetes` plugin sees both objects through its watch and now knows:
   - `yatri-backend-service.default.svc.cluster.local` → A `10.108.21.5` (the ClusterIP)
   - for a headless Service, A records for each Pod IP instead
   - SRV records for named ports.
4. Every Pod's `/etc/resolv.conf` points at `10.96.0.10` with the `search` list `default.svc.cluster.local svc.cluster.local cluster.local`, so `curl http://yatri-backend-service` is enough from inside the namespace.

No registration step, no client library: discovery is just DNS.

## How DNS queries are resolved

```text
Pod: curl http://yatri-backend-service/api
 │
 ├─ libc resolver reads /etc/resolv.conf (ndots:5, search list)
 ├─ "yatri-backend-service" has 0 dots < 5  →  append first search domain
 │     query: yatri-backend-service.default.svc.cluster.local  A?
 ▼
10.96.0.10:53  (kube-dns Service  →  CoreDNS Pod)
 │
 ├─ Corefile zone ".:53" matches
 ├─ plugin chain, in order:
 │     errors → health → ready → kubernetes (zone cluster.local)  ✔ match
 │     answer from informer cache: 10.108.21.5
 │     cache plugin stores it (TTL 30s)
 ▼
answer A 10.108.21.5   →   Pod connects to ClusterIP   →   kube-proxy DNAT to a Pod
```

For a name outside `cluster.local` (e.g. `api.github.com`) the `kubernetes` plugin does not match, so the query falls through to `forward . /etc/resolv.conf`, which sends it to the node's upstream resolver (on minikube: the Docker-provided DNS). Because of `ndots:5`, the Pod first tries `api.github.com.default.svc.cluster.local`, `…svc.cluster.local`, `…cluster.local` (all NXDOMAIN, answered fast from cache), and then `api.github.com` itself.

## CoreDNS configuration
The whole config is the Corefile in the `coredns` ConfigMap:

```bash
kubectl -n kube-system get configmap coredns -o yaml
```

Default Corefile shipped by minikube/kubeadm:

```text
.:53 {
    errors                      # log errors to stdout
    health {                    # /health on :8080 for the liveness probe
       lameduck 5s
    }
    ready                       # /ready on :8181 for the readiness probe
    kubernetes cluster.local in-addr.arpa ip6.arpa {
       pods insecure            # answer 10-244-0-17.default.pod.cluster.local
       fallthrough in-addr.arpa ip6.arpa
       ttl 30
    }
    prometheus :9153            # metrics
    forward . /etc/resolv.conf { # everything else -> upstream resolvers
       max_concurrent 1000
    }
    cache 30                    # cache answers for 30 s
    loop                        # detect forwarding loops
    reload                      # re-read the Corefile when the ConfigMap changes
    loadbalance                 # round-robin A records
}
```

Common edits:

```text
# send *.corp.example.com to an internal DNS server (stub domain)
corp.example.com:53 {
    errors
    cache 30
    forward . 10.0.0.53
}

# log every query (debugging only, noisy)
.:53 {
    log
    ...
}

# use public resolvers instead of the node's /etc/resolv.conf
forward . 8.8.8.8 1.1.1.1
```

After `kubectl edit configmap coredns -n kube-system` the `reload` plugin picks the change up within ~30 s, otherwise `kubectl rollout restart deploy/coredns -n kube-system`.

## How to troubleshoot DNS issues
Checklist I used in this session, from the Pod outward:

1. **Is it DNS or the Service?**
   ```bash
   kubectl run dns-test --rm -it --image=busybox:1.36 --restart=Never -- \
     nslookup yatri-backend-service.default.svc.cluster.local
   ```
   - `NXDOMAIN` → the Service name/namespace is wrong or the Service does not exist (`kubectl get svc -A | grep name`).
   - resolves but connection hangs → DNS is fine; check endpoints: `kubectl get endpoints <svc>` (empty = selector/label mismatch or Pods not Ready).
   - `;; connection timed out; no servers could be reached` → CoreDNS itself is unreachable.

2. **Is CoreDNS running?**
   ```bash
   kubectl get pods -n kube-system -l k8s-app=kube-dns
   kubectl logs -n kube-system -l k8s-app=kube-dns --tail=50
   kubectl get svc kube-dns -n kube-system        # must have ClusterIP 10.96.0.10 and endpoints
   kubectl get endpoints kube-dns -n kube-system
   ```
   `CrashLoopBackOff` with `plugin/loop: Loop detected` means the node's `/etc/resolv.conf` points back at CoreDNS; fix the upstream in the `forward` line.

3. **Is the Pod's resolver configured?**
   ```bash
   kubectl exec <pod> -- cat /etc/resolv.conf
   ```
   `nameserver` must be the kube-dns ClusterIP; `dnsPolicy: Default` or `hostNetwork: true` Pods use the node's resolver and cannot see cluster names unless `dnsPolicy: ClusterFirstWithHostNet` is set.

4. **Cross-namespace mistakes** – `nslookup api` from `staging` will not find `api` in `prod`; use `api.prod` or the full FQDN.

5. **Enable query logging temporarily** – add `log` to the Corefile and watch `kubectl logs -f -n kube-system -l k8s-app=kube-dns` while reproducing.

6. **Network policy / CNI** – a NetworkPolicy that blocks egress UDP 53 to `kube-system` silently breaks all name resolution; also check `kubectl get pods -n kube-system` for the CNI DaemonSet.

7. **Upstream failures** – cluster names resolve but `nslookup google.com` fails → the `forward` target is down; test from the node with `minikube ssh -- nslookup google.com`.

Scenario 4 of the Session 14 triage drill (`postgres-db-wrong-name.production.svc.cluster.local`) is the first case: the FQDN was well-formed, CoreDNS was healthy, and the answer was NXDOMAIN simply because no Service of that name existed. The fix was the hostname, not DNS.
