# Feature Specification: Release Slash-Command Parser and Authorization Check

**Feature Branch**: `005-release-command-parser`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "Release slash-command parser and authorization
check — the engine command that powers the `release-commands` reusable
workflow's comment-handling. The grammar is already fully specified: exactly
six valid command forms (`/release remove KEY`, `/release add KEY reason:
TEXT`, `/release nonjira PR reason: TEXT`, `/release abort`, `/release waive
dev-green reason: TEXT`, `/research close`), one command per comment, only
the first line is read, the verb is case-insensitive, the author must belong
to the release-managers team, and `waive dev-green` is restricted to the
Tech Lead alone. This feature parses and authorizes a comment given explicit
inputs (author, team membership, Tech Lead identity) — it does not act on a
release, call any GitHub or GCP API, or implement the other `release`
subcommands."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A valid, authorized command is recognized precisely (Priority: P1)

A release manager comments one of the six recognized commands on a release
pull request — for example, to pull a ticket back out of the release before
it ships. They need the exact command and its arguments recognized
correctly, every time, so the system acting on their instruction later
(a future feature) can trust it was really authorized and really means
what it says.

**Why this priority**: this is the entire reason the parser exists —
without reliably recognizing a genuine, authorized command, nothing else in
this feature matters. It is independently valuable and testable on its own.

**Independent Test**: can be fully tested by feeding each of the six exact
command forms, from an author who is a release manager, and confirming each
is recognized as valid and authorized with its arguments correctly
extracted — independent of any rejection-path behaviour.

**Acceptance Scenarios**:

1. **Given** a comment whose first line is exactly `/release remove
   RAD-123` from a release manager, **When** it is checked, **Then** it is
   recognized as valid and authorized, naming the command as "remove" with
   the ticket key `RAD-123`.
2. **Given** a comment whose first line is exactly `/release add RAD-456
   reason: customer asked for it` from a release manager, **When** it is
   checked, **Then** it is recognized as valid and authorized, naming the
   command as "add" with the ticket key and the reason text.
3. **Given** a comment whose first line is exactly `/release nonjira 42
   reason: hotfix for broken build` from a release manager, **When** it is
   checked, **Then** it is recognized as valid and authorized, naming the
   command as "nonjira" with the pull request number and the reason text.
4. **Given** a comment whose first line is exactly `/release abort` from a
   release manager, **When** it is checked, **Then** it is recognized as
   valid and authorized, with no arguments.
5. **Given** a comment whose first line is exactly `/research close` from a
   release manager, **When** it is checked, **Then** it is recognized as
   valid and authorized, with no arguments.
6. **Given** the same six commands typed with the verb in a different
   letter case (for example `/release REMOVE RAD-123`), **When** checked,
   **Then** each is still recognized exactly as its lowercase form.

---

### User Story 2 - An ordinary comment is quietly not a command (Priority: P1)

Most comments on a release pull request are ordinary conversation, not
commands at all. The system must recognize this instantly and say so
plainly — never treating an ordinary comment as a malformed command, and
never raising it as if something went wrong.

**Why this priority**: equally foundational to User Story 1 — a system that
cannot tell "not a command" apart from "a broken command" will either spam
every PR discussion with rejection noise or risk mis-firing on ordinary
text. Both stories are P1 because the feature is incomplete without either.

**Independent Test**: can be fully tested by feeding ordinary, command-like-
only-by-coincidence, and clearly unrelated comment text and confirming every
one is classified as "not a command," independent of how real commands are
classified.

**Acceptance Scenarios**:

1. **Given** a comment that is ordinary conversation ("looks good to me!"),
   **When** it is checked, **Then** it is classified as not a command, not
   as an error.
2. **Given** a comment whose first line merely mentions the word "release"
   without starting with the required leading shape, **When** it is
   checked, **Then** it is classified as not a command.
3. **Given** a multi-line comment where a later line (not the first) looks
   like a valid command, **When** it is checked, **Then** only the first
   line is considered, and if the first line is not a command, the whole
   comment is classified as not a command regardless of later lines.

