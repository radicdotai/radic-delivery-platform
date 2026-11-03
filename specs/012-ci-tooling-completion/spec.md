# Feature Specification: CI Tooling Completion

**Feature Branch**: `012-ci-tooling-completion`

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "CI tooling completion — two related, small CLI
commands bundled into one feature per the project's explicit request to
combine related, independently small features: `radic-delivery tests
inventory` (counts a service's unit tests per suite — including skipped
and quarantined — from a real, descriptor-driven test run) and
`radic-delivery policy rulesets-diff` (compares this platform's committed
GitHub ruleset JSON against a live ruleset state, reporting drift).
Bundled because both are small, standalone CI-visibility tools with no
dependency on each other, share no code, and are each scoped to exactly
the parts testable without live GCP/Docker/authenticated-GitHub access in
this environment. `tests inventory` reuses `gate evaluate`'s own
descriptor-driven test-command construction and output parsing
(specs/002); `rulesets-diff`'s live ruleset state (normally fetched via
`gh api repos/<repo>/rulesets`, which this sandbox cannot do — `gh` is
installed but not authenticated here) is taken as explicit file input
instead, the same external-dependency boundary every live-GitHub/GCP call
in this platform already draws. This feature also seeds the `rulesets/`
directory CLAUDE.md's own repo layout names as a target but which nothing
has created yet, with the five real ruleset JSON files the approved
architecture (Confluence RAITSDA Reference 2: Workflow Contracts, §5)
already specifies verbatim, so `rulesets-diff --dir rulesets/` has real
committed files to compare against from day one."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A service's test counts are visible without reading CI logs (Priority: P1)

Before and after a CI run, anyone — not just someone reading the raw
pytest/vitest log — needs to see exactly how many of a service's tests
ran, passed, failed, were skipped, or are currently quarantined, as one
clear, structured fact.

**Why this priority**: skipped and quarantined tests are easy to miss in
a wall of CI log output; this is the platform's one dedicated place to
see them called out explicitly, which is the whole reason Reference 2
names this an artifact every CI run produces.

**Independent Test**: can be fully tested by running it against a real
local service checkout with a real, small test suite, once where every
test passes cleanly and once where some tests are skipped and/or
currently quarantined, confirming each count is reported accurately and
distinctly.

**Acceptance Scenarios**:

1. **Given** a service whose full unit-test suite passes with nothing
   skipped and nothing quarantined, **When** its tests are inventoried,
   **Then** the report shows an accurate total and passed count, with
   zero for failed, skipped, and quarantined.
2. **Given** a service with one or more deliberately skipped tests,
   **When** its tests are inventoried, **Then** the skipped count
   reflects exactly how many were skipped, distinguishable from passed
   and failed.
3. **Given** a service with a test currently recorded as quarantined
   (within its allowed quarantine window), **When** its tests are
   inventoried, **Then** that test is counted as quarantined, reported
   separately from the plain pass/fail/skip counts.
4. **Given** a quarantined test whose quarantine window has run past the
   platform's maximum allowed duration, **When** its tests are
   inventoried, **Then** the report distinguishes it from a
   still-within-window quarantined test, rather than silently reporting
   both the same way.
