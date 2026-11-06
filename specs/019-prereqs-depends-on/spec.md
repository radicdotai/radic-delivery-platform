# Feature Specification: Prereqs and Depends-On Tracking and Enforcement

**Feature Branch**: `019-prereqs-depends-on`

**Created**: 2026-11-06

**Status**: Draft

**Input**: User description: "Prereqs and Depends-on fields, parsing,
rendering, and enforcement — the third spec in an 11-spec roadmap
implementing the C1-C13 architecture-review changes to
radic-delivery-platform. Per Confluence RAITSDA Runbook §1.2/§3.1/§3.3
and Reference 3 §2/§5 (review comments C5 and C7): a `Prereqs:` checklist
in a PR body (non-code actions like a feature flag or a Secret Manager
value) must be ticked before prod runs, and an optional `Depends-on:
RAD-11` trailer declares a non-migration dependency on another ticket,
closed over the same way a migration dependency already is, with
`/release remove` refused while a depended-on ticket is still selected.
This feature: adds `prereqs`/`depends_on` fields to the change-note
schema; a pure parser for the `Prereqs:` checklist block and `Depends-on:`
trailer from PR body text; change-note record construction optionally
computes both from a supplied PR body (mirroring the just-merged migration
flag's 'computed from a real artifact, not freely typed' discipline);
`release cut` gains a confirming guard refusing the cut when a selected
ticket's dependency is neither already selected nor already known to be
in prod (an explicit input, never a live lookup) — corrected in scope
from the original roadmap wording of 'auto-add or refuse' to 'refuse
only,' since auto-adding a dependency ticket's own commits requires a
ticket-to-commit discovery capability this engine does not have and which
belongs to `release propose`'s selector, not `release cut`, if ever
prioritized; the release PR body renders a new Prereqs-and-dependencies
section; and `gate evaluate --mode release-gate` gains two new checks —
every selected ticket's Prereqs are all ticked, and every Depends-on
ticket is satisfied — completing the release-gate requirement Reference 2
already documents. The non-removable-ticket refusal in `/release remove`
itself is explicitly out of scope for this feature (a later spec in the
same roadmap, once this feature's Depends-on data exists to refuse
against)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prereqs and dependencies are captured as real, parsed facts, never freely typed into the record (Priority: P1)

Whoever writes a PR needs to declare a non-code prerequisite or a
dependency on another ticket in the PR body itself, in plain text, and
have that declaration become a real, structured fact on the change-note
record — not something a human has to separately re-type anywhere else.

**Why this priority**: every other part of this feature reads this
captured data; it is independently valuable and independently testable
on its own, with real PR-body text fixtures and no dependency on any
other spec in the roadmap.

**Independent Test**: can be fully tested by parsing a handful of real PR
body texts — one with a `Prereqs:` checklist (some items ticked, some
not), one with a `Depends-on:` trailer naming one or more tickets, one
with both, one with neither — and confirming each produces the correct
structured result, then confirming a change-note record built from that
PR body carries the same structured data.

**Acceptance Scenarios**:

1. **Given** a PR body containing a `Prereqs:` checklist block with a mix
   of ticked (`- [x]`) and unticked (`- [ ]`) items, **When** it is
   parsed, **Then** every item is captured with its exact text and
   ticked state, in the order written.
2. **Given** a PR body containing a `Depends-on: RAD-11, RAD-12` trailer,
   **When** it is parsed, **Then** both ticket keys are captured, in the
   order written.
3. **Given** a PR body with neither a `Prereqs:` block nor a `Depends-on:`
   trailer, **When** it is parsed, **Then** both results are empty —
   never an error, since both are optional.
4. **Given** a PR body supplied when building a change-note record,
   **When** the record is built, **Then** its `prereqs` and `depends_on`
   fields exactly match what parsing that same PR body produces.

---

### User Story 2 - A release is never cut while a selected ticket's dependency is unsatisfied (Priority: P2)

Whoever cuts a release needs the cut to refuse, by name, when a selected
ticket depends on another ticket that is neither already selected in this
same release nor already known to be in production — never a cut that
silently ships half of a declared dependency pair.

**Why this priority**: this is the enforcement half of the Runbook's own
rule ("`/release remove` is refused while a depended-on ticket is
selected" implies the inverse must also hold at cut time: a dependency
must actually be present); it depends on User Story 1's parsed data
existing on real change-note records.

**Independent Test**: can be fully tested by cutting a release whose
selection includes a ticket with an unsatisfied `Depends-on:` ticket,
confirming the cut refuses by name before any branch is created — then
confirming the cut proceeds when that dependency is already selected, or
is supplied as already-known-in-prod.

**Acceptance Scenarios**:

1. **Given** a selected ticket's change-note record declares a
   `Depends-on:` ticket that is neither in the current selection nor in
   a supplied list of tickets already known to be in production, **When**
   the release is cut, **Then** the cut is refused before any branch is
   created, naming the specific ticket and its unmet dependency.
2. **Given** the same situation, but the depended-on ticket is itself
   part of the current selection, **When** the release is cut, **Then**
   the cut proceeds normally.
3. **Given** the same situation, but the depended-on ticket is supplied
   as already known to be in production, **When** the release is cut,
   **Then** the cut proceeds normally.

---

### User Story 3 - The release PR and the release gate both show and enforce completeness before prod (Priority: P3)

Whoever reviews a release PR needs to see, at a glance, every selected
ticket's Prereqs and dependencies and their completeness — and whoever
relies on the release gate needs prod approval blocked outright when any
Prereqs item is unticked or any dependency is unsatisfied, not just
informed about it.

**Why this priority**: this is the visibility-and-final-enforcement layer
on top of User Story 1's captured data; it has no purpose until that data
exists, and is naturally built last.

**Independent Test**: can be fully tested by rendering a release PR body
for a manifest whose tickets have a mix of complete and incomplete
Prereqs/dependencies, confirming the new section reports each accurately,
and by evaluating the release gate against the same data, confirming it
fails specifically when any ticket's Prereqs or dependencies are
incomplete and passes when all are complete.

**Acceptance Scenarios**:

1. **Given** a release manifest whose tickets have a mix of fully-ticked
   and partially-ticked Prereqs, **When** the release PR body is
   rendered, **Then** each ticket's Prereqs are reported as a specific
   ticked/total count, never a single yes/no.
2. **Given** the same manifest, **When** the release gate is evaluated,
   **Then** it reports a specific failing check naming which ticket has
   an unticked Prereqs item, if any do.
3. **Given** a release manifest where every selected ticket's Prereqs are
   fully ticked and every Depends-on ticket is satisfied, **When** the
   release gate is evaluated, **Then** both new checks pass.

### Edge Cases

- What happens when the same ticket key appears more than once in a
  `Depends-on:` trailer, or a ticket declares itself as its own
  dependency? Duplicates are collapsed to one; a ticket depending on
  itself is never treated as unsatisfied (trivially always present in its
  own selection).
- What happens when a `Prereqs:` checklist item's text is empty or
  whitespace-only? It is not counted as a valid item — only lines with
  real, non-empty text after the checkbox marker count.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST parse an optional `Prereqs:` checklist
  block from PR body text, capturing each item's text and ticked state in
  the order written.
- **FR-002**: The system MUST parse an optional `Depends-on:` trailer from
  PR body text, capturing each named ticket key in the order written,
  with duplicates collapsed.
- **FR-003**: Absence of either the `Prereqs:` block or the `Depends-on:`
  trailer MUST produce an empty result for that field, never an error.
- **FR-004**: The change-note record construction MUST accept a PR body
  and populate its `prereqs`/`depends_on` fields from the parse in FR-001
  and FR-002, never from a separately-typed input for those two fields.
- **FR-005**: The system MUST refuse to cut a release when any selected
  ticket's `depends_on` names a ticket key that is neither among the
  current selection's own ticket keys nor among an explicitly supplied
  set of tickets already known to be in production.
- **FR-006**: The refusal in FR-005 MUST happen before any git branch is
  created, and MUST name the specific ticket and its unmet dependency.
- **FR-007**: A ticket depending on itself, or on a ticket already present
  in the same selection, MUST never be treated as unsatisfied.
- **FR-008**: The release PR body MUST report, for every selected ticket,
  its Prereqs completeness as a specific ticked-versus-total count and its
  Depends-on tickets by name.
- **FR-009**: The release gate MUST fail, naming the specific ticket and
  the specific incomplete item, when any selected ticket has an unticked
  Prereqs item.
- **FR-010**: The release gate MUST fail, naming the specific ticket and
  the specific unmet dependency, when any selected ticket's dependency is
  neither in the selection nor in the supplied known-in-production set.
- **FR-011**: The release gate's two new checks MUST both pass when every
  selected ticket's Prereqs are fully ticked and every dependency is
  satisfied.

### Key Entities

- **Prereqs Checklist**: an ordered list of (text, ticked) pairs declared
  in a PR body, each a non-code action that must be completed before prod.
- **Depends-On Set**: an ordered, deduplicated list of ticket keys a given
  ticket's PR body declares it depends on.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A Prereqs or Depends-on declaration written in a PR body is
  always captured as a structured fact identical to what was written —
  never lost, never requiring a second manual entry.
- **SC-002**: A release can never be cut while a declared dependency is
  genuinely missing from both the selection and the known-production set.
- **SC-003**: Every incomplete Prereqs item or unmet dependency is always
  named specifically, by ticket and item — never a generic, unexplained
  gate failure.
- **SC-004**: Every functional requirement is verified by a real test
  against real PR-body text and real git fixtures — no GCP, Docker, or
  live Jira/GitHub call anywhere in this feature.

## Assumptions

- Determining whether a ticket is "already known to be in production" is
  the calling workflow's responsibility (a live `delivery-records`/Jira
  fact this sandbox cannot look up) — this feature only consumes an
  explicitly supplied set of such tickets, the same boundary this
  platform has already drawn more than once (`rollback plan`,
  `release cut`'s own `other_manifests` from the prior spec in this
  roadmap).
- **Scope correction from the original roadmap wording**: `release cut`
  only *refuses* on an unmet dependency; it does not *auto-add* a missing
  dependency ticket to the selection. Auto-adding would require
  discovering that ticket's own commits, a capability that belongs to
  `release propose`'s ticket-selection logic, not `release cut`'s
  cherry-pick orchestration — out of scope here, and not yet scheduled
  elsewhere in this roadmap.
- The non-removable-ticket refusal in `/release remove` (refusing to
  remove a ticket something else depends on) is a separate, later spec in
  this roadmap — this feature only produces the `depends_on` data it will
  need; it does not itself change `/release remove`'s behavior.
- Prereqs items are never independently validated for truthfulness (the
  system trusts that a ticked item really was completed) — only their
  presence and ticked state are tracked.