---

### User Story 3 - A broken command is rejected with a specific reason (Priority: P2)

Someone attempts a command but gets the shape wrong — a typo'd verb, a
missing required argument, or an invented seventh form that doesn't exist.
They need to know their command was recognized as an *attempt* but was
rejected, and specifically why, so they can fix it and try again, rather
than wondering if it silently did nothing.

**Why this priority**: this is the "attempted but malformed" middle ground
between a real command (Story 1) and no command at all (Story 2); it
depends on both already being distinguishable, so it is correctly
sequenced after them, but it is still core, not optional.

**Independent Test**: can be fully tested by feeding comments that start
with the right leading shape but have an invalid verb, a missing required
argument, or extra unexpected content, and confirming each is rejected with
a reason distinct from both "not a command" and "unauthorized."

**Acceptance Scenarios**:

1. **Given** a comment starting `/release` followed by a verb that is not
   one of the five recognized release verbs, **When** checked, **Then** it
   is rejected as an unrecognized command, distinct from "not a command."
2. **Given** `/release add RAD-123` with no `reason:` text at all, **When**
   checked, **Then** it is rejected for a missing required argument, naming
   which argument is missing.
3. **Given** `/release waive` followed by anything other than the exact
   literal `dev-green`, **When** checked, **Then** it is rejected as an
   unrecognized command.
4. **Given** `/research` followed by a verb that is not `close`, **When**
   checked, **Then** it is rejected as an unrecognized command.

---

### User Story 4 - An unauthorized author is told exactly why they were refused (Priority: P2)

A person who is not a release manager — or who is a release manager but
attempts the one command reserved for the Tech Lead alone — posts an
otherwise well-formed command. They need to be refused clearly, with the
refusal distinguishable from "this isn't a real command" or "this command
is malformed," so nobody mistakes a permissions problem for a typo.

**Why this priority**: authorization is the security-relevant heart of this
feature (the same "no arbitrary commands" principle applied to human input)
but depends on syntax recognition (Stories 1 and 3) already working
correctly, so it is sequenced after them.

**Independent Test**: can be fully tested by feeding a syntactically valid
command from a non-release-manager, and separately feeding the Tech-Lead-
only command from an ordinary release manager, confirming both are refused
for an authorization reason distinct from a syntax reason.

**Acceptance Scenarios**:

1. **Given** a syntactically valid `/release remove RAD-123` from someone
   who is not on the release-managers team, **When** checked, **Then** it
   is refused for lacking authorization, not treated as malformed or
   accepted.
2. **Given** a syntactically valid `/release waive dev-green reason: ...`
   from a release manager who is not the Tech Lead, **When** checked,
   **Then** it is refused specifically because this one command is
   Tech-Lead-only, distinguishable from the general release-managers
   authorization rule.
3. **Given** the same Tech-Lead-only command from the Tech Lead themselves,
   **When** checked, **Then** it is accepted.

### Edge Cases

- What happens when the comment body is empty or contains only whitespace?
  It must be classified as not a command, not as an error.
- What happens when the first line has correct structure but trailing
  whitespace or extra spaces between tokens? Reasonable whitespace
  variation around the fixed tokens should still be recognized, since a
  person typing by hand will not always space things identically.
- What happens when the same comment is checked more than once (for
  example, if the surrounding system retries)? This feature's own output
  does not change between identical calls — out-of-scope is making sure
  the *effect* of a command only happens once; that needs state this
  feature does not introduce (see Assumptions).
- What happens when the author is both the Tech Lead and a release manager
  (the expected case) and uses an ordinary release-manager command, not the
  Tech-Lead-only one? It is authorized under the ordinary release-managers
  rule, same as any other release manager.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST classify a given comment's first line into
  exactly one of: not a command, a recognized form with invalid or missing
  arguments, a syntactically valid command the author is not authorized
  for, or a valid and authorized command.
