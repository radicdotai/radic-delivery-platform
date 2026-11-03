# Feature Specification: Quality Gate Completion

**Feature Branch**: `013-quality-gate-completion`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Quality gate completion — two related, small
CLI commands bundled into one feature per the project's explicit request
to combine related, independently small features: `radic-delivery gate
evaluate --mode release-gate` (the prod-approval gate: the same real
lint/typecheck/unit/coverage/skip-budget checks `ci-gate` already runs,
plus a new check confirming a local stage regression test-result record
exists, matches the digest, and passed) and `radic-delivery migrations
check` (the descriptor-driven migration safety checks: a port of
`check_migrations_frozen.py`, and a migration-chain integrity check).
Bundled because both close out this platform's `gate`/quality-check
command family, reuse existing real local machinery (specs/002's gate
evaluator, specs/010's test-result record shape), and are each scoped to
exactly the parts testable without a live GCP/Docker/database connection
in this environment. The literal `alembic check` (needs a live database
connection to diff against) and `schema_check` (same) are explicitly out
of scope, reported as not available rather than approximated by a
look-alike that doesn't actually test what they test."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The prod-approval gate reflects the full release picture, not just the code (Priority: P1)

Before a release is approved for production, whoever is deciding needs
one clear answer: has this exact release — the code itself, and the
stage environment it actually ran in — fully passed everything required,
with nothing silently missing?

**Why this priority**: this is the gate the entire platform's prod
approval sits behind; a release gate that only checks the code and
silently ignores a missing or failing stage regression result would let
an unverified release through.

**Independent Test**: can be fully tested by evaluating the release gate
against a real local service checkout once with a matching, passing stage
test-result record present, and once with that record missing or failing,
confirming the gate's overall result and the specific named reason differ
accordingly.

**Acceptance Scenarios**:

1. **Given** a service whose code passes every check `ci-gate` already
   runs, and a local stage test-result record exists for the exact digest
   being evaluated, is scoped as a full regression, and passed, **When**
   the release gate is evaluated, **Then** the overall result is a pass.
2. **Given** the same passing code, but no stage test-result record
   exists at all for the digest being evaluated, **When** the release
   gate is evaluated, **Then** the overall result is a failure, naming
   specifically that the stage regression record is missing.
3. **Given** a stage test-result record exists for the exact digest but
   reports an overall failure or any skipped test, **When** the release
   gate is evaluated, **Then** the overall result is a failure, naming
   specifically that the stage regression did not pass cleanly.
4. **Given** a stage test-result record exists for a different digest
   than the one being evaluated, **When** the release gate is evaluated,
   **Then** it is treated exactly as if no record exists at all —
   never silently matched to the wrong release.

---

### User Story 2 - A service's migration setup is checked for safety before it ships (Priority: P2)

Before a service with database migrations ships, whoever is reviewing
needs to know the migration chain itself is sound (one clear, linear
sequence, not a fork or a loop) and that the platform's own
migration-freeze safeguards are still genuinely in place, not quietly
removed.

**Why this priority**: this is a standalone safety check on a service's
migration setup, not something every release depends on (only services
with `migrations.enabled: true`), and it is independent of the release
gate above.

**Independent Test**: can be fully tested by running it against a real,
small set of local migration files and workflow files, once where
everything is sound and once with a deliberately broken chain or a
deliberately missing safeguard, confirming each failure is named
specifically.

**Acceptance Scenarios**:

1. **Given** a service's migration files form one single, unbroken,
   linear chain, **When** its migration graph is checked, **Then** it is
   reported sound.
2. **Given** two migration files both claim the same file as their
   predecessor (a fork), **When** its migration graph is checked, **Then**
   this is reported specifically as a fork, naming the files involved.
3. **Given** a migration file's predecessor chain loops back on itself,
   **When** its migration graph is checked, **Then** this is reported
   specifically as a cycle.
4. **Given** the descriptor names a workflow file that is supposed to
   keep the platform's migration-freeze safeguard in place, and that file
   is missing from the repository, **When** the freeze check runs,
   **Then** this is reported specifically as the safeguard being gone,
   naming the missing file.
5. **Given** that same workflow file exists but no longer contains the
   expected migration job, **When** the freeze check runs, **Then** this
   is reported specifically as the safeguard having been altered, naming
   the file.
6. **Given** a check that fundamentally requires a live database
   connection is requested, **When** migrations are checked, **Then** it
   is reported as not available, never silently skipped and never faked.

### Edge Cases

- What happens when `release-gate` is evaluated for a service with
  `migrations.enabled: false`? Migration state has no bearing on the
  release gate at all — they are entirely separate checks.
- What happens when more than one stage test-result record exists for the
  same digest? The first one found that matches is used; this is flagged
  as a convention needing confirmation, not treated as an error.
- What happens when a service has `migrations.enabled: false` and
  `migrations check` is still run against it? It reports plainly that
  migrations are not enabled for this service, rather than attempting any
  check.
- What happens when the migration-chain check is run against a directory
  with zero migration files? It is reported as sound (a trivially empty
  chain), not an error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST evaluate the release gate using the same
  real lint, typecheck, unit, coverage, and skip-budget checks the CI
  gate already performs, with no duplicated logic.
- **FR-002**: The system MUST additionally check, for the release gate
  only, that a local stage test-result record exists for the exact digest
  being evaluated, is scoped as a full regression, and reports an overall
  pass with zero skipped tests — reporting this as one further, distinctly
  named check, never folded into or confused with the code-level checks.
- **FR-003**: When no matching stage test-result record exists for the
  digest being evaluated, the system MUST fail the release gate, naming
  specifically that the record is missing — never treating a missing
  record as a pass.
- **FR-004**: The system MUST check a service's migration files for a
  single, linear chain, naming specifically whether a fork or a cycle was
  found and which files are involved, when the chain is not sound.
- **FR-005**: The system MUST check that every workflow file the
  descriptor names as carrying the platform's migration-freeze safeguard
  still exists and still contains the expected migration job, naming
  specifically which file is missing or altered when it is not.
- **FR-006**: The system MUST report any requested check that
  fundamentally requires a live database connection as not available,
  never silently skipped and never approximated by a check that doesn't
  actually test the same thing.
- **FR-007**: This feature MUST NOT make any external network call (to a
  database, GCP, GitHub, or Jira) in the course of either of its two
  commands.
- **FR-008**: Every result MUST be available in both a human-readable
  form and a machine-readable form carrying the same facts, consistent
  with every other command this platform's CLI already provides.

### Key Entities

- **Release Gate Result**: the outcome of one `gate evaluate --mode
  release-gate` run — the same check set `ci-gate` already reports, plus
  one further, distinctly named stage-regression check.
- **Migration Graph Result**: the outcome of one migration-chain check —
  sound, or specifically a fork or a cycle, naming the files involved.
- **Migration Freeze Result**: the outcome of one freeze-safeguard check
  per named workflow file — intact, missing, or altered.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The release gate never passes when its digest's stage
  regression record is missing, failing, or scoped incorrectly, 100% of
  the time.
- **SC-002**: A forked or cyclical migration chain is always reported
  specifically as such, naming the files involved, never as a generic
  failure.
- **SC-003**: A missing or altered migration-freeze safeguard is always
  named specifically, by file, never reported as a single undifferentiated
  failure.
- **SC-004**: A check requiring a live database connection is always
  reported as not available, never as a false pass or a silently skipped
  check.

## Assumptions

- The live Cloud-Deploy-rollout-succeeded fact (also part of the real
  `promote` workflow's own prod-approval sequence) remains
  `promote`'s own concern, not `release-gate`'s — consistent with
  Reference 2's own description, which lists it as a separate checklist
  item from `release-gate` itself.
- A stage test-result record is produced by a separate, already-built
  capability (`radic-delivery records put-test-result`, specs/010); this
  feature only reads an already-stored record as given, the same way
  `release finalise` (specs/011) only consumes an already-`prod-deployed`
  manifest as given.
- The literal `alembic check` command (comparing migration state against
  a live database) and `schema_check` both require a live database
  connection this sandbox cannot make; both are explicitly out of scope,
  reported not-available rather than approximated by a file-based
  look-alike that wouldn't actually test the same thing.
- `migration_graph`'s chain analysis is scoped to Alembic-style migration
  files (a `revision`/`down_revision` header pair per file) — the one
  concrete, inspectable chain shape this platform's descriptor schema
  names; a Django-style numbered-migration chain is a different shape not
  covered by this feature.
