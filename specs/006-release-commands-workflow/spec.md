# Feature Specification: Release-Commands Reusable Workflow

**Feature Branch**: `006-release-commands-workflow`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "Release-commands reusable workflow — wires the
already-built release slash-command parser and authorization check
(feature 005) into the real GitHub Actions contract that lets a release
manager actually get a reply when they comment a slash command on a release
pull request. Triggered by a comment on a release PR, looks up the
commenter's team membership and the current Tech Lead, runs the existing
parser/authorizer, and replies on the same PR stating the outcome. Defers
the release-manifest audit-log write, comment-id idempotency, and any real
Jira call, each visibly rather than silently — and must decide, as a
flagged convention, how a recognized `/research close` command is reported
through outputs that were only ever specified for the five `/release`
forms."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A release manager gets an immediate, clear reply (Priority: P1)

A release manager comments one of the six recognized commands (for example
`/release remove RAD-123`) on a release pull request. Today nothing reacts
to that comment at all — feature 005 built the logic that can recognize and
authorize it, but nothing yet triggers on a real comment or tells the
commenter anything happened. They need a reply on that same pull request,
within the same automated flow, stating plainly whether their command was
recognized, whether it was accepted, and — if not — why not.

**Why this priority**: this is the entire reason the parser (feature 005)
was built — a recognized-and-authorized command that nobody and nothing
ever acts on or acknowledges delivers no value. This is the minimum slice
that makes the whole release-commands capability real and observable.

**Independent Test**: can be fully tested by posting a comment matching one
of the six recognized forms from an authorized author on a pull request,
and confirming a reply appears on that same pull request stating the
command was accepted, naming which command it was.

**Acceptance Scenarios**:

1. **Given** a release manager comments `/release remove RAD-123` on a
   release pull request, **When** the comment is posted, **Then** a reply
   appears on that pull request stating the `remove` command for `RAD-123`
   was accepted.
2. **Given** a release manager comments `/release waive dev-green reason:
   ci is flaky today` on a release pull request, **When** the comment is
   posted, **Then** the system determines whether that commenter is the
   current Tech Lead and replies accordingly (accepted if they are,
   refused if they are not), without ever requiring a human to manually
   look up who the Tech Lead is.
3. **Given** a comment that does not start with the recognized command
   shape (ordinary discussion), **When** the comment is posted, **Then** no
   reply is posted and no outcome is recorded as rejected or applied — the
   comment is quietly ignored, exactly as feature 005 classifies it.

---

### User Story 2 - A mistaken or unauthorized attempt is refused with a clear reason, on the same thread (Priority: P1)

Someone comments something that looks like a command but is malformed, or a
well-formed command from someone not authorized to issue it. They need to
see, on the same pull request, specifically why it did not take effect —
not silence, and not a generic failure — using the exact distinctions
feature 005 already makes between "malformed" and "unauthorized."

**Why this priority**: equally foundational to User Story 1 — a workflow
that only reports success leaves every rejection case invisible, which is
worse than not automating replies at all, since a release manager would
reasonably but wrongly assume a command that got no reply was accepted.

**Independent Test**: can be fully tested by posting a malformed command and
separately an unauthorized-but-well-formed command, and confirming each
produces a distinct, specific reply naming the reason, without any
reply ever claiming a command was applied when it was not.

**Acceptance Scenarios**:

1. **Given** a comment `/release add RAD-123` (missing the required reason
   text), **When** posted on a release pull request, **Then** a reply
   appears stating the command was not accepted because it is malformed,
   naming what is missing.
2. **Given** a comment `/release remove RAD-123` from someone who is not a
   release manager, **When** posted, **Then** a reply appears stating the
   command was refused because the commenter is not authorized, distinct
   from a malformed-command reply.

---

### User Story 3 - Only comments on an actual release pull request trigger this at all (Priority: P2)

A comment with the exact same text is posted on a plain GitHub issue (not a
pull request), or on a pull request that isn't a release pull request. The
platform maintainer needs certainty that this automated reply-and-authorize
flow never fires outside the context it's meant for.

**Why this priority**: this is a scoping/safety guarantee rather than a
day-to-day release-manager need, so it's correctly sequenced after the core
reply behaviour, but it protects against the workflow firing somewhere it
was never meant to run and surprising someone with an authorization refusal
on an unrelated issue.

**Independent Test**: can be fully tested by posting a command-shaped
comment on a plain issue (not a pull request) and confirming nothing is
triggered — no reply, no authorization check performed.

**Acceptance Scenarios**:

1. **Given** a comment on a plain GitHub issue (not attached to a pull
   request) whose text would otherwise match a recognized command,
   **When** it is posted, **Then** the release-commands flow never
   triggers at all.

### Edge Cases

- What happens when the same comment is somehow processed more than once
  (e.g. a webhook redelivery)? The same reply behaviour runs again —
  duplicate-processing prevention is explicitly deferred (see Assumptions);
  this is a known, flagged gap, not a silently accepted risk.
- What happens when the lookup of the commenter's team membership or the
  current Tech Lead's identity itself fails or is unavailable (for example,
  an outage of the identity source)? The commenter must be told the check
  could not be completed, distinguishable from being told they are
  unauthorized — a failed lookup must never be silently treated as "not
  authorized" or, worse, "authorized."
