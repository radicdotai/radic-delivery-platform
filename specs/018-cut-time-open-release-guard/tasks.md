# Tasks: Cut-Time Open-Release Guard

**Input**: Design documents from `/specs/018-cut-time-open-release-guard/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Builds on**: `engine/src/radic_delivery/release/cut.py` (specs/009/014,
`cut()`'s existing early-guard sequence and `_refused()` helper, edited
in place); `engine/src/radic_delivery/release/result.py` (`CutReason`
extended).

**Tests**: included — real local git fixtures, extending
`test_release_cut.py`'s own existing style exactly, the same discipline
as every prior feature.

**Organization**: a single user story (P1) — this feature has no smaller
independently-valuable slice.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: User Story 1 - A second release for the same service is refused while one is still open (P1) 🎯 MVP

**Goal**: `release cut` refuses cleanly, before any branch is created,
when another already-known manifest for the same service repo is still
open — and is a complete no-op when it isn't.

**Independent Test**: attempt a cut while supplying another manifest for
the same service whose status is still open, confirming refusal, no
branch created, and a detail naming the blocker; confirm the cut proceeds
normally when that manifest is closed, for a different service, or
simply absent.

### Tests for User Story 1

- [X] T001 [P] [US1] Unit test in `engine/tests/unit/test_release_cut.py`
      (real git fixture, reusing the existing `repo`/`_manifest`/
      `_write_and_commit`/`_write_note` helpers exactly): another
      manifest for the same repo with status `stage-verified` refuses the
      cut with `reason == "release_already_open"`, a detail naming its
      release id and status, and no `release/<id>` branch created
      (Acceptance Scenario 1)
- [X] T002 [P] [US1] Unit test (same file): another manifest for the same
      repo with status `finalised` (and, parametrized, `aborted` and
      `failed`) does not block the cut — `result.ok is True`, identical
      to the same cut without it (Acceptance Scenario 2)
- [X] T003 [P] [US1] Unit test (same file): another manifest with an open
      status but a different `repo` does not block the cut (Acceptance
      Scenario 3)
- [X] T004 [P] [US1] Unit test (same file): `other_manifests=None` (the
      default) and `other_manifests=[]` both behave identically to every
      existing `test_release_cut.py` test written before this feature —
      a direct regression check, not just an absence-of-error check
      (Acceptance Scenario 4)
- [X] T005 [P] [US1] Unit test (same file): an other manifest sharing the
      *same* `release_id` as the one being cut is never treated as a
      blocker, regardless of its status (Edge Case 1)
- [X] T006 [P] [US1] Unit test in `engine/tests/unit/
      test_release_cut_cli.py` — `--other-manifests` loads one or more local
      JSON files and passes them through; an open blocker exits
      `INVALID_INPUT` with `reason: "release_already_open"` in the JSON
      payload; omitting the option behaves exactly as before this feature

### Implementation for User Story 1

- [X] T007 [US1] `engine/src/radic_delivery/release/result.py`: add
      `"release_already_open"` to the `CutReason` Literal (research.md D3)
- [X] T008 [US1] `engine/src/radic_delivery/release/cut.py`: `cut()` gains
      `other_manifests: list[dict[str, Any]] | None = None`; insert the
      new guard immediately after the existing `missing_change_note`
      check and before `ordered_shas`/branch creation (research.md D2,
      D4) — filters `other_manifests` to same-`repo`,
      different-`release_id`, status-not-in-`{finalised, aborted,
      failed}`, and refuses via the existing `_refused()` helper naming
      the first match's `release_id`/`status` in the detail — depends on
      T007
- [X] T009 [US1] `engine/src/radic_delivery/cli.py`: `release cut`
      command gains `--other-manifests` (comma-separated local file
      paths, each loaded with `json.loads`, matching the existing
      `manifest_path` loading convention exactly, research.md D5) —
      depends on T008
- [X] T010 [US1] Run T001-T006 against the implementation; fix until
      green

**Checkpoint**: feature complete — a service can never have two releases
cut and open at once once this guard is exercised with accurate input,
and zero existing behavior changes for any caller that doesn't use it.

---

## Phase 2: Polish & Cross-Cutting Concerns

- [X] T011 [P] Update `engine/README.md`'s `release cut` documentation to
      describe the new `--other-manifests` option and the
      `release_already_open` refusal reason
- [X] T012 Run `uv run pytest -q`, `uv run ruff check .`, and
      `uv run mypy src/` from `engine/`; fix until clean
- [X] T013 Run `specs/018-cut-time-open-release-guard/quickstart.md`'s
      scenarios end-to-end manually and confirm every one behaves as
      documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **User Story 1 (Phase 1)**: no dependencies on any other spec in the
  roadmap
- **Polish (Phase 2)**: depends on User Story 1

### Parallel Opportunities

- T001-T006 in parallel (independent fixture cases, mostly the same file
  but non-overlapping test functions)

## Implementation Strategy

**Single-story feature**: unlike specs/014/015/016's two-story bundles,
this feature has exactly one independently-valuable slice — the guard
itself. There is no smaller MVP to carve out of it.
