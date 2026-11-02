# Feature Specification: Release Selection and Draft Manifest

**Feature Branch**: `008-release-propose`

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "Release selection and draft manifest —
`radic-delivery release propose`, the command that selects which merged
commits/tickets are candidates for the next release and writes a draft
release manifest, reading from change-note records (specs/007) already
written for each merged commit. The architecture fully specifies the
manifest's schema and the selection algorithm's three steps: collect
commits since the last release, group them by Jira ticket through the
change-note records, filter to eligible (ready) work via Jira readiness
and the dev-green gate, and finalize the selection into a schema-valid
draft manifest. Ticket readiness and dev-green status depend on live
external systems (Jira, a separate private records repository) this
environment cannot reach, so this feature takes both as explicit,
caller-supplied input rather than looking them up itself — the single
biggest external-dependency boundary this platform has drawn so far.
Explicitly out of scope: any live Jira or records-repository call, writing
the manifest to its real shared location, and actually cutting the release
branch (a separate, later feature)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A release manager sees a trustworthy draft selection of what's ready (Priority: P1)

A release manager wants to see, before anything is cut, exactly which
tickets and commits would go into the next release: which tickets are
ready and their associated commits, grouped correctly even when a ticket
has more than one commit behind it.

**Why this priority**: this is the entire reason the command exists —
without a correct, trustworthy selection of ready work, nothing else about
this feature (holding back unready work, handling non-Jira PRs) has
anything to build on.

**Independent Test**: can be fully tested by supplying a known set of
already-captured change-note records (some for ready tickets, some with
multiple commits for the same ticket) and confirming the resulting draft
selection groups commits under the correct ticket, with the right commit
count.

**Acceptance Scenarios**:

1. **Given** change-note records for two commits belonging to the same
   ready ticket, **When** a release is proposed, **Then** the draft
   selection lists that ticket once, with both commits recorded under it.
2. **Given** change-note records for two different ready tickets, each
   with one commit, **When** a release is proposed, **Then** the draft
   selection lists both tickets separately, each with its own commit.
3. **Given** a complete, valid proposal, **When** it is produced, **Then**
   it is a well-formed draft release record that matches this platform's
   release-manifest shape in every respect — nothing is ever close-enough
   or informally structured.

---

### User Story 2 - Work that isn't ready is held back, visibly and specifically (Priority: P1)

A ticket whose work has merged but isn't actually ready for release (not
yet marked ready for review, or whose latest commit hasn't passed the
pre-release regression check) must never be silently included in, nor
silently dropped from consideration for, the proposed release — it must
be visibly held back, with a specific, stated reason.

**Why this priority**: equally foundational to User Story 1 — a release
manager who can't trust that "not shown as proposed" means "deliberately
held back, for a stated reason" (rather than "silently missed") can't
trust the proposal at all.

**Independent Test**: can be fully tested by supplying change-note records
for a ticket explicitly marked not-ready, and separately for a ticket
whose commit has a known-failing pre-release check, and confirming each
appears in the held-back list with the correct, specific reason —
independent of how the ready tickets are selected.

**Acceptance Scenarios**:

1. **Given** a ticket's work has merged but it is explicitly marked as not
   ready for release, **When** a release is proposed, **Then** that ticket
   appears in the held-back list with a reason identifying it as not
   ready, and does not appear in the proposed selection.
2. **Given** a ticket whose associated commit is explicitly marked as
   having failed the pre-release regression check, **When** a release is
   proposed, **Then** that ticket is held back for that specific reason,
   distinguishable from "not ready."
3. **Given** the same ticket is supplied as both ready and ready for
   review, **When** proposed, **Then** it appears in the proposed
   selection, never in held-back.

---

### User Story 3 - A pull request merged without a Jira ticket is handled explicitly, never silently included (Priority: P2)

Some merged pull requests ship without a Jira ticket at all (an explicit,
deliberate choice already captured when the change note was written). A
release manager needs to explicitly list exactly which of these PRs to
include in a given release — any that merged without a ticket but weren't
explicitly listed must not quietly end up in the release.

**Why this priority**: this is a secondary but real path through the same
selection process; it depends on User Story 1's grouping already working
(a PR without a ticket is still grouped by its own identity) but is a
distinct, deliberately-opt-in case, so it's sequenced after the two P1
stories.

**Independent Test**: can be fully tested by supplying a change-note
record for a commit with no Jira ticket, once with its pull request
explicitly listed for inclusion and once without, confirming it's included
only in the first case.

**Acceptance Scenarios**:

1. **Given** a change-note record for a commit with no Jira ticket, whose
   pull request is explicitly listed for inclusion, **When** a release is
   proposed, **Then** it appears in the proposal's no-Jira-ticket section,
   with its reason and approver fields present but not yet filled in (that
   happens later, through a separate process).
2. **Given** the identical change-note record, but its pull request is
   **not** explicitly listed for inclusion, **When** a release is
   proposed, **Then** it does not appear anywhere in the proposal — not
   as proposed, not as held back silently assumed-in.

### Edge Cases

- What happens when no change-note records are found for the given
  repository and starting point at all? The proposal is still produced,
  with an empty selection — this is a valid, if unremarkable, outcome, not
  an error.
- What happens when a change-note record exists for a different
  repository than the one requested? It is ignored — only records for the
  exact requested repository are ever considered.
- What happens when an explicitly-listed non-Jira pull request has no
  matching change-note record at all? It is reported as not found, kept
  distinguishable from a successfully included non-Jira pull request.
