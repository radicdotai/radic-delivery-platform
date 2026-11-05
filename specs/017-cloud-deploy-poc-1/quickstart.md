# Quickstart: validate Cloud Deploy PoC-1

## Prerequisites

- `gcloud` authenticated as the PoC operator with rights to apply the
  `poc-1` Terraform root in `radicai`; Terraform ≥ 1.6; `uv`; Docker.
- A GitHub account with admin on `radicdotai/operations-console` (to create
  the `dev` Environment) and push rights on `radicdotai/radic-delivery-platform`
  (to place `v1-canary`).
- Snapshot of the real services taken first (SC-006):
  `poc/baseline.sh` records revision, image digest, IAM policy and traffic of
  every real service in `radicai` and `radicai-production` (read-only).

## 1. Engine, offline

```bash
cd engine && uv sync && uv run pytest -q && uv run ruff check . && uv run mypy src/
```

Expected: all tests pass, including the new `test_deploy_*` suites using the
fake gcloud.

## 2. Sandbox up

```bash
cd terraform/environments/poc-1 && terraform init && terraform apply
gcloud deploy delivery-pipelines list --project=radicai --region=us-central1 --format='value(name.basename())'
```

Expected: `ops-console-cdpoc-dev` and `ops-console-cdpoc-rel` listed; three
sandbox services exist with the placeholder image. Record the apply in
`poc/results.md`.

## 3. Dev release by hand (User Story 1)

```bash
uv run radic-delivery deploy release --descriptor <ops-console poc checkout>/.radic/service.yml \
  --env dev --image <repo>@sha256:<digest> --commit <sha> --run-number 1 --format json
uv run radic-delivery deploy status --env dev --descriptor ... --format json
```

Expected: `state: SUCCEEDED`, `serving_digest` equals the digest, exit `0`.
Passing a `:tag` image exits `2` with no Cloud Deploy call.

## 4. Merge-to-deploy loop (User Story 6)

Push a trivial commit to `poc/cloud-deploy-1` in `operations-console`.
Expected: the `cd-cdpoc` run builds, then deploys; the job summary shows the
release, rollout and digest; `deploy status` reports Ready on the new digest.
A copy of the caller pointing at `@dev` instead of `@v1-canary` fails at WIF
auth.

## 5. Promotion with separate identities (User Story 2)

```bash
poc/U25/run.sh   # creator cannot create a prod-like rollout
poc/U09/run.sh   # creator approval attempt recorded; approver approves
```

## 6. Rollback, drift, the rest

```bash
for u in poc/U*/run.sh; do "$u"; done
```

Expected: every PoC-1 row in `poc/results.md` is filled; none blank.

## 7. Teardown

```bash
poc/teardown.sh && poc/baseline.sh --compare
```

Expected: no `cdpoc` pipeline, target, service or SA remains (SC-005); the
real services are unchanged from the first baseline (SC-006).
