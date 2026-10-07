# Security gates for the final project

| Stage | Tool | Config | Blocks the pipeline on |
|---|---|---|---|
| SAST | Bandit | `bandit.yaml` | HIGH severity |
| SAST | Semgrep | rulesets `p/python`, `p/flask` | any finding |
| SCA | pip-audit | `application/requirements.txt` | known CVE in a dependency |
| Secret scan | Gitleaks | `gitleaks.toml` (full history) | any credential-looking string outside the allowlist |
| Image scan | Trivy | `.trivyignore` | fixable CRITICAL CVE in the image |
| Gate | `security-gate` job | – | any of the above red → no push, no deploy |

The placeholder tokens in `kubernetes/02-secret.yaml` and `helm/taskboard/values.yaml` are allow-listed on purpose; real values would come from Sealed Secrets / External Secrets and never be committed.
