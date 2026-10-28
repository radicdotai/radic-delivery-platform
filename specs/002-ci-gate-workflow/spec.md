# Feature Specification: Central CI Reusable Workflow (`ci-gate` mode)

**Feature Branch**: `002-ci-gate-workflow`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "Central CI reusable workflow, ci-gate mode — the
platform's own GitHub Actions reusable workflow that every service repo's PR
runs against, plus the engine command that powers it. Reads a service's
`.radic/service.yml` descriptor (built in feature 001), runs the lint/
typecheck/unit-test tools it declares, enforces the descriptor's coverage
floor and the zero-skip-budget rule, and reports a single pass/fail gate
result — so a PR into a service repo is blocked automatically when it fails
this platform's quality bar, without that repo holding any CI logic of its
own. Defers `release-gate` mode, real mutation-test execution, and the
`deploy_lint`/`test_inventory_uri` outputs, each visibly rather than
silently."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A failing change is blocked automatically (Priority: P1)

A contributor opens a pull request against a service repo (for example
`web-bff` or `fastapi-backend`). Their change has a lint violation, a type
error, or a failing unit test. Today, nothing in that repo enforces this
platform's quality bar consistently — each repo's CI is a diverged copy.
They need the same required check, defined once, to catch this automatically
and block the merge, regardless of which of the seven service repos they are
contributing to.

**Why this priority**: this is the platform's entire reason to exist for CI —
without an automatic, blocking, centrally-defined gate, every other
capability in this program (coverage floors, skip-budget enforcement,
eventual release gating) has nothing to attach to. It delivers value
standalone: even before coverage or skip-budget checks exist, "lint/
typecheck/tests must pass before merge, enforced once, not per repo" is
already the fix for the diverged-pipeline problem.

**Independent Test**: can be fully tested by running the gate against a
sample service whose code has a deliberate lint violation, a deliberate type
error, and a deliberate failing test (one at a time), and confirming each one
alone is enough to fail the gate — independent of coverage or skip-budget
behaviour.

**Acceptance Scenarios**:

1. **Given** a service whose code passes lint, type-check, and all unit
   tests, **When** the gate runs against it in `ci-gate` mode, **Then** it
   reports an overall pass.
2. **Given** a service whose code has a lint violation, **When** the gate
   runs, **Then** it reports an overall fail, and the report names lint as
   the failing check.
3. **Given** a service whose code has a type error, **When** the gate runs,
   **Then** it reports an overall fail, and the report names type-checking
   as the failing check.
4. **Given** a service whose code has a failing unit test, **When** the gate
   runs, **Then** it reports an overall fail, and the report names the unit
   test run as the failing check.
5. **Given** a service descriptor declaring the Python toolchain and a
   service descriptor declaring the Node toolchain, **When** the gate runs
   against each, **Then** it runs that service's own declared tools (not a
   fixed, hardcoded toolchain) in both cases.

---

### User Story 2 - Coverage regressions are caught (Priority: P2)

A platform maintainer has set a coverage floor for each service in its
descriptor (feature 001). A contributor's change reduces test coverage below
that floor without breaking any individual test. The gate must catch this
specific regression even though every test still passes.

**Why this priority**: this is the second named quality signal the program
exists to enforce (alongside the pass/fail of individual tests), but it only
matters once the base pass/fail gate from User Story 1 already exists and is
trusted — hence P2.

**Independent Test**: can be fully tested by running the gate against a
service whose measured coverage is deliberately set below its descriptor's
floor (all tests still passing) and confirming the gate fails specifically
for coverage, with the measured percentage reported; and against one at or
above its floor, confirming it passes.

**Acceptance Scenarios**:

1. **Given** a service whose measured coverage is below its descriptor's
   coverage floor, **When** the gate runs, **Then** it reports an overall
   fail, names coverage as the failing check, and reports the measured
   coverage percentage.
2. **Given** a service whose measured coverage meets or exceeds its floor,
   **When** the gate runs, **Then** coverage is reported as passing, with the
   measured percentage shown either way (pass or fail).

---

### User Story 3 - A silently skipped test cannot slip through (Priority: P3)

