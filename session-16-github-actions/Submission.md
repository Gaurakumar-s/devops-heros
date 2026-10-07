# Session 16 – CI/CD with GitHub Actions

Demo project: the calculator app from `session-16-github-actions/10-final-cicd-pipeline/` (app + pytest tests + `build.sh`), wired to a real GitHub Actions pipeline in this repository: [`.github/workflows/session16-ci-cd.yml`](../.github/workflows/session16-ci-cd.yml).

Workflows only run from `.github/workflows/` at the repository root, so the YAML lives there and uses `defaults.run.working-directory` + a `paths:` filter to stay scoped to the Session 16 folder.

## Local run first
![pytest and build.sh locally](/assets/s16-local.png)

`pytest -v` → 5 tests pass; `./build.sh` → `build/calculator.py` + `build/build-info.txt` (`Build Status: SUCCESS`).

## The pipeline
```text
push to main / PR / manual (workflow_dispatch)
        │
        ▼
 test  (matrix: ubuntu-latest + macos-latest × Python 3.11 + 3.12 = 4 jobs)
        │ uploads test-results-<os>-py<version>.xml artifacts
        ├────────────────────────┐
        ▼                        ▼
 build (needs: test)      security-check (needs: test)
   ./build.sh                 fails if .env / *.pem / *.key is committed
   uploads calculator-build
        │                        │
        └──────────┬─────────────┘
                   ▼
 deploy (CD)  needs: build + security-check, only on push to main
   downloads calculator-build, reads secret SESSION16_DEPLOY_TOKEN,
   runs a smoke test on the artifact, "deploys" to environment session16-demo
```

### Successful execution
![gh run list / run view / artifact download / secrets](/assets/s16-pipeline-cli.png)

All seven jobs green (4 test matrix jobs, Build, Security Check, Deploy). The CLI screenshot also shows the artifact downloaded back from GitHub with the build info written by the runner (git SHA, run id), and the repository secret in `gh secret list`. Run: <https://github.com/Gaurakumar-s/devops-heros/actions/workflows/session16-ci-cd.yml>

## Concepts, as used in this workflow

| Concept | Where it is in the YAML | What I understood |
|---|---|---|
| **CI vs CD** | `test`/`build`/`security-check` are CI; `deploy` is CD | CI = every push is built and tested automatically; CD = once CI is green the artifact is promoted/deployed without manual steps. `deploy` has `if: github.ref == 'refs/heads/main'` so PRs get CI only. |
| **CI/CD pipeline** | the `needs:` chain | a DAG of jobs: test → (build ‖ security-check) → deploy. If a test fails, nothing downstream runs. |
| **GitHub Actions** | the whole file | GitHub's hosted automation; events in the repo trigger workflows. |
| **Workflow** | `name:` + `on:` | one YAML file = one workflow; triggers: `push` (with `paths` filter), `pull_request`, `workflow_dispatch` (the "Run workflow" button). |
| **Jobs** | `jobs: test / build / security-check / deploy` | each job runs on a fresh runner VM; jobs run in parallel unless `needs:` orders them. |
| **Steps** | `- name: … uses: / run:` | sequential commands inside a job; `uses:` = reusable action (`actions/checkout@v4`, `actions/setup-python@v5`), `run:` = shell. |
| **Runners** | `runs-on: ${{ matrix.os }}` | the machine that executes a job. The `strategy.matrix` ran the tests on Ubuntu and macOS with two Python versions; the "Show runner info" step prints `runner.os`. |
| **Secrets** | `${{ secrets.SESSION16_DEPLOY_TOKEN }}` | stored encrypted in repo settings (`gh secret set`), injected as an env var, and GitHub masks the value in logs as `***` (the log prints the length but not the token). `GITHUB_TOKEN` is provided automatically. |
| **Artifacts** | `actions/upload-artifact@v4` / `download-artifact@v4` | files passed between jobs or kept after the run (test reports, the `calculator-build` folder). Downloaded with `gh run download`. |
| **Build** | `build` job → `./build.sh` | produces the deployable output and stamps it with SHA + run number. |
| **Test** | `test` job → `pytest -v --junitxml` | unit tests gate everything else. |
| **Pipeline execution** | `gh run list`, `gh run view <id>`, Actions tab | every job, step, log and artifact is visible; re-runs are one click. |

## Failure scenario (what happens when a test fails)
With `needs: test`, a red test job skips `build`, `security-check` and `deploy`, so a broken commit can never produce an artifact or a deployment. I saw this behaviour for real in Session 17's pipeline, where a failed SAST job skipped every later job.

## Commands used
```bash
gh workflow list
gh run list --workflow "Session 16 CI/CD Pipeline"
gh run view <run-id>
gh run view <run-id> --log
gh run download <run-id> -n calculator-build
gh secret set SESSION16_DEPLOY_TOKEN --body "<value>"
gh secret list
```
