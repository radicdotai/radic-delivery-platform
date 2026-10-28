# Feature Specification: Engine Scaffold & Service Descriptor Validation

**Feature Branch**: `001-engine-scaffold`

**Created**: 2026-10-29

**Status**: Draft

**Input**: User description: "Scaffold the delivery-platform engine: a Python/uv CLI (`radic-delivery`) with the full command surface stubbed, with `descriptor validate`, `descriptor show`, and `policy exceptions check` fully implemented; the service descriptor JSON Schema and three record schemas; a seeded `policy/exceptions.yml`; and descriptor fixtures for all seven service repos. This is the first implementable deliverable identified in the approved architecture (Confluence RAITSDA space, Implementation Pack task 6.1) — every later workflow (ci, security, build, deploy, promote, release-cut) depends on being able to parse and validate a service repo's `.radic/service.yml` before it can act on it."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate a service descriptor before it reaches CI (Priority: P1)

A platform maintainer or a service repo owner has written or edited a
`.radic/service.yml` descriptor (by hand, or by copying another service's as a
starting point). Before that descriptor can ever be trusted by a reusable
workflow, they need a fast, local, authoritative way to know whether it is
well-formed and complete — without needing to push a commit and wait on CI.

**Why this priority**: every reusable workflow in this platform (ci, build,
deploy, promote, release-cut, …) reads the descriptor as its first step. If a
malformed or incomplete descriptor can reach a workflow, that workflow fails in
a confusing, late, and expensive way (or worse, partially succeeds with
undefined behaviour). A trustworthy, standalone validator is the precondition
for every other feature in this program and delivers value on its own, with no
other part of the platform built yet.

**Independent Test**: can be fully tested by running the validator against each
of the 7 real service descriptors (expect: valid) and against deliberately
broken copies of each (missing required field, wrong type, disallowed extra
field, invalid enum value) and confirming each failure is reported with the
exact field path and a human-readable reason — no workflow, no GCP access, no
other platform feature required.

**Acceptance Scenarios**:

1. **Given** a descriptor that satisfies every required field, type, and
   enum constraint of the service descriptor schema, **When** a maintainer
   validates it, **Then** validation reports success and exits with the
   platform's "ok" status.
2. **Given** a descriptor missing a required field (e.g. no `environments.prod`
   block), **When** a maintainer validates it, **Then** validation fails,
   reports the exact missing field path, and exits with the platform's
   "invalid input" status — not a generic or unhandled error.
