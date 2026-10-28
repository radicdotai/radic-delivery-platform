# Tasks: Central CI Reusable Workflow (`ci-gate` mode)

**Input**: Design documents from `/specs/002-ci-gate-workflow/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md
**Builds on**: specs/001-engine-scaffold (already implemented) — `descriptor
validate`, `policy/exceptions.py`'s `check()`, `paths.py`, `exit_codes.py`

**Tests**: included — spec.md's Acceptance Scenarios require specific,
distinguishable failure modes per check, so tests are in scope for every
story, same as feature 001.

**Organization**: tasks are grouped by user story (US1 = P1 pass/fail gate,
US2 = P2 coverage floor, US3 = P3 skip-budget) so each is independently
implementable and testable. `GateResult`'s shape (data-model.md) is fixed in
Foundational; each story then adds the `CheckResult`(s) it owns.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Create `engine/src/radic_delivery/gate/{__init__.py, commands.py,
      runner.py, parsers.py, evaluator.py, result.py}` as empty module
      skeletons
- [x] T002 [P] Create
      `engine/tests/fixtures/sample-repos/python-sample/{.radic,src/sample,tests}`
      and `.../python-sample-broken/{.radic,src/sample,tests}` directory
      skeletons

**Checkpoint**: `uv run python -c "import radic_delivery.gate"` succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the `GateResult` shape and the sample-repo fixture every story
extends.

- [x] T003 Write `engine/src/radic_delivery/gate/result.py`:
      `CheckResult`, `CoverageResult`, `TestRunResult`, `GateResult`
      dataclasses per data-model.md, with `GateResult.overall` computed as
      "pass only if every CheckResult is pass" and JSON serialisation (`to_dict`)
      — satisfies data-model.md's GateResult entity
- [x] T004 Write `engine/tests/fixtures/sample-repos/python-sample/pyproject.toml`
      (uv-managed, `ruff`+`mypy`+`pytest`+`pytest-cov` as dependencies),
      `src/sample/__init__.py` (one small, clean function), and
      `tests/test_sample.py` (tests it, 100% coverage, no skips) — a real
      project that passes lint, typecheck, unit tests, and coverage
- [x] T005 Write `engine/tests/fixtures/sample-repos/python-sample/.radic/service.yml`
      — a minimal, schema-valid descriptor (feature 001's
      `schemas/service.schema.json`) declaring `runtime.template: python-uv`,
      `quality.lint.tool: ruff`, `quality.typecheck.tool: mypy`,
      `quality.unit.runner: pytest`, and a `coverage_floor.global` the
      fixture is written to meet
- [x] T006 `uv sync` inside
      `engine/tests/fixtures/sample-repos/python-sample/` and confirm
      `uv run ruff check . && uv run mypy . && uv run pytest --cov -q` all
      pass manually, before any engine code depends on it

**Checkpoint**: the sample-repo fixture is a real, independently-verified
passing project; `GateResult`/`CheckResult` types exist and are importable

---

## Phase 3: User Story 1 - A failing change is blocked automatically (P1) 🎯 MVP

**Goal**: `radic-delivery gate evaluate --mode ci-gate` fully implemented for
the lint/typecheck/unit-test pass-fail decision, for both toolchains'
command construction, with `release-gate` and `run_mutation` visibly
deferred.

**Independent Test**: run against `python-sample` (all pass) and three
variants of `python-sample-broken` (lint-only, type-only, test-only
failure), confirming each fails for the right named reason; confirm Node
command construction is correct without executing it.

### Tests for User Story 1

- [x] T007 [P] [US1] Unit test in `engine/tests/unit/test_gate_commands.py`:
      for a python-uv descriptor, `commands.py` constructs the exact
      `ruff`/`mypy`/`pytest` argv from research.md's D1 table (Acceptance
      Scenario 5 half)
- [x] T008 [P] [US1] Unit test (same file): for a node descriptor (with and
      without `marker_expr`/`script` set), `commands.py` constructs the exact
      `eslint`/`tsc`/`vitest` argv from research.md's D1 table, including the
      `npm run <script>` branch — no real `npm`/`node` toolchain is invoked
      by this test (Acceptance Scenario 5 other half)
- [x] T009 [P] [US1] Unit test in `engine/tests/unit/test_gate_parsers.py`:
      `TestRunResult` parsing against captured sample `pytest` summary lines
      (`"3 passed in 0.01s"`, `"2 passed, 1 failed in 0.02s"`) — pass/failed
      counts only in this story, skipped count added in US3's tests
- [x] T010 [P] [US1] Unit test in `engine/tests/unit/test_gate_evaluator.py`:
      using a fake/injected runner (no real subprocess), confirm one failing
      check (lint, or typecheck, or unit) alone makes `GateResult.overall ==
      "fail"` and names that check (Acceptance Scenarios 2, 3, 4)
- [x] T011 [P] [US1] Unit test (same file): a declared tool that cannot be
      found/executed at all (e.g. `FileNotFoundError` from the fake runner)
      produces `CheckResult.status == "not_executable"`, distinct from
      `"fail"` (Edge Case: missing toolchain)
- [x] T012 [P] [US1] Unit test (same file): `mode: release-gate` produces
      `GateResult.overall == "not_implemented"` without running any check;
      `run_mutation: true` is accepted and reported as
      `mutation.status == "not_implemented"` without affecting `overall`
      (FR-011, FR-012, Edge Cases)
- [x] T013 [P] [US1] Unit test in `engine/tests/unit/test_gate_cli.py` (via
      `typer.testing.CliRunner`, same pattern as feature 001's
      `test_cli.py`): `gate evaluate` against `python-sample` exits `0`; against
      a broken variant exits `2`; `--format json` and `--format text` report
      the same facts (FR-014)

### Implementation for User Story 1

- [x] T014 [US1] Implement `engine/src/radic_delivery/gate/commands.py`:
      pure `build_commands(descriptor: dict) -> list[ToolInvocation]` per
      research.md's D1 table, covering both `runtime.template` values and
      the `marker_expr`/`script` branches
- [x] T015 [US1] Implement `engine/src/radic_delivery/gate/runner.py`:
      `run(invocation: ToolInvocation) -> RunOutcome` (captures exit code,
      stdout, stderr; converts a launch failure, e.g. the executable not
      found, into a distinct outcome rather than letting the exception
      propagate) — satisfies the Edge Case in T011
- [x] T016 [US1] Implement `engine/src/radic_delivery/gate/parsers.py`
      (partial, this story): `parse_test_run(runner: str, stdout: str) ->
      TestRunResult` for `pytest`'s summary line (passed/failed counts;
      skipped count field present but not yet enforced)
- [x] T017 [US1] Implement `engine/src/radic_delivery/gate/evaluator.py`:
      `evaluate(descriptor, mode, run_mutation, runner=run) ->
      GateResult` — for `mode == "ci-gate"`: build commands (T014), execute
      each (T015), classify lint/typecheck as pass/fail/not_executable
      directly from exit code, classify unit via T016's parser; for `mode ==
      "release-gate"`: return `overall="not_implemented"` immediately
      without running anything; always set `mutation`, `deploy_lint`,
      `test_inventory_uri` to their fixed not-implemented/not-available
      markers (FR-011 through FR-013) — depends on T014, T015, T016
- [x] T018 [US1] Wire `gate evaluate` in `cli.py`, replacing the
      feature-001 `gate` stub: calls feature 001's `validate_descriptor`
      first (FR-002) and fails fast with `ExitCode.INVALID_INPUT` if invalid;
      otherwise calls `evaluator.evaluate` and maps `GateResult.overall` to
      `ExitCode.OK` (pass) / `ExitCode.POLICY_FAILURE` (fail — a quality
      gate rejection is a policy failure, distinct from the malformed-input
      case already handled above) / `NOT_IMPLEMENTED_EXIT_CODE` (same code
      every other stub command group uses, for `release-gate`) — both
      `--format json`/`--format text` (FR-014)
- [x] T019 [US1] Write 3 broken sample-repo variants:
      `engine/tests/fixtures/sample-repos/python-sample-broken-lint/`,
      `.../python-sample-broken-type/`, `.../python-sample-broken-test/` —
      each a copy of `python-sample` with exactly one seeded failure, for a
      real, fully-executed end-to-end check (not just the fake-runner unit
      tests in T010-T012)
- [x] T020 [US1] Add 3 end-to-end tests in `test_gate_cli.py` running the
      real CLI (real subprocess, real `ruff`/`mypy`/`pytest`) against each
      T019 fixture, confirming the gate fails for exactly the seeded reason
      — the one place this story exercises a real toolchain, per research.md's
      test-strategy note
- [x] T021 [US1] Run T007-T013 and T020 against the implementation; fix
      until green

**Checkpoint**: User Story 1 fully functional and independently testable —
`gate evaluate --mode ci-gate` correctly passes/fails a real Python project
on lint/typecheck/unit-test grounds, with Node command construction verified
and `release-gate`/`run_mutation` visibly deferred. This alone is a
demonstrable MVP.

---

## Phase 4: User Story 2 - Coverage regressions are caught (P2)

**Goal**: the gate also enforces the descriptor's coverage floor.

### Tests for User Story 2

- [x] T022 [P] [US2] Unit test in `test_gate_parsers.py`: `parse_coverage`
      against a captured `pytest-cov` terminal summary (`TOTAL ... 87%`)
      returns `CoverageResult(global=87.0)`; against a captured `vitest
      --coverage` summary table returns the four-figure
      `CoverageResult(statements=.., branches=.., functions=.., lines=..)`
      shape — matching whichever shape the descriptor declares
      (data-model.md's CoverageResult)
- [x] T023 [P] [US2] Unit test in `test_gate_evaluator.py`: with a fake
      runner returning below-floor coverage output, `GateResult.overall ==
      "fail"` and the `coverage` `CheckResult` names the measured percentage
      and the floor (Acceptance Scenario 1); with at-or-above-floor coverage
      and all other checks passing, `overall == "pass"` (Acceptance Scenario 2)
- [x] T024 [P] [US2] Unit test (same file): the measured coverage
      percentage(s) appear in `GateResult` whether the gate passes or fails
      (FR-007)

### Implementation for User Story 2

- [x] T025 [US2] Implement `parse_coverage` in `gate/parsers.py` (the
      coverage half of research.md's D2) for both the `pytest-cov` and
      `vitest --coverage` summary formats
- [x] T026 [US2] Extend `gate/evaluator.py` to add a `coverage` `CheckResult`:
      run `parse_coverage` on the unit-test step's captured output, compare
      against `descriptor["quality"]["coverage_floor"]` in whichever shape
      is present (`global` vs. four-figure), and fail the gate if below —
      independent of whether the unit tests themselves passed (depends on T017, T025)
- [x] T027 [US2] Write
      `engine/tests/fixtures/sample-repos/python-sample-broken-coverage/` —
      a copy of `python-sample` whose tests all pass but whose descriptor's
      coverage floor is set above the project's actual (deliberately
      incomplete) coverage
- [x] T028 [US2] Add an end-to-end test in `test_gate_cli.py` running the
      real CLI against T027's fixture, confirming the gate fails on coverage
      alone with all tests green
- [x] T029 [US2] Run T022-T024 and T028 against the implementation; fix
      until green

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Phase 5: User Story 3 - A silently skipped test cannot slip through (P3)

**Goal**: the gate enforces the zero-skip-budget rule, consulting feature
001's policy-exception ledger.

### Tests for User Story 3

- [x] T030 [P] [US3] Unit test in `test_gate_parsers.py`: `parse_test_run`
      against a `pytest` summary line including a skip count (`"2 passed, 1
      skipped in 0.01s"`) reports `skipped == 1`
