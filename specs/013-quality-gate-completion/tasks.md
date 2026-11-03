# Tasks: Quality Gate Completion

**Input**: Design documents from `/specs/013-quality-gate-completion/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Builds on**: `engine/src/radic_delivery/gate/{evaluator,commands,parsers,
runner,result}.py` (specs/002, extended in place, not duplicated);
`schemas/test-result.schema.json` (specs/010, read-only — this feature
never rewrites a record, only reads an already-stored one).

**Tests**: included — spec.md's Acceptance Scenarios require specific,
distinguishable outcomes for each command, same discipline as every
prior feature. `release-gate` is tested against this platform's own
existing real fixture repos plus small, hand-written stage test-result
record files; `migrations check` is tested against a new small fixture
directory (sound/forked/cyclical migration chains, an intact/altered
workflow YAML pair) — no git, no database, no external call anywhere.

**Organization**: tasks are grouped by user story (US1 = P1 `gate
evaluate --mode release-gate`, US2 = P2 `migrations check`). The two
stories share no code and have no dependency on each other.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `engine/src/radic_delivery/migrations/{__init__.py,
      result.py, graph.py, frozen.py}` as empty module skeletons

**Checkpoint**: `uv run python -c "import radic_delivery.migrations"`
succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the new result types and fixture files both stories' tests
depend on.

- [X] T002 [P] Extend `engine/src/radic_delivery/gate/result.py`: add
      `"stage_regression"` to the `CheckName` Literal (research.md D1)
- [X] T003 [P] Write `engine/src/radic_delivery/migrations/result.py`:
      `MigrationGraphResult`, `MigrationFreezeResult`,
      `MigrationsCheckResult` dataclasses per data-model.md, each with
      `to_dict()`
- [X] T004 [P] Create `engine/tests/fixtures/migrations/sound/
      {0001_initial.py, 0002_add_table.py, 0003_add_column.py}`: a real,
      minimal Alembic-style linear chain (`revision`/`down_revision`
      literal assignments only, no real migration bodies needed)
- [X] T005 [P] Create `engine/tests/fixtures/migrations/forked/
      {0001_initial.py, 0002a_branch_a.py, 0002b_branch_b.py}`: two files
      both claiming `0001_initial` as their `down_revision`
- [X] T006 [P] Create `engine/tests/fixtures/migrations/cyclical/
      {0001_a.py, 0002_b.py}`: each claiming the other as its
      `down_revision`, no root
- [X] T007 [P] Create `engine/tests/fixtures/migrations/
      deploy-dev-intact.yml` and `deploy-dev-altered.yml`: minimal real
      GitHub Actions workflow YAML, the first with a job named exactly
      `Run Database Migrations`, the second with that job renamed

**Checkpoint**: the three result dataclasses are importable; all eight
new fixture files exist and are valid Python/YAML

---

## Phase 3: User Story 1 - The prod-approval gate reflects the full release picture (P1) 🎯 MVP

**Goal**: `radic-delivery gate evaluate --mode release-gate` fully
implemented — reuses `ci-gate`'s real checks unchanged, adds a real
`stage_regression` check against a local test-result record.

**Independent Test**: evaluate against a real fixture repo with a
matching, passing stage record present (full pass); separately with that
record missing, with the wrong digest, and with a failing/skipped-tests
record, confirming each is named specifically.

### Tests for User Story 1

- [X] T008 [P] [US1] Unit test in `engine/tests/unit/
      test_gate_release_mode.py`: `release-gate` against
      `tests/fixtures/sample-repos/python-sample` with a matching,
      passing, full-scope stage record for the evaluated digest reports
      `overall: "pass"`, including a `stage_regression` check with
      `status: "pass"` (Acceptance Scenario 1)
- [X] T009 [P] [US1] Unit test (same file): the identical setup but with
      no stage record at all for the evaluated digest reports `overall:
      "fail"`, with `stage_regression` named specifically as missing
      (Acceptance Scenario 2)
- [X] T010 [P] [US1] Unit test (same file): a stage record for the exact
      digest that reports `result: "fail"`, and separately one with
      `counts.skipped >= 1`, each reports `stage_regression` as failed,
      naming which condition wasn't met (Acceptance Scenario 3)
- [X] T011 [P] [US1] Unit test (same file): a stage record present for a
      *different* digest than the one being evaluated is treated
      identically to no record existing at all (Acceptance Scenario 4)
- [X] T012 [P] [US1] Unit test (same file): `release-gate`'s reused
      lint/typecheck/unit/coverage/skip_budget checks behave identically
      to `ci-gate`'s own (same fixtures, same results) — confirms no
      duplicated/diverged logic (research.md D1)
- [X] T013 [P] [US1] Unit test in `engine/tests/unit/
      test_quality_gate_completion_cli.py`: `gate evaluate --mode
      release-gate` on a full pass exits `0`; on any failing check
      (including `stage_regression`) exits `3`; on an invalid descriptor
      exits `2`; both `--format json`/`--format text` report every check

### Implementation for User Story 1

- [X] T014 [US1] Implement the `stage_regression` check in
      `engine/src/radic_delivery/gate/evaluator.py`: a new
      `_check_stage_regression(results_dir, digest) -> CheckResult`
      (scans every `*.json` under `results_dir` recursively for a record
      with `environment == "stage"` and `digest == digest`; first match
      wins — research.md D2; passes only when `scope == "full"`,
      `result == "pass"`, `counts.skipped == 0`) — satisfies spec FR-002,
      FR-003 (depends on T002)
- [X] T015 [US1] Remove the `release-gate` `not_implemented`
      short-circuit in `evaluate()`; when `mode == "release-gate"`, run
      the same lint/typecheck/unit/coverage/skip_budget sequence
      `ci-gate` already runs, then append `_check_stage_regression()`'s
      result (T014) to `checks` — satisfies spec FR-001 (depends on T014)
- [X] T016 [US1] Add `--results-dir PATH` and `--digest DIGEST` options to
      `cli.py`'s `gate_evaluate` command (both optional; required in
      practice only for `release-gate` — when `release-gate` is requested
      without them, `_check_stage_regression` reports
      `status: "not_executable"` naming the missing input rather than
      raising) — depends on T015
- [X] T017 [US1] Run T008-T013 against the implementation; fix until green

**Checkpoint**: User Story 1 fully functional — `release-gate` correctly
reuses `ci-gate`'s checks and independently enforces the stage-regression
fact. This alone is a demonstrable MVP. The `gate` command group now has
no stubs left.

---

## Phase 4: User Story 2 - A service's migration setup is checked for safety (P2)

**Goal**: `radic-delivery migrations check` fully implemented —
`migrations_frozen` and `migration_graph` run for real;
`alembic_check`/`schema_check` accepted but always `not_available`.

**Independent Test**: run `migration_graph` against the real sound,
forked, and cyclical fixture directories, confirming each is reported
specifically; run `migrations_frozen` against the intact and altered
workflow fixtures, confirming each is reported specifically.

### Tests for User Story 2

- [X] T018 [P] [US2] Unit test in `engine/tests/unit/
      test_migrations_graph.py`: `tests/fixtures/migrations/sound/`
      reports `sound: true` with the correct `root` (Acceptance Scenario
      1)
- [X] T019 [P] [US2] Unit test (same file): `tests/fixtures/migrations/
      forked/` reports `sound: false` with a `forks` entry naming both
      files (Acceptance Scenario 2)
- [X] T020 [P] [US2] Unit test (same file): `tests/fixtures/migrations/
      cyclical/` reports `sound: false` with a `cycles` entry (Acceptance
      Scenario 3)
- [X] T021 [P] [US2] Unit test (same file): an empty directory reports
      `sound: true`, `root: None` (spec Edge Case)
- [X] T022 [P] [US2] Unit test in `engine/tests/unit/
      test_migrations_frozen.py`: a descriptor naming
      `deploy-dev-intact.yml` reports that file `status: "intact"`
      (Acceptance Scenario, happy path)
- [X] T023 [P] [US2] Unit test (same file): a descriptor naming a
      workflow file that doesn't exist on disk reports that file
      `status: "missing"`, naming it specifically (Acceptance Scenario 4)
- [X] T024 [P] [US2] Unit test (same file): a descriptor naming
      `deploy-dev-altered.yml` reports that file `status: "altered"`,
      naming it specifically (Acceptance Scenario 5)
- [X] T025 [P] [US2] Unit test in `engine/tests/unit/
      test_quality_gate_completion_cli.py`: `migrations check
      --checks alembic_check` (alone) reports `alembic_check:
      "not_available"` and exits `0` — a not-available check is never a
      failure on its own (Acceptance Scenario 6, research.md D3); a
      service with `migrations.enabled: false` reports this plainly and
      exits `0` (spec Edge Case); `migrations_frozen`/`migration_graph`
      failures exit `3`

### Implementation for User Story 2

- [X] T026 [US2] Implement `engine/src/radic_delivery/migrations/
      graph.py`: `check_graph(migrations_dir) -> MigrationGraphResult` —
      parses every `*.py` file's `revision`/`down_revision` literal
      assignments via `ast` (never executes the file), builds the chain,
      detects a missing/multiple root, forks, and cycles — satisfies spec
      FR-004 (depends on T003)
- [X] T027 [US2] Implement `engine/src/radic_delivery/migrations/
      frozen.py`: `check_frozen(descriptor, repo_dir) ->
      MigrationFreezeResult` — for each
      `migrations.frozen_check_workflow_files` path, confirms the file
      exists under `repo_dir` and some job in its parsed YAML has
      `name == migrations.job_name` — satisfies spec FR-005 (depends on
      T003)
- [X] T028 [US2] Wire `migrations check` into `cli.py`, replacing the
      `migrations` stub in `_NOT_IMPLEMENTED_GROUPS` with a real
      `migrations_app` Typer group: `check` subcommand with options
      `--descriptor`, `--repo-dir` (default `.`), `--migrations-dir`
      (optional), `--checks` (comma-separated list), `--format`; when
      `migrations.enabled` is `False`, short-circuits to a plain
      not-enabled report; dispatches `migrations_frozen`/`migration_graph`
      to T026/T027 when requested, and reports `alembic_check`/
      `schema_check` as `"not_available"` when requested, never attempted
      — exit codes per research.md D4 (depends on T026, T027)
- [X] T029 [US2] Run T018-T025 against the implementation; fix until green

**Checkpoint**: both user stories independently functional. The
`migrations` command group now has a real `check` subcommand.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T030 [P] Update `engine/README.md`'s command-surface table: move
      `gate evaluate --mode release-gate` to documented, add
      `migrations check` to documented (noting `alembic_check`/
      `schema_check` as accepted-but-not-available), and update the
      implemented/pending command counts this README currently states —
      note that after this feature, only the six `deploy` subcommands
      remain unimplemented
- [X] T031 Run `uv run pytest -q`, `uv run ruff check .`, and
      `uv run mypy src/` from `engine/`; fix until clean
- [X] T032 Run `specs/013-quality-gate-completion/quickstart.md`
      end-to-end manually and confirm every command shown behaves as
      documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS both user
  stories (T002 blocks US1's new check; T003-T007 block US2's
  implementation and fixtures)
- **User Stories (Phase 3-4)**: both depend on Foundational only; US1 and
  US2 are fully independent of each other (no shared code, no shared
  fixture, `gate/` vs `migrations/`) — sequenced P1 → P2 here, but could
  be built in either order or in parallel
- **Polish (Phase 5)**: depends on both stories

### Parallel Opportunities

- T002-T007 in parallel (two independent groups: `gate/result.py` +
  `migrations/result.py`, and the five fixture-file tasks)
- T008-T013 in parallel; T018-T025 in parallel
- Once Foundational (Phase 2) completes, US1's and US2's entire phases
  could proceed in parallel if staffed — neither shares a file with the
  other except `cli.py` (T016, T028) and
  `test_quality_gate_completion_cli.py` (T013, T025), both of which touch
  disjoint sections

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a
demonstrable, independently valuable capability — `release-gate`
correctly enforcing the stage-regression fact on top of `ci-gate`'s
already-real checks — before `migrations check` (US2) is built. Given
this is the third bundled feature, both stories are still built in the
same implementation pass (per the user's "club features" instruction),
but each remains independently testable and independently revertible if
one needed to be pulled back out. Completing this feature closes out the
entire `gate`/quality-check command family — only the six GCP-calling
`deploy` subcommands remain unimplemented in the backlog afterward.
