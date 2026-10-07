# Session 11 – Kubernetes Service Types (run on minikube)

## ClusterIP
Three nginx Pods behind `web-service-clusterip` on port 8080. The service only has a cluster-internal IP, so I test it from the `curl-client` Pod inside the cluster.

![clusterip service and in-cluster curl](/assets/s11-services-01.png)

## NodePort, LoadBalancer, ExternalName, Headless
All five service types side by side. NodePort exposes 30080 on the node; LoadBalancer stays `<pending>` on minikube because there is no cloud load balancer; ExternalName has no ClusterIP and just returns a CNAME; the headless service has `CLUSTER-IP: None`.

![all service types, pods, and NodePort reachable from the host](/assets/s11-services-02.png)

## DNS behaviour and the empty-endpoints drill
- `nslookup external-database-service` resolves to a CNAME for the external hostname.
- `nslookup web-service-headless` returns the individual Pod IPs of the StatefulSet instead of one virtual IP.
- `broken-backend-service` has a selector typo, so `kubectl get endpoints` shows `<none>` – the first thing to check when a service returns connection refused.

![dns lookups, broken endpoints troubleshooting, cleanup](/assets/s11-services-03.png)

## Task 2 – Object comparison
Written up in [`object-comparison/README.md`](object-comparison/README.md): Deployment vs ReplicaSet (purpose, Pod management, scaling, rolling updates, how a Deployment owns ReplicaSets), Deployment vs DaemonSet vs StatefulSet (use cases, Pod creation, scaling, networking, storage, YAML examples), and ReplicaSet vs Service (who is responsible for what, why a Service is needed, how traffic reaches Pods).

## Task 3 – FQDN
Documented in [`fqdn/README.md`](fqdn/README.md): what an FQDN is, the `name.namespace.svc.cluster.local` convention, how `/etc/resolv.conf` (`search` + `ndots:5`) makes short names work, namespace-based DNS, Pod-to-Service flow and real FQDNs from this cluster.

## Task 4 – CoreDNS
Documented in [`coredns/README.md`](coredns/README.md): what CoreDNS is, why Kubernetes uses it, how Service discovery and query resolution work, the Corefile, and a troubleshooting checklist.

Hands-on check for Tasks 3 and 4 on minikube: CoreDNS Deployment/Service (`kube-dns`, ClusterIP `10.96.0.10`), the live Corefile, `/etc/resolv.conf` inside a curl Pod, `nslookup` of the short name (works through the `search` list after two NXDOMAINs), the full FQDN, `kubernetes.default.svc.cluster.local`, a wrong namespace (NXDOMAIN), an HTTP call by FQDN, and the CoreDNS query log.

![coredns and fqdn checks](/assets/s11-coredns-fqdn.png)
