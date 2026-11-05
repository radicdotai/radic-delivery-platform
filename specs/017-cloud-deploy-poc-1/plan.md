# Implementation Plan: Cloud Deploy PoC-1 (operations-console sandbox)

**Branch**: `018-cloud-deploy-poc-1` | **Date**: 2026-11-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/017-cloud-deploy-poc-1/spec.md`

## Summary

Replace the six `deploy` stubs with real Cloud Deploy calls through one
gcloud boundary in the engine; add the `cloud-deploy` and `wif` Terraform
modules and a `poc-1` root that stands up a private, three-service sandbox
copy of `operations-console` with a dev pipeline and an approval-gated
release pipeline, all in `radicai`; add minimal `build.yml` and `deploy.yml`
reusable workflows and a caller on a PoC branch of `operations-console`, so a
merge builds and deploys by digest; and run one script per PoC-1 U-item,
recording each result in `poc/results.md`. Design decisions are in
[research.md](research.md).

## Technical Context

**Language/Version**: Python ≥ 3.11 (engine, existing); HCL / Terraform ≥ 1.6 with `hashicorp/google` ~> 6.x; bash for `poc/` scripts; GitHub Actions YAML

**Primary Dependencies**: existing `typer`, `jsonschema`, `pyyaml` in the engine (no new Python dependency); `gcloud` CLI on PATH; `google-github-actions/auth@v2`, `docker/login-action`, `docker/build-push-action` in workflows

**Storage**: Terraform state in existing `gs://radicai-terraform-state-dev` (prefix `delivery-platform/poc-1`); Cloud Deploy source bucket `radicai-cd-source-cdpoc`; PoC evidence as files in `poc/`

**Testing**: pytest with a fake `Gcloud` object and canned JSON fixtures (offline); the live PoC scripts are the integration evidence; `actionlint` + `zizmor` for workflows; `terraform validate` + `tflint` if present

**Target Platform**: GitHub-hosted Ubuntu runners; GCP project `radicai`, region `us-central1`

**Project Type**: CLI engine + reusable workflows + Terraform modules (existing repo layout)

**Performance Goals**: dev rollout p90 and stage rollout p90 are recorded, not targeted (U30); rollback duration recorded against the ≤10 min constitution target

**Constraints**: nothing in `radicai-production`; no real dev/stage/prod service changes (SC-006); no JSON keys; evidence holds no secret values (repo is public)

**Scale/Scope**: 1 deployable, 3 sandbox services, 2 pipelines, 3 targets, 10 service accounts, 6 engine commands, 2 workflows, 17 U-items

## Constitution Check

*GATE: checked before Phase 0 research and re-checked after Phase 1 design.*

| Principle | Status | Note |
|---|---|---|
| I. Centralise implementation | Pass | All logic in this repo; operations-console gets only a descriptor, `deploy/` and a thin caller, on a PoC branch |
| II. Build once, promote the digest | Pass | Engine refuses any non-digest image; build emits the digest the deploy uses. Tree-equality promotion is not exercised (no `verify-promotion` in this feature) |
| III. Fail closed | Pass | Timeout, `FAILED`, `CANCELLED` and `REJECTED` are failures (research D8); no `continue-on-error` |
| IV. Keyless, separated identity | Pass with deviation | Per-duty SAs and WIF as designed. Deviation: the WIF condition trusts `v1-canary` (allowed for this canary in dev), and the operator holds token-creator on every PoC SA for the U-scripts. See Complexity Tracking |
| V. Human and machine approval for prod | Not applicable / partially exercised | No real prod. The prod-like target uses `requireApproval` and separate promoter/approver identities; the GitHub `prod` Environment is not part of this feature (FR-019) |
| VI. Terraform / Cloud Deploy boundary | Pass with deviation | Sandbox shells carry the `ignore_changes` list; deploy workflows never apply Terraform. Deviation: the `poc-1` root is applied from a maintainer machine because `infra.yml` does not exist yet. See Complexity Tracking |
| VII. No arbitrary commands | Pass | gcloud argv is built from typed inputs; workflows pass through `actionlint` and `zizmor` |
| VIII. Bot proposes, people decide | Not applicable | No release cut in this feature |
| IX. Parity before strictness | Pass | Sandbox is a shadow; the real dev service and its workflow keep running unchanged |
| X. Traceability | Pass | spec → FR → task → test, plus `poc/results.md` per U-item |
| XI. Scanning | Deferred | `build.yml` in this feature has no scan/SBOM step; the existing `security.yml` is unchanged. The real `build` feature adds them before any non-sandbox use |
| XII. Engine is the only path to GCP | Pass with note | Workflows call only the engine and official auth/registry actions. The `poc/` scripts call `gcloud` and `terraform` directly for read-only evidence (research D13) |

**Post-design re-check**: unchanged; no new violation introduced by the
data model or contracts.

## Project Structure

### Documentation (this feature)

