# Feature Specification: Central Security Scanning Workflow (report-only)

**Feature Branch**: `003-security-scanning`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "Central security scanning workflow — report-only
phase. The platform's reusable `security` GitHub Actions workflow (Confluence
RAITSDA: Technical Design, Reference 2 Workflow Contracts) plus the engine
command that powers it. Scans for hardcoded secrets and Dockerfile/IaC
misconfigurations, aggregates severity-classified findings, and posts them
visibly on the PR — never blocking the PR yet, since this platform's
documented rollout plan starts all new scanning as report-only. Image
scanning and Snyk are explicitly deferred: image scanning has no built
container image to scan yet (no `build` workflow exists), and Snyk's Team
plan purchase is still a pending, unresolved open item in the approved
architecture itself (OI-9) — not a gap invented by this feature."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See what a change exposes, without being blocked by it yet (Priority: P1)

A contributor opens a pull request against a service repo. Their change
happens to include a hardcoded credential, or their Dockerfile has a
misconfiguration a scanner would flag. Today, nothing in this platform
scans for this at all. They need visibility into what was found — clearly
labelled by severity — surfaced where they'll actually see it on the PR,
without their PR being blocked by it, because this platform's security
rollout deliberately starts advisory-only so the team builds the habit of
looking at findings before anything is ever allowed to block a merge.

**Why this priority**: this is the entire point of the report-only phase —
establishing visibility is the prerequisite for ever safely turning on
blocking later. It is independently valuable even though (deliberately)
nothing can fail yet.

**Independent Test**: can be fully tested by running the scan against a
sample service repo with a deliberately planted hardcoded secret and a
deliberately misconfigured Dockerfile, confirming both are reported with
their severity, and confirming the overall scan still reports success (not
blocking) regardless of what was found.

**Acceptance Scenarios**:

1. **Given** a service's code contains a hardcoded secret, **When** the
   scan runs, **Then** the finding is reported with a severity
   classification, and the scan step itself does not fail because of it.
2. **Given** a service's Dockerfile has a misconfiguration a scanner would
   flag, **When** the scan runs, **Then** the finding is reported with a
   severity classification, and the scan step itself does not fail because
   of it.
3. **Given** a service's code and Dockerfile have no findings at all,
   **When** the scan runs, **Then** it reports zero findings at every
   severity level, not an error.
4. **Given** any combination of findings or no findings, **When** the scan
   completes, **Then** the pull request's check for this scan always
   completes successfully — nothing about this feature can fail a PR.

---

### User Story 2 - A security owner can see severity counts to plan the future blocking rollout (Priority: P2)

A security owner needs, for every scan, a count of findings by severity
(critical / high / medium / low) so they can track trend over time and
decide when it's safe to flip specific severities to blocking, per this
platform's documented rollout plan.

**Why this priority**: this is a secondary consumer of the same scan — it
depends on User Story 1's scan existing, but is additional value on top
(aggregate counts for planning), not required for the base visibility goal.

**Independent Test**: can be fully tested by running the scan against a
sample service with a known mix of findings at different severities and
confirming the reported counts match exactly, independent of how any
individual finding is displayed.

**Acceptance Scenarios**:

1. **Given** a scan with a known number of findings at each severity level,
   **When** the scan completes, **Then** the reported critical/high counts
   exactly match what was actually found.
2. **Given** a scan with zero findings, **When** the scan completes, **Then**
   the reported counts are all zero, not missing or null.

---

### User Story 3 - Deferred scanning capabilities are visible, not silently missing (Priority: P3)

A platform maintainer or security owner looking at a scan's report needs to
be able to tell the difference between "this was scanned and found
nothing" and "this capability isn't built yet" for container-image scanning
and for the platform's primary scanner (Snyk), so nobody mistakes an
not-yet-available capability for a clean bill of health.

**Why this priority**: lowest priority because it's about correctly
labelling what's NOT done, rather than adding new scanning capability — but
it's what keeps User Story 1 and 2's reports honest, so it's still in scope
for this feature, not an afterthought.

**Independent Test**: can be fully tested by running the scan and confirming
image-scanning and Snyk both appear in the report as explicitly
not-yet-available, independent of what the secrets/Dockerfile scan itself
finds.

**Acceptance Scenarios**:

1. **Given** any scan run, **When** its report is produced, **Then** it
   explicitly states that container-image scanning is not yet available,
   rather than omitting any mention of it.
2. **Given** any scan run, **When** its report is produced, **Then** it
   explicitly states that the platform's primary scanner (Snyk) is not yet
   available, rather than omitting any mention of it.

### Edge Cases

- What happens when a service's descriptor declares no Dockerfile at all
  (not every service necessarily has container-shaped config in scope for
  this check)? The Dockerfile/IaC check must report that it found nothing
  to check, not an error and not a false "zero findings, all clear."
- What happens when the same secret-shaped string appears more than once in
  a service's code? Each occurrence is reported as its own finding, so a
  count accurately reflects the number of places a secret needs to be
  rotated and removed.
