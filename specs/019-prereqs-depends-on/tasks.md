# Tasks: Prereqs and Depends-On Tracking and Enforcement

**Input**: Design documents from `/specs/019-prereqs-depends-on/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Builds on**: `engine/src/radic_delivery/notes/check.py`'s existing
line-regex convention (specs/007, specs/017); `engine/src/radic_delivery/
release/cut.py`'s existing early-guard pattern (specs/009/014,
specs/018-cut-time-open-release-guard); `engine/src/radic_delivery/
release/render_pr_body.py` (specs/014); `engine/src/radic_delivery/gate/
evaluator.py`'s release-gate mode (specs/013).

**Tests**: included for all three user stories — real PR-body text
fixtures and real local git fixtures, no mocking.

**Organization**: tasks are grouped by user story (US1 = P1 parsing +
schema, US2 = P2 cut-time guard, US3 = P3 rendering + gate enforcement).
US2 and US3 both depend on US1's parsed data existing on real change-note
records.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 `schemas/change-note.schema.json`: add `prereqs` and
      `depends_on` fields per data-model.md

**Checkpoint**: `uv run python -c "import json, jsonschema;
jsonschema.Draft202012Validator.check_schema(json.load(open('schemas/
change-note.schema.json')))"` succeeds from the repo root

---

## Phase 2: User Story 1 - Prereqs and dependencies are captured as real, parsed facts (P1) 🎯 MVP

**Goal**: `pr_body_fields.parse_prereqs`/`parse_depends_on` fully
implemented; `notes/builder.py` and the `notes write` CLI command compute
both fields from a supplied PR body.

**Independent Test**: parse real PR-body text fixtures covering a
Prereqs-only body, a Depends-on-only body, both, and neither; confirm a
change-note record built from a PR body carries identical data.

### Tests for User Story 1

- [X] T002 [P] [US1] Unit test in `engine/tests/unit/
      test_notes_pr_body_fields.py`: a `Prereqs:` block with ticked and
      unticked items parses in order with exact text and state
      (Acceptance Scenario 1)
- [X] T003 [P] [US1] Unit test (same file): a `Depends-on:` trailer with
      duplicate keys parses de-duplicated, in order (Acceptance Scenario
      2, Edge Case 1)
- [X] T004 [P] [US1] Unit test (same file): a PR body with neither marker
      parses both to empty lists, never raising (Acceptance Scenario 3)
- [X] T005 [P] [US1] Unit test (same file): a `Prereqs:` item with
      whitespace-only text after the checkbox is skipped (Edge Case 2)
- [X] T006 [P] [US1] Unit test in `engine/tests/unit/
      test_notes_builder.py`: `build_record(..., pr_body=...)` produces
      `prereqs`/`depends_on` identical to parsing that same PR body
      directly (Acceptance Scenario 4)
- [X] T007 [P] [US1] Unit test in `engine/tests/unit/test_notes_cli.py`:
      `notes write --pr-body-file ...` populates `record.prereqs`/
      `record.depends_on`; omitting the option leaves both empty (no
      regression for existing callers)

### Implementation for User Story 1

- [X] T008 [US1] Implement `engine/src/radic_delivery/notes/
      pr_body_fields.py`: `parse_prereqs(pr_body) -> list[dict]`,
      `parse_depends_on(pr_body) -> list[str]` per research.md D1 —
      depends on T001
- [X] T009 [US1] `engine/src/radic_delivery/notes/builder.py`:
      `build_record()` gains optional `pr_body: str | None = None`,
      populating `prereqs`/`depends_on` via T008 when supplied
      (research.md D2) — depends on T008
- [X] T010 [US1] `engine/src/radic_delivery/cli.py`: `notes write` gains
      optional `--pr-body-file` (matching `notes check`'s existing option
      shape) — depends on T009
- [X] T011 [US1] Run T002-T007 against the implementation; fix until
      green

**Checkpoint**: User Story 1 fully functional — Prereqs/Depends-on are
always parsed facts, never freely typed. This alone is a demonstrable
MVP.

---

## Phase 3: User Story 2 - A release is never cut while a dependency is unsatisfied (P2)

**Goal**: `release cut` refuses, by name, when a selected ticket's
dependency is neither already selected nor already known to be in
production.

**Independent Test**: cut a release with an unsatisfied dependency and
confirm refusal before any branch is created; confirm the cut proceeds
when the dependency is already selected or supplied as known-in-prod.

### Tests for User Story 2

- [X] T012 [P] [US2] Unit test in `engine/tests/unit/test_release_cut.py`
      (real git fixture, extending the existing `_manifest`/`_write_note`
      helpers): a selected ticket's change-note declares `depends_on`
      naming a ticket absent from both the selection and
      `known_prod_tickets` — refuses with `reason ==
      "unmet_dependency"`, detail names both tickets, no branch created
      (Acceptance Scenario 1)
- [X] T013 [P] [US2] Unit test (same file): the same dependency, but
      already present in the selection — cut proceeds (Acceptance
      Scenario 2)
- [X] T014 [P] [US2] Unit test (same file): the same dependency, but
      supplied via `known_prod_tickets` — cut proceeds (Acceptance
      Scenario 3)
- [X] T015 [P] [US2] Unit test (same file): a ticket whose `depends_on`
      names itself is never treated as unsatisfied (Edge Case 1)
- [X] T016 [P] [US2] Unit test in `engine/tests/unit/
      test_release_cut_cli.py`: `--known-prod-tickets` option plumbed
      through; an unmet dependency exits `INVALID_INPUT` with
      `reason: "unmet_dependency"` in the JSON payload

### Implementation for User Story 2

- [X] T017 [US2] `engine/src/radic_delivery/release/result.py`: add
      `"unmet_dependency"` to the `CutReason` Literal
- [X] T018 [US2] `engine/src/radic_delivery/release/cut.py`: new helper
      reading each selected ticket's change-note `depends_on`, and a new
      guard (positioned alongside the existing `other_manifests` guard)
      refusing via `_refused()` when unsatisfied, per research.md D3 —
      depends on T017
- [X] T019 [US2] `engine/src/radic_delivery/cli.py`: `release cut` gains
      `--known-prod-tickets` (comma-separated, matching
      `--other-manifests`'s existing convention) — depends on T018
- [X] T020 [US2] Run T012-T016 against the implementation; fix until
      green

**Checkpoint**: User Story 2 fully functional — a release can never be
cut while a declared dependency is genuinely missing.

---

## Phase 4: User Story 3 - The release PR and release gate show and enforce completeness (P3)

**Goal**: `render_pr_body` gains a Prereqs-and-dependencies section;
`gate evaluate --mode release-gate` gains two new, specifically-named
checks.

**Independent Test**: render a release PR body for a manifest with mixed
Prereqs completeness and confirm the section reports accurately; evaluate
the release gate against the same data and confirm it fails specifically,
then passes once complete.

### Tests for User Story 3

- [X] T021 [P] [US3] Unit test in `engine/tests/unit/
      test_release_render_pr_body.py`: a manifest with mixed Prereqs
      completeness renders a ticked/total count per ticket and lists its
      Depends-on tickets (Acceptance Scenario 1)
- [X] T022 [P] [US3] Unit test in `engine/tests/unit/
      test_gate_release_mode.py`: an unticked Prereqs item fails the
      `prereqs` check naming the specific ticket/item (Acceptance
      Scenario 2)
- [X] T023 [P] [US3] Unit test (same file): an unmet dependency fails the
      `depends_on` check naming the specific ticket/dependency
- [X] T024 [P] [US3] Unit test (same file): fully-ticked Prereqs and
      fully-satisfied dependencies pass both checks (Acceptance Scenario
      3)
- [X] T025 [P] [US3] Unit test (same file): omitting `--manifest`/
      `--change-notes-dir` reports both new checks as `not_executable`,
      matching `stage_regression`'s own precedent — no regression for
      existing `release-gate` callers
- [X] T026 [P] [US3] Unit test in `engine/tests/unit/test_gate_cli.py`:
      `gate evaluate --mode release-gate --manifest ... --change-notes-dir
      ... --known-prod-tickets ...` end-to-end

### Implementation for User Story 3

- [X] T027 [US3] `engine/src/radic_delivery/release/render_pr_body.py`:
      new `_prereqs_and_depends_on_section()` per research.md D4, wired
      into `render()`'s output and the Gates checklist
- [X] T028 [US3] `engine/src/radic_delivery/gate/result.py`: add
      `"prereqs"`/`"depends_on"` to the `CheckName` Literal
- [X] T029 [US3] `engine/src/radic_delivery/gate/evaluator.py`: two new
      check functions, appended in the existing `if mode ==
      "release-gate":` block; `evaluate()` gains optional `manifest`,
      `change_notes_dir`, `known_prod_tickets` parameters per research.md
      D5 — depends on T028
- [X] T030 [US3] `engine/src/radic_delivery/cli.py`: `gate evaluate` gains
      `--manifest`, `--change-notes-dir`, `--known-prod-tickets` (all
      optional, release-gate-only) — depends on T029
- [X] T031 [US3] Run T021-T026 against the implementation; fix until
      green

**Checkpoint**: all three user stories complete. Prereqs/Depends-on are
captured, enforced at cut time, and visible and enforced at release-gate
time.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T032 [P] Update `engine/README.md`'s `notes write`, `release cut`,
      and `gate evaluate` documentation for the new options and checks
- [X] T033 Run `uv run pytest -q`, `uv run ruff check .`, and
      `uv run mypy src/` from `engine/`; fix until clean
- [X] T034 Run `specs/019-prereqs-depends-on/quickstart.md`'s scenarios
      end-to-end manually and confirm every one behaves as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **User Story 1 (Phase 2)**: depends on Setup only
- **User Story 2 (Phase 3)**: depends on US1 (reads real `depends_on`
  data from change-note records)
- **User Story 3 (Phase 4)**: depends on US1 (same reason); independent
  of US2 (reads the same underlying data, doesn't call `cut()`)
- **Polish (Phase 5)**: depends on all three stories

### Parallel Opportunities

- T002-T007 in parallel (US1 tests)
- T012-T016 in parallel (US2 tests), once US1 lands
- T021-T026 in parallel (US3 tests), once US1 lands — US3 can proceed
  alongside US2 since neither depends on the other

## Implementation Strategy

**MVP first**: Phase 1-2 (Setup, US1) deliver a demonstrable,
independently valuable, fully-tested capability — real, parsed Prereqs/
Depends-on facts — before enforcement (US2) and visibility (US3) are
built on top. US2 and US3 can be implemented in either order or in
parallel once US1 lands, since neither depends on the other.
