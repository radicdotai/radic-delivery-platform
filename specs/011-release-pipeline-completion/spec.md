# Feature Specification: Release Pipeline Completion

**Feature Branch**: `011-release-pipeline-completion`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Release pipeline completion — three related
CLI commands that close out the release train after `release propose` and
`release cut`: `radic-delivery release verify-promotion` (confirms a
built artifact's ancestry/tree/tag before it's promoted), `radic-delivery
release finalise` (fast-forwards the production line and tags it once a
release has fully succeeded), and `radic-delivery rollback plan`
(computes, but does not perform, a plan to roll back to a previous
release). Bundled into one feature because all three are small, closely
related steps of the same already-partially-built release pipeline, share
its existing git-operations infrastructure, and are scoped to exactly the
parts testable without live GCP/Docker access in this environment. The
live Cloud-Deploy-digest cross-check in verify-promotion, actually
performing a rollback, and any automatic lookup of 'the previous release'
are all explicitly out of scope, taken as explicit input instead."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A release manager confirms exactly what's about to be promoted (Priority: P1)

Before a built artifact is promoted to the next environment, a release
manager needs certainty that what's about to be promoted is exactly what
was built and reviewed — the same commit history, the same file tree, the
same expected tag — and a specific, named reason the moment anything
doesn't match.

**Why this priority**: this is a safety check sitting directly in front of
a promotion decision; without it, nothing stops a different, unreviewed,
or altered artifact from being promoted by mistake.

**Independent Test**: can be fully tested by supplying a release head and
an expected source commit/tree/tag from a real local git repository, once
where everything matches and once where one specific fact doesn't,
confirming each check is reported individually and accurately.

**Acceptance Scenarios**:

1. **Given** a release head that is genuinely a descendant of the commit
   the artifact was built from, with an unaltered file tree and the
   expected tag present, **When** promotion is verified, **Then** all
   three checks are reported as confirmed.
2. **Given** a release head that is **not** actually a descendant of the
   expected source commit, **When** promotion is verified, **Then** the
   ancestry check specifically is reported as failed, distinguishable from
   the other two checks.
3. **Given** the expected tag is missing or points at the wrong commit,
   **When** promotion is verified, **Then** the tag check specifically is
   reported as failed.
4. **Given** no Cloud Deploy release name was supplied at all, **When**
   promotion is verified, **Then** the Cloud-Deploy-digest check is
   reported as not available, never silently omitted and never treated as
   passed or failed.

---

### User Story 2 - A fully successful release moves the production line forward exactly once (Priority: P1)

Once a release has fully succeeded in production, the production line
needs to be fast-forwarded to it and tagged — and this must happen
exactly once per release, never silently skipped and never repeated.

**Why this priority**: this is the step that actually closes out a
release; getting it wrong either leaves production permanently behind
what was actually released, or risks doing it twice and corrupting the
production line's history.

**Independent Test**: can be fully tested by supplying a release whose
manifest is in the expected pre-finalise state and confirming the
production line is fast-forwarded and tagged exactly as expected; and
separately supplying a manifest already past that state, confirming the
operation refuses rather than repeating itself.

**Acceptance Scenarios**:

1. **Given** a release manifest indicating the release has fully succeeded
   in production, **When** the release is finalised, **Then** the
   production line is moved forward to exactly the release's own head,
   a new tag is created at that point, and the manifest is updated to
   reflect that this release is now finalised.
2. **Given** a manifest that has already been finalised, **When**
   finalising is attempted again, **Then** it is refused, naming the
   manifest's actual state, and nothing changes.
3. **Given** a manifest claiming success but whose release is not actually
   ahead of the current production line, **When** finalising is
   attempted, **Then** it is refused rather than forcing a change that
   isn't a straightforward forward move.

---

### User Story 3 - A clear rollback plan is computed before anyone commits to acting on it (Priority: P2)

When something has gone wrong after a release, a release manager needs a
specific, clear plan — which release and artifact to roll back to, for
which environment — computed and shown before anyone commits to actually
doing it.

**Why this priority**: this is a safety-net, read-only planning capability
rather than a step every release goes through; it depends on nothing else
in this feature and is sequenced after the two higher-priority release-
closing steps.

**Independent Test**: can be fully tested by supplying a current and a
target release/artifact for a given environment and confirming the plan
names both clearly, without performing any action.

**Acceptance Scenarios**:

1. **Given** a current release and a target (previous) release/artifact
   for a specific environment, **When** a rollback plan is requested,
   **Then** a plan is produced naming the environment, the current state,
   and the target to roll back to — and nothing about the environment is
   changed.