5. **Given** a service whose descriptor-declared test command cannot even
   be launched (for example, the test runner isn't installed), **When**
   its tests are inventoried, **Then** this is reported clearly as a
   launch failure, never confused with a suite that ran and reported
   zero of everything.

---

### User Story 2 - Live GitHub ruleset drift is visible before it causes an incident (Priority: P2)

A platform maintainer needs to know, before it causes a surprising bypass
of branch or tag protection, whether a repository's live GitHub ruleset
configuration has drifted from what this platform has actually committed
and reviewed — never discovering the gap only after an unprotected push
or an unapproved tag gets through.

**Why this priority**: this is the platform's own governance-config
integrity check, not something on the direct release path the way
`tests inventory` sits in `ci`'s own required checks — a drift report
other tooling consumes, not something itself blocking a build.

**Independent Test**: can be fully tested by supplying a local committed
ruleset directory and a local file standing in for a live ruleset
API response, once where they match exactly and once with a deliberate
difference, confirming the drift is reported specifically and
distinguishably (added, removed, or changed).

**Acceptance Scenarios**:

1. **Given** a committed ruleset directory and a live ruleset state that
   match exactly on every meaningful field, **When** the two are
   compared, **Then** the report shows no drift at all.
2. **Given** a ruleset present in the committed directory but absent from
   the live state, **When** the two are compared, **Then** it is reported
   as missing from live, distinguishable from a changed or an
   unexpectedly-added ruleset.
3. **Given** a ruleset present in the live state but absent from the
   committed directory, **When** the two are compared, **Then** it is
   reported as an unexpected addition, distinguishable from a missing or
   a changed ruleset.
4. **Given** a ruleset present in both, but with a different rule,
   condition, or bypass configuration, **When** the two are compared,
   **Then** it is reported as changed, naming what differs, distinguishable
   from a ruleset that is entirely missing or entirely new.
5. **Given** the live ruleset state includes fields GitHub itself assigns
   (for example an internal id or a timestamp) that the committed file
   naturally never has, **When** the two are compared, **Then** those
   fields alone never cause a false drift report.

### Edge Cases

- What happens when a service's descriptor declares a test runner this
  platform doesn't support? The same clear, named rejection `gate
  evaluate` already gives for the same situation — never a crash.
- What happens when the quarantine ledger lists a test for a different
  service than the one being inventoried? It is ignored for this
  inventory — never counted against a service it doesn't belong to.
- What happens when the committed ruleset directory is empty, or the live
  file lists zero rulesets? The comparison still runs and reports
  accordingly (everything missing from live, or everything an unexpected
  addition, respectively) — never an error purely for being empty.
- What happens when two rulesets in the committed directory share the
  same name? Refused clearly as a malformed committed set, rather than
  silently comparing against only one of them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST run a service's own descriptor-declared
  unit-test command for real against a local checkout and report the
  total, passed, failed, and skipped counts from that real run.
- **FR-002**: The system MUST additionally report how many of that
  service's tests are currently quarantined, distinguishing a test still
  within its allowed quarantine window from one that has run past it.
- **FR-003**: When the descriptor-declared test command cannot be
  launched at all, the system MUST report this as a distinct launch
  failure, never as a suite that ran and produced all-zero counts.
- **FR-004**: The system MUST compare a locally committed set of ruleset
  definitions against a supplied live ruleset state and report, for every
  ruleset name present in either, whether it is unchanged, missing from
  live, an unexpected live addition, or changed — never collapsing these
  four outcomes into a single pass/fail.
- **FR-005**: When reporting a changed ruleset, the system MUST name
  specifically what differs, and MUST NOT be misled into a false
  "changed" report by fields the live GitHub API assigns on its own that
  a committed file never carries.
- **FR-006**: The system MUST refuse cleanly, naming the problem, if the
  committed ruleset set itself contains two entries with the same name,
  rather than silently comparing against only one.
- **FR-007**: This feature MUST NOT make any external network call (to
  GitHub, GCP, or Jira) in the course of either of its two commands; the
  live ruleset state is supplied as explicit local input.
- **FR-008**: Every result MUST be available in both a human-readable
  form and a machine-readable form carrying the same facts, consistent
  with every other command this platform's CLI already provides.
- **FR-009**: This platform's own committed ruleset directory MUST
  contain the five real ruleset definitions the approved architecture
  specifies (`dev-trunk`, `main-prod-line`, `release-branches`,
  `product-tags`, `platform-tags`), so `rulesets-diff` has real,
  verbatim-correct files to compare against from day one.

### Key Entities

- **Test Inventory Result**: the outcome of one `tests inventory` run —
  total, passed, failed, skipped, and quarantined counts (the last split
  into within-window and past-window), plus whether the underlying test
  command could even be launched.
- **Rulesets Diff Result**: the outcome of one `rulesets-diff` comparison
  — the set of ruleset names found unchanged, missing from live,
  unexpectedly added in live, and changed (each changed entry naming what
  differs).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A service's total, passed, failed, skipped, and quarantined
  test counts are each reported accurately and distinguishably, 100% of
  the time a real test run completes.
- **SC-002**: A ruleset's drift status (unchanged, missing, added, or
  changed) is always one of exactly those four outcomes, never combined
  or omitted, for every ruleset name present in either the committed set
  or the live state.
- **SC-003**: A GitHub-assigned field present only in the live state
  never by itself causes a ruleset to be reported as changed.
- **SC-004**: This platform's own `rulesets/` directory, once seeded by
  this feature, byte-for-byte matches the five ruleset JSON bodies the
  approved architecture specifies.

## Assumptions

- `tests inventory` re-executes the service's own descriptor-driven
  unit-test command independently of `gate evaluate`, reusing the same
  command-construction and output-parsing logic (specs/002) rather than
  reading an already-produced result — consistent with every command
  group in this platform being independently invocable on its own.
- A quarantine ledger recording which tests are currently quarantined,
  for which service, and since when, is a new, local, committed
  convention this feature introduces (no prior feature or Confluence
  reference defines one) — the same "flagged, not asserted as
  self-evidently correct" treatment given to every other convention this
  platform has had to invent where the approved architecture names a
  policy without naming its concrete mechanism.
- The platform-wide quarantine window (maximum duration a test may stay
  quarantined) and the platform-wide quarantine-share cap are existing,
  fixed constants this feature reads and reports against, not something
  it invents or makes configurable per service.
- The live ruleset state `rulesets-diff` compares against is supplied as
  an explicit local file standing in for `gh api repos/<repo>/rulesets`'s
  real response shape; this sandbox has `gh` installed but not
  authenticated, so no live call is attempted or faked.
- `rulesets-diff` is a drift *report*, not a fail-closed gate — matching
  Reference 2's own framing ("diffs against the committed files (drift
  report)") and this platform's "parity before strictness" principle; it
  does not itself decide which of the five rulesets are expected to
  apply to which specific repository — that judgment is left to whoever
  reads the report.
- This feature does not implement actually applying a ruleset to GitHub
  (`gh api -X POST repos/<repo>/rulesets --input ...`), creating GitHub
  Environments, or the GitHub Teams/App identity lookups Reference 2
  flags as still-open (`TODO-VERIFY OI-11`) — only the local
  committed-vs-supplied-live comparison itself.
