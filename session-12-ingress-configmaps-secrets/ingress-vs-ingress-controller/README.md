# Ingress vs Ingress Controller

## What is Ingress?
An **Ingress** is a Kubernetes API object (`networking.k8s.io/v1`) that describes HTTP/HTTPS routing rules: *which host and path should go to which Service and port*, plus optional TLS termination.

It is **only data**. Creating an Ingress by itself does nothing: no process reads it, no port is opened, no traffic moves. It is a routing table waiting for something to implement it.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: yatri-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  ingressClassName: nginx
  rules:
    - host: yatri.local
      http:
        paths:
          - path: /api(/|$)(.*)
            pathType: ImplementationSpecific
            backend:
              service: { name: yatri-backend-service, port: { number: 80 } }
          - path: /
            pathType: Prefix
            backend:
              service: { name: yatri-frontend-service, port: { number: 80 } }
```

## What is an Ingress Controller?
An **Ingress Controller** is the actual reverse proxy / load balancer running in the cluster (usually as a Deployment or DaemonSet with a Service of type LoadBalancer or NodePort). It:

1. watches the API server for Ingress objects (and the Services/EndpointSlices they refer to),
2. translates them into its own configuration (an `nginx.conf`, HAProxy config, Envoy xDS, Traefik dynamic config…),
3. listens on ports 80/443 and forwards each request to the right Pod according to those rules.

Examples: **ingress-nginx** (what `minikube addons enable ingress` installs), NGINX Inc. controller, Traefik, HAProxy, Contour/Envoy, Istio Gateway, AWS ALB Ingress Controller, GKE Ingress.

On my minikube:

```bash
kubectl get pods -n ingress-nginx
# ingress-nginx-controller-d7cd8c989-t4xnl   1/1   Running
```

## Difference between them

| | Ingress | Ingress Controller |
|---|---|---|
| Kind | Kubernetes object (YAML in etcd) | Running software (Pods) |
| Created by | Application teams, per app | Cluster admins, once per cluster (or per class) |
| Contains | host/path → Service rules, TLS secret names | The proxy that enforces those rules |
| Does traffic touch it? | No | Yes, every request passes through it |
| Namespaced? | Yes, lives next to the app | Usually its own namespace (`ingress-nginx`) |
| Without the other | Sits there with no ADDRESS, nothing is routed | Runs but has no rules, returns 404 for everything |
| Vendor specific bits | `ingressClassName` and `annotations` choose/configure a controller | Reads only Ingresses whose class matches it |

Analogy: the Ingress is the sign on the door ("Billing → room 3, Support → room 5"); the Ingress Controller is the receptionist who reads the sign and walks people there.

## Why both are required
- Kubernetes deliberately ships the **spec** (Ingress) but not an **implementation**, so you can pick the proxy that fits (nginx, Envoy, cloud ALB). A bare cluster has zero ingress controllers.
- The Ingress gives developers a portable, declarative way to say "route this host/path to my Service" without knowing nginx syntax.
- The controller gives one entry point (one external IP / one LoadBalancer) for many Services instead of one LoadBalancer per Service, handles TLS termination, path rewrites, rate limiting, etc.
- If you apply an Ingress on a cluster with no controller, `kubectl get ingress` shows an empty ADDRESS forever and `curl` fails. If you run a controller but write no Ingress, you get the controller's default 404 page. You need the rule *and* the thing that executes it.

`IngressClass` is the glue: the controller registers a class (`nginx`), and each Ingress says `ingressClassName: nginx`. With two controllers (e.g. nginx for internal, ALB for internet-facing) the class decides who handles which Ingress.

## Examples

### 1. Path-based routing (used in this session's `04-full-demo`)
```text
http://yatri.local/        → yatri-frontend-service → nginx frontend Pod
http://yatri.local/api/    → yatri-backend-service  → Python backend Pod (path rewritten to /)
```
Verified with:
```bash
curl -H "Host: yatri.local" http://$(minikube ip)/
curl -H "Host: yatri.local" http://$(minikube ip)/api/
```

### 2. Host-based routing (`03-ingress/ingress-tls.yaml`)
```yaml
rules:
  - host: portal.yatri.local
    http: { paths: [{ path: /, pathType: Prefix, backend: { service: { name: frontend, port: { number: 80 } } } }] }
  - host: api.yatri.local
    http: { paths: [{ path: /, pathType: Prefix, backend: { service: { name: backend,  port: { number: 80 } } } }] }
tls:
  - hosts: [portal.yatri.local, api.yatri.local]
    secretName: yatri-tls
```
Same IP, same port 443; the controller picks the backend from the `Host` header / SNI and terminates TLS with the cert in `yatri-tls`.

### 3. Enabling a controller on minikube
```bash
minikube addons enable ingress
kubectl get pods -n ingress-nginx
kubectl get ingressclass          # nginx
```

### 4. What a missing controller looks like
```bash
kubectl get ingress
NAME            CLASS   HOSTS         ADDRESS   PORTS   AGE
yatri-ingress   nginx   yatri.local             80      2m     <- ADDRESS empty
```
The Ingress is accepted (it is valid YAML) but nothing implements it. Enabling the addon fills in ADDRESS within a minute.
