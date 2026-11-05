# Tasks: Cloud Deploy PoC-1 (operations-console sandbox)

**Input**: `specs/017-cloud-deploy-poc-1/` (plan, spec, research, data-model, contracts)

**Tests**: required. Engine code is test-first with the fake gcloud; live
behaviour is proven by the `poc/` scripts.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency)
- **[Story]**: US1 … US6 from spec.md

## Phase 1: Setup

- [ ] T001 Confirm with Vijit: ownership split (`deploy` package, Terraform, `poc/`, `build.yml`/`deploy.yml` are this feature; the rest of the engine is his) and the `v1-canary` decision (research D5)
- [ ] T002 Get a GitHub login with admin on `radicdotai/operations-console` and push on `radicdotai/radic-delivery-platform` (blocker for Phase 6)
- [ ] T003 [P] Add canned gcloud JSON fixtures in `engine/tests/fixtures/cloud_deploy/` (release describe, rollout states, rollouts list, run service describe, export, targetArtifacts), captured shapes from gcloud docs; no real project data needed
- [ ] T004 [P] Fix the image repository in `engine/tests/fixtures/operations-console.yml` (`operations-console`, per research Observed)

## Phase 2: Foundational (blocks every story)

- [ ] T005 Test, then implement `engine/src/radic_delivery/deploy/gcloud.py`: `Gcloud` protocol, real runner (fixed argv, `--format=json`, `GcloudError` with stderr), fake for tests — `engine/tests/unit/test_deploy_gcloud.py`
- [ ] T006 [P] Test, then implement `deploy/naming.py`: digest image-ref validation, dev/rel release names, labels and annotations (data-model "Release naming") — `test_deploy_naming.py`
- [ ] T007 [P] Implement `deploy/deploy_result.py` (`DeployResult`, `DriftResult`, `to_dict`, outcome rules of research D8)
- [ ] T008 Schema: add `cloud_deploy.sandbox` with the `if/then` rule (research D9) in `schemas/service.schema.json`; tests in `test_descriptor_validate.py` for sandbox-allowed, non-sandbox-refused, and `-cdpoc-` naming
- [ ] T009 Shared rollout poller (10 s interval, `--timeout`, terminal-state mapping) in `deploy/cloud_deploy.py` with fake-clock tests

**Checkpoint**: engine foundations green offline (`uv run pytest -q && uv run ruff check . && uv run mypy src/`).

## Phase 3: US1 — dev deploy by digest (P1)

- [ ] T010 [US1] Tests: `deploy release --env dev` builds the exact argv of contracts/deploy-cli.md, refuses a `:tag` image (exit 2, no gcloud call), maps `SUCCEEDED`/`FAILED`/timeout to 0/3/3, gcloud error to 4 — `test_deploy_cloud_deploy.py`
- [ ] T011 [US1] Implement `release` (dev and stage modes) and `status` in `deploy/cloud_deploy.py`
- [ ] T012 [US1] Replace the `release` and `status` stubs in `engine/src/radic_delivery/cli.py`; CLI tests in `test_deploy_cli_gcp.py` (JSON and text output)

## Phase 4: US2 — promote and approve with separate identities (P1)

- [ ] T013 [P] [US2] Tests: `promote` stops at `PENDING_APPROVAL` and never calls approve; `approve` waits for `SUCCEEDED`
- [ ] T014 [US2] Implement `promote` and `approve`; replace their stubs in `cli.py`

## Phase 5: US3 + US4 — rollback and drift (P2)

- [ ] T015 [P] [US3] Tests: rollback with and without `--release`; `--expect-digest` mismatch exits 2 before any mutating call; duration reported
- [ ] T016 [US3] Implement `rollback`; replace stub
- [ ] T017 [P] [US4] Tests: drift field set and allowlist (research D15); env values never in output
- [ ] T018 [US4] Implement `deploy/drift.py` and the `drift` command; replace the last stub; remove `_DEPLOY_NOT_IMPLEMENTED`
- [ ] T019 Update `engine/README.md` command table (23 of 23 commands implemented)

**Checkpoint**: engine PR-able on its own (Phase 1 of plan.md).

## Phase 6: Sandbox infrastructure

- [ ] T020 [P] `terraform/modules/wif/` (pool, provider, mapping, condition of research D4, SA bindings) with `terraform validate`
- [ ] T021 [P] `terraform/modules/cloud-deploy/` (per-deployable pipelines, targets with labels/`executionConfigs`/`deploy_parameters`/`requireApproval`, pipeline- and target-level IAM, custom role and conditions of research D3)
- [ ] T022 `terraform/environments/poc-1/` (sandbox services with placeholder image and `ignore_changes`, all `cdpoc-*` SAs, source bucket, operator token-creator grants, module calls; backend prefix `delivery-platform/poc-1`)
- [ ] T023 `poc/baseline.sh` (read-only snapshot of every real service: revision, digest, IAM, traffic; `--compare` mode) and run it; commit the snapshot
- [ ] T024 `terraform plan` reviewed, then `terraform apply`; log in `poc/results.md`

