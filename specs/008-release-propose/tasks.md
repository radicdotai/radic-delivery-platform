# Tasks: Release Selection and Draft Manifest

**Input**: Design documents from `/specs/008-release-propose/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md
**Builds on**: specs/007-change-note-capture (already implemented, merged)
— reads the exact `change-notes/<repo>/<sha>.json` local layout `notes
write` already produces (data-model.md's "Relationship to prior features'
entities")

**Tests**: included — spec.md's Acceptance Scenarios require specific,
distinguishable grouping/held-back/non-jira-pr outcomes, same discipline
as every prior feature. Candidate-loading, grouping, and manifest
construction are pure function tests; git reachability is the one real,
unmocked dependency, exercised against a real local git repository
(research.md D7).

**Organization**: tasks are grouped by user story (US1 = P1 trustworthy
ready-selection grouping, US2 = P1 held-back visibility, US3 = P2
ticket-less-PR explicit opt-in). The core pipeline (candidate loading,
git filtering, selection, manifest construction) is realistically one
small, interdependent unit — like specs/005's `grammar.py` and specs/006's
`map_outcome`, it is built in full during US1, with US2/US3 closing any
gaps their own test cases reveal, not re-designing from scratch.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `engine/src/radic_delivery/release/{__init__.py,
      schema_loader.py, result.py, candidates.py, git_history.py,
      selector.py, manifest.py}` as empty module skeletons

**Checkpoint**: `uv run python -c "import radic_delivery.release"`
succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the corrected schema and the shared result types every story
extends.

- [X] T002 Correct `schemas/release-manifest.schema.json` per research.md
      D1: drop `approvals`/`digests`/`gates` from the top-level
      `required` array (keep them as optional properties with their full
      nested shape); relax `selection.tickets[].commits[]`'s and
      `selection.non_jira_prs[].commits[]`'s required fields to
      `dev_sha` only; correct `non_jira_prs[].second_approver`'s type to
      `["string", "null"]`; correct `base` from a bare string to
      `{branch, sha}`; set `additionalProperties: false` — keep `$id`/
      `title` unchanged
- [X] T003 [P] Write `engine/src/radic_delivery/release/schema_loader.py`:
      `load_release_manifest_schema()`, the same `lru_cache`-wrapped
      pattern as `descriptor/schema_loader.py`/`notes/schema_loader.py`
- [X] T004 [P] Write `engine/src/radic_delivery/release/result.py`:
      `Candidate`, `Selection`, `ProposeResult` dataclasses per
      data-model.md, each with `to_dict()` where applicable

**Checkpoint**: the corrected schema is valid JSON and importable via
`load_release_manifest_schema()`; the result types exist and are
importable

---

## Phase 3: User Story 1 - A release manager sees a trustworthy draft selection of what's ready (P1) 🎯 MVP

**Goal**: `radic-delivery release propose` fully implemented for the
ready-ticket path: load candidates, filter by real git reachability,
group by ticket, build and validate a `proposed` manifest.

**Independent Test**: supply change-note records for a ready ticket with
two commits and for two separate ready tickets with one commit each,
confirming correct grouping in both cases, and confirm the result is
schema-valid.

### Tests for User Story 1

- [X] T005 [P] [US1] Unit test in `engine/tests/unit/
      test_release_propose_candidates.py`: loading change-note records
      from a directory filters out records for a different `repo` and
      reports (not raises on) a malformed/unreadable record file
- [X] T006 [P] [US1] Unit test in `engine/tests/unit/
      test_release_propose_git_history.py` (real `tmp_path` git
      repository, real `git init`/`commit`/branch commands): commits
      reachable from `--base`'s HEAD are correctly identified; commits
      already an ancestor of an explicit `--since-sha` are excluded
- [X] T007 [P] [US1] Unit test in `engine/tests/unit/
      test_release_propose_selector.py`: two commits belonging to the
      same ready ticket are grouped under one entry with both commits
      recorded (Acceptance Scenario 1); two different ready tickets, each
      with one commit, are listed separately (Acceptance Scenario 2)
- [X] T008 [P] [US1] Unit test in `engine/tests/unit/
      test_release_propose_manifest.py`: a valid selection builds a
      manifest with `status: "proposed"` that validates against the
      corrected schema (Acceptance Scenario 3)
- [X] T009 [P] [US1] Unit test in `engine/tests/unit/
      test_release_propose_cli.py` (real `tmp_path` git repo + real
      change-note files written via `notes write` or constructed
      directly): `release propose` with a ready ticket exits `0` and
      reports the correct grouped selection in `--format json`

### Implementation for User Story 1

- [X] T010 [US1] Implement `engine/src/radic_delivery/release/
      candidates.py`: `load_candidates(change_notes_dir: Path, repo: str)
      -> tuple[list[Candidate], list[issue]]` — satisfies spec FR-001,
      Edge Cases (depends on T004)
- [X] T011 [US1] Implement `engine/src/radic_delivery/release/
      git_history.py`: `reachable_shas(repo_dir: Path, base: str,
      since_sha: str | None) -> set[str]` via real `git log --format=%H`
      subprocess calls and a set difference (research.md D2)
- [X] T012 [US1] Implement `engine/src/radic_delivery/release/
      selector.py`: `select(candidates, ready_tickets, dev_green_failed,
      non_jira_prs) -> Selection` — covering every classification per
      data-model.md (ready/held-back/non-jira-pr/not-found), per
      research.md D4 — satisfies spec FR-002 through FR-008 (depends on
      T004)
- [X] T013 [US1] Implement `engine/src/radic_delivery/release/
      manifest.py`: `build_manifest(selection, repo, base_branch,
      base_sha, release_id, initiator, kind) -> ProposeResult`, validated
      via `jsonschema.Draft202012Validator` against the corrected schema
      — satisfies spec FR-009 (depends on T002, T003, T004)
- [X] T014 [US1] Wire `release propose` into `cli.py`'s existing
      `release_app`: remove `"propose"` from `_RELEASE_NOT_IMPLEMENTED`;
      options `--repo`, `--base`, `--repo-dir`, `--change-notes-dir`,
      `--tickets`, `--non-jira-prs`, `--dev-green-failed`, `--since-sha`,
      `--release-id`, `--out-dir`, `--dry-run`, `--format`; computes
      `release_id` default per research.md D5; writes the manifest
      locally under `<out-dir>/releases/<release_id>.json` unless
      `--dry-run` (research.md D6); exit codes per spec FR-009/Edge
      Cases (`INVALID_INPUT` for an unparseable candidate or a manifest
      that fails validation, `INFRA_ERROR` for an invalid `--repo-dir`/
      `--base`) — depends on T010, T011, T012, T013
- [X] T015 [US1] Run T005-T009 against the implementation; fix until
      green

**Checkpoint**: User Story 1 fully functional — ready tickets are
correctly selected and grouped into a schema-valid draft manifest. This
alone is a demonstrable MVP.

---

## Phase 4: User Story 2 - Work that isn't ready is held back, visibly and specifically (P1)

**Goal**: a not-ready ticket and a dev-green-failed ticket are each held
back with a specific, distinguishable reason — never silently included,
never silently dropped.

### Tests for User Story 2

- [X] T016 [P] [US2] Unit test in `test_release_propose_selector.py`: a
      candidate ticket not listed in `ready_tickets` is held back with
      reason `"not Ready for Review"` (Acceptance Scenario 1)
- [X] T017 [P] [US2] Unit test (same file): a ready ticket whose commit
      is listed in `dev_green_failed` is held back with a reason naming
      that commit, distinguishable from the not-ready reason (Acceptance
      Scenario 2)
- [X] T018 [P] [US2] Unit test (same file): a ticket listed as ready and
      with no failing commit appears in the proposed selection, never in
      held-back (Acceptance Scenario 3)
- [X] T019 [P] [US2] Unit test in `test_release_propose_cli.py`: CLI
      end-to-end confirms both held-back reasons appear correctly in
      `--format json`'s `held_back` list

### Implementation for User Story 2

- [X] T020 [US2] Close any gaps T016-T018 reveal in `selector.py`'s
      held-back branch (T012) — the not-ready/dev-green-failed
      distinction should already be covered by research.md D4's design;
      this task is verification-and-fix, not new design
- [X] T021 [US2] Run T016-T019 against the implementation; fix until
      green

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - A pull request merged without a Jira ticket is handled explicitly (P2)

**Goal**: an explicitly-listed ticket-less PR is included with placeholder
`reason`/`second_approver` values; an unlisted one never appears anywhere;
a listed-but-not-found one is reported distinctly.

### Tests for User Story 3

- [X] T022 [P] [US3] Unit test in `test_release_propose_selector.py`: a
      ticket-less candidate (`jira_key == "None"`) whose PR is explicitly
      listed appears in `non_jira_prs` with `reason == "MISSING"` and
      `second_approver is None` (Acceptance Scenario 1)
- [X] T023 [P] [US3] Unit test (same file): the identical ticket-less
      candidate, when its PR is **not** explicitly listed, appears
      nowhere — not proposed, not held back (Acceptance Scenario 2)
- [X] T024 [P] [US3] Unit test (same file): an explicitly-listed PR number
      with no matching candidate is reported in
      `non_jira_prs_not_found`, distinguishable from a successfully
      included one (Edge Case, spec FR-008)
- [X] T025 [P] [US3] Unit test in `test_release_propose_cli.py`: CLI
      end-to-end confirms the non-Jira-PR path in `--format json`

### Implementation for User Story 3

- [X] T026 [US3] Close any gaps T022-T024 reveal in `selector.py`'s
      non-Jira-PR branch (T012) — verification-and-fix, not new design
- [X] T027 [US3] Run T022-T025 against the implementation; fix until
      green

**Checkpoint**: all three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T028 [P] Update `engine/README.md`'s command-surface table: move
      `release propose` from "not implemented yet" to documented
      (describing the readiness/dev-green explicit-input boundary and the
      `--dry-run` local-write behavior), and update the "8 of 23
      implemented, 15 pending" counts this README currently states
- [X] T029 Run `specs/008-release-propose/quickstart.md` end-to-end
      manually (including the real local git repo setup) and confirm
      every command shown behaves as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
  (the corrected schema and result types are shared)
- **User Stories (Phase 3-5)**: all depend on Foundational; US2 and US3
  both extend US1's `selector.py` (T012) and `cli.py` wiring (T014), so
  US1 should land first even though US2/US3's test cases are independent
  of each other
- **Polish (Phase 6)**: depends on all three stories

### Parallel Opportunities

- T003 and T004 in parallel; T005-T009 in parallel; T016-T019 in
  parallel; T022-T025 in parallel
- T010 and T011 in parallel (different files, no dependency on each
  other) once T004 exists

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a
demonstrable, independently valuable capability — a trustworthy,
schema-valid draft selection of ready work — before the held-back
visibility (US2) or ticket-less-PR handling (US3) exist. Given how
interdependent the underlying selection logic is (one function covering
every classification), all three stories are realistically a single
short implementation pass, but remain separated here for clear,
independently-verifiable checkpoints, consistent with specs/005's and
specs/006's precedent for similarly small, indivisible core logic.