- [x] T031 [P] [US3] Unit test in `test_gate_evaluator.py`: with a fake
      runner reporting 1 skipped test and no matching exception in a fake
      exceptions ledger, `GateResult.overall == "fail"` and the
      `skip_budget` `CheckResult` reports the count (Acceptance Scenario 1)
- [x] T032 [P] [US3] Unit test (same file): with 1 skipped test and an
      active, unexpired exception with `scope: quality.unit.skip` for the
      descriptor's `service.name` in the fake ledger, the `skip_budget`
      check does not by itself fail the gate (Acceptance Scenario 2)
- [x] T033 [P] [US3] Unit test (same file): the skipped-test count appears
      in `GateResult` whether the gate passes or fails (FR-009)

### Implementation for User Story 3

- [x] T034 [US3] Extend `gate/evaluator.py` to add a `skip_budget`
      `CheckResult`: when the unit-test step's `TestRunResult.skipped > 0`,
      call feature 001's `radic_delivery.policy.exceptions.check()` for an
      exception matching `scope == "quality.unit.skip"` and
      `owner == descriptor["service"]["name"]` (data-model.md's documented
      convention); fail unless that exception is `"active"` (depends on T017, T016)
- [x] T035 [US3] Write
      `engine/tests/fixtures/sample-repos/python-sample-broken-skip/` — a
      copy of `python-sample` with one test marked `@pytest.mark.skip`
      and no covering exception
