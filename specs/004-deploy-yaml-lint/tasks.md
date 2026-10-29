# Tasks: Deploy YAML Lint

**Input**: Design documents from `/specs/004-deploy-yaml-lint/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md
**Builds on**: specs/001-engine-scaffold (`descriptor validate`), specs/002-ci-gate-workflow
(`ci.yml`'s `deploy_lint` placeholder output), specs/003-security-scanning
(`security/runner.py`, `security/parsers.py::parse_gitleaks`)

**Tests**: included — spec.md's Acceptance Scenarios require specific,
distinguishable outcomes per rule, same as prior features.

**Organization**: tasks are grouped by user story (US1 = P1 per-file
content rules, US2 = P2 cross-environment parity).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Create `engine/src/radic_delivery/deploy/{__init__.py, rules.py,
      parity.py, linter.py, result.py}` as empty module skeletons
- [x] T002 [P] Create `engine/tests/fixtures/sample-repos/python-sample/deploy/run/`
      directory and `engine/tests/fixtures/sample-repos/python-sample-bad-deploy/`
      directory skeletons

**Checkpoint**: `uv run python -c "import radic_delivery.deploy"` succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the `ManifestCheck`/`DeployLintResult` shape and the clean
deploy-manifest fixture every story extends.

- [x] T003 Write `engine/src/radic_delivery/deploy/result.py`:
      `ManifestCheck`, `DeployLintResult` dataclasses per data-model.md,
      with `overall` computed as "pass only if every check is pass or
      not_applicable" and JSON serialisation (`to_dict`)
- [x] T004 Write `engine/tests/fixtures/sample-repos/python-sample/deploy/skaffold.yaml`
      (per Reference 1's template: `apiVersion: skaffold/v4beta9`, one
      `profiles[]` entry per env with `manifests.rawYaml: [run/<env>.yaml]`)
      and `.../deploy/run/{dev,stage,prod}.yaml` — three clean, valid
      Cloud Run Service manifests (`apiVersion: serving.knative.dev/v1`)
      satisfying every rule in research.md: `image: app`, no `traffic` key,
      a `startupProbe`, no inline secret (env vars use `secretKeyRef`),
      and dev/stage/prod identical except for a `metadata.name` difference
      already covered by `python-sample`'s `service_name` parity.allow
      entry (research.md D3) — update that fixture's `.radic/service.yml`
      cloud_deploy deployable to declare `service_yaml: {dev: deploy/run/dev.yaml,
      stage: deploy/run/stage.yaml, prod: deploy/run/prod.yaml}` and
      `parity.allow: [service_name]` if not already present
- [x] T005 Manually run `gitleaks detect --source
      tests/fixtures/sample-repos/python-sample/deploy/run/dev.yaml --no-git
      --report-format json --report-path - --exit-code 0` against each new
      clean manifest file to confirm none of them trip the secret scanner
      before any engine code depends on them being clean (research.md D2)

**Checkpoint**: the clean deploy-manifest fixture is real, schema-
referenced from its descriptor, and independently confirmed secret-free;
`ManifestCheck`/`DeployLintResult` types exist and are importable

---

## Phase 3: User Story 1 - A manifest mistake is caught before it ever reaches a real deploy (P1) 🎯 MVP

**Goal**: `radic-delivery deploy lint` fully implemented for the four
per-file content rules (image placeholder, no traffic key, startup probe,
no inline secret).

**Independent Test**: run against the clean fixture (pass) and four
single-rule-violation variants (each fails for exactly its one seeded
reason).

### Tests for User Story 1

- [x] T006 [P] [US1] Unit test in `engine/tests/unit/test_deploy_rules.py`:
      a manifest dict with `image: app` passes the image-placeholder rule;
      one with a real image reference fails it, naming the rule
      (Acceptance Scenario 2)
- [x] T007 [P] [US1] Unit test (same file): a manifest dict with a
      `spec.traffic` key fails the no-traffic-key rule (Acceptance
      Scenario 3); one without it passes
- [x] T008 [P] [US1] Unit test (same file): a manifest dict with a
      `startupProbe` under its container passes; one without it fails
      (Acceptance Scenario 4)
- [x] T009 [P] [US1] Unit test in `engine/tests/unit/test_deploy_linter.py`:
      using the real `gitleaks` binary (same precedent as specs/003), a
      manifest file containing a planted fake secret in an `env[].value`
      fails the no-inline-secret rule (Acceptance Scenario 5); a clean one
      passes
- [x] T010 [P] [US1] Unit test (same file): a descriptor-declared manifest
      path that does not exist on disk produces `status ==
      "missing_file"`, distinct from `"fail"` (Edge Case: missing file)
- [x] T011 [P] [US1] Unit test (same file): a manifest file that is not
      valid YAML produces `status == "parse_error"`, distinct from both
      `"fail"` and `"missing_file"` (Edge Case: invalid YAML)
- [x] T012 [P] [US1] Unit test (same file): a descriptor declaring two
      deployables has both deployables' manifests checked, not just the
      first (Edge Case: multiple deployables)
- [x] T013 [P] [US1] Unit test in `engine/tests/unit/test_deploy_cli.py`:
      `deploy lint` against the clean fixture exits `0`; against an invalid
      descriptor exits `2` (FR-002); `--format json`/`--format text` report
      the same facts (FR-012)

### Implementation for User Story 1

- [x] T014 [US1] Implement `engine/src/radic_delivery/deploy/rules.py`:
      pure `check_image_placeholder`, `check_no_traffic_key`,
      `check_startup_probe`, each `(manifest: dict) -> ManifestCheck`
      (research.md D1 for the `spec.traffic` path) — satisfies FR-004,
      FR-005, FR-006
- [x] T015 [US1] Implement the no-inline-secret rule in
      `engine/src/radic_delivery/deploy/linter.py`: run `gitleaks` against
      the manifest file path via `security/runner.py` (reused, not
      duplicated — research.md D2), translate a hit into a failing
      `ManifestCheck` via `security/parsers.py::parse_gitleaks` — satisfies
      FR-007
- [x] T016 [US1] Implement `engine/src/radic_delivery/deploy/linter.py`'s
      main orchestration: for each deployable in
      `descriptor["cloud_deploy"]["deployables"]` with a `service_yaml`,
      for each of dev/stage/prod, load the file (producing
      `missing_file`/`parse_error` statuses per Edge Cases), run T014's
      three rules plus T015's secret rule, collecting `ManifestCheck`s; a
      deployable with no `service_yaml` (job-only) produces a single
      `not_applicable` check (research.md D4) — satisfies FR-003, FR-009,
      FR-010, FR-011
- [x] T017 [US1] Wire `deploy lint` in `cli.py` as a new command group
      (there is no pre-existing stub to replace): calls feature 001's
      `validate_descriptor` first and fails fast with
      `ExitCode.INVALID_INPUT` if invalid; otherwise calls
      `linter.lint` and maps `DeployLintResult.overall` to `ExitCode.OK`
      (pass) / `ExitCode.INVALID_INPUT` (fail — a bad manifest is invalid
      input to a deploy that must not happen, not a policy threshold) —
      both `--format json`/`--format text` (FR-012)
- [x] T018 [US1] Write
      `engine/tests/fixtures/sample-repos/python-sample-bad-deploy/` — a
      full copy of `python-sample` (including its clean `deploy/` from
      T004) whose `.radic/service.yml` is used by T013's tests; the
      individual rule-violation variants for T006-T011 are expressed as
      in-memory manifest dicts (pure, no fixture file needed) except T009's
      real-gitleaks test and T013's end-to-end CLI test, which need one
      on-disk variant each — add
      `python-sample-bad-deploy/deploy/run/dev-with-secret.yaml` (a copy of
      `dev.yaml` plus one planted fake secret) for those
- [x] T019 [US1] Run T006-T013 against the implementation; fix until green

**Checkpoint**: User Story 1 fully functional and independently testable —
each of the four content rules is enforced for real against real files.
This alone is a demonstrable MVP.

---

## Phase 4: User Story 2 - Unexplained drift between environments is caught (P2)

**Goal**: the cross-environment parity rule fully implemented per
research.md D3's mapping table.

### Tests for User Story 2

- [x] T020 [P] [US2] Unit test in `engine/tests/unit/test_deploy_parity.py`:
      three manifest dicts differing only in `metadata.name`, with
      `parity.allow: [service_name]`, pass the parity check (Acceptance
      Scenario 1)
- [x] T021 [P] [US2] Unit test (same file): three manifest dicts differing
      in `metadata.name` with an **empty** `parity.allow` fail, naming the
      key and the differing environments (Acceptance Scenario 2, Edge Case:
      nothing declared means nothing may differ)
- [x] T022 [P] [US2] Unit test (same file): manifests whose only difference
      is the **set of `secretKeyRef`-sourced env var names**, with
      `parity.allow: [secret_count]`, pass; the same difference with an
      empty `parity.allow` fails
- [x] T023 [P] [US2] Unit test (same file): manifests differing in a
      **plain (non-secret) env var's name** (one environment has an extra
      config var the others lack) fail regardless of `parity.allow`
      content, since `parity.allow`'s two defined values never cover plain
      config vars (research.md D3)
- [x] T024 [P] [US2] Unit test (same file): manifests differing in
      `serviceAccountName`, `containerConcurrency`, or an autoscaling
      annotation fail regardless of `parity.allow` content (research.md D3's
      "everything else" list)

### Implementation for User Story 2

- [x] T025 [US2] Implement `engine/src/radic_delivery/deploy/parity.py`:
      pure `check_parity(manifests: dict[str, dict], allow: list[str]) ->
      list[ManifestCheck]` per research.md D3's exact mapping table
      (`service_name` → `metadata.name`; `secret_count` → `secretKeyRef`-
      sourced env var name membership only); everything else compared
      exactly, with no exceptions
- [x] T026 [US2] Wire `parity.check_parity` into `linter.py`'s
      orchestration (T016) — one parity check per deployable, after all
      three environment files have been loaded and validated against the
      per-file rules (depends on T016, T025)
- [x] T027 [US2] Run T020-T024 against the implementation; fix until green

**Checkpoint**: both user stories independently functional

---

## Phase 5: Polish & Cross-Cutting Concerns

- [x] T028 Edit `.github/workflows/ci.yml` (specs/002): replace the
      `deploy_lint` output's hardcoded `not_available` value with the real
      result — run `radic-delivery deploy lint --format json`, extract
      `.overall`, set `deploy_lint=<overall>` — alongside (not replacing)
      the existing `gate evaluate` call in the same job (FR-013, SC-004)
- [x] T029 Validate the change with `actionlint .github/workflows/ci.yml`
      and fix any findings; manually run the updated jq/shell logic against
      a real `deploy lint --format json` output first, same discipline as
      specs/002 and specs/003's workflow changes
- [x] T030 [P] Update `engine/README.md`'s command-surface table: move
      `deploy lint` from absent to documented, with its exit-code mapping
      and a note that every other `deploy` subcommand remains unimplemented
- [x] T031 Run `specs/004-deploy-yaml-lint/quickstart.md` end-to-end
      manually and confirm every command shown behaves as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
  (the result shape and the clean fixture are shared by every story)
- **User Stories (Phase 3-4)**: both depend on Foundational; US2 extends
  US1's `linter.py` orchestration (T016), so US1 should land first
- **Polish (Phase 5)**: depends on both stories, since `ci.yml`'s edit
  should reflect the complete lint, not just the per-file rules

### Parallel Opportunities

- T006-T013 in parallel (independent test files/cases)
- T020-T024 in parallel
- T030 can run in parallel with T028/T029 (different files)

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a
demonstrable, independently valuable lint — all four per-manifest content
rules enforced for real — before the cross-environment parity rule (US2)
is layered on. The `ci.yml` wiring (Phase 5) only needs US1's result shape
to exist, but lands last so the PR check reflects the complete lint.
