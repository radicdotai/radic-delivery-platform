# Feature Specification: Change-Note Record Capture and Release-Note Gate

**Feature Branch**: `007-change-note-capture`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "Change-note record capture and release-note
gate — the `notes` command group: `radic-delivery notes write` builds and
validates one change-note record per merged commit, and `radic-delivery
notes check` validates a pull request has the release-note information it
needs before merge. The change-note record's schema is already specified
by the architecture (Confluence RAITSDA Reference 3, section 2): a fixed
set of fields including a Jira ticket key, with a documented `Jira: None`
escape hatch for PRs that genuinely ship without one. `notes write`
constructs and validates one record from explicit, fully-resolved CLI
inputs (never fetching a PR's details from GitHub itself — that is the
calling workflow's job) and writes it locally (the real cloud storage
upload is out of scope, reported honestly as not-yet-available). `notes
check` reads a PR body from a file and determines whether it contains a
Jira reference or the explicit opt-out, warning by default and blocking
only when explicitly configured to, per the platform's report-only-before-
blocking rollout principle."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A merged commit gets a reliable, structured change-note record (Priority: P1)

A service repo's CI pipeline, after a pull request merges, needs to record
what shipped — its type, audience, a human-readable summary, and either a
Jira ticket or an explicit, deliberate statement that there isn't one — in
one consistent, structured format across all seven service repos, instead
of each repo running its own slightly-different capture script.

**Why this priority**: this is the foundational capability the rest of
this feature (and later, the release process itself) depends on — without
a reliable, schema-valid record for every merged commit, nothing
downstream (release note generation, release selection) has anything
trustworthy to read.

**Independent Test**: can be fully tested by supplying a complete, valid
set of values for one merged commit and confirming a change-note record
matching the schema is produced and written, independent of any later
gate or release-selection behavior.

**Acceptance Scenarios**:

1. **Given** a merged commit's full details (repository, commit SHA, pull
   request number, type, audience, title, summary, and a Jira ticket key),
   **When** a change-note record is requested for it, **Then** a
   schema-valid record is produced and written, and reports success.
2. **Given** the same details but with the Jira ticket explicitly stated as
   "none" (the commit genuinely shipped without a ticket), **When** a
   record is requested, **Then** a schema-valid record is produced and
   written with that explicit non-ticket value recorded — never rejected
   for lacking a ticket key, and never confused with simply omitting the
   field.
3. **Given** details that don't form a valid record (for example, a title
   that's empty, or a type that isn't one of the recognized kinds),
   **When** a record is requested, **Then** it is rejected with a specific
   reason identifying what's invalid, and nothing is written.

---

### User Story 2 - A pull request author is told, before merge, whether their release note is complete (Priority: P1)

Before a pull request merges, its author needs to know whether they've
provided what the release process needs: a clear reference to the Jira
ticket it addresses, or an explicit statement that it intentionally has
none. They need this feedback to be specific enough to act on immediately.

**Why this priority**: equally foundational to User Story 1 — the two are
opposite sides of the same requirement (what gets recorded, and whether
what's offered is acceptable before it's recorded), so neither delivers
the full value alone.

**Independent Test**: can be fully tested by checking PR bodies that do,
and don't, contain a recognizable Jira reference or the explicit
non-ticket statement, and confirming each is correctly classified,
independent of whether the check is configured to warn or to block.

**Acceptance Scenarios**:

1. **Given** a pull request body that clearly states its Jira ticket,
   **When** it is checked, **Then** it passes, with nothing to fix.
2. **Given** a pull request body that explicitly states it has no Jira
   ticket, **When** it is checked, **Then** it passes — an explicit,
   deliberate "none" is acceptable, not a violation.
3. **Given** a pull request body with neither a Jira reference nor an
   explicit non-ticket statement, **When** it is checked, **Then** it is
   flagged as incomplete, naming specifically what's missing.

---

### User Story 3 - The release-note check starts as a warning and only blocks once the rollout says so (Priority: P2)

A platform maintainer is rolling out the release-note completeness check
across all seven service repos. They need every repo to see the check's
result from day one, but they need it to only warn — never block a
merge — until the team has had time to adapt, and then to actually block
once that time has passed, without the check's logic changing in between.

**Why this priority**: this is the staged-rollout behavior every new gate
on this platform follows (the same discipline already applied to the CI
quality gate and the security scan); it depends on User Story 2's
classification already working correctly, so it's sequenced after it, but
it's what makes introducing this check safe to roll out at all.

**Independent Test**: can be fully tested by checking the same incomplete
pull request body twice — once in warning configuration, once in blocking
configuration — and confirming the same underlying classification produces
a passable (non-blocking) result in the first case and a blocking result
in the second.

**Acceptance Scenarios**:

1. **Given** an incomplete pull request body, **When** checked without
   blocking enabled, **Then** the result names the incompleteness clearly
   but does not fail the check.
2. **Given** the identical incomplete pull request body, **When** checked
   with blocking enabled, **Then** the result fails the check, for the
   same stated reason.
3. **Given** a complete pull request body (a Jira reference or an explicit
   non-ticket statement), **When** checked in either configuration,
   **Then** it passes in both — blocking mode never fails something
   warning mode would have passed.

### Edge Cases

- What happens when a change-note record's details would describe the
  commit as shipped to end customers but internal-only, or vice versa,
  inconsistently? This feature validates each field's own stated shape
  (e.g. which audience values are recognized at all) but does not try to
  infer or second-guess whether a human-supplied combination of fields is
  "logically consistent" beyond that.
