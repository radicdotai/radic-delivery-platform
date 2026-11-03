# Feature Specification: Release Cut Workflow

**Feature Branch**: `014-release-cut-workflow`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Release cut workflow — the `release-cut`
reusable GitHub Actions workflow (Confluence RAITSDA Reference 2:
Workflow Contracts, §3.4), the next of this platform's 12 reusable
workflows after `ci`, `security`, and `release-commands`. Bundled with a
new, small, genuinely testable engine command this workflow depends on:
`radic-delivery release render-pr-body`, which renders the real release
PR body/checklist (Reference 3's own template, read in full) from an
already-produced release manifest. Reusable-workflow authoring in this
platform is validated statically (`actionlint`/`zizmor`), the same bar
every prior workflow (`ci.yml`, `security.yml`, `release-commands.yml`)
was built to — this sandbox has no GitHub Actions runner to execute any
workflow live, live Jira, or live GCP access, so this feature's one piece
of genuinely testable logic (the PR-body rendering) is pulled into the
engine, pytest-tested for real, and the workflow itself only orchestrates
already-real pieces: `radic-delivery release propose`, `radic-delivery
release cut`, and this new render command. Two real gaps the authoritative
architecture documents don't fully resolve are explicitly flagged rather
than guessed past: exactly which event re-triggers the actual cherry-pick
after a second person approves the release PR (resolved via Reference 3's
bot-identity page, which names `pull_request_review` among the bot's
subscribed events, and Technical Design's own strictly-ordered propose-
then-cut sequence — recorded as a flagged convention, not asserted as
self-evidently correct), and how ticket dev-green status and a service's
migration-chain membership are supplied, since neither is a field the
already-built release-manifest schema stores per ticket."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A release PR reads exactly like the architecture's own template, every time (Priority: P1)

Whoever opens, edits, or reviews a release PR needs its body to always
show the same real, complete, machine-readable sections — the selection
table, non-Jira PRs, held-back tickets, the gates checklist, the commands
reference — generated fresh from the release's own manifest, never
hand-typed and never silently missing a section.

**Why this priority**: every other part of this feature depends on this
rendering being correct and complete; it is also independently valuable
and independently testable without any GitHub Actions workflow at all.

**Independent Test**: can be fully tested by rendering a PR body from a
real, hand-built manifest at each of several different states (freshly
proposed, with non-Jira PRs, with held-back tickets, after cut, after
stage success), confirming each section's content and the gates
checklist's checkbox states match exactly.

**Acceptance Scenarios**:

1. **Given** a freshly proposed manifest with two selected tickets and no
   non-Jira PRs or held-back tickets, **When** its PR body is rendered,
   **Then** the selection table lists both tickets, and the "Released
   without a Jira key" section is omitted entirely.
2. **Given** a manifest with one non-Jira PR whose reason is still
   missing, **When** its PR body is rendered, **Then** that section is
   included, the row shows the reason as missing, and the gates checklist
   shows the non-Jira-PRs gate as not yet satisfied.
3. **Given** a manifest with one held-back ticket and a reason, **When**
   its PR body is rendered, **Then** the held-back section lists it with
   its reason and who removed it.
4. **Given** a manifest whose status shows the release PR has been
   approved, **When** its PR body is rendered, **Then** the gates
   checklist's "release PR approved" item is checked.
5. **Given** a manifest recording a passing release-gate result and a
   passing stage regression record, **When** its PR body is rendered,
   **Then** both corresponding gates checklist items are checked.
6. **Given** the same manifest rendered twice with no changes in between,
   **When** both renderings are compared, **Then** they are identical —
   this is a pure, deterministic rendering, never one that varies run to
   run.

---

### User Story 2 - A release PR is proposed and, once approved, actually cut — through one real, reviewable workflow (Priority: P2)

A release manager needs the release-PR-then-branch-cut sequence to run
through this platform's own central, reviewable automation — not a
hand-run local command — from the moment a release is proposed through
the moment a second person's approval causes the real release branch to
be cut.

**Why this priority**: this is the orchestration layer around User Story
1's rendering and this platform's already-built `release propose`/
`release cut` commands; it has no logic of its own beyond sequencing and
gating, and depends on User Story 1 existing first.

**Independent Test**: can be read and statically validated
(`actionlint`/`zizmor`) as a complete, correct reusable workflow matching
Reference 2 §3.4's contract — inputs, outputs, secrets, permissions — and
exercised locally only insofar as the commands it calls (`release
propose`, `release cut`, `release render-pr-body`) are each already
independently real and tested; this sandbox cannot execute the workflow
itself, the same testability boundary already accepted for `ci.yml`/
`security.yml`/`release-commands.yml`.

**Acceptance Scenarios**:

1. **Given** the workflow is manually dispatched for a release, **When**
   it runs, **Then** it proposes a draft manifest and opens (or updates)
   a release PR whose body is this feature's own rendering of that
   manifest — never a second, divergent rendering path.
2. **Given** a release PR receives an approving review from someone other
   than the release's initiator, **When** that review is submitted,
   **Then** the workflow's cut job is the one that runs `release cut` for
   real — never a review from the initiator themselves, and never a
   review that isn't an approval.
3. **Given** the same release PR has one or more non-Jira PRs still
   missing a reason or a second approver, **When** an otherwise-valid
   approval is submitted, **Then** the cut is refused, naming specifically
   why, consistent with the gates checklist User Story 1 already renders.

### Edge Cases

- What happens when a manifest has no selected tickets at all (every
  commit held back)? The selection table is rendered empty, not omitted
  — a reviewer still needs to see that nothing was selected, not assume
  the section is missing by mistake.
- What happens when the release head hasn't been cut yet (no
  `release_head` in the manifest)? The "deploy files changed" section
  reports this plainly as not yet determinable, rather than a comparison
  against a commit that doesn't exist yet.