A contributor's change includes a test that got marked "skip" (deliberately
or accidentally) instead of fixed. Per this platform's zero-skip-budget rule
(constitution Principle III), a skipped test in a required suite is only
acceptable when a Tech-Lead-approved, dated exception for it is recorded in
`policy/exceptions.yml` — never silently.

**Why this priority**: this closes a known, named loophole (a test quietly
marked skipped instead of fixed) that the pass/fail and coverage checks above
do not catch on their own — a skipped test still "passes." It is P3 because
it is the narrowest of the three checks and depends on the exception-lookup
machinery already built in feature 001.

**Independent Test**: can be fully tested by running the gate against a
service with one skipped test and no matching exception recorded (fails),
and against a service with one skipped test that IS covered by an active,
unexpired exception (passes) — independent of the lint/type/coverage checks.

**Acceptance Scenarios**:

1. **Given** a service's unit test run reports one or more skipped tests and
   no active exception covers them, **When** the gate runs, **Then** it
   reports an overall fail, names the skip-budget check as failing, and
   reports how many tests were skipped.
2. **Given** a service's unit test run reports skipped tests that are fully
   covered by an active, unexpired exception recorded in
   `policy/exceptions.yml`, **When** the gate runs, **Then** the skip-budget
   check does not by itself fail the gate.

### Edge Cases

- What happens when the descriptor itself is invalid (the case feature 001
  already handles)? The gate MUST fail immediately with that specific
  reason, before attempting to run any tool, rather than attempting to guess
  reasonable defaults.
- What happens when a declared tool (lint, type-check, or unit test runner)
  cannot be found or cannot be executed at all, as opposed to running and
  reporting failures? This MUST be reported as a distinct outcome from "the
  tool ran and found a problem," so a maintainer isn't told their code is
  low-quality when the real issue is a missing toolchain.