- What happens when a pull request body contains a Jira reference that
  isn't a real Jira ticket format (e.g. a typo, or a reference to a
  different system entirely)? It is evaluated purely on whether the body
  text matches the recognized reference shape — this feature does not
  verify a ticket actually exists in Jira.
- What happens when neither a Jira reference nor an explicit non-ticket
  statement is given, but also the body is completely empty? Treated the
  same as "neither given" — an empty body is not itself a special case.
- What happens when the record-writing step is asked to write to a
  location that can't be written (e.g. an unwritable path)? It fails
  clearly and distinctly from a validation failure, so the two causes are
  never confused with each other.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST construct a change-note record from a fully
  specified set of inputs (repository, commit, pull request number, type,
  audience, title, summary, and Jira ticket reference, plus the other
  fields the record's schema defines) and validate it against that schema
  before writing anything.
- **FR-002**: The system MUST reject a record whose inputs do not satisfy
  the schema, naming specifically which field and why, and MUST NOT write
  anything in that case.
- **FR-003**: The system MUST accept an explicit, deliberate statement that
  a change has no associated Jira ticket as a valid, complete value for
  that field — distinct from the field being left unspecified, which is
  invalid.
- **FR-004**: A successfully validated record MUST be written to a
  location the caller can rely on for this platform's own verification
  (e.g. in this feature's own tests and manual verification); the
  system MUST NOT claim to have uploaded it to the platform's real,
  shared cloud storage location, since that upload is not implemented by
  this feature.
- **FR-005**: The system MUST read a pull request's body from a file, never
  from a raw command-line text argument, so that a calling workflow is
  never tempted to interpolate untrusted pull-request text into a shell
  command.
- **FR-006**: The system MUST classify a pull request body into exactly one
  of: contains a recognizable Jira reference, contains an explicit
  statement that it has none, or contains neither.
- **FR-007**: When a pull request body contains neither a Jira reference
  nor the explicit non-ticket statement, the system MUST report this as
  incomplete, naming the missing information specifically enough for the
  author to act on it immediately.
- **FR-008**: The system MUST support a non-blocking (warning) mode and a
  blocking mode for the incompleteness result from FR-007, selectable by
  the caller; the same pull request body MUST be classified identically
  in both modes — only whether an incomplete result fails the check
  differs.
- **FR-009**: In blocking mode, a pull request body that would have passed
  in warning mode (a Jira reference present, or the explicit non-ticket
  statement present) MUST still pass — blocking mode only changes the
  outcome for an incomplete body, never for a complete one.
- **FR-010**: This feature MUST NOT fetch a pull request's title, body,
  author, or any other detail from GitHub itself; every input to record
  construction is supplied explicitly by the caller.
- **FR-011**: Every result MUST be available in both a human-readable form
  and a machine-readable form carrying the same facts, consistent with
  every other command this platform's CLI already provides.

### Key Entities

- **Change-Note Record**: the structured, schema-valid description of one
  merged commit's release-relevant facts — what kind of change it is, who
  it's relevant to, a human-readable title and summary, and either a Jira
  ticket reference or an explicit statement that it has none.
- **Release-Note Check Result**: the outcome of checking one pull request
  body — whether it's complete (a Jira reference or the explicit
  non-ticket statement is present) or incomplete, and whether that
  incompleteness is reported as a warning or a block, depending on the
  caller's chosen mode.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every change-note record this feature constructs from a
  complete, valid set of inputs is schema-valid, 100% of the time.
- **SC-002**: Every attempt to construct a record from incomplete or
  invalid inputs is rejected with a reason specific enough to fix without
  guessing, 100% of the time, and nothing is written in that case.
- **SC-003**: A pull request body's Jira-completeness is classified
  identically regardless of whether the check is run in warning or
  blocking mode; only the pass/fail outcome for an incomplete body differs
  between the two modes.
- **SC-004**: An explicit "no Jira ticket" statement is accepted as
  complete 100% of the time — it is never treated as equivalent to a
  missing or incomplete release note.

## Assumptions

- Resolving a pull request's actual title, body, author, merge commit SHA,
  and similar facts from GitHub is the responsibility of whatever calls
  this feature (a future reusable workflow, not built by this feature) —
  this feature only consumes them as already-resolved input, the same
  split already established for `gate evaluate` (toolchain installation),
  `security scan` (scanner installation), and `release command`
  (team-membership/Tech-Lead identity).
- Uploading a change-note record to this platform's real, shared cloud
  storage location is out of scope for this feature; this sandbox has no
  credentials for it, and the real upload path is reported as not-yet-
  available rather than silently skipped or faked as successful — the
  same honest-reporting precedent set by security scanning's undeployable
  scanners.
- The existing `schemas/change-note.schema.json` (written by feature 001
  as an intentionally loose placeholder, explicitly documented at the time
  as "a stable contract for a later feature") is tightened by this feature
  to match the architecture's fully-specified version exactly, now that
  this feature is the first to actually read and write against it — the
  same kind of schema-completion work feature 004 did for its own
  previously-loose field.
- A recognizable Jira reference and the explicit non-ticket statement are
  both free-text conventions a pull request body can contain; the exact
  textual shape of each is a convention this feature defines and documents
  (not something to guess at per-PR), consistent with how every prior
  feature has handled an architecture-referenced-but-not-fully-specified
  text convention.
- Change-note records feeding a future release-selection feature (reading
  "which tickets shipped to `dev`") is explicitly out of scope here; this
  feature only produces and validates individual records — it does not
  read or aggregate across them.