2. **Given** the same inputs requested twice, **When** a rollback plan is
   produced each time, **Then** both plans are identical — this is a pure
   computation, not an action with side effects.

### Edge Cases

- What happens when `release verify-promotion` is asked to check a commit
  that doesn't exist in the given repository at all? It fails clearly,
  distinguishable from a genuine ancestry/tree/tag mismatch.
- What happens when `release finalise` is asked to finalise a release
  whose branch no longer exists? It refuses cleanly, naming the problem,
  rather than fast-forwarding to nothing.
- What happens when `rollback plan`'s target is the same as the current
  release? The plan is still produced, stating plainly that no actual
  change would occur — not an error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST independently verify and report, for a
  given release head and the commit/tree/tag an artifact is expected to
  have come from: whether the release head is genuinely descended from
  that commit, whether the file tree at that commit is unaltered, and
  whether the expected tag exists and points at the right place —
  reporting each of these three facts distinctly, never combined into a
  single pass/fail outcome.
- **FR-002**: When no Cloud Deploy release identifier is supplied, the
  system MUST report the Cloud-Deploy-digest check as not available,
  never silently omitted and never reported as passed or failed.
- **FR-003**: The system MUST refuse to finalise a release whose manifest
  is not in the expected "fully succeeded in production" state, naming
  the manifest's actual state, and MUST NOT make any change in that case.
- **FR-004**: On a valid finalisation, the system MUST move the real
  production line forward to exactly the release's own head, create a
  real tag at that point, and update the manifest to record that this
  release is now finalised — all three together, or none of them if
  anything fails partway through.
- **FR-005**: The system MUST refuse to finalise a release whose head is
  not actually ahead of the current production line in a straightforward
  way, rather than forcing a change that isn't a clean forward move.
- **FR-006**: The system MUST compute a rollback plan from an explicitly
  supplied current state and target release/artifact for a given
  environment, without performing any action and without needing to look
  up either value itself.
- **FR-007**: A rollback plan MUST clearly name the environment, the
  current state, and the specific target being planned for.
- **FR-008**: This feature MUST NOT make any external network call (to
  Jira, GitHub, or any GCP service) in the course of any of its three
  commands.
- **FR-009**: Every result MUST be available in both a human-readable
  form and a machine-readable form carrying the same facts, consistent
  with every other command this platform's CLI already provides.

### Key Entities

- **Promotion Verification Result**: the outcome of one `verify-
  promotion` check — the three individually-reported git facts (ancestry,
  tree, tag), plus the Cloud-Deploy-digest fact when requested (or marked
  not available when it wasn't).
- **Finalisation Result**: the outcome of one `finalise` attempt — whether
  it succeeded, and if so, the production line's new position and the
  tag created; if refused, specifically why.
- **Rollback Plan**: the computed plan from one `rollback plan` request —
  the environment, the current state, and the target being rolled back
  to.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the three promotion-verification facts is reported
  individually and accurately, 100% of the time — a failure in one never
  obscures or is confused with the state of the other two.
- **SC-002**: A release is never finalised more than once; a second
  attempt is always refused, naming the manifest's actual state.
- **SC-003**: A successful finalisation always results in the production
  line and its tag reflecting exactly the finalised release's head — never
  a different commit, never left partially updated.
- **SC-004**: A rollback plan always names the environment, current
  state, and target explicitly, and never changes anything about the
  environment it describes.

## Assumptions

- Comparing a Cloud Deploy release's recorded digest against the stage-
  tested digest (the optional, Cloud-Deploy-backed half of `verify-
  promotion`) requires a live GCP call this sandbox cannot make; it
  remains out of scope, reported as not-available rather than attempted
  or faked — the same honest-reporting precedent specs/003/007 already
  set for their own undeployable/not-yet-built real-world paths.
- A release manifest reaching the "fully succeeded in production" status
  `finalise` expects as its starting point is produced by a separate,
  not-yet-built capability (an actual prod deploy and its gate); this
  feature only consumes that status as given, the same way specs/009's
  `release cut` only consumes a `proposed` manifest as given.
- Restricting `finalise` to only ever be run by the release bot, never a
  human directly, is a real-world identity restriction on whatever calls
  this command, not something this CLI command enforces itself — the same
  identity-boundary split already established for specs/005's team-
  membership/Tech-Lead checks.
- Resolving "the previous release" or "the current release" automatically
  for `rollback plan` would require a live call to this platform's
  shared release history, which this sandbox cannot make; both are
  supplied explicitly by the caller instead.
- Actually performing a rollback (applying the computed plan) is a
  separate, not-yet-built capability (`deploy rollback`, already stubbed)
  — this feature only ever plans, never acts.
