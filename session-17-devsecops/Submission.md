# Session 17 – Complete CI/CD + DevSecOps

Application: the Flask "hey-cicd" dashboard in [`demo/`](demo/) (app, tests, Dockerfile, `k8s/` manifests, `security/` tool configs). Pipeline: [`.github/workflows/session17-devsecops.yml`](../.github/workflows/session17-devsecops.yml) at the repo root (scoped to `session-17-devsecops/demo/**`).

## Flow (each stage `needs:` the previous one)
```text
Code ──▶ Build ──▶ Unit Test ──▶ SAST ──▶ SCA ──▶ Secret Scan ──▶ Docker Build
                                                                      │
          Deploy to Kubernetes ◀── Push Image (GHCR) ◀── Security Gate ◀── Container Image Scan
```

| Stage | Tool | Fails when |
|---|---|---|
| Build | `pip install`, `python -m compileall` | dependencies or syntax broken |
| Unit Test | pytest + coverage (`pytest.xml` artifact) | any test fails |
| SAST | **Bandit** (`security/bandit.yaml`, HIGH severity gate) + **Semgrep** (`p/python`, `p/flask`, `--error`) | a code-level security finding |
| SCA | **pip-audit** on `requirements.txt` | a dependency with a known CVE |
| Secret Scan | **Gitleaks** (`security/gitleaks.toml`) over the full git history of the folder | a credential-looking string |
| Docker Build | buildx → `image.tar` artifact | Dockerfile broken |
| Container Image Scan | **Trivy** on the tarball: full table report + gate on fixable **CRITICAL** CVEs | critical OS/pip CVE in the image |
| Security Gate | job that `needs` all four scanners | any scanner red → nothing is published |
| Push Image | `docker/login-action` with `GITHUB_TOKEN` → **ghcr.io/gaurakumar-s/session17-hey-cicd:<sha>** and `:latest` | login/push error |
| Deploy | `helm/kind-action` creates a kind cluster in the runner, pull secret for GHCR, `kubectl apply` + `rollout status`, `curl` smoke test of `/health` and `/api/status` through the Service | rollout or smoke test fails |

## Running the tools locally before pushing
![pytest, bandit before/after fix, pip-audit, gitleaks, image build and trivy](/assets/s17-local-scans.png)

- `pytest --cov=app` → 8 tests pass, 69 % coverage.
- **Bandit found a real HIGH finding**: `B201 flask_debug_true` – `app.run(debug=True)` exposes the Werkzeug debugger (remote code execution). After the fix (`debug` only when `FLASK_DEBUG=1`) Bandit exits 0.
- `pip-audit` → no known vulnerabilities in Flask 3.1.3 and friends.
- `gitleaks dir .` → no leaks found.
- Image built (`python:3.12-alpine` base) and scanned with Trivy → 0 HIGH/CRITICAL.

## Pipeline execution on GitHub
The first two runs were **red on purpose of the gate**, which is exactly what DevSecOps is for:

1. Run 1: SAST failed – Semgrep `avoid_app_run_with_bad_host` (binding `0.0.0.0` by default). Every job after SAST was skipped, so no image was built or pushed. Fix: the host comes from `FLASK_HOST` (default `127.0.0.1`), and the Dockerfile sets `FLASK_HOST=0.0.0.0` explicitly because inside a container that is required.
2. Run 2: Docker Build failed – GHCR image names must be lowercase (`ghcr.io/Gaurakumar-s/…` is invalid). Fixed the `IMAGE_NAME`.
3. Run 3: Trivy action version could not be resolved → switched to installing the Trivy binary directly.
4. Run 4: **all 10 jobs green**, image pushed to GHCR, deployed to a kind cluster inside the runner and smoke-tested.

![gh run list / view: all ten jobs green, scanner output lines, GHCR package versions](/assets/s17-pipeline-cli.png)

Run: <https://github.com/Gaurakumar-s/devops-heros/actions/workflows/session17-devsecops.yml> · Package: <https://github.com/Gaurakumar-s?tab=packages>

## What the security stages mean (in my words)
- **SAST** (static application security testing) reads the *source* for dangerous patterns: debug mode, hard-coded hosts, `eval`, SQL built with f-strings, weak hashes. Bandit is Python-specific; Semgrep is rule-based across languages and has a Flask rule-pack.
- **SCA** (software composition analysis) checks the *third-party packages* you ship against vulnerability databases (OSV/PyPI advisories). Most real CVEs in a web app are in dependencies, not in your 200 lines.
- **Secret scanning** looks for keys, tokens and passwords in the files *and git history*, because a secret that was committed once and "removed" is still in the history. Gitleaks runs with `fetch-depth: 0` for that reason.
- **Container image scanning** looks at the *built artifact*: base image OS packages (alpine apk) and the Python packages inside it. A clean `requirements.txt` does not help if the base image ships an old OpenSSL.
- **Security gate** is the policy: nothing is published or deployed unless every scanner passed. Thresholds matter (HIGH for Bandit, fixable CRITICAL for Trivy); gating on every LOW would block all delivery.

## Kubernetes deployment details
`demo/k8s/deployment.yaml`: 2 replicas, image placeholder `__IMAGE__` replaced with the exact `ghcr.io/...:<git-sha>` that was scanned (immutable tag, not `latest`), `imagePullSecrets` for GHCR, readiness + liveness probes on `/health`, CPU/memory requests and limits. `service.yaml` exposes port 80 → 5001. The pipeline proves the deployment with `kubectl rollout status` and a `curl` through `kubectl port-forward`.

## Repository layout for this session
```text
session-17-devsecops/demo/
├── app/                 Flask app (hardened app.run)
├── tests/test_app.py
├── k8s/deployment.yaml, service.yaml
├── security/bandit.yaml, gitleaks.toml, .trivyignore, README.md
├── Dockerfile           python:3.12-alpine, FLASK_HOST=0.0.0.0
├── requirements.txt / requirements-dev.txt
└── README.md
.github/workflows/session17-devsecops.yml
```
