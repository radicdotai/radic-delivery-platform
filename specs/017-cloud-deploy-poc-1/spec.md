# Feature Specification: Cloud Deploy PoC-1 (operations-console sandbox)

**Feature Branch**: `018-cloud-deploy-poc-1`

**Created**: 2026-11-06

**Status**: Draft

**Input**: User description: "Run Cloud Deploy PoC-1 on a sandbox copy of
operations-console and build what it needs: the six GCP-calling `deploy`
subcommands (`release`, `promote`, `approve`, `rollback`, `status`,
`drift`), the Cloud Deploy machinery for the sandbox, and one repeatable
script per PoC-1 item of the UNVERIFIED register (Technical Design §9.11),
each with a recorded result. The sandbox never touches a real dev, stage or
prod service. Jira RAD-691."

## Why this feature exists

Cloud Deploy is mandatory in the approved design (Overview §4), but about
30 of its behaviours are unverified (OI-10, register U1 to U30). The
Migration plan §8.4 assigns 17 of them to PoC-1 on `operations-console`,
the simplest service (Node, environment-agnostic image, full-apply
Terraform). Until PoC-1 records a result for each item, no service can move
its deploys to Cloud Deploy, and the engine's `deploy` command group is
still a stub that prints "would call real Cloud Deploy".

This feature delivers both halves together: the engine code that every
later deploy workflow will call, and the evidence that the code works
against real Cloud Deploy.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A dev deploy goes through Cloud Deploy by digest (Priority: P1)

A platform maintainer runs the engine's release command with a built
image digest and the sandbox service's `deploy/` directory. Cloud Deploy
creates a release on the sandbox dev pipeline, rolls it out, and the
sandbox service then serves exactly that digest. The command waits for
the rollout to finish and reports the release, rollout and final state in
the same JSON shape every other engine command uses.

**Why this priority**: this is the dev path (`cd-dev`) every service will
use on every merge, and every other story builds on a release existing.

**Independent Test**: run the release command against the sandbox dev
pipeline with a known digest; then the status command shows the rollout
`SUCCEEDED`, and the sandbox service's running image ends in that digest.

**Acceptance Scenarios**:

1. **Given** a digest-pinned image and a valid `deploy/` directory, **When**
   the release command runs, **Then** a release named per the naming rule
   (`d-<sha7>-<run>`) exists, its rollout reaches `SUCCEEDED`, and the
   sandbox service runs that digest.
2. **Given** an image given by tag instead of digest, **When** the release
   command runs, **Then** it refuses before calling Cloud Deploy.
3. **Given** a rollout that fails (for example a container that never
   becomes healthy), **When** the release command waits, **Then** it reports
   `FAILED` with the failed job named and exits non-zero; it never reports
   success on a timeout.

---

### User Story 2 - Promotion needs two separate identities (Priority: P1)

A release that passed the sandbox stage target is promoted to the sandbox
prod target. The promote command creates a prod rollout that waits for
approval; only the separate approver identity can approve it; the identity
that created the release cannot create a prod rollout.

**Why this priority**: separation of duties for prod (design B, OI-4) is
the core safety claim of the design. If Cloud Deploy cannot enforce it as
designed, the prod design changes before any real service migrates.

**Independent Test**: create a release as the release-creator identity,
promote as the promoter identity, attempt approval as the creator (result
recorded), approve as the approver identity, and confirm the rollout
`SUCCEEDED`.

**Acceptance Scenarios**:

1. **Given** a release whose stage rollout succeeded, **When** the promote
   command runs as the promoter, **Then** a rollout to the prod-like target
   exists in `PENDING_APPROVAL`.
2. **Given** a pending rollout, **When** the approve command runs as the
   approver, **Then** the rollout proceeds to `SUCCEEDED`.
3. **Given** the release-creator identity, **When** it tries to create a
   rollout on the prod-like target, **Then** Cloud Deploy denies it (U25).
