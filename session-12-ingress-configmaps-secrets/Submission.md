# Session 12 – ConfigMaps, Secrets and Ingress (run on minikube)

## ConfigMap
Create `yatri-app-config`, inspect it with `describe`, and read a single key with jsonpath.

![configmap create, describe, jsonpath](/assets/s12-configmap.png)

## Secret
`describe secret` only shows byte counts. The value is base64-encoded, not encrypted – decoding `POSTGRES_PASSWORD` gives the plain text back.

![secret create, describe, base64 decode](/assets/s12-secret.png)

## Ingress
Enable the minikube NGINX ingress controller, apply `yatri-ingress`, and check the rules: `/api(/|$)(.*)` goes to the backend service (rewritten to `/$2`), `/` goes to the frontend. Requests are sent through the controller with `Host: yatri.local`; `/` returns the nginx frontend and `/api/` returns the Python backend, which prints the ConfigMap and Secret values it received.

![ingress controller, ingress rules, routing test](/assets/s12-ingress.png)

## Full demo (`04-full-demo/`)
ConfigMap + Secret + frontend Deployment/Service + backend Deployment/Service, all rolled out.

![full demo deploy](/assets/s12-fulldemo-01.png)

Inside the backend Pod, `env` shows the ConfigMap keys injected via `envFrom` and the Secret keys via `secretKeyRef`. Cleanup with `cleanup.sh`.

![env injection check and cleanup](/assets/s12-fulldemo-02.png)

## Task 4 – Ingress vs Ingress Controller
Written up in [`ingress-vs-ingress-controller/README.md`](ingress-vs-ingress-controller/README.md): what each one is, the difference, why both are needed, and path-based / host-based / TLS examples from this session.

## Task 5 – Troubleshooting (`troubleshooting/`)
**Problem:** the backend cannot log in to Postgres even though "the password is correct". `troubleshooting/secret-base64-gotcha.md` describes the incident; I reproduced it with `broken-secret.yaml` (password encoded with plain `echo`) and `db-auth-check.yaml`, a Pod that acts as the database login.

**Investigation:** `kubectl get pod` → `Error`; `kubectl logs` → `password authentication failed … received 15 characters, expected 14`; `kubectl describe` → `Exit Code 1`. Decoding the Secret value with `base64 --decode | od -c` shows the extra `\n` at the end, and the encoded string ends in `Ao=` (`echo` without `-n`).

**Root cause:** `echo "secretpassword" | base64` includes a trailing newline, so the Secret holds `secretpassword\n`.

**Fix:** re-encode with `echo -n`, apply `fixed-secret.yaml`, re-create the check Pod. It now reaches `Completed` with `password authentication OK`, and `od -c` shows exactly 14 characters.

![secret newline bug – before and after](/assets/s12-troubleshooting.png)