- What happens for a recognized `/research close` command, given the
  reusable workflow's reply/outcome reporting was only ever specified in
  terms of the five `/release` forms? It still gets a clear reply stating
  whether it was accepted, using the same accepted/malformed/unauthorized
  distinctions as every other recognized form (see Assumptions for how
  this is represented without inventing a new outcome category this
  feature isn't authorized to add).
- What happens when a reply cannot be posted back to the pull request at
  all (for example, a transient failure posting the comment)? The command
  must not be silently recorded as applied when no one was ever told the
  outcome.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST react to a new comment posted on a release
  pull request by evaluating whether that comment's first line is one of
  the six recognized release-command forms, using feature 005's existing
  classification and authorization logic unchanged.
- **FR-002**: The system MUST NOT react at all to a comment posted on
  anything other than a pull request (for example, a plain issue), even if
  its text would otherwise match a recognized command shape.
- **FR-003**: For a comment classified as a recognized, authorized command,
  the system MUST post a reply on the same pull request stating which
  command was accepted and its key details (the ticket key, pull request
  number, or reason, as applicable).
- **FR-004**: For a comment classified as a recognized-but-malformed
  attempt, the system MUST post a reply on the same pull request stating
  that it was not accepted and specifically what about it was invalid,
  distinguishable from an unauthorized refusal.
- **FR-005**: For a syntactically valid command from an author who is not
  authorized to issue it, the system MUST post a reply on the same pull
  request stating it was refused for lack of authorization, distinguishable
  from a malformed-command reply.
- **FR-006**: For a comment that is not a command at all, the system MUST
  take no visible action — no reply, no refusal, no record of an attempt.
- **FR-007**: The system MUST determine the commenter's membership in the
  release-managers team and the current Tech Lead's identity itself (unlike
  feature 005, which took these as given inputs), so that a release manager
  never has to supply or prove their own identity by hand.
- **FR-008**: The system MUST treat a failure to determine team membership
  or Tech Lead identity as its own distinct outcome, never silently
  defaulting to "authorized" and never being indistinguishable from an
  ordinary "unauthorized" refusal.
- **FR-009**: The system MUST NOT ever execute any part of the raw comment
  text as a command or script — only feature 005's fixed parser may
  interpret it.
- **FR-010**: The system MUST record which command was recognized (if any)
  and whether it was ultimately accepted, refused, or could not be
  evaluated, in a form other parts of the platform can read, for every
  comment it reacts to (not only accepted ones).
- **FR-011**: The system MUST NOT make any change to release state (adding
  or removing a ticket from a release, aborting it, or waiving a gate) as a
  result of an accepted command — "accepted" in this feature means
  "recognized, authorized, and acknowledged," not "acted upon," since
  acting on a release remains a separate, not-yet-built capability.
- **FR-012**: Repeated processing of the same comment (for example, if the
  triggering event is redelivered) is explicitly out of scope for
  prevention in this feature; the system MAY react to the same comment more
  than once, and this is a known, documented limitation rather than a
  defect this feature must fix.

### Key Entities

- **Command Outcome Report**: the structured record this feature produces
  for a single comment it reacted to — which of the six forms was
  recognized (if any), whether it was accepted, refused for being
  malformed, refused for lacking authorization, or could not be evaluated
  due to an identity-lookup failure, and the reply text that was (or would
  be) shown back on the pull request. Builds on feature 005's "Command
  Check Result," adding the pull-request-reply and identity-lookup-failure
  dimensions that only exist once this is wired into a real trigger.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every comment on a release pull request matching one of the
  six recognized command forms, from an authorized author, receives a
  reply on that same pull request confirming acceptance, with no manual
  step required.
- **SC-002**: Every malformed or unauthorized command attempt receives a
  reply on the same pull request stating specifically why it was not
  accepted, with the two kinds of refusal always distinguishable from each
  other.
- **SC-003**: No comment that is not one of the six recognized forms ever
  produces a visible reply or refusal.
- **SC-004**: No comment on a non-pull-request issue ever triggers this
  capability, 100% of the time.
- **SC-005**: No command is ever reported as accepted without both the
  grammar check and the authorization check having actually passed for
  that specific comment.

## Assumptions

- Looking up real GitHub team membership and the current Tech Lead's
  identity — deferred by feature 005 to "whatever calls it" — is built by
  this feature, using whatever identity source the platform's release-bot
  automation already relies on; the exact mechanism (API call, caching) is
  a flagged convention (see this feature's `research.md`), not something
  the approved architecture specifies down to that level of detail.
- The recognized `/research close` form has no dedicated outcome category
  in the architecture's existing outcome-reporting contract, which was
  specified only in terms of the five `/release` forms; this feature
  reports `/research close` through the same accepted/malformed/
  unauthorized/could-not-evaluate outcomes as any other recognized form,
  without inventing a new, uncovered outcome category — the exact
  representation is a flagged convention requiring platform-maintainer
  confirmation, the same treatment given to feature 004's `parity.allow`
  convention.
- Preventing the same comment from being processed more than once (e.g. on
  a webhook redelivery) needs persistent state this platform does not yet
  have; feature 005 already flagged this as deferred, and this feature
  inherits that same deferral rather than solving it.
- Writing an entry to the platform's release-manifest audit trail is a
  separate, not-yet-built capability; this feature's Command Outcome
  Report is produced and made available, but nothing yet guarantees it is
  durably recorded beyond the pull request reply itself.
- Any call to an external issue tracker (for example, to cross-reference a
  ticket key) is out of scope; this feature never fabricates such an
  integration and reports that capability, if referenced at all, as not yet
  available — the same honest-reporting pattern feature 003 used for
  capabilities it declared but did not yet implement.
- Actually mutating any release's state (adding/removing a ticket,
  aborting, waiving a gate) remains unimplemented; "accepted" in this
  feature's outcome means the command was recognized and authorized, not
  that a release was changed.