4. **Given** the release-creator identity, **When** it tries to approve,
   **Then** the result is recorded either way (U9; expected: allowed, which
   is why design B relies on separate identities).

---

### User Story 3 - Roll back to the previous digest and measure it (Priority: P2)

An operator rolls the sandbox back to the previous successful release. The
rollback command reports the digest now serving and how long it took.

**Why this priority**: rollback time is an SLO (Quality page) and the
design's fallback depends on the measured time (U29 is PoC-2, but the
command is needed here and its timing is recorded now).

**Independent Test**: deploy release A then release B; roll back; the
sandbox serves A's digest; the duration is recorded.

**Acceptance Scenarios**:

1. **Given** two successful releases, **When** rollback runs with no
   release named, **Then** the previous release's digest serves.
2. **Given** a named release, **When** rollback runs, **Then** that
   release's digest serves, and a digest given alongside it that does not
   match the release is refused.

---

### User Story 4 - Drift is detected (Priority: P2)

The drift command compares the live sandbox service with the manifest of
the last rollout and reports any difference; the U1 script separately
confirms `terraform plan` stays clean.

**Why this priority**: the design's ownership boundary (Technical Design
§9.4) only holds if Terraform never reverts a Cloud Deploy revision (U1)
and console edits are caught (U14).

**Independent Test**: after three consecutive deploys, drift reports zero
Terraform changes; after a console edit to an env var, drift reports that
field.

**Acceptance Scenarios**:

1. **Given** three consecutive Cloud Deploy rollouts, **When** the U1
   script runs, **Then** `terraform plan` shows zero changes for the
   sandbox service, and drift reports none.
2. **Given** a manual console change to the sandbox, **When** drift runs,
   **Then** it names the changed field and exits non-zero.

---

### User Story 5 - Every PoC-1 item has a recorded, repeatable result (Priority: P1)

A reviewer opens the PoC record and, for each of the 17 PoC-1 items, sees
the question, the script that tests it, the command output (project ids,
release and rollout names, no secrets), the result (pass, fail or
partial), and the fallback adopted where it did not pass.

**Why this priority**: the PoC exit review (story E6c-3) is signed on this
record; without it Cloud Deploy stays a decision without evidence.

**Independent Test**: re-run any item's script from a clean checkout and
get the same result.

**Acceptance Scenarios**:

1. **Given** the PoC-1 item list, **When** the record is reviewed, **Then**
   every item has a script under `poc/Uxx/` and a result entry; none is
   blank.
2. **Given** an item the sandbox cannot test (for example cross-project
   image pull while everything stays in the non-prod project), **When** the
   record is reviewed, **Then** it is marked `deferred` with the reason and
   the PoC that will test it, never marked `pass`.

---

### User Story 6 - A merge builds and deploys the sandbox on its own (Priority: P1)

An engineer merges a PR into the PoC branch of `operations-console`. With
no other step, the image is built once, pushed, and deployed by digest to
the sandbox dev target through Cloud Deploy, and the run summary shows the
digest, release, rollout and health result.

**Why this priority**: this is the PoC exit criterion "one full dev
merge-to-rollout cycle" and the first real use of the central workflows by
a service repo.

**Independent Test**: merge a trivial change to the PoC branch; the
sandbox serves the new digest and the old services do not change.

**Acceptance Scenarios**:

1. **Given** a merge to the PoC branch, **When** the caller runs, **Then**
   build and deploy both succeed and the sandbox serves the new digest.
2. **Given** a merge to `operations-console`'s real `dev` branch, **When**
   it runs, **Then** only the existing workflows run and the sandbox is not
   touched.
3. **Given** the workflow run from any ref other than the pinned platform
   ref, **When** it requests the deploy identity, **Then** WIF refuses it.

### Edge Cases

- Two releases created within two minutes on the dev pipeline: the final
  serving digest must be the newest; the behaviour is recorded (U10).
- A release created while a target's parameters were later changed: the
  effect on a later promotion is recorded (U19).
