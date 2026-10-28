# Tasks: Engine Scaffold & Service Descriptor Validation

**Input**: Design documents from `/specs/001-engine-scaffold/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**Tests**: included — spec.md's Edge Cases and Acceptance Scenarios require
specific failure modes to be verified, so tests are in scope for every story.

**Organization**: tasks are grouped by user story (US1 = P1 validate, US2 = P2
show, US3 = P3 policy check) so each is independently implementable and
testable, per the spec's independent-test statements.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies)
- Exact file paths are given for every task

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Create `engine/pyproject.toml` (uv-managed, Python 3.11, console
      script `radic-delivery = radic_delivery.cli:app`); deps: `typer`,
      `jsonschema`, `pyyaml`; dev deps: `pytest`, `ruff`, `mypy`,
      `types-pyyaml`, `types-jsonschema` (resolver.py's default-application
      is a small hand-written walker, not `pydantic` — see research.md)
- [x] T002 Run `uv sync` in `engine/` and commit the generated lockfile
- [x] T003 [P] Add `engine/pyproject.toml` `[tool.ruff]` and `[tool.mypy]`
      config sections (strict mode for `src/`)
- [x] T004 [P] Create empty package skeleton: `engine/src/radic_delivery/{__init__.py, cli.py, exit_codes.py, descriptor/__init__.py, policy/__init__.py}`

**Checkpoint**: `uv run python -c "import radic_delivery"` succeeds from `engine/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the schema files, exit-code contract, and CLI skeleton every
story depends on.

- [x] T005 Write `engine/src/radic_delivery/exit_codes.py` with the fixed
      enum (`OK=0, INVALID_INPUT=2, POLICY_FAILURE=3, INFRA_ERROR=4`) per
      data-model.md / FR-015
- [x] T006 Write `schemas/service.schema.json` per data-model.md's Service
      Descriptor entity (all required fields, enums, patterns,
      `additionalProperties: false` throughout) — satisfies FR-005, FR-006,
      FR-007
- [x] T007 [P] Write `schemas/exceptions.schema.json` for
      `policy/exceptions.yml` per data-model.md's Policy Exception entity —
      satisfies FR-010
- [x] T008 [P] Write `schemas/release-manifest.schema.json` (shape only, per
      data-model.md) — satisfies FR-012
- [x] T009 [P] Write `schemas/change-note.schema.json` (shape only) —
      satisfies FR-012
- [x] T010 [P] Write `schemas/test-result.schema.json` (shape only) —
      satisfies FR-012
- [x] T011 Write `engine/src/radic_delivery/cli.py`: register every command
      group from the approved architecture (`descriptor`, `gate`, `notes`,
      `tests`, `release`, `deploy`, `policy`, `records`, `rollback`,
      `migrations`); every command not implemented in this feature returns a
      distinct "not implemented yet" result and `exit_codes.INFRA_ERROR` is
      NOT used for this — define and use a dedicated not-implemented path
      that is visibly different from all four real exit codes in its message
      — satisfies FR-002, FR-003
- [x] T012 Write `policy/exceptions.yml` seeded with EXC-0001 (web-bff),
      EXC-0002 (image-studio), EXC-0003 (brand_research) per data-model.md's
      seed table — satisfies FR-011

**Checkpoint**: `uv run radic-delivery --help` lists every command group;
schema files are valid JSON Schema (parse with `jsonschema` with no
documents yet); `policy/exceptions.yml` validates against
`schemas/exceptions.schema.json`

---

## Phase 3: User Story 1 - Validate a service descriptor before it reaches CI (P1) 🎯 MVP

**Goal**: `radic-delivery descriptor validate <path>` fully implemented.

**Independent Test**: run against all 7 real fixtures (pass) and a broken
variant per failure category (fail, with field path).

### Tests for User Story 1

- [x] T013 [P] [US1] Unit test in
      `engine/tests/unit/test_descriptor_validate.py`: valid descriptor →
      success + `exit_codes.OK` (Acceptance Scenario 1)
- [x] T014 [P] [US1] Unit test (same file): missing required field → failure
      naming the exact field path + `exit_codes.INVALID_INPUT` (Acceptance
      Scenario 2)
- [x] T015 [P] [US1] Unit test (same file): disallowed extra field → failure
      naming the field (Acceptance Scenario 3)
- [x] T016 [P] [US1] Unit test (same file): invalid enum value → failure
      naming the value and the allowed set (Acceptance Scenario 4)
- [x] T017 [P] [US1] Unit test (same file): descriptor with invalid YAML
      syntax → a distinct "parse error" reason, not a schema-violation
      reason (Edge Case 1)
- [x] T018 [P] [US1] Unit test (same file): `post_deploy.suites` empty +
      `exception_id` missing/expired/unresolvable → validation fails with
      that specific reason (Edge Case 2)
- [x] T019 [P] [US1] Unit test (same file): two exception entries sharing an
      id → `policy/exceptions.yml` itself is reported invalid (Edge Case 3)

### Implementation for User Story 1

- [x] T020 [US1] Write `engine/tests/fixtures/{fastapi-backend,web-bff,
      design_service,image-studio,brand_research,frontend-v2,
      operations-console}.yml` reflecting each service's real descriptor
      content from Reference 1b/1c (marking any field the architecture
      itself flags `TODO-VERIFY` the same way, per research.md) — satisfies
      FR-013, SC-002