- What happens when a service's coverage floor is expressed as a single
  overall number versus as four separate figures (statements/branches/
  functions/lines, as feature 001's schema allows for Node services)? The
  gate MUST check whichever shape that service's own descriptor declares.
- What happens when the gate is asked to run in `release-gate` mode? It MUST
  report clearly that this mode is not implemented yet by this feature,
  consistent with how other not-yet-built parts of this platform already
  behave — never silently falling back to `ci-gate` behaviour and never
  crashing.
- What happens when mutation testing is requested (the `run_mutation`
  input)? It MUST be visibly reported as not implemented yet rather than
  silently ignored, and MUST NOT by itself fail the gate.
- What happens to the deploy-lint and test-inventory results this gate is
  ultimately supposed to report? Since neither is built yet, the gate MUST
  report them as explicitly not-yet-available rather than omitting them or
  fabricating a value.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST provide one, centrally defined way for a
  service repo's pull request to be checked against this platform's quality
  bar, such that no service repo needs to hold its own copy of that logic.
- **FR-002**: The gate MUST first confirm the service's descriptor is valid
  (reusing feature 001's validation) and MUST fail immediately, before
  running any quality tool, if it is not.
- **FR-003**: For a descriptor declaring the Python toolchain, the gate MUST
  run that service's own lint, type-check, and unit-test tools as declared
  by its descriptor (not a tool hardcoded by this feature).
- **FR-004**: For a descriptor declaring the Node toolchain, the gate MUST
  run that service's own lint, type-check, and unit-test tools as declared
  by its descriptor (not a tool hardcoded by this feature).
- **FR-005**: The gate MUST report an overall pass only when lint,
  type-checking, and the unit-test run all succeed; a failure in any one of
  them MUST produce an overall fail that names which check(s) failed.
- **FR-006**: The gate MUST compare the service's measured test coverage
  against its descriptor's declared coverage floor (in whichever shape that
  descriptor declares — a single overall figure, or separate statements/
  branches/functions/lines figures) and MUST fail when the measurement is
  below the floor, independent of whether every individual test passed.
- **FR-007**: The gate MUST report the measured coverage percentage(s)
  regardless of whether the gate passes or fails.
- **FR-008**: The gate MUST treat a skipped test in the unit-test run as a
  failure unless every skipped test is covered by an active, unexpired
  exception recorded in the platform's policy-exceptions ledger (reusing
  feature 001's exception-check).
- **FR-009**: The gate MUST report how many tests were skipped, regardless
  of whether the gate passes or fails.
- **FR-010**: The gate MUST distinguish "a declared tool could not be found
  or executed at all" from "the tool ran and reported a failure," and MUST
  report which of these occurred.
- **FR-011**: The gate MUST support a mode selector, and MUST only fully
  implement the `ci-gate` mode in this feature; selecting the other named
  mode (`release-gate`) MUST produce a clear, distinct "not implemented yet"
  outcome rather than silently behaving like `ci-gate` or crashing.
- **FR-012**: The gate MUST accept a request to also run mutation testing,
  and MUST report that capability as not implemented yet without it, by
  itself, causing an overall fail.
- **FR-013**: The gate's report MUST include placeholders for the
  deploy-lint result and the test-inventory reference, each explicitly
  marked as not yet available, rather than omitting them or inventing a
  value.
- **FR-014**: The gate's result MUST be available in both a human-readable
  form and a machine-readable form carrying the same facts, consistent with
  every other command this platform's CLI already provides.
- **FR-015**: When a service repo's pull request is checked, an overall gate
  failure MUST be visible as a failed, blocking status on that pull request,
  and an overall pass MUST be visible as a passed status — a contributor or
  reviewer must not need to open raw logs to learn the outcome.
- **FR-016**: The mechanism that performs this check MUST itself be defined
  only in this platform's own repository, never copied into or maintained
  separately by a service repo (Principle I); a service repo's own
  configuration selects nothing more than an exact, published version of it.

### Key Entities

- **Gate Result**: the single, structured outcome of one `ci-gate` run for
  one service at one commit — an overall pass/fail, which named checks
  passed or failed (lint, type-check, unit tests, coverage, skip-budget),
  the measured coverage figure(s), the skipped-test count, and explicit
  not-yet-available placeholders for deploy-lint and test-inventory.
- **Quality Check**: one of the individually named checks a Gate Result is
  built from (lint, type-check, unit tests, coverage, skip-budget); each has
  its own pass/fail/not-executable outcome, independent of the others.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A pull request with a lint violation, a type error, or a
  failing test is blocked 100% of the time, for both a Python-toolchain
  service and a Node-toolchain service.
- **SC-002**: A pull request whose change drops measured coverage below its
  service's declared floor is blocked 100% of the time, even when every
  individual test still passes.
- **SC-003**: A pull request introducing a newly skipped test with no
  matching recorded exception is blocked 100% of the time; one covered by an
  active exception is not blocked by the skip-budget check alone.
- **SC-004**: A reviewer can learn the full gate outcome (pass/fail per
  check, coverage figures, skipped-test count) from the pull request's own
  status and report, without needing to open the underlying tool logs.
- **SC-005**: A service repo onboarding onto this platform adds zero lines
  of CI *logic* of its own for this check — only a reference to an exact,
  published version of the centrally defined one.

## Assumptions

- This feature covers `ci-gate` mode only. `release-gate` mode, real
  mutation-test execution, and the real deploy-lint/test-inventory results
  are deliberately deferred to later features, consistent with how feature
  001 already stubbed command groups it did not yet implement — this spec's
  requirements (FR-011 through FR-013) describe the *visible, honest*
  deferral behaviour expected now, not the deferred capability itself.
- Installing each service's own declared toolchain (its lint/type-check/
  unit-test tools, and its own project dependencies) is assumed to happen
  before this gate runs, as part of the surrounding automation — this
  feature's scope is running the already-installed tools and judging their
  results against the descriptor, not installing a service's dependencies.
- "The platform's own repository" in FR-016 is this repository
  (`delivery-platform`); the mechanism a service repo references is
  published from here at an exact, versioned reference, per Principle I.
- Which recorded exception covers a *unit-test* skip (as opposed to the
  deployed-environment regression-suite exception feature 001 already
  defined) is a convention this feature introduces rather than one the
  architecture specified — flagged for confirmation in research.md, same
  treatment as a similar discrepancy already flagged in feature 001.
- No real service repo exists for this platform to test against yet (the
  seven repos are external and out of this repository's control); this
  feature is validated against representative sample services built for
  that purpose, one per toolchain, standing in for a real service repo's
  pull request.