- The engine is asked to act on a pipeline not named in the descriptor: it
  refuses; names come only from the descriptor's `cloud_deploy` block.
- A Cloud Deploy call returns an error the engine does not recognise: the
  command fails with the raw error and exit code `4` (infrastructure
  error), never a partial success.
- Teardown: after the exit review every sandbox resource is destroyed and
  a listing of pipelines, targets, services and service accounts shows
  none left.

## Requirements *(mandatory)*

### Functional Requirements

**Engine (`deploy` command group)**

- **FR-001**: The engine MUST provide `deploy release`, `deploy promote`,
  `deploy approve`, `deploy rollback`, `deploy status` and `deploy drift`,
  replacing today's stubs, with the inputs, outputs and identities in
  Reference 2 §3.13 and Reference 3 §6.
- **FR-002**: Every command MUST take pipeline, target and service names
  only from the descriptor's `cloud_deploy` block, and MUST refuse any
  image reference that is not `repository@sha256:<digest>`.
- **FR-003**: `deploy release` MUST create the release with the naming,
  labels and annotations in Technical Design §9.3 and wait until the
  rollout reaches a terminal state; a timeout is a failure.
- **FR-004**: `deploy promote` and `deploy approve` MUST be separate
  commands so each can run under its own identity; `promote` MUST report
  the rollout as pending approval and never approve it.
- **FR-005**: `deploy rollback` MUST use the standard Cloud Deploy target
  rollback, report the serving digest and duration, and refuse a digest
  that does not match the chosen release.
- **FR-006**: `deploy status` MUST be read-only and report release,
  rollout, state and serving digest for a target.
- **FR-007**: `deploy drift` MUST be read-only and report differences
  between the live service and the manifest Cloud Deploy rendered for the
  last successful rollout. The `terraform plan` half of the boundary check
  (U1) lives in the PoC script, not the engine, because the engine holds no
  Terraform state access.
- **FR-008**: Every command MUST emit the same machine-readable JSON and
  human-readable forms as the existing commands, and use the engine's
  existing exit-code contract (`0` ok, `2` invalid input, `3` policy
  failure, `4` infrastructure error).
- **FR-009**: The engine remains the only code path to `gcloud deploy` and
  `gcloud run` (constitution rule 12); tests run without GCP by faking the
  `gcloud` boundary, and the live PoC proves the real calls.

**Sandbox and machinery**

- **FR-010**: The Cloud Deploy machinery for the sandbox (pipelines,
  targets, execution and release identities, IAM, source bucket) MUST be
  Terraform under `terraform/modules/cloud-deploy`, the module the real
  rollout will reuse; nothing is created by hand except the Terraform
  state bucket.
- **FR-011**: The sandbox MUST be a new Cloud Run service copied from
  `operations-console-dev`'s live spec, in the non-prod project, with its
  own runtime service account; it MUST NOT share a domain, secret write
  access or runtime identity with any real service.
- **FR-012**: The sandbox pipelines MUST mirror the design: a single-target
  dev pipeline, and a release pipeline with a stage-like target and a
  prod-like target that requires approval. All of it lives in the non-prod
  project `radicai` (decision 6 Nov 2026). Nothing is created in
  `radicai-production`; U11 (cross-project image pull) and the
  release-plane location (OI-5) are recorded as `deferred` to a follow-up
  run that needs prod-project access.
- **FR-013**: Separate identities MUST exist for release creation,
  promotion, approval, rollback and execution, with the conditions in
  Technical Design §10.3, so U9, U25 and U26 can be tested as designed.

**PoC record**

- **FR-014**: Each PoC-1 item (U1, U2, U6, U9, U10, U11, U13, U14, U15,
  U17, U19, U20, U25, U26, U27, U28, U30) MUST have a repeatable script
  under `poc/Uxx/` and a result entry with evidence and the fallback
  adopted.
- **FR-015**: Results MUST be copied to the U-register in Technical Design
  after review; the record in this repo is the source.