- [x] T036 [US3] Add an end-to-end test in `test_gate_cli.py` running the
      real CLI against T035's fixture, confirming the gate fails on
      skip-budget alone with lint/typecheck/coverage all green
- [x] T037 [US3] Run T030-T033 and T036 against the implementation; fix
      until green

**Checkpoint**: all three user stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T038 [P] Write `actions/setup-engine/action.yml` (composite action):
      checkout `radicdotai/delivery-platform` at `${{ github.action_ref }}`
      into `.platform-engine/`, install `uv` (`astral-sh/setup-uv`), `uv
      sync --project .platform-engine/engine` — per research.md's D3
- [x] T039 [P] Write `.github/workflows/ci.yml` (the reusable workflow):
      `workflow_call` inputs `mode` (default `ci-gate`), `run_mutation`
      (default `false`), `descriptor` (default `.radic/service.yml`);
      outputs `gate_result`, `coverage_total`, `skipped_count` read from
      `gate evaluate --format json`'s output, plus `test_inventory_uri` and
      `deploy_lint` passed through as fixed not-available markers (FR-013);
      steps: default checkout (the calling service repo), `./actions/
      setup-engine` (local-path reference, resolves per research.md D3),
      install the service's own toolchain per its descriptor's
      `runtime.template` (`uv sync` or `npm ci`), run `uv run --project
      .platform-engine/engine radic-delivery gate evaluate`, fail the job
      when `gate_result != "pass"` (FR-015)
