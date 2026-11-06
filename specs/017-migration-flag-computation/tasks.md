# Tasks: Migration Flag Computation

**Input**: Design documents from `/specs/017-migration-flag-computation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Builds on**: `engine/src/radic_delivery/release/git_history.py`
(specs/009/014, `changed_paths` reused as the pattern for the new
`added_paths`); `engine/src/radic_delivery/notes/` (specs/007,
`builder.py`/`check.py`/`result.py` all edited in place);
`schemas/change-note.schema.json` (specs/007, `migration` field edited).

**Tests**: included for both user stories — real local git fixtures, the
same discipline as every prior feature in this platform.

**Organization**: tasks are grouped by user story (US1 = P1 migration
flag computation, US2 = P2 PR-body cross-check). US2 depends on US1's
computed value existing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Add `added_paths(repo_dir: Path, base: str, head: str) ->
      set[str]` to `engine/src/radic_delivery/release/git_history.py`
      (research.md D2 — `git diff --name-only --diff-filter=A`, mirroring
      `changed_paths`'s existing implementation and `GitHistoryError`
      handling exactly)

**Checkpoint**: `uv run python -c "from radic_delivery.release.git_history
import added_paths"` succeeds from `engine/`

---

## Phase 2: User Story 1 - A change-note's migration flag always reflects what the diff actually did (P1) 🎯 MVP

**Goal**: `notes.migration_flag.compute()` fully implemented and wired
into `notes/builder.py` and the `notes write` CLI command, replacing the
free-form `migration` boolean entirely.

**Independent Test**: compute the flag against real small git diffs (no
migration, expand-only, contract-marked, legacy-excluded, mixed
expand+contract, and `phase_header_required=False`) and confirm each
returns the documented value, with zero dependency on User Story 2.

### Tests for User Story 1

- [X] T002 [P] [US1] Unit test in `engine/tests/unit/
      test_notes_migration_flag.py` (real git fixture): a diff adding no
      file under `migrations/versions/` computes `none` (Acceptance
      Scenario 1)
- [X] T003 [P] [US1] Unit test (same file): a diff adding a migration
      file with no contract marker computes `expand` (Acceptance
      Scenario 2)
- [X] T004 [P] [US1] Unit test (same file): a diff adding a migration
      file whose first non-blank line is `# phase: contract` computes
      `contract` (Acceptance Scenario 3)
- [X] T005 [P] [US1] Unit test (same file): a diff adding a file under
      the configured `legacy_dir` is excluded entirely — computes `none`
      even though the file carries the contract marker (Acceptance
      Scenario 4, Edge Case 1)
- [X] T006 [P] [US1] Unit test (same file): a diff adding both an
      expand-phase and a contract-phase file in the same change computes
      `contract` (Acceptance Scenario 5)
- [X] T007 [P] [US1] Unit test (same file): with
      `phase_header_required=False`, a diff adding a migration file that
      literally carries the contract marker still computes `expand` —
      detection is never attempted in this mode (Acceptance Scenario 6)
