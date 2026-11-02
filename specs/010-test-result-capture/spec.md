# Feature Specification: Test-Result Record Capture

**Feature Branch**: `010-test-result-capture`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Test-result record capture — `radic-delivery
records put-test-result`, the command that validates and stores one
test-result record for a release. The architecture fully specifies the
record's schema already (feature 001's intentionally loose placeholder,
now corrected: a nullable release identifier for dev-environment runs
that happen before any release exists, a required scope that must be
'full' specifically for a stage-environment run, and the zero-skip-budget
rule expressed at the schema level — any run reporting a skipped test
must report an overall failing result). The command reads a complete
record from a file, validates it (rejecting anything that violates the
schema's own rules), cross-checks its release identifier against the
caller's, and stores it locally in the same real-path, local-root pattern
already established for the release manifest and change-note records.
Reading these records back to decide anything (a future release gate) is
explicitly out of scope."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A completed test run's result is captured reliably, in one trustworthy shape (Priority: P1)

After a suite of tests finishes running against a dev or stage deploy, the
result needs to be captured as a complete, structured record — in the
same place, in the same shape, every time — so that anything reading
these records later can trust what they contain.

**Why this priority**: this is the entire reason the command exists —
without a reliable, schema-valid record for every test run, nothing
downstream (a future release gate, an audit of what was actually tested)
has anything trustworthy to read.

**Independent Test**: can be fully tested by supplying a complete, valid
test-result record and confirming it's accepted and stored at the
expected location, independent of any rejection-path behaviour.

**Acceptance Scenarios**:

1. **Given** a complete, valid test-result record for a stage-environment
   run, **When** it is submitted, **Then** it is accepted and stored,
   reporting where and its overall result.
2. **Given** a complete, valid test-result record for a dev-environment
   run with no release identifier at all, **When** it is submitted,
   **Then** it is still accepted and stored — a dev run happens
   continuously, often before any release exists, and must never be
   forced to claim a release it isn't part of.
3. **Given** a record whose own release identifier doesn't match what the
   caller specified, **When** it is submitted, **Then** it is rejected,
   naming the mismatch, and nothing is stored.

---

### User Story 2 - A run that skipped tests can never report itself as passing (Priority: P1)

A test run that skipped one or more tests must never be stored as an
overall pass — skipping a test is exactly the situation this platform's
zero-skip-budget principle exists to catch, and a record is the thing a
future gate will trust to enforce it.

**Why this priority**: equally foundational to User Story 1 — a record-
capture command that can be fooled into storing "passed" for a run that
actually skipped something would make every later consumer of these
records untrustworthy, which defeats the entire purpose of capturing them
in the first place.

**Independent Test**: can be fully tested by supplying a record reporting
one or more skipped tests alongside an overall passing result, and
confirming it's rejected, independent of every other validation rule.

**Acceptance Scenarios**:

1. **Given** a record reporting at least one skipped test but an overall
   result of "passed", **When** it is submitted, **Then** it is rejected,
   naming the inconsistency, and nothing is stored.
2. **Given** a record reporting at least one skipped test and an overall
   result of "failed", **When** it is submitted, **Then** it is accepted
   — a skipped test correctly reported as part of an overall failure is
   not a violation.
3. **Given** a record reporting zero skipped tests, **When** it is
   submitted, **Then** this rule does not affect it either way.

---

### User Story 3 - A stage run must carry the completeness a stage run requires (Priority: P2)

A test run against the stage environment is expected to be the full,
complete regression check before a release can proceed — it must
explicitly state that it was the full scope, and it must be tied to a
real release, never left ambiguous about either.

**Why this priority**: this is a stage-specific completeness rule, sequenced
after the two universal P1 rules (correct capture, the skip-budget rule),
since it narrows what's acceptable only for the stage environment
specifically, not every run.

**Independent Test**: can be fully tested by supplying a stage-environment
record missing its release identifier, and separately one missing the
required full-scope declaration, confirming each is rejected for the
specific missing piece.

**Acceptance Scenarios**:

1. **Given** a stage-environment record with no release identifier,
   **When** it is submitted, **Then** it is rejected, naming that a
   release identifier is required for a stage run.
2. **Given** a stage-environment record that doesn't declare itself as the
   full scope, **When** it is submitted, **Then** it is rejected, naming
   that a stage run must be the full scope.
3. **Given** a stage-environment record with both a release identifier and
   the full-scope declaration present, **When** it is submitted, **Then**
   this rule does not block it.

### Edge Cases

- What happens when the record is well-formed JSON but simply missing a
  required field, or has a field of the wrong shape entirely (not related
  to the skip-budget or stage-completeness rules)? It is rejected, naming
  the specific field and what's wrong with it.
- What happens when the caller doesn't specify a release identifier at
  all (no `--release-id`)? The record's own identifier (or lack of one,
  for a dev run) is used as-is; there is simply nothing to cross-check
  against.
