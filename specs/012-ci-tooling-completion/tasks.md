# Tasks: CI Tooling Completion

**Input**: Design documents from `/specs/012-ci-tooling-completion/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Builds on**: `engine/src/radic_delivery/gate/{commands,runner,parsers}.py`
(specs/002, reused directly, unmodified) and
`engine/src/radic_delivery/descriptor/validator.py` (specs/001, reused
directly); `policy/exceptions.py` (specs/001) as the structural pattern
`policy/quarantine.py` follows, not a code dependency; `deploy/parity.py`
(specs/004) as the structural pattern `policy/rulesets_diff.py`'s
projected-field comparison follows.

**Tests**: included — spec.md's Acceptance Scenarios require specific,
distinguishable outcomes for each command, same discipline as every prior
feature. `tests inventory` is tested against this platform's own existing
real fixture repos (no new fixtures invented); `rulesets-diff` is tested
against small, inline, hand-written JSON fixtures — no git, no external
call, pure local file I/O.

**Organization**: tasks are grouped by user story (US1 = P1 `tests
inventory`, US2 = P2 `policy rulesets-diff`). The two stories share no
code and have no dependency on each other.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `engine/src/radic_delivery/tests_inventory/{__init__.py,
      result.py, inventory.py}` as empty module skeletons
- [X] T002 [P] Create `engine/src/radic_delivery/policy/
      {quarantine_schema_loader.py, quarantine.py, rulesets_diff.py}` as
      empty module skeletons

**Checkpoint**: `uv run python -c "import radic_delivery.tests_inventory,
radic_delivery.policy.quarantine, radic_delivery.policy.rulesets_diff"`
succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the new schema/ledger `tests inventory` depends on, and the
five real committed ruleset files `rulesets-diff` depends on. These two
groups are independent of each other but both block their respective
story.

- [X] T003 [P] Write `schemas/quarantine.schema.json`: `schema_version`
      (const 1), `quarantine` (array of `{service, test_id, reason,
      jira_key, quarantined_since}`, all required strings except
      `quarantined_since` which is `format: date`), `additionalProperties:
      false` at both levels — per research.md D2
- [X] T004 [P] Write `policy/quarantine.yml`: `schema_version: 1`,
      `quarantine: []` (seeded empty — no real quarantined test exists in
      this platform yet), with a header comment explaining its purpose and
      pointing at the schema, matching `policy/exceptions.yml`'s own
      header-comment style
- [X] T005 [P] Write `engine/src/radic_delivery/policy/
      quarantine_schema_loader.py`: `load_quarantine_schema()`, the exact
      `lru_cache`-wrapped pattern `exceptions_schema_loader.py` already
      uses
- [X] T006 [P] Create `rulesets/{dev-trunk,main-prod-line,
      release-branches,product-tags,platform-tags}.json`, each
      byte-for-byte the JSON body Reference 2 §5.1-§5.5 gives verbatim
      (research.md D6, spec FR-009)

**Checkpoint**: `schemas/quarantine.schema.json` is valid JSON and
importable via `load_quarantine_schema()`; `policy/quarantine.yml` parses
as YAML and validates against it; all five `rulesets/*.json` files are
valid JSON and byte-for-byte match Reference 2

---

## Phase 3: User Story 1 - A service's test counts are visible without reading CI logs (P1) 🎯 MVP

**Goal**: `radic-delivery tests inventory` fully implemented — runs a
service's real unit-test command, reports total/passed/failed/skipped,
and reports quarantine-ledger counts split into active/expired.

**Independent Test**: run against a real, cleanly-passing fixture repo
and a real fixture repo with a deliberately skipped test, confirming each
count is reported accurately; separately supply a quarantine ledger
naming one of a fixture's tests, confirming active-vs-expired
classification by `--as-of` date.

### Tests for User Story 1

- [X] T007 [P] [US1] Unit test in `engine/tests/unit/
      test_policy_quarantine.py`: a ledger entry whose
      `quarantined_since` is within 7 days of `--as-of` classifies as
      `active`; one more than 7 days before classifies as `expired`;
      entries for a different `service` are excluded entirely (research.md
      D2, spec Edge Case)
- [X] T008 [P] [US1] Unit test (same file): a malformed ledger (schema
      violation) raises a clear, distinct error, the same
      `ExceptionsFileError`-equivalent discipline `policy/exceptions.py`
      already applies
