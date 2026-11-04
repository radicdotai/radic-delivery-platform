# Feature Specification: Cleanup Workflow (branches scope only)

**Feature Branch**: `016-cleanup-branches-workflow`

**Created**: 2026-11-04

**Status**: Draft

**Input**: User description: "Cleanup workflow (branches scope only) — the
`cleanup` reusable GitHub Actions workflow (Confluence RAITSDA Reference 2:
Workflow Contracts, §3.11), this platform's sixth reusable workflow after
`ci`, `security`, `release-commands`, `release-cut`, and `hotfix-backport`.
Reference 2 names four cleanup scopes (`research`, `branches`, `images`,
`all`): `research` and `images` both require live GCP calls and are
explicitly out of scope for this feature — this feature covers only the
`branches` scope: deleting merged `release/**` branches, a purely
local-git/GitHub-API operation with zero GCP dependency. Bundled with a
new, small, genuinely testable engine command this workflow depends on:
`radic-delivery cleanup branches`, which finds every `release/**` branch
whose tip commit is already an ancestor of `main` and whose last commit
is older than a retention window, and deletes it — reporting exactly
which branches were deleted, which were kept and why, and never touching
`main`, `dev`, or the currently checked-out branch under any
circumstances. Defaults to `dry_run: true`."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A fast-forwarded release branch is cleaned up automatically, never a protected branch (Priority: P1)

Once a release has been promoted to production and `main` has moved past
a release branch's tip commit, that branch is pure clutter — but a
platform maintainer needs certainty that cleaning it up can never, under
any circumstance, touch `main`, `dev`, or whatever branch happens to be
checked out, and that a branch too recent to be safe to remove yet is
left alone.

**Why this priority**: this is the entire value of the feature; every
other part depends on this command existing and being safe.

**Independent Test**: can be fully tested by creating a real local
repository with a `main` branch, a `release/**` branch merged into it
(fast-forwarded past), and one not yet merged, then running the command
once in dry-run mode (nothing deleted, both reported) and once for real
(only the merged, old-enough one actually deleted).

**Acceptance Scenarios**:

1. **Given** a `release/**` branch whose tip is an ancestor of `main` and
   whose last commit is older than the retention window, **When** cleanup
   runs for real (not dry-run), **Then** that branch is deleted and named
   in the deleted list.
2. **Given** a `release/**` branch whose tip is an ancestor of `main` but
   whose last commit is newer than the retention window, **When** cleanup
   runs, **Then** that branch is kept, named in the kept list with the
   reason "too recent."
3. **Given** a `release/**` branch whose tip is not yet an ancestor of
   `main`, **When** cleanup runs, **Then** that branch is kept, named in
   the kept list with the reason "not yet merged."
4. **Given** any run, **When** cleanup examines `main`, `dev`, or the
   currently checked-out branch, **Then** none of them is ever deleted or
   even considered as a candidate, regardless of ancestry or age.
5. **Given** dry-run mode (the default), **When** cleanup runs, **Then**
   every branch that would be deleted is named in the report exactly as
   it would be in a real run, but no branch is actually deleted.

### Edge Cases

- What happens when no `release/**` branches exist at all? The command
  reports zero deleted, zero kept — a plain empty result, not an error.
- What happens when every `release/**` branch is still unmerged? The
  command reports all of them kept, none deleted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST only ever consider branches matching
  `release/**` as deletion candidates — never any other branch name.
- **FR-002**: The system MUST never delete `main`, `dev`, or the branch
  currently checked out, even if one of them happens to match
  `release/**` or satisfies the merged/age conditions.
- **FR-003**: The system MUST delete a candidate branch only when its tip
  commit is an ancestor of `main` AND its last commit is older than the
  configured retention window.
- **FR-004**: The system MUST report, by name, every branch deleted and
  every branch kept, with a specific reason for each kept branch ("not
  yet merged" or "too recent").
- **FR-005**: The system MUST default to a dry run (reporting only,
  deleting nothing) unless real deletion is explicitly requested.
- **FR-006**: The reusable workflow MUST push each locally-deleted branch's
  removal to the remote, since a local-only deletion in a CI run has no
  lasting effect.
- **FR-007**: This feature MUST NOT make any GCP call of any kind — the
  `research` and `images` cleanup scopes are explicitly out of scope.

### Key Entities

- **Cleanup Branches Result**: the outcome of one `cleanup branches` run —
  the branches deleted, the branches kept (each with its specific
  reason), and whether the run was a dry run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `main`, `dev`, and the currently checked-out branch are
  never deleted, in any test scenario, under any combination of inputs.
- **SC-002**: Every kept branch's reason is always one of two specific,
  named reasons — never an unexplained omission from the deleted list.
- **SC-003**: A dry run and a real run against the same repository state
  always agree on which branches would be/were deleted.
- **SC-004**: The reusable workflow passes `actionlint` and `zizmor` with
  zero error/warning findings, verified directly.

## Assumptions

- The retention window's default value for the `branches` scope is a new,
  flagged convention (Reference 2 only states explicit defaults of 30
  days for `images` and 7 days for `research`, not `branches`) —
  documented in research.md.
- "Merged" for a release branch means its tip is a real git ancestor of
  `main` (the fact `release finalise`, specs/011, itself establishes by
  fast-forwarding `main` to the release head) — never a GitHub PR-merge
  event, since release branches are never merged via PR.
- The `research` and `images` cleanup scopes, and the `scope: all` input
  value, are out of scope for this feature — this feature implements only
  `scope: branches`, documented precisely in research.md.
- The daily-schedule trigger and the "called by `promote` after prod
  success" trigger named in Reference 2 are external orchestration
  concerns outside this workflow's own job definition, the same boundary
  already drawn for every other workflow built so far.