- What happens when a requested scan scope doesn't apply to anything in the
  service (e.g. an IaC-only scope requested for a service with no
  Dockerfile)? The scan reports that scope as having nothing to check,
  consistent with the Dockerfile case above, not an error.
- What happens when a scanning tool itself cannot run at all (distinct from
  running and finding nothing)? This must be reported as a distinct,
  visible outcome — "this check could not run" — so it is never confused
  with "this check ran and found nothing."

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST provide one, centrally defined way for a
  service repo's pull request to be scanned for hardcoded secrets and for
  Dockerfile/IaC misconfigurations, such that no service repo needs to hold
  its own copy of that logic (mirrors Principle I, same as the existing
  quality gate).
- **FR-002**: The scan MUST detect hardcoded secrets present in a service's
  own source code and report each occurrence found, with a severity
  classification.
- **FR-003**: The scan MUST check a service's Dockerfile (when its
  descriptor declares one) for known misconfiguration patterns and report
  each finding, with a severity classification.
- **FR-004**: When a service's descriptor declares no Dockerfile, the scan
  MUST report that the Dockerfile/IaC check found nothing applicable to
  check, distinguishable from "checked and found zero issues."
- **FR-005**: The scan MUST classify every finding into exactly one of a
  fixed set of severities (critical, high, medium, low) and MUST report an
  aggregate count of findings at each severity level.
- **FR-006**: The scan's own completion MUST NOT depend on what it finds —
  any combination of findings, including the most severe, MUST still result
  in the scan itself completing successfully. This feature introduces no
  blocking behavior of any kind.
- **FR-007**: The scan's report MUST explicitly state that container-image
  scanning is not yet available, every time, rather than omitting any
  mention of it.
- **FR-008**: The scan's report MUST explicitly state that the platform's
  primary scanner (Snyk) is not yet available, every time, rather than
  omitting any mention of it.
- **FR-009**: When a requested scan scope doesn't apply to anything in a
  given service, the scan MUST report that scope as having nothing
  applicable to check, not as an error and not by silently skipping it
  without mention.
- **FR-010**: If an individual scanning check cannot run at all (distinct
  from running and finding nothing), the scan MUST report that distinctly
  from both "found issues" and "found nothing."
- **FR-011**: The scan's findings and severity counts MUST be visible to a
  pull request's author and reviewers directly from the pull request,
  without needing to open a raw execution log to learn the outcome.
- **FR-012**: The scan MUST be available in both a human-readable form and a
  machine-readable form carrying the same facts, consistent with every
  other command this platform's CLI already provides.

### Key Entities

- **Security Scan Result**: the single, structured outcome of one scan run
  for one service at one commit — which scopes were requested, which
  applied vs. had nothing to check, the list of findings (each with a
  severity, a location, and a human-readable description), the aggregate
  severity counts, and explicit not-yet-available markers for image
  scanning and Snyk.
- **Finding**: one individual thing the scan detected — a secret occurrence
  or a Dockerfile/IaC misconfiguration — with a severity, a location
  (file and, where applicable, line), and a human-readable description.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A pull request containing a deliberately planted hardcoded
  secret has that secret reported as a finding 100% of the time, and the
  pull request is never blocked because of it.
- **SC-002**: A pull request containing a deliberately misconfigured
  Dockerfile has that misconfiguration reported as a finding 100% of the
  time, and the pull request is never blocked because of it.
- **SC-003**: A reviewer can see every finding's severity and the aggregate
  severity counts directly from the pull request, without opening a raw
  execution log.
- **SC-004**: 100% of scan reports explicitly state that image scanning and
  Snyk are not yet available — never silently absent.
- **SC-005**: A service repo onboarding onto this platform adds zero lines
  of scanning *logic* of its own — only a reference to an exact, published
  version of the centrally defined workflow.

## Assumptions

- This feature is scoped entirely to the report-only rollout phase, per the
  architecture's own documented schedule — no blocking/failing behavior of
  any kind is introduced by this feature, not even for the most severe
  findings. A later feature introduces blocking, on the architecture's own
  documented timeline.
- Container-image scanning and the Snyk scanner are out of scope for this
  feature for reasons already settled by the existing program state (no
  `build` workflow/image exists yet; Snyk's purchase is a pending,
  unresolved open item, OI-9, in the approved architecture) — this spec
  does not reopen either decision, it only requires both gaps to be
  reported honestly rather than silently.
- "Hardcoded secrets" and "Dockerfile/IaC misconfiguration" are assumed to
  be detectable using established, open-source scanning approaches already
  in wide industry use for exactly these two problems; this spec does not
  prescribe a specific tool, only the detection capability and its
  reporting contract.
- As with prior features, no real service repo exists for this platform to
  test against yet; this feature is validated against representative sample
  services built for that purpose (reusing and extending the sample
  services from specs/002-ci-gate-workflow where practical).