- [X] T009 [P] [US1] Unit test in `engine/tests/unit/
      test_tests_inventory.py`: against the real
      `tests/fixtures/sample-repos/python-sample` fixture, a clean run
      reports `launched: true`, `total: 2`, `passed: 2`, `failed: 0`,
      `skipped: 0` (Acceptance Scenario 1)
- [X] T010 [P] [US1] Unit test (same file): against the real
      `tests/fixtures/sample-repos/python-sample-broken-skip` fixture, the
      skipped count is exactly 1, distinguishable from passed/failed
      (Acceptance Scenario 2)
- [X] T011 [P] [US1] Unit test (same file): supplying a quarantine ledger
      naming one of that fixture's tests with `quarantined_since` within
      the window reports `quarantined_active: 1`, `quarantined_expired: 0`
      (Acceptance Scenario 3); the same ledger with an `--as-of` more than
      7 days later reports `quarantined_active: 0`, `quarantined_expired:
      1` (Acceptance Scenario 4)
- [X] T012 [P] [US1] Unit test (same file): pointing `--repo-dir` at a
      descriptor whose `quality.unit.runner` names a tool not actually on
      `PATH` reports `launched: false` with every count `None`, never an
      all-zero "ran successfully" result (Acceptance Scenario 5, research.md
      D3)
- [X] T013 [P] [US1] Unit test in `engine/tests/unit/
      test_ci_tooling_completion_cli.py`: `tests inventory` on a clean
      fixture exits `0`; on an invalid descriptor exits `2`; on an
      unlaunchable test command exits `4`; both `--format json` and
      `--format text` report every field

### Implementation for User Story 1

- [X] T014 [US1] Implement `engine/src/radic_delivery/policy/
      quarantine.py`: `QuarantineEntry` dataclass, `load(path) ->
      list[QuarantineEntry]` (schema-validated, mirrors
      `exceptions.py::load()` exactly), `classify_for_service(entries,
      service, as_of) -> tuple[int, int]` (active, expired counts) — depends
      on T003, T005
- [X] T015 [US1] Implement `engine/src/radic_delivery/tests_inventory/
      result.py`: `TestInventoryResult` dataclass per data-model.md, with
      `to_dict()`
- [X] T016 [US1] Implement `engine/src/radic_delivery/tests_inventory/
      inventory.py`: `inventory(descriptor, *, repo_dir, quarantine_entries,
      as_of) -> TestInventoryResult` — builds the unit invocation via
      `gate.commands.unit_command(descriptor)` (made public by this task,
      alongside the existing `build_commands()`), runs it via
      `gate.runner.run()`, parses via `gate.parsers.parse_test_run()`,
      computes `total`, calls `classify_for_service()` (T014), computes
      `within_quarantine_share_cap` — satisfies spec FR-001, FR-002, FR-003
      (depends on T014, T015)
- [X] T017 [US1] Replace the `tests` stub in `cli.py`'s
      `_NOT_IMPLEMENTED_GROUPS` with a real `tests_app` Typer group:
      `inventory` subcommand with options `--repo-dir`, `--out` (optional;
      writes the JSON payload there), `--quarantine-file` (optional,
      default `policy_dir() / "quarantine.yml"`), `--as-of` (optional,
      default today), `--format`; resolves/validates the descriptor at
      `<repo-dir>/.radic/service.yml` the same way `gate evaluate`'s CLI
      wiring does; exit codes per research.md D3 — depends on T016
- [X] T018 [US1] Run T007-T013 against the implementation; fix until green

**Checkpoint**: User Story 1 fully functional — `tests inventory`
independently reports accurate counts against real fixtures. This alone
is a demonstrable MVP.

---

## Phase 4: User Story 2 - Live GitHub ruleset drift is visible before it causes an incident (P2)

**Goal**: `radic-delivery policy rulesets-diff` fully implemented — loads
the committed `rulesets/` directory and a supplied live-state file,
reports unchanged/missing/added/changed by name, ignoring GitHub-assigned
housekeeping fields.

**Independent Test**: supply a committed directory and a live file that
match exactly (no drift); separately supply one with a missing ruleset,
one with an extra, and one with a changed rule, confirming each is
reported under its own distinct category.

### Tests for User Story 2

- [X] T019 [P] [US2] Unit test in `engine/tests/unit/
      test_policy_rulesets_diff.py` (inline fixtures, `tmp_path`): a
      committed set and a live set identical on the meaningful-fields
      projection report `ok: true`, `unchanged` listing every name
      (Acceptance Scenario 1)
