# Tasks: Release Pipeline Completion

**Input**: Design documents from `/specs/011-release-pipeline-completion/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Builds on**: specs/008/009's `release/` subpackage — extends
`release/git_history.py` (specs/009) and `release/result.py` (specs/008)
in place; reads/writes the same release-manifest file convention
specs/008/009 already established, with no schema change. `rollback/` is
a brand-new subpackage with no dependency on any prior feature's entities.

**Tests**: included — spec.md's Acceptance Scenarios require specific,
distinguishable pass/fail/refusal outcomes for each of the three
commands, same discipline as every prior feature. Like specs/009, every
git-touching behaviour (`verify-promotion`, `finalise`) is exercised
against a real local git repository; `rollback plan` needs no fixture at
all — pure function, inline assertions (research.md D6).

**Organization**: tasks are grouped by user story (US1 = P1
`release verify-promotion`, US2 = P1 `release finalise`, US3 = P2
`rollback plan`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `engine/src/radic_delivery/release/{verify_promotion.py,
      finalise.py}` as empty module skeletons
- [X] T002 [P] Create `engine/src/radic_delivery/rollback/{__init__.py,
      result.py, planner.py}` as empty module skeletons

**Checkpoint**: `uv run python -c "import radic_delivery.release,
radic_delivery.rollback"` succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the extended git-history primitives and result types every
story's implementation task depends on.

- [X] T003 Extend `engine/src/radic_delivery/release/git_history.py`:
      `tree_sha(repo_dir, commit) -> str` (`<commit>^{tree}`),
      `is_ancestor(repo_dir, ancestor, descendant) -> bool` (`git
      merge-base --is-ancestor`), `tag_exists_at(repo_dir, tag, commit) ->
      bool`, `list_version_tags(repo_dir) -> list[str]` (`git tag --list
      'v*'`), `create_tag(repo_dir, tag, commit) -> None`,
      `fast_forward_branch(repo_dir, branch, target) -> Literal["ok",
      "not_fast_forward"]` (`git checkout <branch> && git merge --ff-only
      <target>`) — per research.md D1/D3
- [X] T004 [P] Extend `engine/src/radic_delivery/release/result.py`: add
      `PromotionVerification` (`ancestry_verified`, `tree_verified`,
      `tag_verified`, `release_digest_equals_stage_digest`, `ok`,
      `detail`) and `FinaliseResult` (`ok`, `manifest`, `reason`, `detail`,
      `tag`) dataclasses per data-model.md, each with `to_dict()`
- [X] T005 [P] Write `engine/src/radic_delivery/rollback/result.py`:
      `RollbackPlan` dataclass (`environment`, `current_release`,
      `current_digest`, `target_release`, `target_digest`,
      `estimated_minutes`, `migrations_reverted`, `no_op`) per
      data-model.md, with `to_dict()`

**Checkpoint**: the six new `git_history.py` functions are importable and
individually callable against a scratch real git repo; `PromotionVerification`,
`FinaliseResult`, `RollbackPlan` are all importable

---

## Phase 3: User Story 1 - A release manager confirms exactly what's about to be promoted (P1) 🎯 MVP

**Goal**: `radic-delivery release verify-promotion` fully implemented —
ancestry/tree/tag checked independently and for real against a release
manifest and a real local git repository; the Cloud-Deploy-digest fact
always reported `not_available`.

**Independent Test**: supply a release head/manifest/expected-tag where
everything matches (all three pass); separately break ancestry only, then
break the expected tag only; confirm each failure is reported
individually without affecting the other two checks.

### Tests for User Story 1

- [X] T006 [P] [US1] Unit test in `engine/tests/unit/
      test_release_git_history.py` (real git fixture, extends specs/009's
      existing fixture pattern): `tree_sha` returns equal values for two
      commits with identical content and a different value when content
      differs; `is_ancestor` true/false cases; `tag_exists_at` true when a
      tag was created at that commit, false when missing or pointing
      elsewhere; `list_version_tags` returns only `v*`-pattern tags,
      sorted; `create_tag` creates a real, readable tag;
      `fast_forward_branch` returns `"ok"` and actually moves the branch
      when a clean fast-forward is possible, `"not_fast_forward"` and
      leaves the branch untouched otherwise
