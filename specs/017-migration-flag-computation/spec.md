# Feature Specification: Migration Flag Computation

**Feature Branch**: `017-migration-flag-computation`

**Created**: 2026-11-06

**Status**: Draft

**Input**: User description: "Migration flag computation — the first spec
in an 11-spec roadmap implementing the C1-C13 architecture-review changes
to radic-delivery-platform. This feature replaces the free-form,
manually-supplied `migration` boolean on the change-note record
(schemas/change-note.schema.json, specs/007) with a value computed
automatically from the real git diff, per Confluence RAITSDA Reference 3
§2 (as revised 2026-11-03, review comment C4): 'The migration value is
computed by the check from the PR diff, never typed by the author:
expand or contract when the PR adds a file under migrations/versions/
(files under migrations/legacy/ are excluded), otherwise none. A PR that
adds a migration and states "Migrations: none" in its body fails the
check; the PR-body line is only a cross-check. contract is set from the
migration file's header, and a ticket with a contract step cannot be held
back on its own.' New module `notes/migration_flag.py` computes the value
from a real diff, taking `legacy_dir`/`phase_header_required` as explicit
parameters (not hardcoded) so a later descriptor-driven spec can wire real
per-repo values through without reworking this feature. The contract
marker convention is resolved as `# phase: contract` (not Confluence's
current, SQL-only `-- phase: contract` text — a real, flagged
inconsistency, since the migration files are `.py`, not `.sql`) as the
first non-blank line of the file, confirmed with the page owner, who
will update Confluence separately. `notes/builder.py` stops accepting a
free `migration` input and computes it instead; `notes/check.py` gains a
PR-body cross-check that fails on mismatch. No GCP, Docker, or live
Jira/GitHub call anywhere in this feature — pure local git and schema
logic."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A change-note's migration flag always reflects what the diff actually did (Priority: P1)

Whoever reviews a release needs the `migration` value on a change-note
record to be a fact about the code, not a claim the PR author typed in —
so a release-manager reading the record can trust it without re-checking
the diff by hand.

**Why this priority**: every other part of this feature (the PR-body
cross-check) exists only to protect this computed value's correctness;
this is independently valuable and independently testable with zero
dependency on anything else in this feature.

**Independent Test**: can be fully tested by computing the flag against a
handful of real, small git diffs — one with no migration file, one adding
an expand-phase migration, one adding a contract-phase migration, one
adding a migration under the excluded legacy directory — and confirming
each returns the documented value.

**Acceptance Scenarios**:

1. **Given** a diff that adds no file under `migrations/versions/`,
   **When** the migration flag is computed, **Then** the result is
   `none`.
2. **Given** a diff that adds a new file under `migrations/versions/`
   with no contract marker, **When** the migration flag is computed,
   **Then** the result is `expand`.
3. **Given** a diff that adds a new file under `migrations/versions/`
   whose first non-blank line is the contract marker, **When** the
   migration flag is computed, **Then** the result is `contract`.
4. **Given** a diff that adds a file under the configured legacy
   directory, **When** the migration flag is computed, **Then** that file
   is excluded entirely and does not by itself produce `expand` or
   `contract`.
5. **Given** a diff that adds both an expand-phase file and a
   contract-phase file in the same change, **When** the migration flag is
   computed, **Then** the result is `contract` — the stricter value wins.
6. **Given** a repo whose descriptor declares that the contract marker
   cannot be reliably detected, **When** the migration flag is computed
   for a diff that adds a migration file, **Then** the result is always
   `expand`, regardless of the file's actual content.

---

### User Story 2 - A PR body that disagrees with reality is caught, not trusted (Priority: P2)

Whoever wrote the release-note gate check needs a PR whose body claims a
migration state that doesn't match what the diff actually did to fail
loudly — never silently accept the author's typed claim over the real,
computed fact.

**Why this priority**: this is a protective check layered on top of User
Story 1's computed value; it has no purpose and nothing to compare
against until that value exists.

**Independent Test**: can be fully tested by computing a real migration
flag for a fixture diff, then checking it against a deliberately
mismatched declared value in a fixture PR body, confirming the check
fails with a specific, named reason.

**Acceptance Scenarios**:

1. **Given** a diff whose computed migration flag is `expand`, and a PR
   body declaring `Migrations: none`, **When** the check runs, **Then**
   it fails, naming the mismatch between the declared and computed
   values.