- [X] T020 [P] [US2] Unit test (same file): a ruleset in the committed
      directory absent from the live set is reported in
      `missing_from_live` only (Acceptance Scenario 2)
- [X] T021 [P] [US2] Unit test (same file): a ruleset in the live set
      absent from the committed directory is reported in `added_in_live`
      only (Acceptance Scenario 3)
- [X] T022 [P] [US2] Unit test (same file): a ruleset present in both with
      a differing `rules` entry is reported in `changed`, naming what
      differs (Acceptance Scenario 4)
- [X] T023 [P] [US2] Unit test (same file): a live entry carrying
      GitHub-assigned fields (`id`, `node_id`, `created_at`, `updated_at`,
      `source_type`, `source`, `_links`, `current_user_can_bypass`) that the
      committed file never has is still reported `unchanged` when every
      meaningful field matches (Acceptance Scenario 5, research.md D4)
- [X] T024 [P] [US2] Unit test (same file): two files in the committed
      directory sharing the same `name` field is refused cleanly, naming
      the duplicate, rather than silently comparing against only one
      (spec FR-006, Edge Case)
- [X] T025 [P] [US2] Unit test (same file): an empty committed directory
      against a non-empty live file reports everything live as
      `added_in_live`; the reverse reports everything committed as
      `missing_from_live` (spec Edge Case)
- [X] T026 [P] [US2] Unit test in `test_ci_tooling_completion_cli.py`:
      `policy rulesets-diff` always exits `0` once both inputs are read,
      drift or not; a duplicate committed name exits `2`; an unreadable
      `--dir`/`--live-file` or invalid JSON exits `4`; both `--format
      json`/`--format text` report every category

### Implementation for User Story 2

- [X] T027 [US2] Implement `engine/src/radic_delivery/policy/
      rulesets_diff.py`: `RulesetsDiffResult` dataclass per data-model.md
      with `to_dict()`; `_project(ruleset) -> dict` (keeps only `target`,
      `enforcement`, `conditions`, `bypass_actors`, `rules`); `diff(repo,
      committed, live) -> RulesetsDiffResult` — pure, keyed by `name`,
      refuses on a duplicate committed name via a dedicated exception —
      satisfies spec FR-004, FR-005, FR-006 (research.md D4)
- [X] T028 [US2] Wire `policy rulesets-diff` into `cli.py`'s existing
      `policy_app`: options `--repo`, `--dir`, `--live-file`, `--format`;
      reads every `*.json` file in `--dir` and the JSON array in
      `--live-file`, calls `diff()` (T027); exit codes per research.md D5
      — depends on T027
- [X] T029 [US2] Run T019-T026 against the implementation; fix until green

**Checkpoint**: both user stories independently functional.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T030 [P] Update `engine/README.md`'s command-surface table: move
      `tests inventory` and `policy rulesets-diff` from "not implemented
      yet" to documented, and update the implemented/pending command
      counts this README currently states
- [X] T031 Run `uv run pytest -q`, `uv run ruff check .`, and
      `uv run mypy src/` from `engine/`; fix until clean
- [X] T032 Run `specs/012-ci-tooling-completion/quickstart.md` end-to-end
      manually and confirm every command shown behaves as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS both user stories
  (T003-T005 block US1's `quarantine.py`; T006 blocks US2's real
  comparison inputs)
- **User Stories (Phase 3-4)**: both depend on Foundational only; US1 and
  US2 are fully independent of each other (no shared code, no shared
  fixture) — sequenced P1 → P2 here, but could be built in either order or
  in parallel
- **Polish (Phase 5)**: depends on both stories

### Parallel Opportunities

- T001 and T002 in parallel; T003-T006 in parallel (two independent
  groups); T007-T013 in parallel; T019-T026 in parallel
- Once Foundational (Phase 2) completes, US1's and US2's entire phases
  could proceed in parallel if staffed — neither shares a file with the
  other except `cli.py` (T017, T028) and
  `test_ci_tooling_completion_cli.py` (T013, T026), both of which touch
  disjoint sections

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a
demonstrable, independently valuable capability — `tests inventory`
reporting accurate, distinct counts against real fixtures — before
`rulesets-diff` (US2) is built. Given this is the second bundled feature,
both stories are still built in the same implementation pass (per the
user's "club features" instruction), but each remains independently
testable and independently revertible if one needed to be pulled back
out.
