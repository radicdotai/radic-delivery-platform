# Tasks: Release-Commands Reusable Workflow

**Input**: Design documents from `/specs/006-release-commands-workflow/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md
**Builds on**: specs/005-release-command-parser (already implemented,
merged) — `release_commands.grammar.parse`, `release_commands.
authorization.authorize`, `CommandCheckResult`; specs/002-ci-gate-workflow
(already implemented, merged) — the `setup-engine` composite action,
`actionlint` already wired into `engine-ci.yml`

**Tests**: included for the engine-side logic (US1, US2) — spec.md's
Acceptance Scenarios require specific, distinguishable mapping outcomes,
same as every prior feature. US3 is pure GitHub Actions YAML (trigger
gating); its "test" is structural validation (`actionlint`/`zizmor`) plus
reading the trigger condition itself, since there is no live webhook
delivery in this sandbox to exercise it end-to-end (research.md D1).

**Organization**: tasks are grouped by user story (US1 = P1 accepted-command
reply, US2 = P1 malformed/unauthorized reply, US3 = P2 PR-only trigger
gating). `WorkflowOutcome`'s shape (data-model.md) is fixed in Foundational;
US1 and US2 together implement `map_outcome()` fully, split along
`CommandCheckResult.classification`'s four values exactly as spec.md's own
two P1 stories split them (US1 owns `accepted`/`not_a_command`, US2 owns
`malformed`/`unauthorized`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Create `engine/src/radic_delivery/release_commands/
      workflow_outcome.py` as an empty module skeleton

**Checkpoint**: `uv run python -c "import radic_delivery.release_commands.workflow_outcome"`
succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the `WorkflowOutcome` shape every story's mapping logic
populates.

- [X] T002 Write the `WorkflowOutcome` dataclass in `workflow_outcome.py`:
      `command` (`Literal["remove","add","nonjira","abort","waive","none"]`),
      `outcome` (`Literal["applied","rejected","ignored"]`), `reply_body`
      (`str | None`), with JSON serialisation (`to_dict`) — satisfies
      data-model.md's WorkflowOutcome entity shape

**Checkpoint**: the type exists and is importable

---

## Phase 3: User Story 1 - A release manager gets an immediate, clear reply (P1) 🎯 MVP

**Goal**: an `accepted` or `not_a_command` `CommandCheckResult` maps
correctly onto `command`/`outcome`/`reply_body`, including the
`research_close` convention, and is exposed via the existing CLI's JSON
output.

**Independent Test**: feed `map_outcome` a `CommandCheckResult` for each of
the six accepted forms and for `not_a_command`, confirming each produces
the exact `command`/`outcome`/`reply_body` data-model.md's table specifies;
confirm the CLI's JSON output carries the same facts.

### Tests for User Story 1

- [X] T003 [P] [US1] Unit test in `engine/tests/unit/
      test_release_workflow_outcome.py`: an `accepted` result for each of
      the five `release_*` forms maps to `command` equal to that form's
      short verb, `outcome == "applied"`, and a `reply_body` naming the
      command and its arguments (Acceptance Scenarios 1-2)
- [X] T004 [P] [US1] Unit test (same file): an `accepted` `research_close`
      result maps to `command == "none"` (research.md D2's flagged gap) and
      `outcome == "applied"`, with `reply_body` still naming `research
      close` specifically
- [X] T005 [P] [US1] Unit test (same file): a `not_a_command` result maps
      to `command == "none"`, `outcome == "ignored"`, `reply_body is None`
      (Acceptance Scenario 3 — no reply is ever posted for this case)
- [X] T006 [P] [US1] Unit test in `engine/tests/unit/test_release_cli.py`:
      `release command --format json` for `/release remove RAD-123` from an
      authorized author includes `workflow_command: "remove"`,
      `workflow_outcome: "applied"`, and a non-null `reply_body`, alongside
      feature 005's unchanged `classification`/`form`/`args` fields

### Implementation for User Story 1

- [X] T007 [US1] Implement `map_outcome(result: CommandCheckResult) ->
      WorkflowOutcome` in `workflow_outcome.py`, covering every
      classification per data-model.md's full mapping table (research.md
      D2) — satisfies spec FR-001, FR-003, FR-006, FR-010
- [X] T008 [US1] Wire `map_outcome`'s result into `cli.py`'s `release
      command`: add `workflow_command`, `workflow_outcome`, `reply_body` as
      additive keys on the existing JSON payload and corresponding lines in
      the text-format output, without modifying any existing key (data-
      model.md) — depends on T002, T007
- [X] T009 [US1] Run T003-T006 against the implementation; fix until green

**Checkpoint**: User Story 1 fully functional — accepted commands (all six
forms) and non-commands map correctly and are visible via the CLI. This
alone is a demonstrable MVP for the engine-side half of this feature.

---

## Phase 4: User Story 2 - A mistaken or unauthorized attempt is refused with a clear reason (P1)

**Goal**: `malformed` and `unauthorized` results map to distinct, correct
`command`/`outcome`/`reply_body` values, including `research_close`'s
refusal path.

**Independent Test**: feed `map_outcome` a malformed result and an
unauthorized result (for each of the six forms), confirming each maps to
`outcome == "rejected"` with a `reply_body` distinguishable from the other
and from an accepted reply.

### Tests for User Story 2

- [X] T010 [P] [US2] Unit test in `test_release_workflow_outcome.py`: a
      `malformed` result maps to `command == "none"`, `outcome ==
      "rejected"`, and a `reply_body` naming what was invalid (Acceptance
      Scenario 1)
- [X] T011 [P] [US2] Unit test (same file): an `unauthorized` result for
      each of the five `release_*` forms maps to `command` equal to that
      form's short verb (not `"none"`) and `outcome == "rejected"`
      (Acceptance Scenario 2)
- [X] T012 [P] [US2] Unit test (same file): an `unauthorized` `research_close`
      result maps to `command == "none"`, `outcome == "rejected"` —
      symmetric with US1's T004 for the refusal path
- [X] T013 [P] [US2] Unit test (same file): a malformed `reply_body` and an
      unauthorized `reply_body` for the same underlying comment text are
      never equal to each other or to an accepted `reply_body` (spec
      SC-002's distinguishability requirement)
- [X] T014 [P] [US2] Unit test in `test_release_cli.py`: `release command`'s
      JSON output for a malformed command and, separately, for an
      unauthorized command, each report the correct additive
      `workflow_command`/`workflow_outcome`/`reply_body` fields

### Implementation for User Story 2

- [X] T015 [US2] Extend `map_outcome` (T007) to close any gaps T010-T013
      reveal — the `malformed`/`unauthorized` branches should already be
      covered by data-model.md's table; this task is verification-and-fix,
      not new design, same as feature 005's equivalent US2/US3 tasks
- [X] T016 [US2] Run T010-T014 against the implementation; fix until green

**Checkpoint**: User Stories 1 AND 2 both work independently — together
they are the complete, fully-tested engine-side mapping this feature's two
P1 stories exist for. Everything remaining is GitHub Actions wiring.

---

## Phase 5: User Story 3 - Only comments on an actual release pull request trigger this at all (P2)

**Goal**: the reusable workflow and its caller exist per the architecture's
contract, and a plain-issue comment can never reach them.

**Independent Test**: read the caller job's trigger condition and confirm
it gates on `github.event.issue.pull_request`; validate every new/changed
workflow file with `actionlint` and `zizmor` and confirm both report zero
findings, in particular no script-injection finding against the comment-
body/reply-text handling (research.md D1/D5).

### Implementation for User Story 3

- [X] T017 [US3] Write `.github/workflows/release-commands.yml` — the
      reusable `workflow_call` workflow per Reference 2 §3.5: inputs
      `descriptor`, `issue_number`, `comment_id`, `actor`; outputs
      `command`, `outcome`, `reply_comment_id`; secrets
      `DELIVERY_BOT_APP_ID`, `DELIVERY_BOT_PRIVATE_KEY`, `ATLASSIAN_URL`,
      `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN`; permissions `issues:
      write`, `pull-requests: write`, `contents: write`. Steps: `./actions/
      setup-engine`; resolve the release-managers team membership and Tech
      Lead identity per research.md D4, failing the step (after a
      best-effort reply) if either cannot be resolved, per research.md D3;
      fetch the triggering comment's body to a file; invoke `radic-delivery
      release command --comment-file ... --author ... --release-managers
      ... --tech-lead ... --format json` via `.platform-engine`; call
      `actions/post-release-command-reply` with the CLI's `reply_body` (if
      non-null) and record its `reply_comment_id` output; set the
      workflow's own `command`/`outcome` outputs directly from the CLI's
      `workflow_command`/`workflow_outcome` fields — satisfies spec FR-001,
      FR-003 through FR-010
- [X] T018 [P] [US3] Write `actions/post-release-command-reply/action.yml`
      — a composite action taking the pull request/issue number, the
      comment id to fetch, and (for the reply step) the reply text as
      inputs; fetches the comment body via the GitHub API into a file
      (never a shell-interpolated variable) and, when given non-empty reply
      text, posts it as a PR comment via the GitHub API, outputting the new
      comment's id — satisfies research.md D5, directly continuing feature
      005's research.md D4 script-injection discipline
- [X] T019 [P] [US3] Write `templates/callers/release.yml`'s `commands`
      job: triggers on `issue_comment: types: [created]`, gated with `if:
      github.event.issue.pull_request` so a comment on a plain issue never
      triggers the job at all (Acceptance Scenario 1, FR-002, SC-004); on
      trigger, calls `release-commands.yml@v1.0.0` with `descriptor`,
      `issue_number: ${{ github.event.issue.number }}`, `comment_id: ${{
      github.event.comment.id }}`, `actor: ${{ github.event.comment.user.
      login }}`
- [X] T020 [US3] Validate the new/changed workflow YAML:
      `actionlint .github/workflows/release-commands.yml
      .github/workflows/engine-ci.yml`; fix any findings
- [X] T021 [US3] Validate the same files with `uvx zizmor
      .github/workflows/release-commands.yml
      actions/post-release-command-reply/action.yml
      templates/callers/release.yml`; fix any script-injection findings —
      confirms research.md D1/D5's "never shell-interpolate comment text"
      design holds structurally, not just in prose

**Checkpoint**: all three user stories independently functional. US3's
`if: github.event.issue.pull_request` gate is itself the acceptance
criterion (verified by reading the condition plus clean `actionlint`/
`zizmor` runs), since no live webhook delivery exists in this sandbox to
exercise it end-to-end.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T022 [P] Add a "Workflow security scan" step to
      `.github/workflows/engine-ci.yml` running `uvx zizmor --min-severity
      medium .github/workflows/release-commands.yml
      actions/post-release-command-reply/action.yml
      templates/callers/release.yml` — scoped to only this feature's new
      files, not the whole tree, after discovering a substantial
      pre-existing `zizmor` backlog in specs/001-004's already-merged
      workflow artifacts that this feature explicitly does not fix
      (research.md D6's documented scope correction)
- [X] T023 [P] Update `engine/README.md`'s description of `release
      command` to mention the new additive `workflow_command`/
      `workflow_outcome`/`reply_body` JSON fields and link to this
      feature's spec, alongside feature 005's existing description
- [X] T024 Run `specs/006-release-commands-workflow/quickstart.md`
      end-to-end: the CLI portions for real, `actionlint`/`uvx zizmor` for
      real against the new YAML; confirm (and note in the run, not just
      assume) that the live comment-to-reply loop cannot be exercised in
      this sandbox, per research.md D1

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS User Stories 1 and 2
  (both extend the same `WorkflowOutcome` shape and the same `map_outcome`
  function)
- **User Stories 1-2 (Phase 3-4)**: both depend on Foundational; US2 extends
  US1's `map_outcome` (T007) and CLI wiring (T008), so US1 should land
  first even though the two stories' test cases never overlap
- **User Story 3 (Phase 5)**: depends only on US1's CLI output shape being
  stable (T008) — the workflow YAML reads `workflow_command`/
  `workflow_outcome`/`reply_body` from the CLI's JSON output, so it needs
  that shape finalized, which happens at the end of US2 in practice, but
  has no logical dependency on US2's specific test cases
- **Polish (Phase 6)**: depends on all three stories

### Parallel Opportunities

- T003-T006 in parallel; T010-T014 in parallel
- T018 and T019 in parallel with each other (different files), both after
  T017 exists so the caller's `uses:` pin and the composite action's
  interface are known
- T022 and T023 in parallel

## Implementation Strategy

**MVP first**: Phases 1-4 (Setup, Foundational, US1, US2) deliver the
complete, fully-tested engine-side mapping — every one of
`CommandCheckResult`'s four classifications correctly becomes a
`command`/`outcome`/`reply_body`, exposed via the existing CLI's JSON
output, before any GitHub Actions YAML is written. Phase 5 (US3) is then a
single, realistically-indivisible slice (the reusable workflow, its one
composite action, and its caller all reference each other's exact
input/output names), followed by Polish closing the `zizmor` tooling gap
and documenting the change.