- What happens when the exact same record is submitted twice? Each
  submission is handled independently; storing it again simply overwrites
  the same location with the same content — this feature does not try to
  detect or prevent a duplicate submission.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST read a complete test-result record from a
  file and validate it against this platform's test-result schema before
  storing anything.
- **FR-002**: The system MUST reject a record that fails validation,
  naming specifically which part of it is invalid, and MUST NOT store
  anything in that case.
- **FR-003**: The system MUST accept a record with no release identifier
  at all as valid for a dev-environment run — this is not a missing
  value, it is the correct shape for a run that happens before any
  release exists.
- **FR-004**: The system MUST require a real release identifier for a
  stage-environment record, and MUST reject a stage-environment record
  lacking one.
- **FR-005**: The system MUST require a stage-environment record to
  explicitly declare itself as covering the full test scope, and MUST
  reject one that doesn't.
- **FR-006**: The system MUST reject any record that reports one or more
  skipped tests alongside an overall passing result; a skipped-test
  record reporting an overall failing result MUST be accepted (subject to
  every other rule).
- **FR-007**: When the caller specifies a release identifier and the
  record itself also declares one, the system MUST reject the record if
  the two don't match, naming the mismatch; it MUST NOT silently prefer
  one over the other or silently proceed.
- **FR-008**: On acceptance, the system MUST store the record at a
  location that mirrors this platform's real, shared storage location
  exactly (by release identifier, environment, repository, and test
  suite), and MUST report where it was stored and the record's overall
  result.
- **FR-009**: The system MUST NOT claim to have uploaded a record to this
  platform's real, shared storage location, since that upload is not
  implemented by this feature — the same honest-reporting treatment this
  platform already applies to every other not-yet-built real-storage
  path.
- **FR-010**: This feature MUST NOT make any external network call (to a
  deployment system or any other live service) to verify any part of the
  record it is given; every fact in the record is trusted, structurally-
  validated input.
- **FR-011**: Every result MUST be available in both a human-readable
  form and a machine-readable form carrying the same facts, consistent
  with every other command this platform's CLI already provides.

### Key Entities

- **Test-Result Record**: the structured, schema-valid description of one
  completed test suite run — which repository and environment it ran
  against, which release (if any) it belongs to, the exact counts of
  passed/failed/skipped/quarantined tests, and the overall result.
- **Put Result**: the outcome of one submission attempt — whether it was
  accepted and, if so, where it was stored and what overall result it
  reported, or specifically why it was rejected.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every complete, valid test-result record is accepted and
  stored at its correct location, 100% of the time.
- **SC-002**: A record reporting a skipped test alongside an overall
  passing result is rejected, 100% of the time, and never stored.
- **SC-003**: A stage-environment record missing its release identifier
  or its full-scope declaration is rejected, 100% of the time, naming
  specifically which is missing.
- **SC-004**: A dev-environment record with no release identifier is
  accepted, 100% of the time — never confused with a missing-value
  rejection.

## Assumptions

- Verifying any claim a record makes about a real deploy (a digest, a
  Cloud Deploy rollout's actual state) against a live system is out of
  scope; every field is trusted, structurally-validated input, the same
  "no external call" boundary specs/005, specs/007, and specs/009 already
  established for their own inputs.
- Storing a record at this platform's real, shared location
  (`radicdotai/delivery-records`) is out of scope; this feature stores
  locally, mirroring the real path exactly, and reports the real upload
  as not-yet-available rather than attempted or silently skipped — the
  same precedent specs/007's `notes write` already set.
- Reading these records back to decide any outcome (a release gate, a
  dev-green or stage-regression judgment) is a separate, later feature;
  this feature only validates and stores one record at a time.
- A dev-environment record's own "which release it was a candidate for"
  is left unspecified by the architecture at this stage, since a dev run
  can happen before a release even exists; this feature stores a
  release-less record under a fixed, documented location distinct from
  any real release identifier, rather than inventing a fake one.