- **FR-002**: The system MUST recognize exactly six command forms and no
  others: `release remove`, `release add`, `release nonjira`, `release
  abort`, `release waive dev-green` (a fixed literal, not a variable
  argument), and `research close`.
- **FR-003**: The system MUST read only the comment's first line; content
  on any other line MUST NOT affect the classification.
- **FR-004**: The system MUST match the command's verb without regard to
  letter case.
- **FR-005**: For `release remove` and `release add`, the system MUST
  extract the ticket key argument; for `release add` and `release nonjira`
  and `release waive dev-green`, the system MUST extract the required
  reason text (or pull request number, for `nonjira`); `release abort` and
  `research close` MUST take no arguments.
- **FR-006**: A command missing a required argument, or carrying an
  argument shape that does not match what that command requires, MUST be
  rejected as a recognized-but-malformed command, distinguishable from "not
  a command" and from an authorization refusal.
- **FR-007**: Comment text that does not begin with the grammar's required
  leading shape MUST be classified as not a command, never as an error or a
  rejection.
- **FR-008**: A syntactically valid command MUST be authorized only when
  its author belongs to the release-managers team; otherwise it MUST be
  refused for lacking authorization, with that refusal distinguishable from
  a syntax rejection.
- **FR-009**: The `release waive dev-green` command specifically MUST be
  authorized only for the Tech Lead; a release manager who is not the Tech
  Lead attempting it MUST be refused, with that refusal distinguishable
  from the general release-managers authorization rule.
- **FR-010**: Team membership and Tech Lead identity MUST be supplied to
  this feature as explicit input; this feature MUST NOT look either of
  these up itself.
- **FR-011**: This feature MUST NOT take any action on a release, post
  anything back to a pull request, or call any external service; its only
  output is the classification and, where applicable, the extracted
  command and arguments.
- **FR-012**: The result MUST be available in both a human-readable form
  and a machine-readable form carrying the same facts, consistent with
  every other command this platform's CLI already provides.

### Key Entities

- **Command Check Result**: the single, structured outcome of checking one
  comment — its classification (not a command / malformed / unauthorized /
  accepted), and, when accepted, which of the six forms it is and its
  extracted arguments.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the six valid command forms, from an authorized
  author, is recognized correctly with its arguments extracted accurately,
  100% of the time, regardless of the verb's letter case.
- **SC-002**: Ordinary, non-command PR conversation is classified as "not a
  command" 100% of the time, never surfaced as an error or a rejection.
- **SC-003**: A malformed attempt at a command is distinguishable from both
  "not a command" and "unauthorized" 100% of the time, with a reason
  specific enough that a person can fix and retry without guessing.
- **SC-004**: An unauthorized author's attempt, and a non-Tech-Lead's
  attempt at the Tech-Lead-only command, are each refused 100% of the time,
  with the two refusal reasons distinguishable from each other.

## Assumptions

- Looking up real GitHub team membership and the current Tech Lead's
  identity is the responsibility of whatever calls this feature (the
  eventual `release-commands` reusable workflow); this feature only
  consumes them as already-resolved input, the same split already
  established for `gate evaluate` (toolchain installation) and `security
  scan` (scanner installation).
- The architecture's "each comment id processed once" rule needs
  persistent state (tracking which comments have already been acted on)
  that this feature deliberately does not introduce — this feature answers
  "what does this comment mean and is it authorized," not "has this
  already been handled," which is a concern for whatever later feature
  acts on an accepted command.
- This feature does not implement the `release-commands` reusable workflow,
  nor the other `release` subcommands (`propose`, `cut`, `verify-
  promotion`, `finalise`) — all remain exactly as unimplemented as every
  other not-yet-built part of this platform.
- Reasonable whitespace variation (extra spaces between tokens, trailing
  whitespace) is tolerated when recognizing a command's shape; this is a
  usability default for hand-typed comments, not a change to the six fixed
  forms themselves.
