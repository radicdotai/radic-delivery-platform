# Feature Specification: Deploy YAML Lint

**Feature Branch**: `004-deploy-yaml-lint`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "Deploy YAML lint — validates a service's
Cloud Run service YAML and skaffold.yaml against this platform's
deploy-manifest rules, and closes the `deploy_lint` gap left open by
specs/002-ci-gate-workflow (currently a hardcoded 'not_available'
placeholder). Checks: the service YAML must use the placeholder image
reference `image: app`; it must never contain a `traffic` key; it must
declare a startup probe; it must never contain an inline secret value
(only `secretKeyRef` references); and the dev/stage/prod YAML files must
be identical except for keys the descriptor's own `parity.allow` list
permits to differ. Adds exactly one real subcommand, `deploy lint`, to a
new `deploy` command group — every other `deploy` subcommand
(release/promote/approve/rollback/status/drift) touches real Cloud Deploy
and stays unimplemented."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A manifest mistake is caught before it ever reaches a real deploy (Priority: P1)

A contributor edits a service's Cloud Run deploy manifest — for example,
they paste in a real image reference instead of the required placeholder,
or they add a `traffic` key they saw in an old example, or they hardcode a
database password instead of referencing it from Secret Manager, or they
forget a startup probe. Because this platform's deploy manifests are
applied by Cloud Deploy exactly as committed — they are the complete
desired state of a running service, not a template filled in at deploy
time, except for the image itself — any one of these mistakes becomes a
live problem the moment it is ever deployed. They need this caught while
reviewing the pull request, not after.

**Why this priority**: this is the entire reason the check exists — every
other story in this feature depends on this one existing first, and it is
independently valuable even on its own (today, nothing catches any of
these mistakes at all).

**Independent Test**: can be fully tested by running the lint against a
sample service's deploy manifests, once clean (passes) and once with each
of the four manifest-content rules individually violated (each one alone
fails, naming which file and which rule).

**Acceptance Scenarios**:

1. **Given** a service's deploy manifests that satisfy every rule, **When**
   the lint runs, **Then** it reports an overall pass.
2. **Given** a service's manifest that uses a real image reference instead
   of the required placeholder, **When** the lint runs, **Then** it reports
   a failure naming that file and that rule.
3. **Given** a service's manifest that contains a `traffic` key, **When**
   the lint runs, **Then** it reports a failure naming that file and that
   rule.
4. **Given** a service's manifest that has no startup probe declared,
   **When** the lint runs, **Then** it reports a failure naming that file
   and that rule.
5. **Given** a service's manifest that contains what looks like an inline
   secret value rather than a reference to Secret Manager, **When** the
   lint runs, **Then** it reports a failure naming that file and that rule.

---

### User Story 2 - Unexplained drift between environments is caught (Priority: P2)

A platform maintainer needs the dev, stage, and prod versions of a
service's manifest to be identical except for the specific, declared
differences the service's own descriptor says are allowed (for example, a
different Cloud Run service name per environment). An unexplained
difference between environments — something nobody decided to allow — is
exactly the kind of drift that causes "it worked in stage but not in prod"
incidents.

**Why this priority**: this is a second, independent check layered on top
of User Story 1's per-file content rules — it compares files to each
other rather than checking one file in isolation, so it is naturally a
distinct, later-landing capability, but it is still core to what this
feature exists to catch.

**Independent Test**: can be fully tested by running the lint against a
service whose three environment manifests differ only in a key the
descriptor explicitly allows (passes), and against one where they differ
in a key the descriptor does not allow (fails, naming the file, the key,
and the environments that disagree).

**Acceptance Scenarios**:

1. **Given** a service's dev/stage/prod manifests that differ only in keys
   the descriptor's `parity.allow` list permits, **When** the lint runs,
   **Then** it reports a pass for the cross-environment check.
2. **Given** a service's dev/stage/prod manifests that differ in a key not
   covered by `parity.allow`, **When** the lint runs, **Then** it reports a
   failure naming the offending key and which environments disagree.

### Edge Cases