2. **Given** a diff whose computed migration flag matches its PR body's
   declared value, **When** the check runs, **Then** it passes.
3. **Given** a PR body with no `Migrations:` line at all, **When** the
   check runs, **Then** it passes regardless of the computed value — the
   line is an optional cross-check, never a required declaration.

### Edge Cases

- What happens when a migration file under `migrations/versions/` is
  modified or deleted, but not added, in the diff? It is never treated as
  a qualifying addition — only a genuinely new file counts, matching
  Reference 3's own "adds a file" wording.
- What happens when the contract marker is present but not on the file's
  first non-blank line (for example, after a module docstring)? It is not
  detected — the convention requires the marker to be the first non-blank
  line precisely so there's one unambiguous place to look; a file whose
  own tooling emits a leading docstring must be updated to emit the
  marker above it (an action for whichever system generates the file, out
  of scope for this feature's own code).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST compute a change-note's migration value
  from a real diff between two git references, never accept it as a free
  caller-supplied value.
- **FR-002**: The system MUST return `none` when the diff adds no
  qualifying migration file.
- **FR-003**: The system MUST return `expand` when the diff adds at least
  one qualifying migration file and none of them carry the contract
  marker.
- **FR-004**: The system MUST return `contract` when the diff adds at
  least one qualifying migration file carrying the contract marker on its
  first non-blank line, even if other added migration files in the same
  diff do not carry it.
- **FR-005**: The system MUST exclude any file under a configured legacy
  directory from being treated as a qualifying migration file.
- **FR-006**: The system MUST accept both the legacy-directory path and
  whether contract-marker detection is possible at all as explicit,
  per-call parameters, each with a stated default — never a hardcoded
  constant.
- **FR-007**: When contract-marker detection is not possible, the system
  MUST always return `expand` for a diff that adds a qualifying migration
  file, and MUST NOT attempt to scan file contents for the marker in that
  mode.
- **FR-008**: The system MUST provide a check comparing the computed
  migration value against an optional, explicitly-labeled declaration in
  a PR body, failing with a specific reason when they disagree.
- **FR-009**: The check in FR-008 MUST pass when no such declaration is
  present in the PR body, regardless of the computed value.
- **FR-010**: The computed migration value, never the PR body's declared
  value, MUST be the one recorded on the change-note record.

### Key Entities

- **Migration Flag**: one of `none`, `expand`, or `contract` — a computed
  fact about a single diff, replacing a previously free-form boolean on
  the change-note record.
- **Change-Note Record**: the existing per-PR record (specs/007) that
  this feature's computed migration flag becomes a field of.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The migration flag on every newly-built change-note record
  is always derived from the actual diff — never settable by any input
  that isn't the diff itself and the two explicit configuration
  parameters.
- **SC-002**: A PR body's own claim about migration state can never
  override the computed value, and a disagreement between the two is
  always caught and named, never silently accepted.
- **SC-003**: Every functional requirement is verified by a real,
  unmocked local git fixture — no GCP, Docker, or live Jira/GitHub call
  anywhere in this feature.

## Assumptions

- The contract-marker convention is `# phase: contract` as the first
  non-blank line of the migration file — a new, flagged resolution of a
  real inconsistency in the current Confluence text (`-- phase: contract`,
  SQL-comment syntax that cannot apply to a `.py` file), confirmed
  directly with the page owner, who will update Confluence separately.
  This feature's code and tests use the resolved form.
- Whichever system generates new migration files for a given service repo
  (for example, an Alembic `script.py.mako` template that emits a leading
  docstring) is responsible for placing the contract marker above any
  such docstring so it remains the first non-blank line; updating that
  generator is out of scope for this feature.
- `legacy_dir` and `phase_header_required` are per-repo descriptor
  settings in the platform's broader architecture, but wiring real
  descriptor values through is explicitly out of scope for this feature —
  this feature only defines the computation function's explicit
  parameters and their defaults (`"migrations/legacy"` and `true`,
  respectively) so a later feature can supply real values without
  reworking this one.
- Prereqs/Depends-on fields, the migration head lockfile, hotfix
  merge-revision handling, cross-repo schema ownership, revert-pair
  netting, subset-mode selection, cross-repo release-gate checks,
  non-removable-ticket refusal, the verify-promotion rework, and the
  pr-title-jira check are all out of scope for this feature — each is a
  separate, later spec in the same roadmap.
