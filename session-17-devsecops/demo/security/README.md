# Security tool configuration

| File | Tool | Stage | Fails the pipeline when |
|---|---|---|---|
| `bandit.yaml` | Bandit | SAST | any HIGH severity finding in `app/` |
| (Semgrep rulesets `p/python`, `p/flask`) | Semgrep | SAST | any finding (`--error`) |
| `requirements.txt` | pip-audit | SCA | any known vulnerability in a pinned dependency |
| `gitleaks.toml` | Gitleaks | Secret scan | any credential-looking string in the demo folder |
| `.trivyignore` | Trivy | Container image scan | any **fixable CRITICAL** CVE in the image |

The `security-gate` job needs all four scanning jobs to succeed; only then is the image pushed to GHCR and deployed.