- [x] T021 [US1] Write `engine/tests/fixtures/broken/` variants: one each for
      missing-required-field, wrong-type, extra-field, invalid-enum,
      invalid-yaml, unresolvable-exception, duplicate-exception-id (7 files)
      — satisfies SC-002
- [x] T022 [US1] Implement `engine/src/radic_delivery/descriptor/
      schema_loader.py`: loads and caches `schemas/service.schema.json`
- [x] T023 [US1] Implement `engine/src/radic_delivery/policy/
      exceptions_schema_loader.py` + `engine/src/radic_delivery/policy/
      exceptions.py` (`load()`, `check(id, as_of) -> active|expired|not_found`)
      — needed by T024's cross-document check and by US3 — satisfies FR-009,
      FR-010
- [x] T024 [US1] Implement `engine/src/radic_delivery/descriptor/
      validator.py`: schema validation via `jsonschema` (field-path +
      reason per failure) plus the cross-document exception-reference check
      from data-model.md, using T023 (depends on T022, T023)
- [x] T025 [US1] Wire `descriptor validate` in `cli.py` to `validator.py`,
      both `--format json` and `--format text` output modes — satisfies
      FR-004, FR-014
- [x] T026 [US1] Run T013-T019 against the implementation; fix until green

**Checkpoint**: User Story 1 fully functional and independently testable —
this alone is a demonstrable MVP per spec.md

---

## Phase 4: User Story 2 - Inspect the fully-resolved descriptor (P2)

**Goal**: `radic-delivery descriptor show <path>` fully implemented.

### Tests for User Story 2

- [x] T027 [P] [US2] Unit test in `engine/tests/unit/test_descriptor_show.py`:
      descriptor omitting optional fields → resolved output includes
      schema-declared defaults, distinguishable from author-set values
      (Acceptance Scenario 1)
- [x] T028 [P] [US2] Unit test (same file): invalid descriptor → `show`
      reports the same validation failure as `validate`, not a partial view
      (Acceptance Scenario 2)

### Implementation for User Story 2

- [x] T029 [US2] Implement `engine/src/radic_delivery/descriptor/
      resolver.py`: applies schema defaults on top of a validator.py-passed
      document, tagging each field as `set` or `default` (depends on T024)
- [x] T030 [US2] Wire `descriptor show` in `cli.py` to `resolver.py`
      (refuses to resolve an invalid descriptor — reuses T024's validation
      first) — satisfies FR-008
- [x] T031 [US2] Run T027-T028 against the implementation; fix until green

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Phase 5: User Story 3 - Check whether a policy exception is active (P3)

**Goal**: `radic-delivery policy exceptions check <id>` fully implemented.

### Tests for User Story 3

- [x] T032 [P] [US3] Unit test in
      `engine/tests/unit/test_policy_exceptions_check.py`: future expiry →
      reported active (Acceptance Scenario 1)
- [x] T033 [P] [US3] Unit test (same file): past expiry → reported expired +
      `exit_codes.POLICY_FAILURE` (Acceptance Scenario 2)
- [x] T034 [P] [US3] Unit test (same file): unknown id → reported "not
      recorded", distinct from active/expired (Acceptance Scenario 3)
- [x] T035 [P] [US3] Unit test (same file): all 3 seeded exceptions
      (EXC-0001/2/3) are active as of their creation date — satisfies SC-004

### Implementation for User Story 3

- [x] T036 [US3] Wire `policy exceptions check <id>` in `cli.py` to
      `policy/exceptions.py`'s `check()` (built in T023), both output modes
      — satisfies FR-009
- [x] T037 [US3] Run T032-T035 against the implementation; fix until green

**Checkpoint**: all three user stories independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T038 [P] Add a repo-root `.github/workflows/engine-ci.yml` that runs
      `uv run pytest -q`, `uv run ruff check .`, `uv run mypy src/` on every
      PR touching `engine/`, `schemas/`, or `policy/` (this repo's own CI,
      distinct from the 12 reusable workflows it will later ship)
- [x] T039 [P] Add `engine/README.md` documenting the command surface,
      exit-code contract, and how to add a new fixture
- [x] T040 Confirm no command or output path reads/prints `.env`,
      `gcs-service-account.json`, `Service Account Radic.rtf`, or a secret
      value — add a unit test asserting the CLI's file-access surface is
      limited to descriptor/exceptions/schema paths (FR-016)
- [x] T041 Run `specs/001-engine-scaffold/quickstart.md` end-to-end manually
      and confirm every command shown behaves as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories
  (schemas and the exceptions file are shared by every story)
- **User Stories (Phase 3-5)**: all depend on Foundational; US2 depends on
  US1's `validator.py` (T024); US3 depends on Foundational's T023 only, not
  on US1/US2, and can proceed in parallel with them
- **Polish (Phase 6)**: depends on all three stories being complete

### Parallel Opportunities

- T003, T004 in parallel after T001
- T007-T010 in parallel after T006 establishes the schema directory
  convention
- All T013-T019 tests in parallel (same file, but independent test cases —
  write together, then implement)
- T027-T028 in parallel; T032-T035 in parallel
- US3 (Phase 5) can be staffed in parallel with US1/US2 once Phase 2 is done,
  since it only depends on T023, not on T024's validator

## Implementation Strategy

**MVP first**: Phases 1-3 (Setup, Foundational, US1) deliver a demonstrable,
independently valuable tool — a working `descriptor validate` against all 7
real services — before US2 or US3 exist. Stop and validate there if the
program needs to re-prioritize.
