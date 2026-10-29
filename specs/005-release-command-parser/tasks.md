# Tasks: Release Slash-Command Parser and Authorization Check

**Input**: Design documents from `/specs/005-release-command-parser/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md
**Builds on**: nothing from specs/001-004 — see data-model.md's "Relationship to prior features' entities"

**Tests**: included — spec.md's Acceptance Scenarios require specific,
distinguishable classifications, same as prior features. Every test is a
pure function call; no fixtures, no subprocess, no `tmp_path`.

**Organization**: tasks are grouped by user story (US1 = P1 valid+authorized
recognition, US2 = P1 ordinary-comment non-classification, US3 = P2
malformed rejection, US4 = P2 unauthorized rejection).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create `engine/src/radic_delivery/release_commands/{__init__.py,
      grammar.py, authorization.py, result.py}` as empty module skeletons

**Checkpoint**: `uv run python -c "import radic_delivery.release_commands"`
succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the `ParsedCommand`/`CommandCheckResult` shape every story
extends.

- [ ] T002 Write `engine/src/radic_delivery/release_commands/result.py`:
      `ParsedCommand`, `CommandCheckResult` dataclasses per data-model.md,
      with JSON serialisation (`to_dict`)

**Checkpoint**: types exist and are importable

---

## Phase 3: User Story 1 - A valid, authorized command is recognized precisely (P1) 🎯 MVP

**Goal**: all six forms are correctly matched and their arguments extracted,
for an authorized author.

**Independent Test**: feed each of the six exact forms, from a release
manager, and confirm each is `accepted` with the right form name and
arguments; confirm verb case-insensitivity.

### Tests for User Story 1

- [ ] T003 [P] [US1] Unit test in
      `engine/tests/unit/test_release_grammar.py`: each of the six exact
      command strings parses to `status="recognized"` with the correct
      `form` and `args` (Acceptance Scenarios 1-5)
- [ ] T004 [P] [US1] Unit test (same file): the same six commands with the
      verb in uppercase/mixed case still parse identically (Acceptance
      Scenario 6)
- [ ] T005 [P] [US1] Unit test (same file): reasonable whitespace variation
      (extra spaces between tokens, trailing whitespace) is still
      recognized (spec Edge Case)
- [ ] T006 [P] [US1] Unit test in
      `engine/tests/unit/test_release_authorization.py`: a `recognized`
      `ParsedCommand` whose author is in the release-managers list is
      `accepted` (Acceptance Scenario 1 of this story, via the
      authorization layer)
- [ ] T007 [P] [US1] Unit test in `engine/tests/unit/test_release_cli.py`:
      the CLI, given `/release remove RAD-123` on stdin from an authorized
      author, exits `0` and reports `accepted`; `--format json`/`--format
      text` report the same facts (FR-012)

### Implementation for User Story 1

- [ ] T008 [US1] Implement `engine/src/radic_delivery/release_commands/
      grammar.py`: `parse(first_line: str) -> ParsedCommand` using six
      per-form regexes with scoped inline-flag verb case-insensitivity
      (research.md D2) — satisfies FR-002, FR-004, FR-005
- [ ] T009 [US1] Implement `engine/src/radic_delivery/release_commands/
      authorization.py`: `authorize(parsed: ParsedCommand, author: str,
      release_managers: list[str], tech_lead: str) -> CommandCheckResult`
      — for this story, only the "author in release_managers" path
      (depends on T008)
- [ ] T010 [US1] Wire `release command` in `cli.py` as a new command group
      (there is no pre-existing stub to replace): reads the comment's first
      line from `--comment-file` or stdin, calls `grammar.parse` then
      `authorization.authorize`, maps `classification` to `ExitCode.OK`
      (accepted/not_a_command) — both `--format json`/`--format text`
      (FR-012) — depends on T008, T009
- [ ] T011 [US1] Run T003-T007 against the implementation; fix until green

**Checkpoint**: User Story 1 fully functional — this alone is a
demonstrable MVP (recognize and authorize a real command end to end)

---

## Phase 4: User Story 2 - An ordinary comment is quietly not a command (P1)

**Goal**: non-command text, command-adjacent text, and multi-line comments
are all classified `not_a_command`, never as an error.

### Tests for User Story 2

- [ ] T012 [P] [US2] Unit test in `test_release_grammar.py`: ordinary
      conversation text parses to `status="not_a_command"` (Acceptance
      Scenario 1)
- [ ] T013 [P] [US2] Unit test (same file): a line merely mentioning
      "release" without the required leading `/release`/`/research` shape
      parses to `not_a_command` (Acceptance Scenario 2)
- [ ] T014 [P] [US2] Unit test (same file): a multi-line comment whose
      first line is not a command is `not_a_command` even when a later
      line looks like one (Acceptance Scenario 3)
- [ ] T015 [P] [US2] Unit test (same file): an empty or whitespace-only
      comment body parses to `not_a_command` (spec Edge Case)
- [ ] T016 [P] [US2] Unit test in `test_release_cli.py`: the CLI, given
      ordinary text on stdin, exits `0` and reports `not_a_command`

### Implementation for User Story 2

- [ ] T017 [US2] Extend `grammar.py`'s `parse` with the NOT_A_COMMAND
      pre-check (research.md D3): only the first line (split on `\n`,
      first element) is ever considered, and a line not starting with
      `/release` or `/research` followed by whitespace/end-of-line short-
      circuits to `not_a_command` before any per-form regex runs (depends
      on T008)
- [ ] T018 [US2] Run T012-T016 against the implementation; fix until green

**Checkpoint**: User Stories 1 AND 2 both work independently — together
they are the complete classification behaviour the feature exists for

---

## Phase 5: User Story 3 - A broken command is rejected with a specific reason (P2)

**Goal**: an attempted-but-malformed command is distinguishable from both
`not_a_command` and `unauthorized`.

### Tests for User Story 3

- [ ] T019 [P] [US3] Unit test in `test_release_grammar.py`: `/release`
      followed by an unrecognized verb parses to `status="malformed"`
      (Acceptance Scenario 1)
- [ ] T020 [P] [US3] Unit test (same file): `/release add RAD-123` with no
      `reason:` text parses to `malformed`, naming the missing argument in
      `detail` (Acceptance Scenario 2)
- [ ] T021 [P] [US3] Unit test (same file): `/release waive` followed by
      anything other than the exact literal `dev-green` parses to
      `malformed` (Acceptance Scenario 3)
- [ ] T022 [P] [US3] Unit test (same file): `/research` followed by a verb
      other than `close` parses to `malformed` (Acceptance Scenario 4)
- [ ] T023 [P] [US3] Unit test in `test_release_cli.py`: the CLI, given a
      malformed command on stdin, exits `2`

### Implementation for User Story 3

- [ ] T024 [US3] Extend `grammar.py`'s per-form regex matching (T008) so
      that once NOT_A_COMMAND is ruled out, failing every per-form regex
      for the matched noun produces `status="malformed"` with a specific
      `detail` (which verb was attempted and why it didn't match) — mostly
      already exercised by T008/T017; this task closes any gaps T019-T022
      reveal
- [ ] T025 [US3] Wire the `malformed` classification to `ExitCode.
      INVALID_INPUT` in `cli.py` (depends on T010)
- [ ] T026 [US3] Run T019-T023 against the implementation; fix until green

**Checkpoint**: User Stories 1-3 all independently functional

---

## Phase 6: User Story 4 - An unauthorized author is told exactly why (P2)

**Goal**: both the general release-managers rule and the Tech-Lead-only
rule produce distinguishable refusals.

### Tests for User Story 4

- [ ] T027 [P] [US4] Unit test in `test_release_authorization.py`: a
      syntactically valid `release_remove` from a non-release-manager is
      `unauthorized`, with a detail naming the release-managers rule
      (Acceptance Scenario 1)
- [ ] T028 [P] [US4] Unit test (same file): a syntactically valid
      `release_waive_dev_green` from a release manager who is not the Tech
      Lead is `unauthorized`, with a detail distinguishable from T027's
      (Acceptance Scenario 2)
- [ ] T029 [P] [US4] Unit test (same file): the same Tech-Lead-only command
      from the Tech Lead themselves is `accepted` (Acceptance Scenario 3)
- [ ] T030 [P] [US4] Unit test in `test_release_cli.py`: the CLI, given an
      unauthorized author's valid command, exits `3`

### Implementation for User Story 4

- [ ] T031 [US4] Extend `authorization.py`'s `authorize` (T009) with the
      `release_waive_dev_green`-specific Tech-Lead check, applied before
      the general release-managers check so its refusal detail is
      distinguishable (data-model.md's `CommandCheckResult.detail`)
- [ ] T032 [US4] Wire the `unauthorized` classification to
      `ExitCode.POLICY_FAILURE` in `cli.py` (depends on T010)
- [ ] T033 [US4] Run T027-T030 against the implementation; fix until green

**Checkpoint**: all four user stories independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T034 [P] Add `--comment-file`/stdin input handling in `cli.py` with
      no `--comment-body` text flag offered at all (research.md D4 — a
      deliberate omission, not an oversight)
- [ ] T035 [P] Update `engine/README.md`'s command-surface table: add
      `release command`, documenting its four-way classification and exit
      codes, and that every other `release` subcommand remains unimplemented
- [ ] T036 Run `specs/005-release-command-parser/quickstart.md` end-to-end
      manually and confirm every command shown behaves as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
- **User Stories (Phase 3-6)**: all depend on Foundational; US2-US4 all
  extend US1's `grammar.py`/`authorization.py`/`cli.py` (T008-T010), so US1
  should land first even though US2/US3/US4 do not depend on each other
- **Polish (Phase 7)**: depends on all four stories

### Parallel Opportunities

- T003-T007 in parallel; T012-T016 in parallel; T019-T023 in parallel;
  T027-T030 in parallel
- Once US1 lands, US2, US3, and US4 can be staffed in parallel, since they
  extend different parts of the same small module set without touching
  each other's test cases

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a
demonstrable, independently valuable capability — recognizing and
authorizing a real command end to end — before the three rejection paths
(US2, US3, US4) are layered on. Given how small and interdependent the
underlying module set is (three files, no external dependency), all four
stories are realistically a single short implementation pass, but remain
separated here for clear, independently-verifiable checkpoints.