- [x] T040 [P] Write `templates/callers/ci.yml` — the example thin caller: a
      `pull_request` trigger into `dev`, one job `uses:
      radicdotai/delivery-platform/.github/workflows/ci.yml@v1.0.0` with
      `mode: ci-gate`, documented as an example only (SC-005, FR-016)
- [x] T041 Validate the three new YAML files with `actionlint
      .github/workflows/ci.yml actions/setup-engine/action.yml
      templates/callers/ci.yml` and fix any findings
- [x] T042 [P] Update `engine/README.md`'s command-surface table: move `gate`
      from "not implemented yet" to documented, with its `--mode` values and
      exit-code mapping
- [x] T043 Run `specs/002-ci-gate-workflow/quickstart.md` end-to-end
      manually and confirm every command shown behaves as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
  (`GateResult`/`CheckResult` shape and the base sample-repo fixture are
  shared by every story)
- **User Stories (Phase 3-5)**: all depend on Foundational; US2 and US3 both
  depend on US1's `evaluator.py` (T017) and `parsers.py` (T016) existing to
  extend, so in practice US1 should land first even though US2/US3 do not
  depend on each other and could be staffed in parallel once US1's
  `evaluator.py` exists
- **Polish (Phase 6)**: the GitHub Actions artifacts (T038-T040) only need
  `gate evaluate` to exist and produce the right JSON shape (end of US1 is
  sufficient; they do not strictly need US2/US3), but should land after all
  three stories so `ci.yml`'s documentation accurately describes the full
  gate

### Parallel Opportunities

- T007-T013 in parallel (independent test files/cases); T019's three broken
  fixtures in parallel with each other
- T022-T024 in parallel; T030-T033 in parallel
- T038, T039, T040, T042 in parallel (different files) once US1 is done
- US2 (Phase 4) and US3 (Phase 5) can be staffed in parallel once US1's
  `evaluator.py`/`parsers.py` exist, since they extend different
  `CheckResult` kinds and touch different fixture directories

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a demonstrable,
independently valuable gate — real lint/typecheck/unit-test pass-fail
enforcement for a Python sample project, with Node command construction
verified — before coverage or skip-budget enforcement exist. The GitHub
Actions artifacts (T038-T040) can follow immediately after US1 if the
program wants the reusable workflow wired up before coverage/skip-budget
land, since `gate evaluate`'s JSON shape (data-model.md) is already stable
at that point.
