# radic-delivery-platform

Centralised CI/CD and software delivery platform for Radic's 7 GCP-hosted
service repos (`fastapi-backend`, `web-bff`, `design_service`, `image-studio`,
`brand_research`, `frontend-v2`, `operations-console`), on GCP projects
`radicai` (non-prod) and `radicai-production` (prod), region `us-central1`,
using GitHub Actions, Google Cloud Deploy, Cloud Run, Workload Identity
Federation and Terraform.

Authoritative design source: Confluence space **RAITSDA**, page tree rooted at
"Centralised CI/CD: Overview and Architecture". This repo's constitution
(`.specify/memory/constitution.md`) formalises that design — read it first for
the non-negotiable rules referenced below.

## Repo layout (target — build incrementally per approved specs)

```text
.github/workflows/     # 12 reusable workflows (workflow_call) + this repo's own CI
actions/               # composite actions: setup-engine, gcp-auth, build-push, cosign-sign
engine/src/radic_delivery/
  cli.py               # typer entrypoint: radic-delivery
  descriptor/ release/ notes/ gates/ deploy/ tests/ commands/ adapters/
engine/tests/          # unit, property, golden-git fixtures
schemas/               # service.schema.json, release-manifest, change-note, test-result (JSON Schema draft 2020-12)
templates/             # runtime/{python-uv,node}, callers/*.yml (8 caller templates), deploy/(skaffold.yaml, run/<env>.yaml)
policy/                # severity policy, exceptions.yml (the one exceptions ledger)
terraform/modules/     # wif, registry, cloud-deploy, runtime-sa
terraform/environments/{dev-plane,release-plane}
rulesets/              # GitHub ruleset JSON (dev-trunk, main-prod-line, release-branches, tag rulesets)
docs/                  # ADRs, onboarding
specs/                 # Spec Kit feature specs (spec.md, plan.md, tasks.md per feature)
```

## Commands

```bash
uv sync                                                  # install engine deps
uv run pytest -q                                         # engine unit/property tests
uv run ruff check . && uv run mypy engine/               # lint + typecheck
uv run radic-delivery descriptor validate <path>         # validate a service descriptor
uv run radic-delivery --help                             # list all CLI command groups
actionlint && zizmor .github/workflows/                  # workflow lint + injection check
```

## Non-negotiable rules (see constitution for full rationale)

1. Pipeline logic lives only here, exact-tag pinned (`v1.x.y`); service repos hold only a descriptor + `deploy/` + thin callers.
2. Build once; promote only by verified `sha256:` digest; no mutable-tag deploys.
3. Fail-closed: required-check skip budget is always 0; exceptions only via dated `policy/exceptions.yml` entries (`EXC-####`, Jira ticket, Tech Lead approval, ≤30d/≤14d-Critical expiry).
4. WIF-only identity, one service account per duty per environment; no identity both creates and approves a prod rollout.
5. Prod rollout needs both a human approval (`prod` GitHub Environment, approver ≠ initiator) and a separate machine approver identity.
6. Terraform owns infra; Cloud Deploy + per-env service YAML own the running revision; Terraform `lifecycle.ignore_changes` the revision/traffic; `infra.yml` is the only path to `terraform apply`.
7. No arbitrary commands in descriptors/workflow inputs — named templates and typed, schema-validated parameters only.
8. The release bot proposes (cherry-pick -x, release PR); a human edits the selection and a different human approves.
9. Migrate each service via shadow-then-cutover with a parity diff before removing old workflows; new gates start report-only, become blocking on a recorded schedule.
10. Every change traces: spec → acceptance criteria → task → test → (where applicable) a release manifest/test-result record; every UAT-escaped defect gets a regression test before the next cut.
11. Every build is scanned (Snyk + gitleaks + Hadolint + Trivy + SBOM); Critical findings and verified secrets block outright.
12. `engine/`'s `radic-delivery` CLI is the only code path to `gcloud deploy`/`gcloud run`; workflows never shell out to gcloud/Terraform directly.

## Never do

- Never read, print, or quote `.env`, `gcs-service-account.json`, `Service Account Radic.rtf`, or any Secret Manager value.
- Never commit a long-lived GCP key or widen a WIF trust condition beyond exact repo + exact tag + environment.
- Never add `continue-on-error`, a workflow-level `if: always()` that swallows a required check, or any skip outside `policy/exceptions.yml`.
- Never have a deploy workflow run `terraform apply`, and never have a workflow call `gcloud` directly instead of the `radic-delivery` CLI.
- Never overwrite a service repo's existing `CLAUDE.md` wholesale — merge the service-repo template into it.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