- [X] T007 [P] [US1] Unit test in `engine/tests/unit/
      test_release_verify_promotion.py` (real git fixture): a release
      head that is a real descendant of the manifest's `base.sha`, with
      an unaltered tree and the expected tag present, reports
      `ancestry_verified`/`tree_verified`/`tag_verified` all `true` and
      `ok: true` (Acceptance Scenario 1)
- [X] T008 [P] [US1] Unit test (same file): a release head that is **not**
      a descendant of `base.sha` reports `ancestry_verified: false`,
      distinguishable from (and not affecting) `tree_verified`/
      `tag_verified` (Acceptance Scenario 2)
- [X] T009 [P] [US1] Unit test (same file): a missing `--expected-tag`, and
      separately one that exists but resolves to a different commit, each
      report `tag_verified: false` without affecting
      `ancestry_verified`/`tree_verified` (Acceptance Scenario 3,
      research.md D1)
- [X] T010 [P] [US1] Unit test (same file): regardless of whether
      `--cd-release` is supplied, `release_digest_equals_stage_digest` is
      always `"not_available"` (Acceptance Scenario 4, research.md D2)
- [X] T011 [P] [US1] Unit test (same file): a `--release-head` commit that
      doesn't exist in `--repo-dir` fails clearly with an
      `ExitCode.INFRA_ERROR`-classified error, distinguishable from a
      genuine check failure (spec Edge Case)
- [X] T012 [P] [US1] Unit test in `engine/tests/unit/
      test_release_pipeline_completion_cli.py`: `release verify-promotion`
      on a fully-matching fixture exits `0`; on any one failing check
      exits `3`; on an unusable `--repo-dir`/commit exits `4`; both
      `--format json` and `--format text` report all four facts

### Implementation for User Story 1

- [X] T013 [US1] Implement `engine/src/radic_delivery/release/
      verify_promotion.py`: `verify_promotion(manifest, *, repo_dir,
      release_head, expected_tag, cd_release) -> PromotionVerification` —
      calls `is_ancestor` (T003) against `manifest["base"]["sha"]`,
      `tree_sha` (T003) equality over every `manifest["selection"]`
      commit pair, `tag_exists_at` (T003) for `expected_tag` at
      `release_head`, and always sets
      `release_digest_equals_stage_digest = "not_available"` — satisfies
      spec FR-001, FR-002 (depends on T003, T004)
- [X] T014 [US1] Wire `release verify-promotion` into `cli.py`'s existing
      `release_app`, removing it from `_RELEASE_NOT_IMPLEMENTED`: options
      `--manifest`, `--repo-dir`, `--release-head`, `--expected-tag`,
      `--image`, `--digest`, `--cd-release`, `--format`; exit codes per
      research.md D5 — depends on T013
- [X] T015 [US1] Retarget the stub-swap test that used
      `verify-promotion`/`finalise` as its "still not implemented"
      example (`test_release_cli.py`) at the next remaining stub, if any
      remain, or remove the now-obsolete assertion if `release` has no
      stubs left
- [X] T016 [US1] Run T006-T012 against the implementation; fix until green

**Checkpoint**: User Story 1 fully functional — `release verify-promotion`
independently reports all four facts correctly. This alone is a
demonstrable MVP.

---

## Phase 4: User Story 2 - A fully successful release moves the production line forward exactly once (P1)

**Goal**: `radic-delivery release finalise` fully implemented —
fast-forwards `main`, creates a real semver tag, and updates the manifest
to `status: "finalised"`, refusing cleanly on any mismatch or a
non-fast-forward situation.

**Independent Test**: supply a `prod-deployed` manifest and confirm `main`
is fast-forwarded and tagged exactly once; re-run the same finalisation
and confirm it is refused, naming the manifest's actual state; separately
supply a manifest whose release head is not actually ahead of `main` and
confirm that refusal too.

