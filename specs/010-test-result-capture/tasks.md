# Tasks: Test-Result Record Capture

**Input**: Design documents from `/specs/010-test-result-capture/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md
**Builds on**: nothing from specs/002-009 directly (data-model.md's
"Relationship to prior features' entities") — only
`schemas/test-result.schema.json` (feature 001's intentionally loose
placeholder, corrected by this feature) and the general `cli.py`/
`exit_codes.py` scaffolding, following specs/007's `notes/` subpackage
shape exactly

**Tests**: included — spec.md's Acceptance Scenarios require specific,
distinguishable acceptance/rejection outcomes, same discipline as every
prior feature. Like specs/007 and specs/009, this feature has no
external-dependency boundary at all: every test is a real, unmocked local
file read/write and a real schema validation call.

**Organization**: tasks are grouped by user story (US1 = P1 reliable
record capture, US2 = P1 the zero-skip-budget rejection rule, US3 = P2
stage-completeness requirements).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `engine/src/radic_delivery/records/{__init__.py,
      schema_loader.py, result.py, validator.py, writer.py}` as empty
      module skeletons

**Checkpoint**: `uv run python -c "import radic_delivery.records"`
succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the corrected schema and the result type every story extends.

- [X] T002 Correct `schemas/test-result.schema.json` per research.md D1:
      make `release_id` nullable (`type: ["string", "null"]`); add
      `scope` (enum `regression`/`full`/`smoke`), `target_url`,
      `tags_run`, `seeded_tenant`; tighten `cloud_deploy`'s required
      fields (`pipeline`, `release`, `rollout`, `rollout_state`) and
      correct `verify` to the `pass`/`fail`/`not-run` enum; add the
      second `allOf` conditional (`counts.skipped >= 1` → `result ==
      "fail"`) alongside the existing stage-completeness conditional; set
      `additionalProperties: false` — keep `$id`/`title` unchanged
- [X] T003 [P] Write `engine/src/radic_delivery/records/
      schema_loader.py`: `load_test_result_schema()`, the same
      `lru_cache`-wrapped pattern as the other `schema_loader.py` modules
- [X] T004 [P] Write `engine/src/radic_delivery/records/result.py`:
      `RecordIssue`, `PutResult` dataclasses per data-model.md, with
      `to_dict()`

**Checkpoint**: the corrected schema is valid JSON and importable via
`load_test_result_schema()`; `PutResult` is importable

---

## Phase 3: User Story 1 - A completed test run's result is captured reliably, in one trustworthy shape (P1) 🎯 MVP

**Goal**: `radic-delivery records put-test-result` fully implemented:
validate a complete record (including the `--release-id` cross-check)
and store it at the correct mirrored local path.

**Independent Test**: supply a complete, valid stage record and a
complete, valid release-less dev record, confirming both are accepted and
stored at their correct respective locations; supply a record whose own
`release_id` doesn't match `--release-id`, confirming it's rejected.

### Tests for User Story 1

- [X] T005 [P] [US1] Unit test in `engine/tests/unit/
      test_records_validator.py`: a complete, valid stage-environment
      record validates with no issues (Acceptance Scenario 1)
- [X] T006 [P] [US1] Unit test (same file): a complete, valid
      dev-environment record with `release_id: null` validates with no
      issues (Acceptance Scenario 2)
- [X] T007 [P] [US1] Unit test (same file): a record whose `release_id`
      doesn't match the caller's `--release-id` is rejected, naming the
      mismatch (Acceptance Scenario 3)
- [X] T008 [P] [US1] Unit test (same file): `--release-id` supplied
      while the record's own `release_id` is `null` is **not** treated as
      a mismatch (research.md D4)
- [X] T009 [P] [US1] Unit test (same file): a record missing a required
      field, or with a field of the wrong shape, is rejected naming that
      specific field (Edge Case)
- [X] T010 [P] [US1] Unit test in `engine/tests/unit/
      test_records_writer.py` (using `tmp_path`): a valid record is
      written to `<out_dir>/releases/<release_id>/test-results/
      <environment>-<repo>-<suite>.json`; a release-less record is
      written under the fixed `dev` segment instead (research.md D2);
      the result always reports `upload_status: "not_available"`
- [X] T011 [P] [US1] Unit test in `engine/tests/unit/
      test_records_cli.py`: `records put-test-result` on a complete,
      valid record exits `0`, writes a real file, and reports `result`/
      `local_path` in `--format json`

### Implementation for User Story 1

- [X] T012 [US1] Implement `engine/src/radic_delivery/records/
      validator.py`: `validate(record: dict, release_id: str | None) ->
      list[RecordIssue]` — schema validation via
      `jsonschema.Draft202012Validator` against the corrected schema
      (T002), plus the `--release-id` cross-check (research.md D4) —
      satisfies spec FR-001, FR-002, FR-007 (depends on T002, T004)
- [X] T013 [US1] Implement `engine/src/radic_delivery/records/
      writer.py`: `write(record: dict, out_dir: Path) -> str` (the local
      path written to), constructing the mirrored path per research.md
      D2 (the `release_id` or `"dev"` segment) — satisfies spec FR-008,
      FR-009 (depends on T004)
- [X] T014 [US1] Wire `records put-test-result` in `cli.py`, replacing
      the feature-001 `records` stub: options `--file`, `--release-id`,
      `--out-dir`, `--format`; calls `validate` (T012) then `write`
      (T013) only when valid; exit codes per research.md D5 — depends on
      T012, T013
- [X] T015 [US1] Run T005-T011 against the implementation; fix until
      green

**Checkpoint**: User Story 1 fully functional — a complete, valid record
(release or release-less) is reliably captured at the correct location.
This alone is a demonstrable MVP.

---

## Phase 4: User Story 2 - A run that skipped tests can never report itself as passing (P1)

**Goal**: the zero-skip-budget rule is enforced — a skipped-test record
claiming an overall pass is rejected; the same record claiming an overall
fail is accepted.

### Tests for User Story 2

- [X] T016 [P] [US2] Unit test in `test_records_validator.py`: a record
      with `counts.skipped >= 1` and `result: "pass"` is rejected, naming
      the inconsistency (Acceptance Scenario 1)
- [X] T017 [P] [US2] Unit test (same file): the identical record with
      `result: "fail"` instead is accepted (Acceptance Scenario 2)
- [X] T018 [P] [US2] Unit test (same file): a record with
      `counts.skipped == 0` is unaffected by this rule regardless of its
      `result` value (Acceptance Scenario 3)
- [X] T019 [P] [US2] Unit test in `test_records_cli.py`: the CLI, given a
      skip-budget-violating record, exits `2`, and nothing is written

### Implementation for User Story 2

- [X] T020 [US2] Confirm T002's `allOf` skip-budget conditional and
      T012's validator correctly surface T016-T018's cases — closes any
      gaps revealed; the rule itself is schema-level (T002), not
      additional Python logic
- [X] T021 [US2] Run T016-T019 against the implementation; fix until
      green

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - A stage run must carry the completeness a stage run requires (P2)

**Goal**: a stage-environment record missing its `release_id` or its
`scope: "full"` declaration is rejected, naming specifically which.

### Tests for User Story 3

- [X] T022 [P] [US3] Unit test in `test_records_validator.py`: a
      stage-environment record with `release_id: null` is rejected,
      naming that a release identifier is required for stage (Acceptance
      Scenario 1)
- [X] T023 [P] [US3] Unit test (same file): a stage-environment record
      missing `scope` (or with a `scope` other than `"full"`) is
      rejected, naming the full-scope requirement (Acceptance Scenario 2)
- [X] T024 [P] [US3] Unit test (same file): a stage-environment record
      with both a real `release_id` and `scope: "full"` present is
      unaffected by this rule (Acceptance Scenario 3)
- [X] T025 [P] [US3] Unit test in `test_records_cli.py`: the CLI, given a
      stage-incomplete record, exits `2`, and nothing is written

### Implementation for User Story 3

- [X] T026 [US3] Confirm T002's `allOf` stage-completeness conditional and
      T012's validator correctly surface T022-T024's cases — closes any
      gaps revealed; the rule itself is schema-level (T002)
- [X] T027 [US3] Run T022-T025 against the implementation; fix until
      green

**Checkpoint**: all three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T028 [P] Update `engine/README.md`'s command-surface table: move
      `records` from "not implemented yet" to documented (describing the
      two schema-level conditional rules and the `not_available` upload
      honesty note), and update the implemented/pending command counts
      this README currently states
- [X] T029 Run `specs/010-test-result-capture/quickstart.md` end-to-end
      manually and confirm every command shown behaves as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
  (the corrected schema and `PutResult` are shared)
- **User Stories (Phase 3-5)**: all depend on Foundational; US2 and US3
  both rely on T002's schema conditionals and T012's validator wiring
  existing, so US1 should land first even though US2/US3's test cases are
  independent of each other and of US1's own cases
- **Polish (Phase 6)**: depends on all three stories

### Parallel Opportunities

- T003 and T004 in parallel; T005-T011 in parallel; T016-T019 in
  parallel; T022-T025 in parallel

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a
demonstrable, independently valuable capability — reliable capture of a
complete, valid test-result record, release or release-less — before the
skip-budget rule (US2) or the stage-completeness rule (US3) are
separately verified. Both rules are actually enforced by the corrected
schema itself (T002), so US2 and US3's "implementation" tasks are
verification-and-fix against T012's already-complete validator, the same
escalating-implementation pattern as every prior feature's core logic.