- What happens when an approving review arrives on a PR that isn't
  actually this platform's own release PR (for example, a PR with no
  matching manifest)? The cut job never runs `release cut` without first
  confirming the PR is a genuine release PR it recognizes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST render a release PR body containing the
  same sections the approved architecture's own template specifies: a
  header summary, the ticket selection table, a non-Jira-PRs section
  (present only when there is at least one), a held-back section, a
  migrations section, a deploy-files-changed section, a gates checklist,
  a commands reference, a links section, and a UAT section.
- **FR-002**: The gates checklist's individual items MUST each reflect
  the manifest's own recorded state for that specific gate — never a
  single combined status, and never a checked item the manifest doesn't
  actually support.
- **FR-003**: Rendering the same manifest twice with no change MUST
  produce byte-identical output.
- **FR-004**: The system MUST compute whether any deploy-relevant file
  changed between the release's base commit and its release head using
  real local git history, when a release head exists; when it does not
  yet exist, this MUST be reported as not yet determinable rather than
  guessed.
- **FR-005**: The reusable workflow MUST propose a release (via the
  existing `release propose` command) and open or update a release PR
  using this feature's own rendering, on a manual dispatch.
- **FR-006**: The reusable workflow MUST run the real branch cut (via the
  existing `release cut` command) only in response to an approving
  review from someone other than the release's own initiator, on the
  platform's own recognized release PR.
- **FR-007**: The reusable workflow MUST refuse to cut when the gates this
  feature's own rendering already surfaces (non-Jira-PR completeness, in
  particular) are not satisfied, naming specifically why.
- **FR-008**: This feature MUST NOT make any call to a live database or
  Cloud Deploy; its Jira and GitHub calls are real, correctly-shaped
  orchestration this sandbox cannot execute end-to-end but can validate
  statically.

### Key Entities

- **Rendered PR Body**: the markdown document produced from one release
  manifest — every section FR-001 names, each gate's checkbox state
  individually traceable to a specific manifest field.
- **Release Cut Workflow**: the reusable workflow itself — a propose
  job (manual dispatch) and a cut job (approval-triggered), each a thin
  orchestration of already-real engine commands.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every section of a rendered PR body traces to a specific,
  named manifest field or a real, computed git fact — never a value this
  feature invents without a traceable source.
- **SC-002**: Rendering is 100% deterministic: the same manifest always
  produces the same body, byte for byte.
- **SC-003**: The reusable workflow passes `actionlint` with zero
  findings and `zizmor` with zero findings (verified directly — this is
  a stricter bar than this platform's prior workflows actually achieve;
  `ci.yml` itself still carries several accepted `template-injection`/
  `unpinned-uses`/`artipacked` findings today, left unaddressed by
  specs/002).
- **SC-004**: The real branch cut never runs from an approval submitted
  by the release's own initiator.

## Assumptions

- Rendering lives in the engine (a new, real, pytest-tested command)
  rather than as inline workflow shell/template logic, consistent with
  this platform's own centralise-implementation principle and with every
  other piece of non-trivial logic this project has built so far.
- The event that triggers the real cherry-pick after a second person's
  approval is a `pull_request_review` (`types: [submitted]`) trigger —
  not shown in Reference 2's own abbreviated caller-template example, but
  supported by Reference 3's bot-identity page naming
  `pull_request_review` among the bot's subscribed events and by
  Technical Design's own strictly-ordered propose-then-cut sequence. This
  is recorded as a flagged convention (research.md D1), the same
  treatment given to every other gap this project has filled where the
  architecture's summary tables prove abbreviated rather than exhaustive.
- Per-ticket dev-green status is not a field the release-manifest schema
  stores (and specs/008's own `release propose` already excludes
  dev-green-failed commits from selection before a manifest is ever
  produced) — so every ticket appearing in a manifest's selection is, by
  construction, already dev-green; this feature's rendering reflects that
  rather than inventing a new per-ticket field.
- A service's migration-chain membership for a given release (the
  "Contains migrations" section) is not derivable from the manifest or
  from real git history alone; it is supplied as small, explicit,
  optional input, the same "accept it, don't fake it" treatment this
  project gives every other fact it cannot compute for real.
- Automatically re-running the propose step after every
  `release-commands` edit (so the rendered PR body stays current between
  edits without a human re-dispatching the workflow) is a further
  orchestration piece explicitly out of scope for this feature; the
  propose job can be re-run manually via `workflow_dispatch` in the
  meantime, the same incremental-slice discipline this project has
  applied to every other not-yet-built automatic trigger.
- Resolving ticket readiness via a real Jira JQL query is in scope for
  the propose job (the workflow's own declared `ATLASSIAN_*` secrets
  exist for exactly this purpose, unlike `release-commands.yml`, which
  never needed a live Jira call at all); this sandbox cannot execute that
  call, but the query itself is real, correctly-shaped orchestration,
  validated statically like the rest of this workflow.
