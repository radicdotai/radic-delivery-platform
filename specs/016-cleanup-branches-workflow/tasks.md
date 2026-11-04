# Tasks: Cleanup Workflow (branches scope only)

**Input**: Design documents from `/specs/016-cleanup-branches-workflow/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Builds on**: `engine/src/radic_delivery/release/git_history.py`
(specs/009/011, reused — `is_ancestor`/`commit_timestamp`/`delete_branch`/
`current_branch`; extended with a new `list_branches` primitive).

**Tests**: included for US1 (`cleanup branches`) — real git fixtures,
same discipline as `release backport`'s own tests. US2 (`cleanup.yml`)
has no pytest tests — validated by `actionlint`/`zizmor` only, the same
bar `hotfix-backport.yml` (specs/015) already achieved with zero findings.

**Organization**: tasks are grouped by user story (US1 = P1 `cleanup
branches`, US2 = P2 `cleanup.yml`). US2 depends on US1 existing (the
workflow calls the new command).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Add `list_branches(repo_dir, pattern) -> list[str]` to
      `engine/src/radic_delivery/release/git_history.py` (real `git
      for-each-ref --format=%(refname:short) refs/heads/<pattern>` call,
      raising `GitHistoryError` on failure, matching every other
      primitive in this module)
- [X] T002 Create `engine/src/radic_delivery/cleanup/__init__.py` and
      `engine/src/radic_delivery/cleanup/result.py` (`KeptBranch`,
      `CleanupBranchesResult` dataclasses per data-model.md)

**Checkpoint**: `uv run python -c "import radic_delivery.cleanup.result"`
succeeds from `engine/`

---

## Phase 2: User Story 1 - A fast-forwarded release branch is cleaned up automatically, never a protected branch (P1) 🎯 MVP

**Goal**: `radic-delivery cleanup branches` fully implemented — finds
every `release/**` branch merged into `main` and past the retention
window, deletes it (unless dry-run), and reports every candidate's
outcome by name; `main`/`dev`/the checked-out branch are never candidates.

**Independent Test**: build a real repo with a merged-and-old release
branch, a merged-but-recent one, and an unmerged one; confirm a dry run
reports correctly without deleting, and a real run deletes only the
first.

### Tests for User Story 1

- [X] T003 [P] [US1] Unit test in `engine/tests/unit/
      test_cleanup_branches.py` (real git fixture, mirroring
      `test_release_backport.py`'s own fixture style): a merged,
      sufficiently-old release branch is deleted on a real (non-dry-run)
      run and named in `deleted` (Acceptance Scenario 1)
- [X] T004 [P] [US1] Unit test (same file): a merged but too-recent
      release branch is kept, named with reason `too_recent` (Acceptance
      Scenario 2)
- [X] T005 [P] [US1] Unit test (same file): an unmerged release branch is
      kept, named with reason `not_yet_merged` (Acceptance Scenario 3)
- [X] T006 [P] [US1] Unit test (same file): `main`, `dev`, and the
      currently-checked-out branch are never deleted or reported, even
      when deliberately shaped to satisfy the merge/age conditions
      (Acceptance Scenario 4)
- [X] T007 [P] [US1] Unit test (same file): a dry run reports the exact
      same `deleted`/`kept` lists a real run would, but performs no
      actual deletion (Acceptance Scenario 5)
- [X] T008 [P] [US1] Unit test (same file): zero `release/**` branches
      present reports empty `deleted`/`kept` (spec Edge Case); all
      `release/**` branches unmerged reports all kept (spec Edge Case)
- [X] T009 [P] [US1] Unit test (same file): CLI-level — `cleanup branches`
      exits `0` on every normal run (dry or real, with or without
      deletions); exits `4` (`INFRA_ERROR`) on an unresolvable
      `--repo-dir`; both `--format json`/`--format text` report
      `deleted`/`kept`/`dry_run`

### Implementation for User Story 1

- [X] T010 [US1] Implement `engine/src/radic_delivery/cleanup/
      branches.py`: `cleanup_branches(*, repo_dir, retention_days, dry_run)
      -> CleanupBranchesResult` — lists `release/**` branches via
      `list_branches` (T001), excludes `main`/`dev`/`current_branch()`
      (research.md D4), for each remaining candidate checks
      `is_ancestor(tip, "main")` and `commit_timestamp(tip)` against
      `retention_days`, classifies as deleted/`too_recent`/
      `not_yet_merged`, calls `delete_branch` for each to-delete candidate
      only when `dry_run` is false (research.md D2-D3, D6) — satisfies
      spec FR-001 through FR-005
- [X] T011 [US1] Wire `cleanup branches` into `cli.py` as a new
      `cleanup_app` Typer group: options `--repo-dir`, `--retention-days`
      (default `14`), `--dry-run/--no-dry-run` (default dry-run true),
      `--format`; exit codes per research.md D6 — depends on T010
- [X] T012 [US1] Run T003-T009 against the implementation; fix until green

**Checkpoint**: User Story 1 fully functional — `cleanup branches`
correctly identifies, protects, and (when not dry-run) deletes exactly
the right branches. This alone is a demonstrable MVP.

---

## Phase 3: User Story 2 - The cleanup runs through this platform's own real, reviewable automation (P2)

**Goal**: `.github/workflows/cleanup.yml` fully authored — a `branches`
job that runs the already-real `cleanup branches` command and pushes each
reported deletion to the remote.

**Independent Test**: `actionlint`/`zizmor` both report zero error/
warning findings; a manual read-through confirms the job matches
Reference 2 §3.11's contract (inputs/outputs/secrets/permissions) for the
`branches` scope, and refuses cleanly for any other `scope` value.

### Implementation for User Story 2

- [X] T013 [US2] Write `.github/workflows/cleanup.yml`: `on:
      workflow_call` with inputs `scope`, `retention_days`, `dry_run`
      (defaults per research.md D3/spec FR-005); outputs `deleted_count`,
      `kept_count`, `report_uri`; secrets `DELIVERY_BOT_APP_ID`/
      `DELIVERY_BOT_PRIVATE_KEY`; permissions `contents: write`,
      `id-token: write` — per Reference 2 §3.11
- [X] T014 [US2] Write the job's steps: refuse cleanly if
      `inputs.scope != 'branches'` (research.md D5); checkout; mint the
      bot App token; run `radic-delivery cleanup branches`; for each
      branch in the result's `deleted` list (when not dry-run), `git push
      origin --delete <branch>`; upload the JSON result as the
      `report_uri` artifact; set `deleted_count`/`kept_count` outputs
      (research.md D5, spec FR-006)
- [X] T015 [US2] Run `actionlint .github/workflows/cleanup.yml` and
      `uvx zizmor .github/workflows/cleanup.yml`; fix until both report
      zero error/warning findings

**Checkpoint**: both user stories complete. This platform now has 6 of 12
reusable workflows built.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T016 [P] Update `engine/README.md`'s command-surface table: add
      `cleanup branches` as documented (noted as outside Reference 3's
      CLI table like `release backport`/`render-pr-body`)
- [X] T017 [P] Update `engine/README.md`'s reusable-workflow count (5 of
      12 built → 6 of 12, naming `cleanup` alongside the other five)
- [X] T018 Run `uv run pytest -q`, `uv run ruff check .`, and
      `uv run mypy src/` from `engine/`; fix until clean
- [X] T019 Run `specs/016-cleanup-branches-workflow/quickstart.md`'s
      commands end-to-end manually and confirm every one behaves as
      documented; run `actionlint`/`zizmor` against the new workflow file
      per quickstart.md's final section

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **User Story 1 (Phase 2)**: depends on Setup only
- **User Story 2 (Phase 3)**: depends on US1 being complete (the workflow
  calls `cleanup branches`, which must exist first)
- **Polish (Phase 4)**: depends on both stories

### Parallel Opportunities

- T003-T009 in parallel (all real-git-fixture tests, independent cases)
- T016 and T017 in parallel

## Implementation Strategy

**MVP first**: Phase 1-2 (Setup, US1) deliver a demonstrable,
independently valuable, fully-tested capability — correct, protection-
guaranteed branch cleanup — before the workflow (US2) is authored. Phase 3
is sequenced after US1 specifically because it depends on US1's command
existing, the same real dependency specs/014/015's own two stories had.
