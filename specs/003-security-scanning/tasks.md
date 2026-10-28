# Tasks: Central Security Scanning Workflow (report-only)

**Input**: Design documents from `/specs/003-security-scanning/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md
**Builds on**: specs/001-engine-scaffold (`descriptor validate`), specs/002-ci-gate-workflow
(`gate/commands.py`/`gate/runner.py`'s shape, `actions/setup-engine`, `templates/callers/ci.yml`)

**Tests**: included — spec.md's Acceptance Scenarios require specific,
distinguishable outcomes per scope/finding, same as features 001 and 002.

**Organization**: tasks are grouped by user story (US1 = P1 visibility
without blocking, US2 = P2 severity counts, US3 = P3 honest deferral of
image/Snyk).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Create `engine/src/radic_delivery/security/{__init__.py, tools.py,
      runner.py, parsers.py, aggregator.py, result.py}` as empty module
      skeletons
- [x] T002 [P] Create
      `engine/tests/fixtures/sample-repos/python-sample-secret/` and
      `.../python-sample-bad-dockerfile/` directory skeletons (copy
      `python-sample`'s structure from specs/002)

**Checkpoint**: `uv run python -c "import radic_delivery.security"` succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the `SecurityScanResult`/`Finding` shape and the two new
sample-repo fixtures every story extends.

- [x] T003 Write `engine/src/radic_delivery/security/result.py`:
      `Finding`, `ScopeResult`, `SecurityScanResult` dataclasses per
      data-model.md, with JSON serialisation (`to_dict`) — `scan_result`
      hardcoded to `"completed"` (FR-006, research.md D4)
- [x] T004 Write
      `engine/tests/fixtures/sample-repos/python-sample-secret/` as a full
      copy of specs/002's `python-sample` fixture, plus one planted,
      obviously-fake secret (e.g. a fake AWS-shaped key) in a new,
      otherwise-unused source file so it doesn't affect `python-sample`'s
      own lint/typecheck/test/coverage behaviour — satisfies FR-002,
      Acceptance Scenario 1
- [x] T005 Write
      `engine/tests/fixtures/sample-repos/python-sample-bad-dockerfile/` as
      a full copy of `python-sample`, plus a `Dockerfile` at the repo root
      (referenced by its `.radic/service.yml`'s `build.dockerfile`) seeded
      with at least one hadolint-flagged issue and one trivy-config-flagged
      issue (e.g. `USER root`) — satisfies FR-003, Acceptance Scenario 2
- [x] T006 Run `gitleaks detect --source
      tests/fixtures/sample-repos/python-sample-secret --no-git
      --report-format json --exit-code 0`, `hadolint --format json
      tests/fixtures/sample-repos/python-sample-bad-dockerfile/Dockerfile`,
      and `trivy config --format json
      tests/fixtures/sample-repos/python-sample-bad-dockerfile` manually to
      confirm each fixture actually trips its intended tool before any
      engine code depends on it (research.md D1)

**Checkpoint**: both new fixtures exist and are independently confirmed (by
hand, with the real tools) to trip exactly the finding they were seeded for

---

## Phase 3: User Story 1 - See what a change exposes, without being blocked by it yet (P1) 🎯 MVP

**Goal**: `radic-delivery security scan --scope source|iac|all` fully
implemented for gitleaks + hadolint + trivy config, never failing on
findings.

**Independent Test**: run against the secret fixture (finding, no failure),
the bad-Dockerfile fixture (finding, no failure), and the clean
`python-sample` fixture (zero findings, no failure).

### Tests for User Story 1

- [x] T007 [P] [US1] Unit test in `engine/tests/unit/test_security_tools.py`:
      `scope=source` selects only gitleaks; `scope=iac` selects
      hadolint+trivy-config only when the descriptor declares a Dockerfile;
      `scope=all` selects all three; `scope=iac` against a descriptor
      without a Dockerfile selects none and marks `iac` `not_applicable`
      (Edge Case: no Dockerfile declared)
- [x] T008 [P] [US1] Unit test in `engine/tests/unit/test_security_parsers.py`:
      parse a captured gitleaks JSON array (research.md D1) into
      `Finding`s, each `severity == "critical"` (research.md D2), and
      confirm the `Secret` field's raw value never appears in any
      `Finding.description` (data-model.md's Security note)
- [x] T009 [P] [US1] Unit test (same file): parse a captured hadolint JSON
      array into `Finding`s with the error/warning/info/style → high/medium/
      low/low mapping (research.md D2)
- [x] T010 [P] [US1] Unit test (same file): parse a captured trivy-config
      JSON `Results[].Misconfigurations[]` array into `Finding`s with the
      CRITICAL/HIGH/MEDIUM/LOW/UNKNOWN → critical/high/medium/low/low
      mapping (research.md D2)
- [x] T011 [P] [US1] Unit test in `engine/tests/unit/test_security_aggregator.py`:
      using a fake/injected runner (no real subprocess), a finding at any
      severity (including critical) never changes `scan_result` away from
      `"completed"` (FR-006, Acceptance Scenario 1 and 2 "does not fail")
- [x] T012 [P] [US1] Unit test (same file): zero findings across every
      requested scope reports zero counts at every severity, not an error
      or a missing field (Acceptance Scenario 3)
- [x] T013 [P] [US1] Unit test (same file): a tool that cannot be launched
      at all (e.g. `FileNotFoundError` from the fake runner) produces that
      scope's `ScopeResult.status == "not_executable"`, distinct from
      `"checked"` with zero findings (Edge Case: tool cannot run)

### Implementation for User Story 1

- [x] T014 [US1] Implement `engine/src/radic_delivery/security/tools.py`:
      `select_tools(descriptor, scope) -> list[ToolInvocation]` plus
      `applicable_scopes(descriptor, requested_scopes) -> dict[str, bool]`
      per research.md D3
- [x] T015 [US1] Implement `engine/src/radic_delivery/security/runner.py`:
      reuses `gate/runner.py`'s `RunOutcome` shape (launched/exit_code/
      stdout/stderr); gitleaks/hadolint invoked with stdout captured as
      their JSON report; trivy invoked with stdout and stderr captured
      **separately** (research.md D1 — merging breaks JSON parsing)
- [x] T016 [US1] Implement `engine/src/radic_delivery/security/parsers.py`:
      `parse_gitleaks`, `parse_hadolint`, `parse_trivy_config`, each
      `RunOutcome -> list[Finding]` per research.md D1/D2 — satisfies
      FR-002, FR-003, FR-005
- [x] T017 [US1] Implement `engine/src/radic_delivery/security/aggregator.py`:
      `scan(descriptor, scopes, run_fn=runner.run) -> SecurityScanResult`
      — builds `ScopeResult`s via T014/T015/T016, classifies
      `not_applicable`/`not_executable`/`checked` per scope, aggregates
      `counts`, always sets `scan_result="completed"` (depends on T014,
      T015, T016)
- [x] T018 [US1] Wire `security scan` in `cli.py` as a new command group
      (there is no pre-existing stub to replace, unlike `gate` in specs/002):
      calls feature 001's `validate_descriptor` first and fails fast with
      `ExitCode.INVALID_INPUT` if invalid; otherwise calls
      `aggregator.scan` and **always** exits `ExitCode.OK` afterward
      (FR-006) — both `--format json`/`--format text` (FR-012)
- [x] T019 [US1] Add 3 end-to-end tests in
      `engine/tests/unit/test_security_cli.py` running the real CLI (real
      `gitleaks`/`hadolint`/`trivy` subprocess calls) against the secret
      fixture, the bad-Dockerfile fixture, and clean `python-sample`,
      confirming findings land where expected and the command always exits
      `0`
- [x] T020 [US1] Run T007-T013 and T019 against the implementation; fix
      until green

**Checkpoint**: User Story 1 fully functional and independently testable —
secrets and Dockerfile misconfigurations are detected and reported, nothing
ever fails. This alone is a demonstrable MVP.

---

## Phase 4: User Story 2 - Severity counts for planning the blocking rollout (P2)

**Goal**: aggregate severity counts are correct and always present.

### Tests for User Story 2

- [x] T021 [P] [US2] Unit test in `test_security_aggregator.py`: a scan with
      a fake runner producing a known mix of gitleaks/hadolint/trivy
      findings reports exact counts per severity (Acceptance Scenario 1)
- [x] T022 [P] [US2] Unit test (same file): a scan with zero findings
      reports `{"critical": 0, "high": 0, "medium": 0, "low": 0}`, not
      missing or null fields (Acceptance Scenario 2)

### Implementation for User Story 2

- [x] T023 [US2] Confirm (or extend) `aggregator.py`'s count aggregation
      covers every severity across every `checked` scope — this is
      largely exercised already by T017; this task's job is specifically
      the all-scopes-combined count correctness T021/T022 require
- [x] T024 [US2] Run T021-T022 against the implementation; fix until green

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Phase 5: User Story 3 - Deferred capabilities are visible, not silently missing (P3)

**Goal**: image scanning and Snyk always appear in the report as
not-yet-available.

### Tests for User Story 3

- [x] T025 [P] [US3] Unit test in `test_security_aggregator.py`: every
      `SecurityScanResult` includes an `image` `ScopeResult` with
      `status == "not_available"` regardless of which scopes were
      requested (Acceptance Scenario 1)
- [x] T026 [P] [US3] Unit test (same file): every `SecurityScanResult`'s
      `snyk_status == {"status": "not_available"}` (Acceptance Scenario 2)

### Implementation for User Story 3

- [x] T027 [US3] Extend `aggregator.py` to always append the fixed `image`
      `not_available` `ScopeResult` and the fixed `snyk_status` marker to
      every result, independent of requested scopes (depends on T017)
- [x] T028 [US3] Run T025-T026 against the implementation; fix until green

**Checkpoint**: all three user stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T029 [P] Write `actions/setup-security-tools/action.yml` (composite
      action): installs `gitleaks`, `hadolint`, and `trivy` on the runner
      (pinned versions, per this platform's existing pinning convention for
      third-party tools)
- [x] T030 [P] Write `.github/workflows/security.yml` (the reusable
      workflow): `workflow_call` inputs `scope` (default `all`),
      `image_ref` (accepted, unused — `image` scope is not implemented),
      `enforce`/`fail_on` (accepted, unused — this feature never fails,
      FR-006); outputs `scan_result`, `sbom_uri` (fixed `not_available`),
      `findings_critical`, `findings_high`; steps: default checkout (the
      calling service repo), `./actions/setup-engine` (reused from
      specs/002), `./actions/setup-security-tools`, run `security scan
      --format json`, write a Markdown findings table to
      `$GITHUB_STEP_SUMMARY` (research.md D5, FR-011/SC-003), set outputs
      from the JSON — the job step never ends in a non-zero exit because of
      findings (FR-006)
- [x] T031 [P] Edit `templates/callers/ci.yml` to add a second job,
      `security`, calling `.github/workflows/security.yml@v1.0.0` alongside
      the existing `ci-gate` job, both triggered by the same `pull_request`
      event (no ninth caller file — Reference 2's 8-caller-file count stays
      accurate)
- [x] T032 Validate the new/changed YAML with `actionlint
      .github/workflows/security.yml templates/callers/ci.yml` and fix any
      findings; confirm `actions/setup-security-tools/action.yml` is valid
      YAML with the composite-action shape (same check as specs/002's
      `setup-engine`, since `actionlint` does not lint composite actions)
- [x] T033 [P] Update `engine/README.md`'s command-surface table: add
      `security scan`, documenting that it always exits `0` after a
      descriptor passes validation, regardless of findings
- [x] T034 Run `specs/003-security-scanning/quickstart.md` end-to-end
      manually and confirm every command shown behaves as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
  (the result shape and the two new fixtures are shared by every story)
- **User Stories (Phase 3-5)**: all depend on Foundational; US2 and US3 both
  extend US1's `aggregator.py` (T017), so in practice US1 should land first
- **Polish (Phase 6)**: the GitHub Actions artifacts (T029-T031) only need
  `security scan`'s JSON shape to be stable (end of US1 is sufficient), but
  should land after all three stories so `security.yml`'s job summary
  accurately reflects the full report

### Parallel Opportunities

- T007-T013 in parallel (independent test files/cases)
- T021-T022 in parallel; T025-T026 in parallel
- T029, T030, T031, T033 in parallel (different files) once US1 is done

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a
demonstrable, independently valuable scan — real secret and Dockerfile
misconfiguration detection against real fixtures, never blocking — before
severity-count aggregation (US2) or the image/Snyk honesty markers (US3)
are layered on. US2 and US3 are both small, additive extensions of the
same `aggregator.py` and can be staffed in parallel once US1 lands.