## Phase 7: Live manual runs (US1–US4 against real Cloud Deploy)

- [ ] T025 [US1] Push one sandbox image by hand (digest), run `deploy release --env dev` and `deploy status` as `cdpoc-rel-dev`; record
- [ ] T026 [US2] Stage release as `cdpoc-rel-stage`, promote as `cdpoc-prod-promoter`, approve as `cdpoc-prod-approver`; record
- [ ] T027 [US3] Rollback drill on dev and stage; record durations
- [ ] T028 [US4] Drift with no change, then after a console edit on the dev sandbox; record

## Phase 8: US6 — merge-to-deploy loop (P1)

- [ ] T029 [P] [US6] `.github/workflows/build.yml` per contracts/workflows.md; `actionlint` + `zizmor` clean
- [ ] T030 [P] [US6] `.github/workflows/deploy.yml` per contracts/workflows.md; `actionlint` + `zizmor` clean
- [ ] T031 [US6] `templates/callers/cd-cdpoc.yml`
- [ ] T032 [US6] In `operations-console`, branch `poc/cloud-deploy-1` off `dev`: `.radic/service.yml` (sandbox descriptor), `deploy/skaffold.yaml`, `deploy/run/{dev,stage,prod}.yaml` cloned from the live dev spec, the caller; `radic-delivery deploy lint` passes
- [ ] T033 [US6] Create the `dev` Environment in `operations-console`; place `v1-canary` on this branch head (after T001 agreement)
- [ ] T034 [US6] Push a trivial commit to `poc/cloud-deploy-1`; confirm build → deploy → Ready on the new digest; confirm the real `dev` branch run is unaffected; confirm a caller on `@dev` fails WIF; record

## Phase 9: US5 — U-items (P1)

Each task: write `poc/Uxx/run.sh`, run it, fill the `poc/results.md` row (research D14).

- [ ] T035 [P] [US5] U1 Terraform plan clean after 3 rollouts
- [ ] T036 [P] [US5] U2 IAM policy, ingress, labels survive (domain mapping deferred)
- [ ] T037 [P] [US5] U6 `from-param` string + number; local render check
- [ ] T038 [P] [US5] U9 creator approval attempt
- [ ] T039 [P] [US5] U10 three dev releases within 2 minutes
- [ ] T040 [P] [US5] U11 mark deferred with reason (research D2)
- [ ] T041 [P] [US5] U13 labels in releases and Monitoring
- [ ] T042 [P] [US5] U14 drift catches a console edit (reuses T028)
- [ ] T043 [P] [US5] U15 minimal releaser bucket role set
- [ ] T044 [P] [US5] U17 digest readable from `releases describe`
- [ ] T045 [P] [US5] U19 target parameter changed after release creation
- [ ] T046 [P] [US5] U20 retention config + re-promote oldest PoC release (90-day part deferred)
- [ ] T047 [P] [US5] U25 releaser cannot create a prod-like rollout
- [ ] T048 [P] [US5] U26 service-scoped `run.developer` suffices
- [ ] T049 [P] [US5] U27 `--skaffold-version` pin
- [ ] T050 [P] [US5] U28 dry-run render finding
- [ ] T051 [P] [US5] U30 p90 timings over 5 dev and 5 stage rollouts, Cloud Build minutes
- [ ] T052 `poc/README.md`: how to re-run any item from a clean checkout

## Phase 10: Exit and teardown

- [ ] T053 Review `poc/results.md` with Vijit (exit review input, story E6c-1)
- [ ] T054 Copy results to the Confluence U-register (Technical Design §9.11); note the exit-code doc mismatch and the OI-1 status
- [ ] T055 `poc/teardown.sh`: `terraform destroy`, delete the operations-console PoC branch, the PoC-only `dev` Environment if unused, sandbox image tags
- [ ] T056 `poc/baseline.sh --compare` shows real services unchanged (SC-006); listing shows no `cdpoc` resource (SC-005)

## Dependencies

- Phase 2 blocks 3–5. Phases 3–5 are the mergeable engine slice.
- Phase 6 needs T001 (agreement) for naming only; it does not need Phases 3–5.
- Phase 7 needs Phases 3–6. Phase 8 needs Phases 3, 6 and T002, T033.
- Phase 9 needs Phase 7 (and T034 for U10 if run through the workflow).
- T056 is last.

## Parallel opportunities

- T003/T004; T006/T007; T013 with T015/T017; T020/T021; T029/T030; most U-scripts (T035–T051) once the sandbox is up.