**End-to-end loop** (decision 6 Nov 2026: full merge-to-deploy loop)

- **FR-016**: The platform MUST provide the `build` and `deploy` reusable
  workflows per Reference 2 §3.3 and §3.6, limited to what the sandbox
  needs: build once, push, record the digest; then `deploy release` on the
  dev pipeline by that digest, wait, and run a health check. Migrations,
  change-note upload, Slack and post-deploy regression are out of scope
  (operations-console has no database).
- **FR-017**: A sandbox caller (`cd-dev`-shaped) MUST live in the
  `operations-console` repo on a dedicated branch used only for the PoC,
  so a merge to that branch builds and deploys to the sandbox, while the
  real `dev` branch and its existing workflows are untouched.
- **FR-018**: The workflows MUST authenticate only through WIF, with a
  dev-only provider condition on exact repository, the platform's
  `v1-canary` workflow ref and the `dev` Environment; no JSON key exists.
- **FR-019**: The promote and approve path (User Story 2) MAY run from
  scripts in this feature; the `promote` workflow is a later feature.

### Key Entities

- **Deploy Result**: the JSON outcome of one `deploy` command: command,
  pipeline, target, release, rollout, state, serving digest, duration,
  identity used, and any Cloud Deploy error.
- **PoC Item Result**: U-id, question, script path, run timestamp,
  evidence excerpt, result (`pass`, `fail`, `partial`, `deferred`),
  fallback adopted, reviewer.
- **Sandbox**: the clone service, its runtime identity, and the Cloud
  Deploy pipelines and targets that point at it; created and destroyed as
  one unit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A digest goes from release command to serving on the sandbox
  dev target with no manual step, and the time is recorded (p90 over at
  least 5 runs, U30).
- **SC-002**: The release-creator identity cannot create a prod-like
  rollout, and only the approver identity can move one out of pending
  approval; both are shown by recorded command output.
- **SC-003**: `terraform plan` shows zero changes for the sandbox after 3
  consecutive Cloud Deploy rollouts (U1).
- **SC-004**: Every one of the 17 PoC-1 items has a result; none is blank,
  and any `deferred` item names the PoC that will settle it.
- **SC-005**: After teardown, no sandbox pipeline, target, service or
  service account remains in either project.
- **SC-006**: No real dev, stage or prod service changes revision, IAM or
  traffic during the PoC (checked by comparing their state before and
  after).
- **SC-007**: A merge to the PoC branch reaches the sandbox serving the new
  digest with zero manual steps, and a workflow run from an unpinned ref
  cannot obtain the deploy identity.

## Assumptions

- The approved design (Confluence RAITSDA, updated 3 Nov 2026) is the
  source of truth. Where this feature differs (sandbox instead of the real
  `operations-console-dev`), the difference is the user's decision of 6 Nov
  2026, to keep the real dev console untouched; the takeover of the real
  dev service is part of the later cut-over, not this PoC.
- The live prod services already run in `radicai-production` behind the
  prod load balancer (RAD-736, 4 Nov 2026), so OI-1 / U16 is effectively
  resolved; stale `*-prod` services and domain mappings remain in
  `radicai` and are a cleanup item outside this feature.
- `infra.yml` does not exist yet, so the sandbox Terraform is applied from
  a maintainer's machine for the PoC only, and every apply and destroy is
  recorded in the PoC record. Real environments keep the `infra.yml`-only
  rule.
- The existing descriptor schema fixes the release plane to
  `radicai-production`; the sandbox needs `radicai` for it, so the PoC
  descriptor is validated against a PoC-only override, and the real schema
  is unchanged.
- The PoC uses the mutable `v1-canary` platform ref, which the design
  allows for `operations-console` in dev and stage only.
- Aditya owns this feature (GCP side and `deploy` commands); Vijit owns the
  engine's update to the 3 Nov design and reviews this work.
- PoC-2 items (U3, U4, U5, U7, U8, U12, U16, U18, U21, U22, U23, U24, U29)
  are out of scope.
