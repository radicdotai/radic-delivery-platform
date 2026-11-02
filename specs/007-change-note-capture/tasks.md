# Tasks: Change-Note Record Capture and Release-Note Gate

**Input**: Design documents from `/specs/007-change-note-capture/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md
**Builds on**: nothing from specs/001-006 directly (data-model.md's
"Relationship to prior features' entities") — only `schemas/change-note.
schema.json` (feature 001's intentionally loose placeholder, tightened by
this feature) and the general `cli.py`/`exit_codes.py` scaffolding

**Tests**: included — spec.md's Acceptance Scenarios require specific,
distinguishable classifications and rejections, same discipline as every
prior feature. Every test is either a pure function call or a real,
unmocked local filesystem write (`tmp_path`) — no fixtures, no subprocess,
no network (research.md D6: this feature has no real-vs-mocked testing
asymmetry at all).

**Organization**: tasks are grouped by user story (US1 = P1 record
construction+validation+write, US2 = P1 PR-completeness classification,
US3 = P2 warn-then-block staged rollout).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `engine/src/radic_delivery/notes/{__init__.py,
      schema_loader.py, result.py, builder.py, writer.py, check.py}` as
      empty module skeletons

**Checkpoint**: `uv run python -c "import radic_delivery.notes"` succeeds
from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the tightened schema and the result shapes every story
extends.

- [X] T002 Tighten `schemas/change-note.schema.json` per research.md D1:
      add `schema_version` (const 1, required), add `pr_number` (integer),
      correct `linked_prs` items to
      `{"type": "string", "pattern": "^radicdotai/[A-Za-z0-9_.-]+#[0-9]+$"}`,
      correct `migration` to `{"type": "boolean", "default": false}`, add
      `author` (string) and `merged_at` (date-time), tighten `dev_deploy`
      to the full nested shape (`digest`, `cd_release`,
      `post_deploy_result`), relax `jira_key` to `anyOf` the existing
      ticket-key pattern or the exact literal `"None"`, and set
      `additionalProperties: false` — keep `$id`/`title` unchanged;
      update the `description` field since this is no longer "not read or
      written by the engine scaffold"
- [X] T003 [P] Write `engine/src/radic_delivery/notes/schema_loader.py`:
      `load_change_note_schema()`, the same `lru_cache`-wrapped pattern as
      `descriptor/schema_loader.py::load_service_schema`
- [X] T004 [P] Write `engine/src/radic_delivery/notes/result.py`:
      `ChangeNoteBuildResult`, `WriteResult`, `ReleaseNoteCheckResult`
      dataclasses per data-model.md, each with `to_dict()`

**Checkpoint**: the tightened schema file is valid JSON and importable via
`load_change_note_schema()`; the three result types exist and are
importable

---

## Phase 3: User Story 1 - A merged commit gets a reliable, structured change-note record (P1) 🎯 MVP

**Goal**: `radic-delivery notes write` fully implemented: construct,
validate, and write one change-note record from explicit CLI inputs.

**Independent Test**: supply a complete, valid set of values and confirm a
schema-valid record is written to a real local path; supply the explicit
"no Jira ticket" value and confirm it's accepted; supply invalid values
and confirm nothing is written and the rejection names the specific field.

### Tests for User Story 1

- [X] T005 [P] [US1] Unit test in `engine/tests/unit/
      test_notes_builder.py`: a complete, valid set of explicit field
      values builds a schema-valid record dict with `ok=True` (Acceptance
      Scenario 1)
- [X] T006 [P] [US1] Unit test (same file): `jira_key="None"` (and
      case-insensitive variants, e.g. `"none"`) is accepted as valid,
      stored as the literal `"None"` (Acceptance Scenario 2)
- [X] T007 [P] [US1] Unit test (same file), parametrized: an invalid
      `type`, an empty `title`, a `jira_key` matching neither the ticket
      pattern nor `"None"`, and a missing required field each produce
      `ok=False` with an issue naming the specific field and reason
      (Acceptance Scenario 3)
- [X] T008 [P] [US1] Unit test in `engine/tests/unit/
      test_notes_writer.py` (using `tmp_path`): a validated record is
      written to `<out_dir>/change-notes/<repo>/<sha>.json` with the exact
      record content; the result's `upload_status` is always
      `"not_available"`
- [X] T009 [P] [US1] Unit test in `engine/tests/unit/test_notes_cli.py`:
      `notes write` with a complete, valid set of flags exits `0`, writes
      a real file at the expected path, and reports `local_path`/
      `upload_status` in `--format json`; with an invalid set of flags
      (e.g. bad `--type`) exits `2` and writes nothing

### Implementation for User Story 1

- [X] T010 [US1] Implement `engine/src/radic_delivery/notes/builder.py`:
      `build_record(**fields) -> ChangeNoteBuildResult`, validating via
      `jsonschema.Draft202012Validator` against
      `load_change_note_schema()`, the same pattern as `descriptor/
      validator.py`'s `_schema_issues` — satisfies spec FR-001, FR-002,
      FR-003 (depends on T002, T003, T004)
- [X] T011 [US1] Implement `engine/src/radic_delivery/notes/writer.py`:
      `write(record: dict, repo: str, sha: str, out_dir: Path) ->
      WriteResult` — creates parent directories as needed, writes the
      record as JSON, always reports `upload_status="not_available"`
      (research.md D4) — satisfies spec FR-004 (depends on T004)
- [X] T012 [US1] Wire `notes write` in `cli.py`, replacing the feature-001
      `notes` stub: typer options `--repo`, `--sha`, `--pr`, `--bucket`
      (accepted, unused beyond being recorded as not triggering a real
      upload), `--type`, `--audience`, `--title`, `--summary`,
      `--jira-key` (required), `--linked-prs`, `--migration`/
      `--no-migration`, `--uat-escape`/`--no-uat-escape`,
      `--regression-test-added`/`--no-regression-test-added`, `--author`,
      `--merged-at`, `--out-dir` (default `.`) — calls `build_record`
      (T010) then `write` (T011) only when valid; exit codes per
      research.md D5 (`INVALID_INPUT` for a rejected record, `OK` for a
      successful write) — depends on T010, T011
- [X] T013 [US1] Run T005-T009 against the implementation; fix until green

**Checkpoint**: User Story 1 fully functional — `notes write` reliably
builds, validates, and writes a real change-note record. This alone is a
demonstrable MVP.

---

## Phase 4: User Story 2 - A pull request author is told whether their release note is complete (P1)

**Goal**: `radic-delivery notes check` classifies a PR body correctly in
non-blocking (default) mode.

**Independent Test**: check PR bodies that do, and don't, contain a
recognizable Jira reference or the explicit non-ticket statement, and
confirm each is correctly classified.

### Tests for User Story 2

- [X] T014 [P] [US2] Unit test in `engine/tests/unit/test_notes_check.py`:
      a PR body containing `Jira: RAD-1234` (and lowercase/mixed-case
      variants of the key and the `Jira:` label) classifies as
      `has_jira_key` with the key normalised to upper case (Acceptance
      Scenario 1, research.md D2)
- [X] T015 [P] [US2] Unit test (same file): a PR body containing
      `Jira: None` (any case) classifies as `explicit_none` (Acceptance
      Scenario 2)
- [X] T016 [P] [US2] Unit test (same file): a PR body containing neither
      a `Jira:` line nor an unrecognizable one (e.g. `Jira: see Slack`)
      classifies as `incomplete`, with a `detail` naming what's missing
      (Acceptance Scenario 3)
- [X] T017 [P] [US2] Unit test in `test_notes_cli.py`: `notes check
      --pr-body-file <path>` (no `--require-jira-key`) reports the correct
      classification for each of the three PR-body fixtures, in both
      `--format json` and `--format text`

### Implementation for User Story 2

- [X] T018 [US2] Implement `engine/src/radic_delivery/notes/check.py`:
      `classify(pr_body: str) -> Classification` matching
      `^Jira:\s*(.+)$` case-insensitively on the label anywhere in the
      body text, then classifying the captured value as `explicit_none`
      (case-insensitive `none`), `has_jira_key` (matches
      `^[A-Z]{2,10}-[0-9]+$` case-insensitive, normalised upper), or
      `incomplete` (present but unrecognizable, or the line is absent
      entirely) — satisfies spec FR-006 (research.md D2)
- [X] T019 [US2] Wire `notes check` in `cli.py` (non-blocking path): reads
      `--pr-body-file`, calls `classify` (T018), builds a
      `ReleaseNoteCheckResult` with `blocking=False`, always `passed=True`
      in this mode, emits `--format json`/`text` — depends on T004, T018
- [X] T020 [US2] Run T014-T017 against the implementation; fix until green

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - The release-note check starts as a warning and only blocks once the rollout says so (P2)

**Goal**: `--require-jira-key` changes the pass/fail outcome for an
incomplete body only — never for a complete one.

**Independent Test**: check the identical incomplete PR body once without
and once with `--require-jira-key`, confirming the classification is
identical but the pass/fail outcome differs; confirm a complete body
passes in both modes.

### Tests for User Story 3

- [X] T021 [P] [US3] Unit test in `test_notes_check.py` (or a new
      `test_notes_result.py` if the pass/fail decision lives in
      `result.py` rather than `check.py` — implementer's choice, keep
      whichever file actually holds the logic): `incomplete` +
      non-blocking → `passed=True`; `incomplete` + blocking →
      `passed=False`; `has_jira_key`/`explicit_none` → `passed=True` in
      both blocking and non-blocking modes (Acceptance Scenarios 1-3)
- [X] T022 [P] [US3] Unit test in `test_notes_cli.py`: `notes check
      --require-jira-key` on an incomplete PR body exits `3`; the
      identical complete PR body still exits `0` with `--require-jira-key`
      set

### Implementation for User Story 3

- [X] T023 [US3] Finalize the blocking-mode branch in `cli.py`'s `notes
      check` wiring (T019) and/or `notes/result.py` (T004): map
      `ReleaseNoteCheckResult.passed` to `ExitCode.POLICY_FAILURE` only
      when `blocking and classification == "incomplete"` (research.md D5)
      — closes any gap T021/T022 reveal; the classification logic itself
      (T018) does not change between modes
- [X] T024 [US3] Run T021-T022 against the implementation; fix until green

**Checkpoint**: all three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T025 [P] Update `engine/README.md`'s command-surface table: move
      `notes` from "not implemented yet" to documented, describing both
      subcommands, the `"None"` Jira escape hatch, and the
      `upload_status: "not_available"` honesty note
- [X] T026 Run `specs/007-change-note-capture/quickstart.md` end-to-end
      manually and confirm every command shown behaves as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
  (the tightened schema and the three result types are shared)
- **User Stories (Phase 3-5)**: all depend on Foundational; US2 and US3
  both extend US1's `cli.py` wiring and `result.py` shapes, so US1 should
  land first even though US2/US3 do not depend on each other's test cases;
  US3 specifically extends US2's `notes check` wiring (T019), so US2
  before US3 in practice, though their user-facing capabilities remain
  independently testable per spec.md
- **Polish (Phase 6)**: depends on all three stories

### Parallel Opportunities

- T003 and T004 in parallel; T005-T009 in parallel; T014-T017 in
  parallel; T021-T022 in parallel
- Once US1 lands, US2's tests (T014-T017) can be written in parallel with
  US1's implementation tasks landing, since `check.py` is a separate file
  from `builder.py`/`writer.py`

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a
demonstrable, independently valuable capability — a reliable, schema-valid
change-note record, written for real — before the release-note
completeness check (US2) or its staged-rollout behavior (US3) exist.
Given how small and interdependent the underlying module set is (one
schema file, three small modules, no external dependency), all three
stories are realistically a single short implementation pass, but remain
separated here for clear, independently-verifiable checkpoints.
