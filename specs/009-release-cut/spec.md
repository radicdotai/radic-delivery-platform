# Feature Specification: Release Branch Creation and Cherry-Pick

**Feature Branch**: `009-release-cut`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Release branch creation and cherry-pick —
`radic-delivery release cut`, the command that takes a draft release
manifest (specs/008's `release propose` output) and turns its selection
into a real release branch: creating `release/<id>` from the current
production line and cherry-picking exactly the selected commits onto it,
recording what actually happened back into the manifest. A cherry-pick
conflict aborts the entire operation cleanly, leaving no half-cut branch
behind. Immediately before cherry-picking, every selected commit must
still have a change-note record, per the architecture's own stated safety
rule — a commit that has lost its record stops the cut rather than being
silently cherry-picked anyway. Opening the actual release pull request is
a separate, later concern (a reusable workflow's job, not this command's)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An approved proposal becomes a real release branch with exactly what was approved (Priority: P1)

A release manager has an approved draft proposal and wants the real
release branch created, containing exactly the commits that were
approved — nothing more, nothing silently added or dropped — in a
correct, conflict-free order.

**Why this priority**: this is the entire reason the command exists —
without reliably turning an approved selection into a real branch with
exactly that selection on it, nothing downstream (a real release PR, a
real deploy) has anything trustworthy to build on.

**Independent Test**: can be fully tested by supplying an approved draft
manifest selecting a known set of commits from a real local git
repository, running the cut, and confirming the resulting branch contains
exactly those commits, correctly recorded back into the manifest.

**Acceptance Scenarios**:

1. **Given** an approved draft manifest selecting two commits for two
   different tickets, **When** the release is cut, **Then** a new branch
   is created containing exactly those two commits, in the order they
   originally occurred, and the manifest records each commit's new
   location on that branch.
2. **Given** a successful cut, **When** it completes, **Then** the
   manifest's status moves from its draft state to a cut state, and
   records the resulting branch's name and tip.
3. **Given** the manifest indicates this is a hotfix, **When** the release
   is cut, **Then** the resulting branch and its naming reflect that
   distinctly from an ordinary release.

---

### User Story 2 - A cherry-pick conflict stops the whole operation, cleanly (Priority: P1)

A selected commit can no longer be cleanly applied to the current
production line (its conflicts with something already there). The release
manager needs to be told exactly which commit failed and why, and needs
certainty that nothing was left half-done — no partial branch, no
manifest silently marked as cut when it wasn't.

**Why this priority**: equally foundational to User Story 1 — a command
that can create a correct branch but can't be trusted to fail safely on a
real conflict (which will happen in practice) isn't safe to use at all;
both together are the minimum viable, trustworthy version of this
capability.

**Independent Test**: can be fully tested by supplying a draft manifest
that selects a commit known to conflict with the current production line,
running the cut, and confirming the operation reports the specific
failing commit, makes no change to the manifest, and leaves no
partially-created branch behind.

**Acceptance Scenarios**:

1. **Given** a selected commit that conflicts when applied to the current
   production line, **When** the release is cut, **Then** the operation
   fails, naming that specific commit as the cause.
2. **Given** a cut that failed partway through (some commits already
   applied, one failing), **When** the failure happens, **Then** nothing
   of the attempted branch remains, and the original manifest is
   unchanged.

---

### User Story 3 - A commit that has lost its change-note record stops the cut before anything happens (Priority: P2)

Before any branch is touched, every commit the manifest selected must
still have its change-note record. If one has gone missing since the
manifest was drafted, the release manager needs to be told specifically
which commit, so they can address it before trying again — not have the
cut proceed on an assumption that's no longer true.

**Why this priority**: this is a safety check on an input the first two
stories already assume is trustworthy; it depends on the cutting mechanism
already existing (so there's something to prevent), so it's sequenced
after the core P1 behaviours, but it is a stated, non-negotiable safety
rule, not an optional nicety.

**Independent Test**: can be fully tested by supplying a draft manifest
that selects a commit whose change-note record is missing, running the
cut, and confirming it stops before any branch is created, naming the
specific commit.

**Acceptance Scenarios**:

1. **Given** a selected commit with no matching change-note record,
   **When** the release is cut, **Then** the operation stops before
   creating any branch, naming that specific commit as the reason.
2. **Given** every selected commit still has its change-note record,
   **When** the release is cut, **Then** this check does not block
   anything, and cutting proceeds normally.

### Edge Cases

- What happens when the caller asks to preview the cut without actually
  performing it? Every check (missing change-note records, the exact
  commit order, hotfix/ordinary branch naming) is still computed and
  reported, but no branch is created and the manifest is not changed.
- What happens when the supplied release identifier or hotfix indicator
  doesn't match what the manifest itself records? The operation is
  refused before anything is touched, rather than proceeding on
  mismatched assumptions.
- What happens when the manifest's status isn't the expected
  freshly-proposed state (for example, it was already cut once)? The
  operation is refused, naming the manifest's actual status, rather than
  cutting a second time over an already-cut release.
- What happens when the manifest selects zero commits at all? The branch
  is still created (from the current production line, with nothing
  cherry-picked onto it) and the manifest is still updated to the cut
  state — an empty release is a valid, if unusual, outcome, not an error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST read an existing draft release manifest and
  refuse to proceed, naming the specific mismatch, if the manifest's own
  identifying details (its release identifier, whether it is a hotfix)
  don't match what the caller asked to cut.
- **FR-002**: The system MUST refuse to proceed, naming the manifest's
  actual status, unless that manifest is in the freshly-proposed state
  this feature expects to act on.
- **FR-003**: Before making any change to the repository, the system MUST
  verify that every commit the manifest selected still has a matching
  change-note record, and MUST stop, naming the specific commit, if any
  one of them does not.
- **FR-004**: The system MUST create a new release branch from the
  current tip of the production line, never from any other starting
  point, and never from a caller-suppliable arbitrary reference.
- **FR-005**: The system MUST apply every selected commit onto the new
  branch in the order those commits actually occurred, never in an
  arbitrary or caller-specified order.
- **FR-006**: If any selected commit cannot be applied cleanly, the system
  MUST stop the entire operation, name the specific commit that failed,
  and MUST NOT leave any partially-created branch or other repository
  change behind.
- **FR-007**: On success, the system MUST update the manifest to record
  the new branch's name, its resulting tip, each cherry-picked commit's
  new location, and the manifest's new status — and MUST NOT make this
  update if the operation did not fully succeed.
- **FR-008**: The system MUST support a preview mode that performs every
  check and computes every outcome above without creating a branch or
  changing the manifest.
- **FR-009**: This feature MUST NOT open a pull request, call any Cloud
  Deploy or other GCP service, or delete any branch — producing the real
  release branch and the updated manifest is the entire scope of this
  feature.
- **FR-010**: Every result MUST be available in both a human-readable
  form and a machine-readable form carrying the same facts, consistent
  with every other command this platform's CLI already provides.

### Key Entities

- **Cut Result**: the outcome of one `release cut` attempt — whether it
  succeeded, and if not, specifically why (a mismatched manifest, a
  missing change-note record, or a named commit that failed to apply
  cleanly); on success, the new branch's name and tip and the updated
  per-commit locations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A successfully cut release branch contains exactly the
  commits the approved manifest selected, in their original order, 100%
  of the time.
- **SC-002**: A cherry-pick conflict is reported with the specific commit
  responsible, and leaves no partially-created branch or manifest change
  behind, 100% of the time.
- **SC-003**: A commit missing its change-note record stops the cut
  before any branch is touched, 100% of the time, naming that specific
  commit.
- **SC-004**: A manifest whose identifying details or status don't match
  what was asked for is refused before anything is touched, 100% of the
  time.

## Assumptions

- The manifest to cut, and the local change-note records to re-verify
  against, are read from local paths, the same local-first approach
  specs/007 and specs/008 already established — no live Jira, GCS, or
  `delivery-records` call is made by this feature either.
- Opening the real release pull request, writing its body, and any
  further GitHub interaction is the responsibility of a later, separate
  capability (the architecture's own `release-cut` reusable workflow) —
  this feature only produces the branch and the updated manifest.
- Actually deleting a release branch is the responsibility of the
  `/release abort` command form specs/005 already parses but does not
  yet act on — this feature does not delete branches under any
  circumstance, including its own failure paths (where nothing is created
  in the first place, so there is nothing to delete).
- A migration-dependency relationship between selected tickets (one
  ticket's database migration being a prerequisite for another's,
  affecting cherry-pick order beyond plain chronological order) is not
  evaluated by this feature — commits are ordered strictly by when they
  occurred.