```text
specs/017-cloud-deploy-poc-1/
├── spec.md
├── plan.md              # this file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── deploy-cli.md
│   └── workflows.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
engine/src/radic_delivery/deploy/
├── gcloud.py            # NEW: the only subprocess boundary to gcloud (research D7)
├── naming.py            # NEW: release names, labels, annotations, image-ref validation
├── cloud_deploy.py      # NEW: release / promote / approve / rollback / status
├── drift.py             # NEW: rendered-vs-live comparison (research D15)
├── deploy_result.py     # NEW: DeployResult, DriftResult
└── linter.py, parity.py, result.py, rules.py   # existing, unchanged
engine/src/radic_delivery/cli.py                 # replace the six stubs with real commands
engine/tests/unit/test_deploy_gcloud.py, test_deploy_naming.py,
  test_deploy_cloud_deploy.py, test_deploy_drift.py, test_deploy_cli_gcp.py   # NEW
engine/tests/fixtures/cloud_deploy/*.json        # NEW canned gcloud outputs
engine/tests/fixtures/operations-console.yml     # fix image repository name
schemas/service.schema.json                      # add cloud_deploy.sandbox + if/then (research D9)

terraform/modules/cloud-deploy/                  # NEW: pipelines, targets, IAM per deployable map
terraform/modules/wif/                           # NEW: pool, provider, SA bindings
terraform/environments/poc-1/                    # NEW: sandbox root (services, SAs, bucket, module calls)

.github/workflows/build.yml                      # NEW (PoC subset)
.github/workflows/deploy.yml                     # NEW (PoC subset)
templates/callers/cd-cdpoc.yml                   # NEW: the caller copied to operations-console

poc/README.md, poc/results.md, poc/baseline.sh, poc/teardown.sh   # NEW
poc/U01 … poc/U30 (PoC-1 subset)/run.sh                           # NEW

engine/README.md                                 # update the command table
```

Outside this repo (branch `poc/cloud-deploy-1` in `radicdotai/operations-console`):
`.radic/service.yml`, `deploy/skaffold.yaml`, `deploy/run/{dev,stage,prod}.yaml`,
`.github/workflows/cd-cdpoc.yml`.

**Structure Decision**: extend the existing `deploy/` engine package and add
the Terraform tree the repo's `CLAUDE.md` layout already names
(`terraform/modules/{wif,cloud-deploy}`). The PoC root is
`terraform/environments/poc-1`, beside the future `dev-plane` and
`release-plane`, and is deleted after the exit review.

## Phases

1. **Engine offline** (no GCP): gcloud boundary, naming, the six commands,
   drift, schema change, tests with fakes. Mergeable on its own.
2. **Sandbox infrastructure**: modules and `poc-1` root; baseline snapshot;
   apply; record.
3. **Manual live runs**: User Stories 1 to 4 from the operator's machine
   through the engine, impersonating each identity.
4. **Merge-to-deploy loop**: workflows, `v1-canary`, the operations-console
   PoC branch and `dev` Environment, User Story 6.
5. **U-items**: scripts and results for all 17; review with Vijit.
6. **Exit and teardown**: copy results to the Confluence U-register, destroy,
   compare baseline.

## Dependencies and risks

| Item | Owner | Effect if missing |
|---|---|---|
| GitHub account with admin on `operations-console` (current CLI accounts cannot see private repos) | Aditya | Phase 4 blocked |
| Vijit agrees `v1-canary` may point at the PoC branch (research D5) | Vijit | Use `poc1-canary` instead |
| Vijit's in-flight engine rework touches `cli.py` | Vijit / Aditya | Merge conflicts in `cli.py`; keep deploy changes to the `deploy` section and new modules |
| Operator can create SAs, WIF pools and Cloud Deploy resources in `radicai` | Aditya | Phase 2 blocked; verify with a `terraform plan` first |
| Confluence exit-code mismatch (`0/10/20/30` vs code `0/2/3/4`) | Vijit | Docs fix only |

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| `poc-1` Terraform applied from a maintainer machine, not `infra.yml` (Principle VI) | `infra.yml` does not exist; building it first would put a second feature in front of the PoC | Waiting for `infra.yml` delays the PoC that decides the Cloud Deploy design; every apply/destroy is logged and the root is destroyed at exit |
| Operator holds `serviceAccountTokenCreator` on PoC identities, including the approver (Principles IV, V) | U9 and U25 require acting as each identity to prove what it can and cannot do | Running each check from a separate GitHub workflow per identity triples the workflow work for a throwaway sandbox; the grant exists only in the sandbox root |
| WIF trusts the mutable `v1-canary` ref (Principle IV, exact semver) | The repo has no tags; the design allows `v1-canary` for this canary service in dev | Cutting `v1.0.0` from an unmerged PoC branch would claim a release that does not exist |
| `build.yml` without scan/SBOM (Principle XI) | Keeps the PoC to Cloud Deploy questions | Scanning is a separate, already-designed workflow; the sandbox image is the same code as the dev console, which ships today without it |
