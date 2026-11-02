# Tasks: Release Branch Creation and Cherry-Pick

**Input**: Design documents from `/specs/009-release-cut/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md
**Builds on**: specs/008-release-propose (already implemented, merged) —
extends the existing `release/` subpackage (`git_history.py`, `result.py`,
the manifest schema) rather than creating a new one; specs/007's local
change-note record layout

**Tests**: included — spec.md's Acceptance Scenarios require specific,
distinguishable success/refusal outcomes, same discipline as every prior
feature. This is the first feature with **no** external-dependency
boundary at all (research.md): every test, including the conflict-abort
path, runs against a real local git repository, never mocked.

**Organization**: tasks are grouped by user story (US1 = P1 correct
branch+cherry-pick, US2 = P1 clean conflict abort, US3 = P2 missing-
change-note-record safety check). The core orchestration (`cut()`) is
built in full during US1 — including the conflict-handling and
change-note-verification branches — with US2/US3 closing any gaps their
own test cases reveal, the same escalating-implementation pattern as
specs/005/006/008's core logic.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `engine/src/radic_delivery/release/cut.py` as an empty
      module skeleton

**Checkpoint**: `uv run python -c "import radic_delivery.release.cut"`
succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the result type and the real git operations every story
depends on.

- [X] T002 [P] Extend `engine/src/radic_delivery/release/result.py`: add
      the `CutResult` dataclass per data-model.md, with `to_dict()`
- [X] T003 [P] Extend `engine/src/radic_delivery/release/git_history.py`:
      add `commit_timestamp(repo_dir, sha) -> int`, `current_branch
      (repo_dir) -> str`, `create_branch_from(repo_dir, branch_name,
      base_ref)`, `checkout(repo_dir, ref)`, `cherry_pick(repo_dir, sha)
      -> CherryPickOutcome`, `abort_cherry_pick(repo_dir)`,
      `delete_branch(repo_dir, branch_name)` — research.md D1

**Checkpoint**: `CutResult` is importable; the new git operations exist
and are importable

---

## Phase 3: User Story 1 - An approved proposal becomes a real release branch with exactly what was approved (P1) 🎯 MVP

**Goal**: `radic-delivery release cut` fully implemented for the happy
path: validate the manifest, re-verify change-note records, create the
branch, cherry-pick in chronological order, update the manifest.

**Independent Test**: supply an approved draft manifest selecting two
commits for two different tickets from a real local git repository,
cut it, and confirm the resulting branch contains exactly those commits
in order, correctly recorded back into the manifest.

### Tests for User Story 1

- [X] T004 [P] [US1] Unit test in `engine/tests/unit/
      test_release_cut_git_history.py` (real `tmp_path` git repository):
      `create_branch_from` creates and checks out the new branch from the
      given base; `cherry_pick` succeeds for a clean commit;
      `commit_timestamp` correctly orders commits made in sequence;
      `current_branch`/`checkout`/`delete_branch` round-trip correctly
- [X] T005 [P] [US1] Unit test in `engine/tests/unit/
      test_release_cut.py` (real git fixture): a manifest selecting two
      commits for two different tickets, both with change-note records,
      cuts successfully — the resulting branch has both commits, and the
      manifest records each one's `release_sha`/`cherry_pick_x: true`
      (Acceptance Scenario 1)
- [X] T006 [P] [US1] Unit test (same file): a successful cut moves
      `status` from `"proposed"` to `"cut"` and records `release_branch`/
      `release_head` (Acceptance Scenario 2)
- [X] T007 [P] [US1] Unit test (same file): a `kind: "hotfix"` manifest
      cut with `--hotfix` succeeds; the same manifest cut without
      `--hotfix` (or an ordinary manifest cut with it) is refused with
      `reason == "hotfix_mismatch"` (Acceptance Scenario 3); a
      `--release-id` not matching the manifest's own is refused with
      `reason == "release_id_mismatch"`; a manifest whose `status` isn't
      `"proposed"` is refused with `reason == "status_mismatch"`,
      naming the actual status (spec Edge Case) — none of these three
      touch the repository or the manifest
- [X] T008 [P] [US1] Unit test (same file): `dry_run=True` computes the
      full validation and cherry-pick order but creates no branch and
      leaves the manifest unchanged (research.md D6, spec Edge Case)
- [X] T009 [P] [US1] Unit test in `engine/tests/unit/
      test_release_cut_cli.py` (real git fixture): `release cut` on a
      valid manifest exits `0`, updates the manifest file on disk, and
      reports the new branch/commits in `--format json`

### Implementation for User Story 1

- [X] T010 [US1] Implement the git operations in `git_history.py` per
      T003's list (research.md D1)
- [X] T011 [US1] Implement `engine/src/radic_delivery/release/cut.py`:
      `cut(manifest, *, repo_dir, change_notes_dir, release_id, hotfix,
      dry_run) -> CutResult` — manifest validation (research.md D2),
      change-note re-verification (D3, full implementation — this closes
      User Story 3 too, not a partial stub), chronological ordering (D4),
      branch creation + cherry-pick with conflict rollback (D5, full
      implementation — this closes User Story 2 too), manifest update on
      success — satisfies spec FR-001 through FR-008 (depends on T002,
      T010)
- [X] T012 [US1] Wire `release cut` into `cli.py`'s existing
      `release_app`: remove `"cut"` from `_RELEASE_NOT_IMPLEMENTED`;
      options `--manifest`, `--release-id`, `--hotfix`/`--no-hotfix`,
      `--repo-dir`, `--change-notes-dir`, `--dry-run`, `--format`; reads
      the manifest JSON, calls `cut()`, writes the updated manifest back
      to `--manifest`'s path only when `ok` and not `dry_run`; exit codes
      per research.md D7 — depends on T011
- [X] T013 [US1] Run T004-T009 against the implementation; fix until
      green

**Checkpoint**: User Story 1 fully functional — a valid, approved
manifest is correctly turned into a real release branch. This alone is a
demonstrable MVP.

---

## Phase 4: User Story 2 - A cherry-pick conflict stops the whole operation, cleanly (P1)

**Goal**: a commit that conflicts with the current production line aborts
the entire cut, naming the commit, with no trace left in the repository
or the manifest.

### Tests for User Story 2

- [X] T014 [P] [US2] Unit test in `test_release_cut.py` (real git
      fixture: `main` and the selected commit both modify the same line
      differently): the cut fails with `reason ==
      "cherry_pick_conflict"` and `failed_sha` naming the conflicting
      commit; the manifest returned is unchanged (Acceptance Scenario 1)
- [X] T015 [P] [US2] Unit test (same file): after the conflict, `git
      branch --list "release/*"` in the fixture repository shows no
      branch, and the repository is back on its original branch/HEAD
      (Acceptance Scenario 2)
- [X] T016 [P] [US2] Unit test in `test_release_cut_cli.py`: the CLI,
      given the same conflicting fixture, exits `4`; the manifest file on
      disk is byte-for-byte unchanged

### Implementation for User Story 2

- [X] T017 [US2] Close any gaps T014-T016 reveal in `cut.py`'s conflict-
      handling/rollback path (T011) — verification-and-fix, not new
      design (research.md D1/D5 already specify the exact rollback steps)
- [X] T018 [US2] Run T014-T016 against the implementation; fix until
      green

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - A commit that has lost its change-note record stops the cut before anything happens (P2)

**Goal**: a selected commit with no matching local change-note record
stops the cut before any git mutation, naming the commit.

### Tests for User Story 3

- [X] T019 [P] [US3] Unit test in `test_release_cut.py`: a manifest
      selecting a commit with no matching change-note record in
      `change_notes_dir` fails with `reason == "missing_change_note"`
      and `failed_sha` naming it, before any branch is created
      (Acceptance Scenario 1)
- [X] T020 [P] [US3] Unit test (same file): when every selected commit
      has its change-note record, this check does not block the cut
      (Acceptance Scenario 2)
- [X] T021 [P] [US3] Unit test in `test_release_cut_cli.py`: the CLI,
      given a manifest with a missing change-note record, exits `2`

### Implementation for User Story 3

- [X] T022 [US3] Close any gaps T019-T021 reveal in `cut.py`'s
      change-note re-verification (T011) — verification-and-fix, not new
      design (research.md D3 already specifies the exact check)
- [X] T023 [US3] Run T019-T021 against the implementation; fix until
      green

**Checkpoint**: all three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T024 [P] Update `engine/README.md`'s command-surface table: move
      `release cut` from "not implemented yet" to documented (describing
      the fixed-base/chronological-order guarantees and the conflict/
      missing-change-note refusals), and update the implemented/pending
      command counts this README currently states
- [X] T025 Run `specs/009-release-cut/quickstart.md` end-to-end manually
      (including crafting the deliberate conflict scenario) and confirm
      every command shown behaves as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
  (the result type and git operations are shared)
- **User Stories (Phase 3-5)**: all depend on Foundational; US2 and US3
  both extend US1's `cut()` (T011) and `cli.py` wiring (T012), so US1
  should land first even though US2/US3's test cases are independent of
  each other
- **Polish (Phase 6)**: depends on all three stories

### Parallel Opportunities

- T002 and T003 in parallel; T004-T009 in parallel; T014-T016 in
  parallel; T019-T021 in parallel

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a
demonstrable, independently valuable capability — a trustworthy,
correctly-ordered release branch cut from an approved proposal — before
the conflict-abort guarantee (US2) or the change-note safety check (US3)
are separately verified. Given how interdependent the underlying
orchestration is (one function covering validation, verification,
cutting, and rollback), all three stories are realistically a single
short implementation pass, but remain separated here for clear,
independently-verifiable checkpoints, consistent with specs/005/006/008's
precedent for similarly small, indivisible core logic.
