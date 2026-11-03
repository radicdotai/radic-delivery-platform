# Tasks: Release Cut Workflow

**Input**: Design documents from `/specs/014-release-cut-workflow/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Builds on**: `engine/src/radic_delivery/release/git_history.py`
(specs/009/011, extended in place); `schemas/release-manifest.schema.json`
(specs/008, read-only) and `schemas/change-note.schema.json` (specs/007,
read-only) — this feature never writes either shape, only reads
already-produced records; `.github/workflows/release-commands.yml` and
`templates/callers/release.yml` (specs/006, the latter extended in place).

**Tests**: included for US1 (`release render-pr-body`) — a real,
pytest-tested engine command, same discipline as every prior feature.
US2 (`release-cut.yml`) has no pytest tests at all — it is validated by
`actionlint`/`zizmor` only, the same bar `ci.yml`/`security.yml`/
`release-commands.yml` were already held to, since this sandbox has no
GitHub Actions runner, live Jira, or live GCP access to execute it
against (research.md D4).

**Organization**: tasks are grouped by user story (US1 = P1 `release
render-pr-body`, US2 = P2 `release-cut.yml` + caller template). US2
depends on US1 existing (the workflow calls the new command), but is
otherwise independently reviewable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `engine/src/radic_delivery/release/render_pr_body.py`
      as an empty module skeleton

**Checkpoint**: `uv run python -c "import radic_delivery.release.render_pr_body"`
succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the one new git primitive both the rendering logic and its
own tests depend on.

- [X] T002 Extend `engine/src/radic_delivery/release/git_history.py`:
      add `changed_paths(repo_dir, base, head) -> set[str]` (`git diff
      --name-only <base> <head>`, research.md D2)

**Checkpoint**: `changed_paths()` is importable and callable against a
scratch real git repo

---

## Phase 3: User Story 1 - A release PR reads exactly like the architecture's own template, every time (P1) 🎯 MVP

**Goal**: `radic-delivery release render-pr-body` fully implemented —
every section of Reference 3's template, deterministically rendered from
a manifest, change-note records, and real git facts.

**Independent Test**: render a PR body from real, hand-built manifests at
several different states (freshly proposed, with non-Jira PRs, with
held-back tickets, approved, gates passing), confirming each section and
the gates checklist's checkbox states match exactly; render the same
manifest twice and confirm byte-identical output.

### Tests for User Story 1

- [X] T003 [P] [US1] Unit test in `engine/tests/unit/
      test_release_render_pr_body.py`: a freshly proposed manifest with
      two selected tickets and no non-Jira PRs/held-back renders the
      selection table with both tickets (title/type looked up from real
      change-note records) and omits the "Released without a Jira key"
      section entirely (Acceptance Scenario 1)
- [X] T004 [P] [US1] Unit test (same file): a manifest with one non-Jira
      PR whose `reason` is `"MISSING"` renders that section, shows the
      reason as missing, and renders the non-Jira-PR gate as not
      satisfied (Acceptance Scenario 2)
- [X] T005 [P] [US1] Unit test (same file): a manifest with one held-back
      ticket renders it with its `reason`/`removed_by` (Acceptance
      Scenario 3)
- [X] T006 [P] [US1] Unit test (same file): a manifest with
      `approvals.release_pr.approver` set renders the "Release PR
      approved" gate item checked (Acceptance Scenario 4)
- [X] T007 [P] [US1] Unit test (same file): a manifest with
      `gates.release_gate.result: "pass"` and
      `gates.stage_regression.result: "pass"` renders both corresponding
      gate items checked (Acceptance Scenario 5)
- [X] T008 [P] [US1] Unit test (same file): rendering the same manifest
      twice produces byte-identical output (Acceptance Scenario 6, spec
      FR-003/SC-002)
- [X] T009 [P] [US1] Unit test (same file): a manifest with zero selected
      tickets renders the selection table empty, not omitted (spec Edge
      Case)
- [X] T010 [P] [US1] Unit test (same file): a missing change-note record
      for a given commit renders that ticket's Title/Type as `(unknown)`
      rather than raising (research.md D2)
- [X] T011 [P] [US1] Unit test in `engine/tests/unit/
      test_release_git_history_diff.py` (real git fixture): `changed_paths()`
      against two real commits reports exactly the files that actually
      differ between them
- [X] T012 [P] [US1] Unit test in `test_release_render_pr_body.py`: a
      manifest with no `release_head` renders the deploy-files-changed
      section as not yet determinable; one with a `release_head` and a
      real git fixture whose diff touches `deploy/run/stage.yaml` renders
      "yes", naming the file (spec FR-004, Edge Case)
- [X] T013 [P] [US1] Unit test (same file): CLI-level — `release
      render-pr-body` on a readable manifest exits `0`; on an unreadable
      manifest or one missing a required top-level field exits `2`; both
      `--format json`/`--format text` report the same rendered body

### Implementation for User Story 1

- [X] T014 [US1] Implement `engine/src/radic_delivery/release/
      render_pr_body.py`: `RenderPrBodyResult` dataclass per
      data-model.md; `_lookup_change_note(change_notes_dir, repo, sha) ->
      tuple[str, str]` (title, type — `"(unknown)"` pair when missing);
      `render(manifest, *, change_notes_dir, repo_dir, migrations_chain)
      -> RenderPrBodyResult` — builds every section per research.md D2,
      calling `changed_paths()` (T002) only when `release_head` is
      present — satisfies spec FR-001 through FR-004 (depends on T002)
- [X] T015 [US1] Wire `release render-pr-body` into `cli.py`'s existing
      `release_app`: options `--manifest`, `--change-notes-dir`,
      `--repo-dir` (default `.`), `--migrations-chain` (optional,
      comma-separated), `--out` (optional), `--format`; exit codes per
      research.md/quickstart (`0` normally, `2` on an unreadable/
      incomplete manifest) — depends on T014
- [X] T016 [US1] Run T003-T013 against the implementation; fix until green

**Checkpoint**: User Story 1 fully functional — `release render-pr-body`
deterministically renders every section from real inputs. This alone is
a demonstrable MVP (reviewable and testable with no workflow involved at
all).

---

## Phase 4: User Story 2 - A release PR is proposed and, once approved, actually cut (P2)

**Goal**: `.github/workflows/release-cut.yml` fully authored — a
`propose` job (manual dispatch) and a `cut` job (approval-triggered),
each thin orchestration over already-real engine commands; the caller
template updated to wire both in.

**Independent Test**: `actionlint`/`zizmor` both report zero findings
against the new workflow and the updated caller template; a manual
read-through confirms the job sequencing matches Technical Design §8's
own ordering and Reference 2 §3.4's contract (inputs/outputs/secrets/
permissions) exactly.

### Implementation for User Story 2

- [X] T017 [US2] Write `.github/workflows/release-cut.yml`'s `propose`
      job (`workflow_dispatch`, inputs `base`/`tickets`/`non_jira_prs`/
      `dry_run`/`hotfix`/`release_id`/`initiator` per Reference 2 §3.4,
      plus the new, flagged `dev_green_failed` manual input per
      research.md D3): resolves ticket readiness via a real Jira JQL
      query (`curl` against `${ATLASSIAN_URL}/rest/api/3/search`, Basic
      auth with `ATLASSIAN_EMAIL`/`ATLASSIAN_API_TOKEN`); calls
      `radic-delivery release propose`; calls `release render-pr-body`;
      opens or updates the release PR idempotently (`gh pr create`/
      `gh pr edit --body-file`) — satisfies spec FR-005
- [X] T018 [US2] Write `.github/workflows/release-cut.yml`'s `cut` job
      (`pull_request_review`, `types: [submitted]`): refuses outright
      (no `release cut` call) unless `review.state == 'approved'`, the
      reviewer isn't the PR's own recorded initiator, and the PR is a
      recognised release PR; re-renders the gates checklist via `release
      render-pr-body` and refuses, naming why, if the non-Jira-PR gate
      isn't satisfied; on success calls `radic-delivery release cut` for
      real, pushes the branch, and updates the PR body — satisfies spec
      FR-006, FR-007 (depends on T017 existing in the same file; no code
      dependency)
- [X] T019 [US2] Declare `release-cut.yml`'s outputs
      (`release_id`/`release_branch`/`pr_number`/`selection_count`/
      `held_back`/`non_jira_prs`/`manifest_path`) and secrets
      (`DELIVERY_BOT_APP_ID`/`DELIVERY_BOT_PRIVATE_KEY`/`ATLASSIAN_URL`/
      `ATLASSIAN_EMAIL`/`ATLASSIAN_API_TOKEN`) and permissions
      (`contents: write`, `pull-requests: write`, `issues: write`,
      `id-token: write`) exactly per Reference 2 §3.4
- [X] T020 [US2] Update `templates/callers/release.yml`: add the `cut`
      job (`workflow_dispatch`, calling `release-cut.yml`'s `propose`
      path) and a `cut-approved` job (`pull_request_review`, calling its
      `cut` path) alongside the already-existing `commands` job; update
      the file's own header comment to reflect it's no longer
      deliberately deferring this piece (specs/006's original Assumption)
- [X] T021 [US2] Run `actionlint .github/workflows/release-cut.yml
      templates/callers/release.yml` and `uvx zizmor
      .github/workflows/release-cut.yml templates/callers/release.yml`;
      fix until both report zero findings

**Checkpoint**: both user stories complete. This platform now has 4 of
12 reusable workflows built.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T022 [P] Update `engine/README.md`'s command-surface table: move
      `release render-pr-body` to documented, and update the implemented/
      pending command counts this README currently states (note: this is
      a new command not previously named in Reference 3's own §6 CLI
      table — flag it the same way `security scan` is already flagged as
      existing outside that table)
- [X] T023 [P] Update `engine/README.md`'s reusable-workflow count (3 of
      12 built → 4 of 12, naming `release-cut` alongside `ci`/`security`/
      `release-commands`)
- [X] T024 Run `uv run pytest -q`, `uv run ruff check .`, and
      `uv run mypy src/` from `engine/`; fix until clean
- [X] T025 Run `specs/014-release-cut-workflow/quickstart.md`'s
      `render-pr-body` commands end-to-end manually and confirm every one
      behaves as documented; run `actionlint`/`zizmor` against the new/
      updated workflow files per quickstart.md's final section

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS US1 (the
  rendering logic needs `changed_paths()`)
- **User Story 1 (Phase 3)**: depends on Foundational only
- **User Story 2 (Phase 4)**: depends on US1 being complete (the workflow
  calls `release render-pr-body`, which must exist first) — this is the
  one bundled feature in this project where the second story has a real
  dependency on the first, not just a shared spec/plan/tasks cycle
- **Polish (Phase 5)**: depends on both stories

### Parallel Opportunities

- T003-T013 in parallel (all pure, inline-fixture tests plus one real-git
  fixture test)
- T022 and T023 in parallel

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a
demonstrable, independently valuable, fully-tested capability —
deterministic PR-body rendering from real manifest/change-note/git
inputs — with zero workflow-authoring risk. Phase 4 (US2) is a
documentation-grade authoring task validated statically, consistent with
every prior reusable workflow this platform has built; it is sequenced
after US1 specifically because it depends on US1's command existing, not
merely for process-cycle convenience like every previous bundled
feature's story ordering.