3. **Given** a descriptor containing a field not defined by the schema (e.g. a
   typo'd key), **When** a maintainer validates it, **Then** validation fails
   and names the unexpected field, because the schema forbids undeclared
   additional properties at every level.
4. **Given** a descriptor whose `runtime.template` is a value outside the
   allowed set, **When** a maintainer validates it, **Then** validation fails
   and names the invalid value and the allowed set.
5. **Given** any one of the seven real service repos' current descriptor
   content, **When** a maintainer validates it, **Then** validation succeeds
   (the schema must not be stricter than what the approved architecture
   already specifies for these seven services).

---

### User Story 2 - Inspect the fully-resolved descriptor for a service (Priority: P2)

A platform maintainer reviewing a new service onboarding, or auditing an
existing one, needs to see exactly what configuration a descriptor resolves
to — including every default value the schema would silently apply — in one
place, without mentally cross-referencing the schema's defaults by hand.

**Why this priority**: defaults exist precisely so most descriptors can omit
most fields; a reviewer who only reads the raw YAML cannot see what will
actually be used (e.g. a default health-check mode or timeout). This is lower
priority than validation because it is a review aid, not a release-blocking
gate — but it directly supports the "People decide, the bot proposes"
principle by giving the human reviewer the full picture.

**Independent Test**: can be fully tested by showing the resolved form of a
descriptor that omits several optional fields and confirming every applicable
default appears in the output, fully independent of validation passing or
failing for other descriptors.

**Acceptance Scenarios**:

1. **Given** a valid descriptor that omits optional fields with declared
   defaults, **When** a maintainer asks to see it resolved, **Then** the
   output includes those fields populated with their schema-declared default
   values, clearly distinguishable from values the author actually set.
2. **Given** a descriptor that fails validation, **When** a maintainer asks to
   see it resolved, **Then** the tool reports the same validation failure
   (it does not silently show a partially-resolved, misleading view of an
   invalid descriptor).

---

### User Story 3 - Check whether a policy exception is active before relying on it (Priority: P3)

A platform maintainer, a release manager, or an auditor needs to confirm
whether a specific recorded exception (a skipped suite, a coverage waiver, a
deferred scan severity) is currently active, and to be warned the moment one
has expired — because an expired exception must stop being honoured
automatically, not linger silently.

**Why this priority**: this is the single mechanism (per the approved
architecture) through which any required gate may ever be bypassed; it is
lower priority than descriptor validation only because, at this stage, nothing
yet calls it from a live gate — but it must exist and be correct before any
gate is wired to honour it.

**Independent Test**: can be fully tested by checking the seeded exceptions
file against a fixed "current date" before and after each entry's expiry date,
independent of any workflow or descriptor.

**Acceptance Scenarios**:

1. **Given** an exception entry with an expiry date in the future, **When** a
   maintainer checks it, **Then** it is reported as active.
2. **Given** an exception entry with an expiry date in the past, **When** a
   maintainer checks it, **Then** it is reported as expired, and the check
   exits with the platform's "policy failure" status rather than silently
   treating it as still active.
3. **Given** a request to check an exception id that does not exist in the
   file, **When** a maintainer checks it, **Then** the tool reports clearly
   that no such exception is recorded, rather than succeeding or failing
   ambiguously.

### Edge Cases

- What happens when a descriptor file is present but is not valid YAML at all
  (parse error, not a schema violation)? The tool MUST distinguish "cannot be
  parsed" from "parses but fails schema validation" in its reported reason.
- What happens when a descriptor references an exception id in
  `quality.post_deploy.exception_id` that is not present (or is expired) in
  `policy/exceptions.yml`? Validation of that descriptor MUST fail with that
  specific reason, since an unresolvable or expired exception reference is
  itself an invalid configuration (Principle III, fail-closed).
- What happens when two exception entries in `policy/exceptions.yml` share the
  same id? This MUST be treated as an invalid policy file, not resolved by
  picking either entry.
- What happens when a maintainer runs any not-yet-implemented command listed
  in the CLI's own `--help`? It MUST fail clearly as "not yet implemented"
  (a distinct, documented status), never silently succeed or silently do
  nothing.
- What happens when output is requested in machine-readable form versus for a
  person reading a terminal? Both forms must report the same facts; only
  presentation differs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST provide a single command-line tool that every
  later workflow and every human maintainer uses to interact with descriptors
  and policy — no reusable workflow may re-implement descriptor parsing or
  policy-exception evaluation independently of this tool.
- **FR-002**: The tool MUST list every command group the platform's approved
  architecture defines (descriptor, gate, notes, tests, release, deploy,
  policy, records, rollback, migrations) in its own help output, even for
  commands not yet implemented in this feature, so the full intended surface
  is discoverable from day one.
- **FR-003**: Every command not yet implemented MUST respond with a clear,
  distinct "not implemented yet" outcome rather than an unhandled error, a
  silent no-op, or a false success.
- **FR-004**: The tool MUST fully implement validating a service descriptor
  file against the platform's published descriptor schema, reporting, for
  every failure, the exact field path and a human-readable reason.
- **FR-005**: The descriptor schema MUST require `schema_version`, `service`,
  `repo`, `runtime`, `build`, `environments` (with `dev`, `stage`, and `prod`
  each required), `cloud_deploy`, `quality`, and `release`, and MUST forbid any
  field not explicitly declared anywhere in the schema (no undeclared
  additional properties at any level).
- **FR-006**: The descriptor schema MUST constrain enumerated fields to the
  approved architecture's exact allowed values, including (non-exhaustively)
  `service.kind` to api/bff/web/worker/console, `runtime.template` to
  python-uv/node, and health-check `mode` to http/gcloud-ready.
- **FR-007**: The descriptor schema MUST require `quality.skip_budget` to be
  exactly `0` and MUST require a `quality.post_deploy.exception_id` whenever
  `quality.post_deploy.suites` is empty.
- **FR-008**: The tool MUST fully implement showing a descriptor's fully
  resolved form (every field the author set, plus every schema-declared
  default applied), and MUST refuse to resolve a descriptor that fails
  validation.
- **FR-009**: The tool MUST fully implement checking whether a named policy
  exception is currently active, expired, or not recorded, using the
  exception's recorded expiry date compared against the current date.
- **FR-010**: The platform MUST ship a single policy-exceptions file as the
  only place an exception may be recorded, and that file MUST be schema-
  validated the same way descriptors are (reject unknown fields, reject a
  missing expiry, reject a duplicate id).
- **FR-011**: The platform MUST ship this policy-exceptions file seeded with
  exactly the three exceptions already approved in the architecture for
  services with no `post_deploy` suite defined yet, each carrying: an id, the
  owning service, an approver, a reason, and an expiry date.
- **FR-012**: The platform MUST ship three further record schemas (release
  manifest, change-note, test-result) alongside the descriptor schema, even
  though no command in this feature writes or reads those record types yet —
  later features depend on these schemas already existing and being stable.
- **FR-013**: The platform MUST ship one descriptor fixture per service repo
  (all seven: fastapi-backend, web-bff, design_service, image-studio,
  brand_research, frontend-v2, operations-console) reflecting that service's
  real, approved configuration, and every one of these seven fixtures MUST
  pass validation.
- **FR-014**: The tool MUST support both a machine-readable output mode and a
  human-readable output mode for every implemented command, reporting
  identical facts in both.
- **FR-015**: The tool MUST use a small, fixed set of distinct exit statuses
  that distinguish "succeeded", "invalid input", "policy failure", and
  "infrastructure/environment error", so calling workflows (in later features)
  can branch on outcome without parsing text.
- **FR-016**: The tool MUST NOT, under any command or output mode, print the
  contents of a secret value, an `.env` file, or any service-account
  credential file, even if such a file happens to be reachable from the
  working directory.

### Key Entities

- **Service Descriptor**: the single declaration, owned by a service repo, of
  that service's runtime, build, per-environment deployment targets, Cloud
  Deploy wiring, quality gates, and release settings. One per service repo.
  Identified by the service name; references zero or one policy exception.
- **Service Descriptor Schema**: the platform-owned, versioned contract every
  descriptor is validated against. Changes to it are changes to what every
  service repo is allowed to declare.
- **Policy Exception**: a single dated, approved, auditable record permitting
  one specific, named gap (a missing suite, a coverage shortfall, a deferred
  scan severity) to not block a release until a stated expiry. Has an id,
  owning scope, approver, reason, and expiry; may be active or expired.
- **Record Schema (release manifest / change-note / test-result)**: the
  platform-owned contracts for data later features will write and read.
  Introduced here as stable shapes with no reader/writer yet.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can determine, in under 10 seconds of tool
  runtime and without any network or GCP access, whether a given service
  descriptor is valid.
- **SC-002**: 100% of the seven real service repos' descriptor fixtures pass
  validation, and 100% of deliberately broken variants (one per required
  field category: missing field, wrong type, disallowed extra field, invalid
  enum value) fail validation with a field-path-specific reason.
- **SC-003**: Every command group named in the approved architecture is
  discoverable from the tool's own help output on day one, with zero commands
  missing from that listing.
- **SC-004**: 100% of the three seeded policy exceptions are correctly
  reported as active on their creation date and would be correctly reported
  as expired once their recorded expiry date has passed.
- **SC-005**: A reviewer can see a service's fully-resolved configuration
  (including applied defaults) without needing to separately read the schema
  documentation to know what a default value is.

## Assumptions

- The descriptor schema, record schemas, and seeded exceptions content are
  taken directly from the approved Confluence architecture (Reference 1/1b/1c
  "Service Descriptors and Templates" and the Implementation Pack). Where that
  source is authoritative and specific (e.g. exact required fields, enum
  values, the three seeded exception ids and their owning services), this
  feature follows it exactly rather than inventing an alternative design.
- **Noted discrepancy requiring human confirmation**: the general exceptions
  policy (Quality, Security and Governance page) states a maximum exception
  lifetime of 30 days (14 for Critical severity), while the Implementation
  Pack's specific instruction for these three seed exceptions states a 60-day
  expiry. This spec follows the Implementation Pack's specific, task-level
  instruction for the seed data (60 days) since these three are structural
  "no suite defined yet" gaps during platform bootstrap, not severity
  findings — but the conflict should be resolved explicitly (likely by
  amending one of the two source pages) before this pattern is repeated for
  future exceptions.
- This feature produces no release, deploys nothing, and calls no GCP API —
  it is a local, offline tool and a set of schema/fixture files. GCP identity,
  Workload Identity Federation, and Cloud Deploy wiring are out of scope here
  and are covered by later features in this program.
- "Service repo owners" and "platform maintainers" are treated as the actors
  for this feature; end users of the seven downstream products are not
  actors here.
- The exact on-disk descriptor path (`.radic/service.yml`) and schema path
  (`schemas/service.schema.json`) are fixed by the approved architecture and
  are not reopened for debate in this spec.
