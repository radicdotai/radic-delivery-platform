# Feature Specification: Hotfix Backport Workflow

**Feature Branch**: `015-hotfix-backport-workflow`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Hotfix backport workflow — the
`hotfix-backport` reusable GitHub Actions workflow (Confluence RAITSDA
Reference 2: Workflow Contracts, §3.8), this platform's fifth reusable
workflow after `ci`, `security`, `release-commands`, and `release-cut`.
Bundled with a new, small, genuinely testable engine command this
workflow depends on: `radic-delivery release backport`, which cherry-
picks a succeeded hotfix release's already-cut commits back onto `dev`,
continuing past any individual commit that conflicts (never aborting the
whole backport the way `release cut` aborts an entire release on its
first conflict) and reporting exactly which commits conflicted so a
human can finish the rest by hand. No live GCP/Jira access is needed —
this is a purely git+GitHub operation, triggered only after a hotfix's
prod rollout has already succeeded, the same real, local-git-only
discipline `release cut` (specs/009) already established. The reusable
workflow itself is validated statically (`actionlint`/`zizmor`), the
same bar every prior reusable workflow in this platform was built to —
this sandbox has no GitHub Actions runner to execute it against live."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A hotfix's exact commits are backported, conflicts and all, never silently lost (Priority: P1)

Once a hotfix has succeeded in production, whoever maintains `dev` needs
every one of that hotfix's commits carried back onto `dev` — and if
carrying one specific commit back creates a genuine conflict, that
conflict needs to be visible and specific, never a reason the rest of
the commits silently fail to come back too.

**Why this priority**: every other part of this feature depends on this
command existing and behaving correctly; it is independently valuable
and independently testable without any GitHub Actions workflow at all.

**Independent Test**: can be fully tested by backporting a real, small,
already-cut hotfix manifest onto a real local `dev` branch once where
every commit applies cleanly, and once where one specific commit
conflicts, confirming the clean commits still land and the conflicted
one is reported specifically, by name.

**Acceptance Scenarios**:

1. **Given** a succeeded hotfix release manifest whose commits all apply
   cleanly onto the current `dev`, **When** it is backported, **Then** a
   new branch is created from `dev` carrying every commit, each a real
   `cherry-pick -x` of the hotfix's own release commit, in the release's
   own chronological order.
2. **Given** the same hotfix, but one specific commit's cherry-pick
   conflicts with `dev`'s current state, **When** it is backported,
   **Then** every other commit still lands, that one specific commit is
   named as conflicted, and the backport as a whole is reported as
   needing manual attention — never a silent partial result and never an
   all-or-nothing abort of the clean commits too.
3. **Given** a hotfix manifest whose commits all conflict, **When** it is
   backported, **Then** the resulting branch still exists (created from
   `dev`, with nothing successfully applied), and every commit is named
   as conflicted.

---

### User Story 2 - A succeeded hotfix is backported through this platform's own real, reviewable automation (Priority: P2)

Whoever maintains `dev` needs the backport to happen automatically and
visibly the moment a hotfix's prod rollout actually succeeds — never
hand-run locally, and never attempted before prod success is confirmed.

**Why this priority**: this is the orchestration layer around User Story
1's backport command; it has no logic of its own beyond sequencing and
depends on User Story 1 existing first.

**Independent Test**: can be read and statically validated
(`actionlint`/`zizmor`) as a complete, correct reusable workflow matching
Reference 2 §3.8's contract — inputs, outputs, secrets, permissions —
exercised only insofar as the one command it calls (`release backport`)
is already independently real and tested; this sandbox cannot execute
the workflow itself, the same testability boundary already accepted for
`ci.yml`/`security.yml`/`release-commands.yml`/`release-cut.yml`.

**Acceptance Scenarios**:

1. **Given** a hotfix's prod rollout workflow completes successfully,
   **When** this workflow runs, **Then** it opens a pull request from the
   backported branch into `dev` — never into the release or hotfix
   branch itself.
2. **Given** the backport reported one or more conflicted commits,
   **When** the pull request is opened, **Then** it is opened as a draft,
   naming the specific conflicted commits in its own body, rather than a
   normal, ready-for-review pull request.
3. **Given** a workflow run whose own triggering prod rollout did not
   actually succeed, or whose branch name doesn't end in the hotfix
   suffix, **When** this workflow is invoked, **Then** it performs no
   backport at all.

### Edge Cases

- What happens when a hotfix release's manifest records zero commits at
  all? The backport branch is still created from `dev`, carrying nothing
  — reported plainly as nothing to backport, not an error.
- What happens when the backport branch name already exists from a prior
  attempt? Refused cleanly, naming the problem, rather than silently
  overwriting or appending to whatever is already there.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST cherry-pick every commit a succeeded
  hotfix's manifest records, in the release's own chronological order,
  onto a new branch created from `dev`.
- **FR-002**: When a specific commit's cherry-pick conflicts, the system
  MUST abort only that one commit's attempt and continue with the
  remaining commits — never aborting the entire backport because of one
  conflicting commit.
- **FR-003**: The system MUST report, distinctly and by name, which
  specific commits conflicted and were not carried back, never folding
  this into a single undifferentiated failure.
- **FR-004**: The reusable workflow MUST trigger only after the
  originating hotfix's prod rollout has actually succeeded, and only for
  a branch recognizable as a hotfix.
- **FR-005**: The reusable workflow MUST open its pull request into `dev`
  specifically, never into the release or hotfix branch itself.
- **FR-006**: The reusable workflow MUST open the pull request as a draft
  and name every conflicted commit in its own body when the backport
  reported any conflicts; otherwise a normal, ready-for-review pull
  request.
- **FR-007**: This feature MUST NOT make any external network call beyond
  real local git and the GitHub API needed to open the pull request
  itself.

### Key Entities

- **Backport Result**: the outcome of one `release backport` run — the
  new branch created, the commits that landed cleanly, and the specific
  commits that conflicted and were skipped.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A commit that conflicts never prevents any other commit in
  the same hotfix from being backported.
- **SC-002**: Every conflicted commit is always named specifically in
  the result — never a generic "some commits conflicted" summary.
- **SC-003**: The reusable workflow passes `actionlint` and `zizmor` with
  zero error/warning findings, verified directly.
- **SC-004**: A pull request is never opened ready-for-review when the
  backport reported any conflicts — always a draft in that case.

## Assumptions

- The backport branch's naming convention (`backport/<release_id>`, this
  feature's own choice) is a new, flagged convention — Reference 2 names
  no specific branch name for it.
- `release backport` reads a hotfix manifest already at a succeeded,
  prod-deployed-or-later status as given — the same "consume an
  already-produced artifact" discipline `release finalise` (specs/011)
  and `gate evaluate --mode release-gate` (specs/013) both already apply;
  this feature does not itself determine whether a hotfix actually
  succeeded in prod.
- Determining "the originating hotfix's prod rollout actually succeeded"
  is the triggering `workflow_run` event's own concern (GitHub reports
  this directly); this feature's workflow only checks that event's own
  `conclusion`, never re-deriving success from any other source.
- A dedicated `templates/callers/hotfix.yml` caller template (naming the
  real `workflow_run` trigger Reference 2 places on the caller side) is
  out of scope for this feature — this repo has no such file yet, and
  building the full `hotfix.yml` caller (which also covers cutting a
  hotfix release in the first place, Reference 2 §2.6) is a separate,
  larger piece of work. `hotfix-backport.yml` itself re-checks the
  success/branch-suffix gate defensively in the meantime (research.md
  D5), so it remains safe to invoke even without that caller built yet.