- What happens when the same ticket key appears with commits from more
  than one pull request? All of its commits are grouped together under
  that one ticket, regardless of how many pull requests they came from.
- What happens when this command is run without specifying where the
  previous release left off? A reasonable default is used (treating every
  available change-note record as a candidate), and this is documented
  behavior, not a silent assumption.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST select, as release candidates, only the
  already-captured change-note records that belong to the requested
  repository.
- **FR-002**: The system MUST group selected records by their Jira ticket
  key, combining every commit belonging to the same ticket under one
  entry, regardless of how many separate commits or pull requests
  contributed to it.
- **FR-003**: The system MUST accept, as explicit input, which candidate
  tickets are ready for release and which are not, and MUST NOT determine
  readiness on its own — it never queries an external ticket-tracking
  system itself.
- **FR-004**: The system MUST accept, as explicit input, the pre-release
  regression-check status associated with each candidate commit, and MUST
  NOT determine that status on its own — it never queries an external
  test-results store itself.
- **FR-005**: A ticket that is not ready, or whose associated commit's
  pre-release regression-check status is not passing, MUST be excluded
  from the proposed selection and MUST instead appear in a held-back list
  with a reason specific enough to distinguish "not ready" from "failed
  the regression check."
- **FR-006**: A ticket that is ready and whose associated commit(s) have a
  passing pre-release regression-check status MUST appear in the proposed
  selection, never in the held-back list.
- **FR-007**: The system MUST accept an explicit list of pull request
  numbers to include that merged without a Jira ticket, and MUST include
  in the proposal only those pull requests that are both change-note-
  recorded as ticket-less and explicitly listed — a ticket-less pull
  request that is not explicitly listed MUST NOT appear anywhere in the
  proposal.
- **FR-008**: An explicitly-listed pull request with no matching
  change-note record MUST be reported as not found, distinguishable from
  one successfully included.
- **FR-009**: Every proposal the system produces MUST conform exactly to
  this platform's release-record shape; a proposal that would not conform
  MUST NOT be produced at all.
- **FR-010**: The system MUST NOT make any external network call (to a
  ticket-tracking system, a test-results store, or any other live
  service) in the course of producing a proposal.
- **FR-011**: The system MUST NOT create a release branch, open a pull
  request, or otherwise act on a proposal — producing a reviewable draft
  is the entire output of this feature.
- **FR-012**: Every result MUST be available in both a human-readable form
  and a machine-readable form carrying the same facts, consistent with
  every other command this platform's CLI already provides.

### Key Entities

- **Release Proposal (draft manifest)**: the structured output of one
  `release propose` run — a unique identifier for the release, the
  starting point it was computed from, the list of ready tickets and
  their commits, the list of held-back tickets with reasons, and the list
  of explicitly-included ticket-less pull requests (each still needing a
  reason and a second approver, filled in later by a separate process).
- **Candidate**: one already-captured change-note record being considered
  for inclusion, carrying its ticket key (or an explicit "no ticket"
  marker), its commit, and the pull request it came from.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every commit belonging to the same ready ticket is grouped
  under that one ticket in the proposal, 100% of the time, regardless of
  how many commits or pull requests it came from.
- **SC-002**: A not-ready ticket and a ticket whose commit failed the
  pre-release regression check are each held back with a reason specific
  enough to tell the two apart, 100% of the time, and neither ever appears
  in the proposed selection.
- **SC-003**: A ticket-less pull request is included in a proposal if and
  only if it was explicitly listed for inclusion, 100% of the time.
- **SC-004**: Every proposal this feature produces conforms to this
  platform's release-record shape, 100% of the time — never a near-miss,
  never produced and rejected after the fact.

## Assumptions

- Determining a ticket's readiness for release (e.g., its ticket-tracking
  status) and a commit's pre-release regression-check result are both the
  responsibility of whatever calls this feature — this feature only
  consumes them as already-resolved input, the same split already
  established for `gate evaluate` (toolchain installation), `security
  scan` (scanner installation), `release command` (team-membership/
  Tech-Lead identity), and `notes write`/`notes check` (a pull request's
  details) — here applied to the single largest decision this platform has
  delegated outward so far, since it shapes the entire ready/held-back
  split rather than one narrow check.
- Already-captured change-note records are read from wherever this
  platform's own record-capture feature already writes them locally; this
  feature does not invent a second storage convention.
- Knowing where the previous release left off (so this run only considers
  genuinely new work) is supplied explicitly to this feature rather than
  looked up from a shared release history this environment cannot reach;
  when it is not supplied, every available change-note record for the
  requested repository is treated as a candidate — a documented default,
  not a silent gap.
- Assigning a new release its unique identifier (including disambiguating
  it from any other release proposed the same day) has no described
  mechanism this feature can rely on from a shared history it cannot
  reach; a caller-supplied override is accepted, and a single reasonable
  default is used when none is given — real cross-run sequencing is
  explicitly deferred, the same kind of deferral specs/005 already
  recorded for comment-id idempotency.
- Writing a proposal to this platform's real, shared storage location is
  out of scope; this feature's output is the proposal itself, reported
  honestly as not-yet-persisted anywhere but the caller's own view of it.
- Actually cutting a release branch and cherry-picking the proposed
  selection onto it is a separate, later feature, not built here.
- A migration-dependency relationship between tickets (one ticket's
  database migration being a prerequisite for another's) is not evaluated
  by this feature; every candidate ticket is treated independently.