### Tests for User Story 2

- [X] T017 [P] [US2] Unit test in `test_release_finalise.py` (real git
      fixture): a `prod-deployed` manifest is finalised — `main` is
      fast-forwarded to the release head, a `v<major>.<minor>.<patch>` tag
      is created there, and the returned manifest has
      `status: "finalised"`, `main.fast_forwarded_to`, `main.at`,
      `main.tag` all populated (Acceptance Scenario 1)
- [X] T018 [P] [US2] Unit test (same file): finalising the same
      already-`"finalised"` manifest again is refused with
      `reason: "status_mismatch"`, naming the actual status, and the
      real git repo is left completely unchanged (Acceptance Scenario 2)
- [X] T019 [P] [US2] Unit test (same file): a `prod-deployed` manifest
      whose `release_head` is not actually a fast-forward descendant of
      `main`'s current tip is refused with `reason: "not_fast_forward"`,
      and neither `main` nor any tag is touched (Acceptance Scenario 3)
- [X] T020 [P] [US2] Unit test (same file): a manifest whose
      `release_branch` no longer exists in `--repo-dir` is refused
      cleanly, naming the problem (spec Edge Case)
- [X] T021 [P] [US2] Unit test (same file): tag version auto-bump — no
      prior `v*` tag yields `v1.0.0`; an existing highest tag `v1.2.3`
      yields `v1.2.4` by default; `--bump minor`/`--bump major` bump the
      correct component; an explicit `--tag` overrides the automatic case
      entirely (research.md D3)
- [X] T022 [P] [US2] Unit test (same file): when the manifest already
      records `digests.prod`, a mismatched `--prod-digest` is refused
      with `reason: "digest_mismatch"`; when it doesn't yet record one,
      `--prod-digest` is written into `digests.prod` on success
      (research.md D3)
- [X] T023 [P] [US2] Unit test in `test_release_pipeline_completion_cli.py`:
      `release finalise` on a valid `prod-deployed` manifest exits `0`;
      on a status/digest/release-id mismatch exits `2`; on a
      non-fast-forward or other git-environment problem exits `4`

### Implementation for User Story 2

- [X] T024 [US2] Implement `engine/src/radic_delivery/release/
      finalise.py`: `finalise(manifest, *, repo_dir, release_id,
      prod_digest, tag, bump) -> FinaliseResult` — validates
      `release_id`/`status == "prod-deployed"`/digest consistency first
      (no git touched on any failure), pre-checks fast-forward safety via
      `is_ancestor` (T003), then `fast_forward_branch` (T003); computes
      the next tag via `list_version_tags` (T003) unless `tag` was
      supplied; creates it via `create_tag` (T003); returns the updated
      manifest dict (status, digests.prod, main.*) — satisfies spec
      FR-003, FR-004, FR-005 (depends on T003, T004)
- [X] T025 [US2] Wire `release finalise` into `cli.py`'s `release_app`,
      removing it from `_RELEASE_NOT_IMPLEMENTED`: options `--manifest`,
      `--release-id`, `--prod-digest`, `--repo-dir`, `--tag` (optional),
      `--bump` (optional, default `patch`), `--format`; exit codes per
      research.md D5 — depends on T024
- [X] T026 [US2] Confirm/update the stub-swap test from T015 now that
      `release` has no remaining `_RELEASE_NOT_IMPLEMENTED` entries
- [X] T027 [US2] Run T017-T023 against the implementation; fix until green

**Checkpoint**: User Stories 1 AND 2 both work independently. The
`release` command group now has no stubs left.

---

## Phase 5: User Story 3 - A clear rollback plan is computed before anyone commits to acting on it (P2)

**Goal**: `radic-delivery rollback plan` fully implemented — a pure
computation over fully explicit input, performing no action.

**Independent Test**: supply a current and target release/digest for a
given environment and confirm the plan names both clearly; request the
same inputs twice and confirm both plans are identical; supply identical
current and target releases and confirm a `no_op: true` plan is still
produced, not an error.