- [X] T008 [P] [US1] Unit test (same file): a migration file that is
      *modified*, not added, in the diff is never treated as a
      qualifying addition (Edge Case: modified-not-added); a second case
      confirms the marker is not detected when it appears after a leading
      module docstring rather than as the true first non-blank line
      (Edge Case: marker position, research.md D1's Alembic note)

### Implementation for User Story 1

- [X] T009 [US1] `schemas/change-note.schema.json`: change `migration`
      from `{"type": "boolean", "default": false}` to `{"type": "string",
      "enum": ["none", "expand", "contract"], "default": "none"}`
- [X] T010 [US1] Implement `engine/src/radic_delivery/notes/
      migration_flag.py`: `compute(repo_dir, base, head, *,
      legacy_dir="migrations/legacy", phase_header_required=True) ->
      Literal["none", "expand", "contract"]` per research.md D1-D3 —
      depends on T001, T009
- [X] T011 [US1] `engine/src/radic_delivery/notes/builder.py`:
      `build_record()` drops the `migration: bool | None` parameter;
      takes `repo_dir`, `base`, `head` (plus `legacy_dir`/
      `phase_header_required` pass-through) and computes the value via
      `migration_flag.compute(...)` before validation (research.md D4) —
      depends on T010
- [X] T012 [US1] `engine/src/radic_delivery/cli.py`: `notes write`
      command — replace `--migration/--no-migration` with required
      `--repo-dir`, `--base`, `--head` and optional `--legacy-dir` /
      `--phase-header-required`/`--no-phase-header-required` options —
      depends on T011
- [X] T013 [US1] Update the existing `test_notes_builder.py` and any
      `notes write` CLI test fixtures that passed a free `migration`
      value, to the new computed-value shape; run T002-T008 against the
      implementation and fix until green

**Checkpoint**: User Story 1 fully functional — the migration flag is
always computed from a real diff, never free input. This alone is a
demonstrable MVP.

---

## Phase 3: User Story 2 - A PR body that disagrees with reality is caught, not trusted (P2)

**Goal**: `notes/check.py` and the `notes check` CLI command gain an
optional, additive cross-check comparing the computed migration flag
against a `Migrations:` line in a PR body, failing closed on a mismatch.

**Independent Test**: compute a real migration flag for a fixture diff,
then check it against a deliberately mismatched declared value in a
fixture PR body, confirming the check fails with a specific, named
reason; confirm a matching declaration passes, and an absent declaration
passes regardless of the computed value.

### Tests for User Story 2

- [X] T014 [P] [US2] Unit test in `engine/tests/unit/
      test_notes_check.py`: a PR body declaring `Migrations: none`
      against a computed `expand` value fails, naming both values
      (Acceptance Scenario 1)
- [X] T015 [P] [US2] Unit test (same file): a PR body declaring a value
      matching the computed flag passes (Acceptance Scenario 2)
- [X] T016 [P] [US2] Unit test (same file): a PR body with no
      `Migrations:` line passes regardless of the computed value
      (Acceptance Scenario 3)
- [X] T017 [P] [US2] Unit test (same file): CLI-level — `notes check`
      without `--repo-dir`/`--base`/`--head` preserves today's Jira-only
      behavior exactly (no migration check reported, no regression);
      with all three supplied, both checks are reported side by side

### Implementation for User Story 2

- [X] T018 [US2] `engine/src/radic_delivery/notes/result.py`: add
      `MigrationCheckResult` dataclass (`computed`, `declared`, `matched`,
      `passed`, `detail`, `to_dict()`) per data-model.md
- [X] T019 [US2] `engine/src/radic_delivery/notes/check.py`: add
      `classify_migration_declaration(pr_body) -> Literal["none",
      "expand", "contract"] | None` (new `Migrations:` line regex,
      matching `_JIRA_LINE_RE`'s style) and `check_migration_match(computed,
      declared) -> MigrationCheckResult` per research.md D5 — depends on
      T018
- [X] T020 [US2] `engine/src/radic_delivery/cli.py`: `notes check`
      command — add optional `--repo-dir`, `--base`, `--head`; when all
      three are supplied, compute the real migration flag and run
      `check_migration_match`, reporting it alongside the existing Jira
      classification result; omitted entirely preserves today's
      Jira-only output exactly — depends on T010 (compute), T019
- [X] T021 [US2] Run T014-T017 against the implementation; fix until
      green

**Checkpoint**: both user stories complete. The release-note gate check
now verifies migration-state honesty, not just Jira-key presence.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T022 [P] Update `engine/README.md`'s `notes write`/`notes check`
      command documentation to reflect the new `--repo-dir`/`--base`/
      `--head` options and the removal of `--migration/--no-migration`
- [X] T023 Run `uv run pytest -q`, `uv run ruff check .`, and
      `uv run mypy src/` from `engine/`; fix until clean
- [X] T024 Run `specs/017-migration-flag-computation/quickstart.md`'s
      scenarios end-to-end manually and confirm every one behaves as
      documented, including the schema-validity check

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **User Story 1 (Phase 2)**: depends on Setup only
- **User Story 2 (Phase 3)**: depends on US1 being complete (the check
  compares against US1's computed value)
- **Polish (Phase 4)**: depends on both stories

### Parallel Opportunities

- T002-T008 in parallel (independent fixture cases, same file but
  non-overlapping test functions)
- T014-T017 in parallel, once US1 is complete

## Implementation Strategy

**MVP first**: Phase 1-2 (Setup, US1) deliver a demonstrable,
independently valuable, fully-tested capability — a migration flag that
is always a computed fact, never a typed claim — before the PR-body
cross-check (US2) is built. Phase 3 is sequenced after US1 specifically
because it depends on US1's computed value existing, the same real
dependency specs/014 and specs/015's two-story bundles already had.
