# Feature Specification: Cut-Time Open-Release Guard

**Feature Branch**: `018-cut-time-open-release-guard`

**Created**: 2026-11-06

**Status**: Draft

**Input**: User description: "Cut-time open-release guard — the second
spec in an 11-spec roadmap implementing the C1-C13 architecture-review
changes to radic-delivery-platform. Per Confluence RAITSDA Runbook
§3.2/§5.1 and Reference 2 §3.4 (review comment C11): 'Stage deploys
automatically on every release/* push. If release N is in UAT and N+1 is
cut, N gets replaced mid-UAT... a rule that a new cut waits until the open
release ships or is aborted.' Reference 2 §3.4 documents the resulting
contract precisely: 'Guard: the cut refuses when this service already has
an open release (status before finalised, aborted or failed) or an open
release PR.' `release cut` gains a new, explicit, optional parameter
representing every other already-known manifest for the same service
repo (the established 'explicit input, never a live delivery-records
lookup' boundary); before any git branch operation, it refuses the cut —
a new, named reason — if any other manifest for the same repo has a
status that is not finalised/aborted/failed. Omitted or empty, behavior
is unchanged. A corresponding CLI option lets this be exercised
end-to-end. The GitHub Actions stage-concurrency-group and stage
Environment branch-policy configuration this same review comment also
calls for is explicitly deferred to a later platform-config spec in the
same roadmap — this feature is the cut-time refusal only."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A second release for the same service is refused while one is still open (Priority: P1)

Whoever cuts a release needs to be stopped, with a specific and named
reason, from starting a second release for a service whose first release
hasn't yet finished (or been explicitly aborted) — never allowed to
silently replace it mid-review.

**Why this priority**: this is the entire feature; there is no smaller
independently-valuable slice, and it is fully testable on its own with
real local git fixtures and no dependency on any other spec in the
roadmap.

**Independent Test**: can be fully tested by attempting to cut a release
for a service while supplying another already-known manifest for that
same service whose status is still open, confirming the cut refuses
cleanly, names the other release and its status, and creates no branch —
then confirming the cut proceeds normally when that same other manifest
is closed, for a different service, or simply not supplied at all.

**Acceptance Scenarios**:

1. **Given** another known manifest for the same service repo whose
   status is not yet `finalised`, `aborted`, or `failed`, **When** a new
   release is cut for that service, **Then** the cut is refused before
   any branch is created, with a reason naming the other release's id and
   its current status.
2. **Given** another known manifest for the same service repo whose
   status is `finalised`, `aborted`, or `failed`, **When** a new release
   is cut for that service, **Then** the cut proceeds exactly as it would
   without that manifest present.
3. **Given** another known manifest whose status is still open but whose
   service repo differs from the one being cut, **When** the new release
   is cut, **Then** the cut proceeds — the guard only ever considers
   manifests for the same service.
4. **Given** no other manifests are supplied at all, **When** a release is
   cut, **Then** behavior is identical to every release cut before this
   feature existed.

### Edge Cases

- What happens when one of the "other" manifests supplied is actually the
  same release being cut (same release id)? It is never treated as a
  blocker against itself — only a genuinely different release id for the
  same service counts.
- What happens when multiple other manifests for the same service are
  open at once? The cut is refused naming the first one found; the
  specific choice of which one is named when several qualify is not
  significant, since any one of them is sufficient grounds for refusal.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept, as explicit optional input, a set
  of other already-known release manifests to check against when cutting
  a release — never performing a live lookup of its own to discover them.
- **FR-002**: The system MUST refuse to cut a release when any supplied
  other manifest belongs to the same service repo, has a different
  release id, and has a status other than finalised, aborted, or failed.
- **FR-003**: The refusal in FR-002 MUST happen before any git branch is
  created, and MUST name the specific other release id and its status in
  the refusal detail.
- **FR-004**: The system MUST ignore any supplied other manifest that
  belongs to a different service repo, regardless of its status.
- **FR-005**: The system MUST ignore any supplied other manifest that
  shares the same release id as the release being cut.
- **FR-006**: When no other manifests are supplied, or none qualify under
  FR-002 through FR-005, the system MUST behave exactly as it did before
  this feature existed — no change to any existing acceptance behavior.
- **FR-007**: The command-line interface MUST provide a way to supply one
  or more other manifests from local files, exercising FR-001 through
  FR-006 end-to-end.

### Key Entities

- **Open Release**: a release manifest whose status has not yet reached
  `finalised`, `aborted`, or `failed` — the state this feature treats as
  still in flight and therefore blocking a new cut for the same service.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A service can never have two releases cut and open at the
  same time once this feature's guard is exercised with accurate other-
  manifest input.
- **SC-002**: Every refusal under this feature names a specific other
  release and its status — never a generic, unexplained failure.
- **SC-003**: No existing release-cut behavior changes for a caller that
  doesn't supply any other manifests.
- **SC-004**: Every functional requirement is verified by a real,
  unmocked local git fixture — no GCP, Docker, or live Jira/GitHub/
  delivery-records call anywhere in this feature.

## Assumptions

- Discovering the full, accurate set of "other" manifests for a service
  is the calling workflow's responsibility (reading `delivery-records`,
  a live system this sandbox cannot call) — this feature only consumes
  that set once supplied, the same boundary already drawn for `rollback
  plan`'s current/previous-release inputs.
- The GitHub Actions stage-concurrency-group and stage-Environment
  branch-policy configuration the same review comment also calls for is
  platform configuration, not engine logic, and is out of scope for this
  feature — deferred to a later platform-config spec in the same roadmap.
- Prereqs/Depends-on fields, the migration head lockfile, hotfix merge-
  revision handling, cross-repo schema ownership, revert-pair netting,
  subset-mode selection, the cross-repo all-or-none release-gate check,
  non-removable-ticket refusal, and the verify-promotion build-provenance
  rework are all out of scope for this feature — each is a separate,
  later spec in the same roadmap.