- What happens when the descriptor itself is invalid (a case this
  platform's other commands already handle)? The lint MUST fail
  immediately with that specific reason, before attempting to read any
  deploy manifest file.
- What happens when a descriptor-declared manifest file is missing from
  disk? This MUST be reported as a distinct, named outcome — "the file is
  missing" — never confused with "the file exists and is invalid," and
  never silently skipped.
- What happens when a manifest file exists but is not valid YAML at all?
  This MUST be reported as a distinct parse failure, not confused with a
  rule violation inside a file that did parse.
- What happens when a service declares more than one deployable (for
  example, a service plus a background worker, each with its own set of
  manifests)? Every declared deployable's manifests MUST be checked, not
  just the first one.
- What happens when a service has no `parity.allow` entries declared at
  all? Then its dev/stage/prod manifests must be identical in every key,
  with zero tolerance — "nothing is allowed to differ" is the correct
  default when nothing was explicitly declared otherwise.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST provide one, centrally defined way to
  check a service's deploy manifests against this platform's rules, such
  that no service repo needs to hold its own copy of that logic (mirrors
  Principle I, same as the existing quality gate and security scan).
- **FR-002**: The lint MUST first confirm the service's descriptor is
  valid (reusing the existing descriptor validation) and MUST fail
  immediately, before reading any manifest file, if it is not.
- **FR-003**: For every deployable the descriptor declares, the lint MUST
  check that deployable's dev, stage, and prod manifest files.
- **FR-004**: The lint MUST fail a manifest that does not use the required
  placeholder image reference.
- **FR-005**: The lint MUST fail a manifest that contains a traffic-control
  key, since traffic management belongs to the deployment system, never to
  the committed manifest.
- **FR-006**: The lint MUST fail a manifest that does not declare a startup
  probe.
- **FR-007**: The lint MUST fail a manifest that contains what appears to
  be an inline secret value rather than a reference to a secret-management
  system.
- **FR-008**: The lint MUST compare a deployable's dev, stage, and prod
  manifests against each other and fail when they differ in any way not
  explicitly permitted by the service's own descriptor; when the
  descriptor permits no differences at all, any difference at all is a
  failure.
- **FR-009**: Every failure the lint reports MUST name which file and
  which specific rule it violates, so a reviewer does not need to guess
  which of several possible problems was found.
- **FR-010**: A missing manifest file MUST be reported as a distinct
  outcome from both "passed" and "failed a content rule."
- **FR-011**: A manifest file that cannot be parsed as YAML at all MUST be
  reported as a distinct outcome from a content-rule failure.
- **FR-012**: The lint's result MUST be available in both a human-readable
  form and a machine-readable form carrying the same facts, consistent
  with every other command this platform's CLI already provides.
- **FR-013**: When a service repo's pull request includes a deploy
  manifest change, the lint's real pass/fail result MUST be visible from
  that pull request's existing quality-gate check, replacing today's fixed
  "not available" placeholder.

### Key Entities

- **Deploy Lint Result**: the single, structured outcome of one lint run
  for one service — an overall pass/fail, and the list of individual
  findings (each naming a deployable, a file, which environments it
  involves, which rule was violated, and a human-readable description).
- **Manifest Check**: one of the five rules a given manifest file (or pair
  of files, for the cross-environment comparison) is checked against:
  placeholder image, no traffic key, startup probe present, no inline
  secret, and cross-environment parity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A deploy manifest using a real image reference, containing a
  traffic key, missing a startup probe, or containing an inline secret is
  caught 100% of the time, each reported with the specific file and rule.
- **SC-002**: An unexplained difference between a service's dev, stage, and
  prod manifests is caught 100% of the time the difference is outside the
  descriptor's declared allowances.
- **SC-003**: A reviewer can see exactly which file and which rule failed
  directly from the lint's own report, without needing to manually diff
  manifest files by hand.
- **SC-004**: A service repo's existing quality-gate pull-request check now
  reflects a real deploy-manifest result instead of a fixed placeholder,
  with zero additional configuration required from the service repo.

## Assumptions

- This feature implements only the `lint` subcommand of the architecture's
  `deploy` command group. Every other named subcommand
  (`release`/`promote`/`approve`/`rollback`/`status`/`drift`) calls real
  Cloud Deploy and is out of scope here, left exactly as unimplemented as
  every other GCP-touching command group in this platform today.
- "An inline secret value" is detected using the same class of pattern
  matching already proven for this platform's security scan (secret-shaped
  strings), applied here as a manifest-content rule rather than a
  source-code scan; this spec does not require a new detection technique,
  only applying an established one to a new input.
- The cross-environment comparison (`parity.allow`) reuses the descriptor
  field specs/001-engine-scaffold already defined for exactly this
  purpose; this feature does not change that schema.
- As with prior features, no real service repo exists for this platform to
  test against yet; this feature is validated against representative
  sample services built for that purpose.
