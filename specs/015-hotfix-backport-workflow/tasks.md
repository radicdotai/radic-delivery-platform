# Tasks: Hotfix Backport Workflow

**Input**: Design documents from `/specs/015-hotfix-backport-workflow/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Builds on**: `engine/src/radic_delivery/release/git_history.py`
(specs/009, reused unchanged — `cherry_pick`/`abort_cherry_pick`/
`create_branch_from`/`commit_timestamp`); `schemas/
release-manifest.schema.json` (specs/008, read-only).

**Tests**: included for US1 (`release backport`) — real git fixtures,
same discipline as `release cut`'s own tests. US2
(`hotfix-backport.yml`) has no pytest tests — validated by
`actionlint`/`zizmor` only, the same bar `release-cut.yml` (specs/014)
already achieved with zero findings.

**Organization**: tasks are grouped by user story (US1 = P1 `release
backport`, US2 = P2 `hotfix-backport.yml`). US2 depends on US1 existing
(the workflow calls the new command).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `engine/src/radic_delivery/release/backport.py` as an
      empty module skeleton

**Checkpoint**: `uv run python -c "import radic_delivery.release.backport"`
succeeds from `engine/`

---

## Phase 2: User Story 1 - A hotfix's exact commits are backported, conflicts and all, never silently lost (P1) 🎯 MVP

**Goal**: `radic-delivery release backport` fully implemented — cherry-
picks every selected commit onto a new branch from `--into`, continuing
past any individually-conflicting commit and naming it specifically.

**Independent Test**: backport a real, small hotfix manifest onto a real
local branch once where every commit applies cleanly, and once where one
conflicts, confirming the clean commits land and the conflict is named.

### Tests for User Story 1

- [X] T002 [P] [US1] Unit test in `engine/tests/unit/
      test_release_backport.py` (real git fixture, mirroring
      `test_release_cut.py`'s own fixture style): a hotfix manifest whose
      one recorded commit applies cleanly reports `conflicts: false`,
      `picked_commits` containing that commit, and the new branch
      actually carries it (Acceptance Scenario 1)
- [X] T003 [P] [US1] Unit test (same file): a manifest with two commits
      where the second conflicts reports the first in `picked_commits`,
      the second in `conflicted_commits`, `conflicts: true`, and the
      resulting branch actually carries the first commit's content
      (Acceptance Scenario 2)
- [X] T004 [P] [US1] Unit test (same file): a manifest whose only commit
      conflicts reports `picked_commits: []`, that commit in
      `conflicted_commits`, `conflicts: true`, and the branch still
      exists (created from `--into`, carrying nothing) (Acceptance
      Scenario 3)
- [X] T005 [P] [US1] Unit test (same file): a manifest with zero selected
      commits reports an empty, non-error result; the branch still
      exists (spec Edge Case)
- [X] T006 [P] [US1] Unit test (same file): attempting to backport onto a
      branch name that already exists is refused cleanly (`GitHistoryError`,
      reused from `create_branch_from`'s own existing behaviour — no new
      check needed, spec Edge Case)
- [X] T007 [P] [US1] Unit test (same file): CLI-level — `release
      backport` on a clean manifest exits `0`; on a manifest with a
      conflicting commit still exits `0` (conflicts are a reported fact,
      not a failure, research.md D4); on an existing branch name or an
      unresolvable `--into` exits `4`; both `--format json`/`--format
      text` report `conflicts`/`picked_commits`/`conflicted_commits`

### Implementation for User Story 1

- [X] T008 [US1] Implement `engine/src/radic_delivery/release/
      backport.py`: `BackportResult` dataclass per data-model.md (with a
      `conflicts` property); `backport(manifest, *, repo_dir, into) ->
      BackportResult` — collects selected commits' `release_sha` values
      (tickets + non_jira_prs, same shape as `cut.py`'s own
      `_selected_shas`), orders them via `commit_timestamp`, creates the
      `backport/<release_id>` branch from `into`, then for each commit:
      `cherry_pick`, and on `"conflict"`, `abort_cherry_pick` and record
      it, continuing to the next (research.md D1-D3) — satisfies spec
      FR-001 through FR-003
- [X] T009 [US1] Wire `release backport` into `cli.py`'s existing
      `release_app`: options `--manifest`, `--repo-dir`, `--into`
      (default `dev`), `--format`; exit codes per research.md D4 —
      depends on T008
- [X] T010 [US1] Run T002-T007 against the implementation; fix until green

**Checkpoint**: User Story 1 fully functional — `release backport`
correctly backports clean commits and names every conflict. This alone
is a demonstrable MVP.

---

## Phase 3: User Story 2 - A succeeded hotfix is backported through this platform's own real, reviewable automation (P2)

**Goal**: `.github/workflows/hotfix-backport.yml` fully authored — a
single job, gated on a successful `prod` `workflow_run` for a hotfix
branch, orchestrating the already-real `release backport` command.

**Independent Test**: `actionlint`/`zizmor` both report zero error/
warning findings; a manual read-through confirms the job matches
Reference 2 §3.8's contract exactly (inputs/outputs/secrets/
permissions) and never runs for a non-hotfix or non-successful trigger.

### Implementation for User Story 2

- [X] T011 [US2] Write `.github/workflows/hotfix-backport.yml`: `on:
      workflow_call` with input `hotfix_branch`; outputs `pr_number`,
      `picked_commits`, `conflicts`; secrets `DELIVERY_BOT_APP_ID`/
      `DELIVERY_BOT_PRIVATE_KEY`; permissions `contents: write`,
      `pull-requests: write` — exactly per Reference 2 §3.8
- [X] T012 [US2] Write the job's steps: checkout, mint the bot App token
      (same pattern as `release-cut.yml`), run `radic-delivery release
      backport`, push the resulting branch (the engine itself never
      pushes), open the PR into `dev` — as a draft naming every
      conflicted commit in its body when `conflicts` is `true`, a normal
      PR otherwise (research.md D5, spec FR-005, FR-006)
- [X] T013 [US2] Checked: no `templates/callers/hotfix.yml` exists in
      this repo — confirmed out of scope (Reference 2 §2.6 names a
      `hotfix.yml` caller template, distinct from `release.yml`, not yet
      built here); `hotfix-backport.yml` instead re-checks its own
      success/branch-suffix gate defensively via a new `conclusion`
      input (research.md D5), so it stays safe to invoke without that
      caller existing yet
- [X] T014 [US2] Run `actionlint .github/workflows/hotfix-backport.yml`
      and `uvx zizmor .github/workflows/hotfix-backport.yml` (and the
      caller template, if T013 touched one); fix until both report zero
      error/warning findings

**Checkpoint**: both user stories complete. This platform now has 5 of
12 reusable workflows built.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T015 [P] Update `engine/README.md`'s command-surface table: move
      `release backport` to documented, and update the implemented/
      pending command counts
- [X] T016 [P] Update `engine/README.md`'s reusable-workflow count (4 of
      12 built → 5 of 12, naming `hotfix-backport` alongside `ci`/
      `security`/`release-commands`/`release-cut`)
- [X] T017 Run `uv run pytest -q`, `uv run ruff check .`, and
      `uv run mypy src/` from `engine/`; fix until clean
- [X] T018 Run `specs/015-hotfix-backport-workflow/quickstart.md`'s
      `release backport` commands end-to-end manually and confirm every
      one behaves as documented; run `actionlint`/`zizmor` against the
      new workflow file per quickstart.md's final section

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **User Story 1 (Phase 2)**: depends on Setup only
- **User Story 2 (Phase 3)**: depends on US1 being complete (the
  workflow calls `release backport`, which must exist first)
- **Polish (Phase 4)**: depends on both stories

### Parallel Opportunities

- T002-T007 in parallel (all real-git-fixture tests, independent cases)
- T015 and T016 in parallel

## Implementation Strategy

**MVP first**: Phase 1-2 (Setup, US1) deliver a demonstrable,
independently valuable, fully-tested capability — correct, partial-
conflict-tolerant backporting — before the workflow (US2) is authored.
Phase 3 is sequenced after US1 specifically because it depends on US1's
command existing, the same real dependency specs/014's two stories had.