### Tests for User Story 3

- [X] T028 [P] [US3] Unit test in `test_rollback_planner.py` (pure, no
      fixture): given a current and target release/digest for an
      environment, the plan names the environment, current state, and
      target exactly as supplied (Acceptance Scenario 1)
- [X] T029 [P] [US3] Unit test (same file): the same inputs produce an
      identical plan when computed twice (Acceptance Scenario 2)
- [X] T030 [P] [US3] Unit test (same file): `--estimated-minutes` and
      `--migrations-reverted` default to `5`/`false` when omitted, and
      are carried through unchanged when supplied (research.md D4)
- [X] T031 [P] [US3] Unit test (same file): `current_release ==
      target_release` produces `no_op: true` rather than an error (spec
      Edge Case)
- [X] T032 [P] [US3] Unit test in `test_release_pipeline_completion_cli.py`:
      `rollback plan` always exits `0`, in both `--format json` and
      `--format text`

### Implementation for User Story 3

- [X] T033 [US3] Implement `engine/src/radic_delivery/rollback/
      planner.py`: `plan(*, environment, current_release, current_digest,
      target_release, target_digest, estimated_minutes, migrations_reverted)
      -> RollbackPlan` — zero I/O, zero git, sets `no_op` when
      `current_release == target_release` — satisfies spec FR-006,
      FR-007 (depends on T005)
- [X] T034 [US3] Replace the `rollback` stub in `cli.py`'s
      `_NOT_IMPLEMENTED_GROUPS` with a real `rollback_app` Typer group:
      `plan` subcommand with options `--env`, `--current-release`,
      `--current-digest`, `--target-release`, `--target-digest`,
      `--estimated-minutes` (optional, default `5`),
      `--migrations-reverted`/`--no-migrations-reverted` (optional,
      default `false`), `--format`; always exits `0` — depends on T033
- [X] T035 [US3] Retarget any `cli.py`-level test asserting `rollback`
      remains stubbed (`test_cli.py`) at the next remaining stubbed
      command group, if any remain
- [X] T036 [US3] Run T028-T032 against the implementation; fix until green

**Checkpoint**: all three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T037 [P] Update `engine/README.md`'s command-surface table: move
      `release verify-promotion`, `release finalise`, and `rollback plan`
      from "not implemented yet" to documented, and update the
      implemented/pending command counts this README currently states
- [X] T038 Run `uv run pytest -q`, `uv run ruff check .`, and
      `uv run mypy src/` from `engine/`; fix until clean
- [X] T039 Run `specs/011-release-pipeline-completion/quickstart.md`
      end-to-end manually and confirm every command shown behaves as
      documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
  (the extended `git_history.py` primitives and the three result types
  are shared)
- **User Stories (Phase 3-5)**: all depend on Foundational only; US1, US2,
  US3 are mutually independent of each other (US2's `finalise` consumes a
  manifest already at `prod-deployed`, not anything US1 produces; US3 is
  a pure computation with no entity relationship to either) — sequenced
  P1 → P1 → P2 here, but could be built in any order or in parallel
- **Polish (Phase 6)**: depends on all three stories

### Parallel Opportunities

- T001 and T002 in parallel; T004 and T005 in parallel (after T003)
- T006-T012 in parallel; T017-T023 in parallel; T028-T032 in parallel
- Once Foundational (Phase 2) completes, US1/US2/US3's entire phases
  could proceed in parallel if staffed — none shares a file with another
  except `cli.py` (T014, T025, T034) and
  `test_release_pipeline_completion_cli.py` (T012, T023, T032), both of
  which touch disjoint sections

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a
demonstrable, independently valuable capability — `release
verify-promotion` reporting all four facts correctly against a real git
repository — before `finalise` (US2) or `rollback plan` (US3) are built.
Given this is the first explicitly-bundled feature, all three stories are
still built in the same implementation pass (per the user's "club
features" instruction), but each remains independently testable and
independently revertible if one needed to be pulled back out.
