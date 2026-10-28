<!--
Sync Impact Report
Version change: template → 1.0.0 (initial ratification)
Modified principles: n/a (first adoption)
Added sections: Core Principles (I–XII), Security, Testing & Operational Standards,
  Development Workflow & Quality Gates, Governance
Removed sections: none
Templates requiring updates:
  - .specify/templates/plan-template.md ✅ no change needed (Constitution Check gate
    is derived dynamically from this file; structure is project-agnostic)
  - .specify/templates/spec-template.md ✅ no change needed (generic, project-agnostic)
  - .specify/templates/tasks-template.md ✅ no change needed (generic, project-agnostic)
  - .claude/skills/speckit-*/SKILL.md ✅ no agent-specific rewording needed
Follow-up TODOs: none — all placeholders resolved from the approved Confluence
  architecture (RAITSDA space, "Centralised CI/CD" page tree) and today's date.
-->

# radic-delivery-platform Constitution

## Core Principles

### I. Centralise Implementation, Decentralise Configuration

Pipeline behaviour MUST live only in this repo's reusable GitHub Actions workflows
and `engine/` code, released under exact-tag pins (`v1.x.y`). A service repo
(`fastapi-backend`, `web-bff`, `design_service`, `image-studio`, `brand_research`,
`frontend-v2`, `operations-console`) MUST hold only: its `.radic/service.yml`
descriptor, its `deploy/` directory, and thin caller workflows that call a pinned
tag of a workflow defined here. No service repo may hold a forked or duplicated
copy of CI/CD logic; differences between services are expressed exclusively as
descriptor fields validated against `schemas/service.schema.json`.

**Rationale**: the seven repos currently carry diverged pipeline copies — the
root cause of inconsistent promotion logic and un-auditable releases. Centralising
logic here and pushing variability into a typed descriptor is the only way one fix
lands everywhere at once.

### II. Build Once, Promote the Verified Digest (NON-NEGOTIABLE)

An image is built exactly once per release candidate and referenced thereafter
only by its `sha256:` digest. Promotion from dev → stage → prod MUST be verified
by ancestry, git-tree equality, and tag checks (`verify-promotion`) before any
release or rollout command runs. No workflow, descriptor field, or manual
procedure may deploy a mutable tag (e.g. `latest`, `v1-canary` in prod) to stage
or prod.

**Rationale**: build-once/promote-by-digest is the only way to guarantee that
what passed stage regression is bit-for-bit what reaches production.

### III. Fail-Closed Quality Gates, Zero Skip Budget

A missing, skipped, errored, or timed-out required check is treated as a release
blocker, never as a pass. The skip budget for any required suite is always `0`.
The only way to tolerate a known gap (a flaky test, a coverage shortfall, a scan
finding, a missing suite) is a dated entry in the single file
`delivery-platform/policy/exceptions.yml`, carrying an id (`EXC-####`), a Jira
ticket, Tech Lead approval, and an expiry (≤30 days, ≤14 days for Critical
severity). No other mechanism (inline `continue-on-error`, workflow-level
`if: always()` swallowing failures, ad hoc per-repo overrides) may suppress a
required check.

**Rationale**: stage today is validated by smoke checks only and defects reach
UAT; fail-closed gates plus a single auditable exceptions ledger are the
mechanism that closes that gap without becoming unworkable.

### IV. Keyless, Separated-Duty Identity

Every GCP-facing identity MUST be Workload Identity Federation (WIF), scoped to
an exact repository, an exact semver workflow tag, and an environment — never a
long-lived JSON key. Build, dev-release, stage-release, prod-promote,
prod-approve, rollback, per-environment migration, and infrastructure duties each
use a distinct service account. No single identity may both create and approve a
production Cloud Deploy rollout.

**Rationale**: broad, undifferentiated credentials are a named root cause in the
current state; per-duty WIF identities make privilege escalation and accidental
cross-environment access structurally impossible, not just policy-forbidden.

### V. Human-and-Machine Approval for Production

A production rollout requires both a human approval (GitHub Environment `prod`,
team `release-managers`, approver distinct from the initiator) and a separate
machine approval (`cd-prod-approver` identity, distinct from `cd-prod-promoter`).
Break-glass access is the only exception path: it requires two named approvers
(Tech Lead and deputy), is time-boxed, and MUST be reconciled back to the
standard state within the same incident.

**Rationale**: four-eyes review on a human axis and a separated-identity axis
means no single compromised account or process can push to production alone.

### VI. Terraform and Cloud Deploy Have a Stated Ownership Boundary

Terraform owns infrastructure: IAM, WIF, Artifact Registry, Cloud Deploy
pipelines/targets, Cloud SQL, Secret Manager containers. Cloud Deploy plus the
per-environment service YAML (`deploy/run/<env>.yaml`) own the running Cloud Run
revision and are the complete desired spec for it. Any Terraform-managed
`google_cloud_run_v2_service`/`service` resource MUST `lifecycle { ignore_changes
= [...] }` the revision template, traffic, and related fields Cloud Deploy
manages. A deploy workflow never runs `terraform apply`; `infra.yml` is the only
path to applying Terraform. `terraform plan` MUST stay clean after consecutive
Cloud Deploy rollouts.

**Rationale**: without an explicit boundary, Terraform silently reverts
Cloud Deploy's revisions (or vice versa) — this principle makes the boundary a
build-time check, not a tribal-knowledge rule.

### VII. No Arbitrary Commands in Configuration

A service descriptor, workflow input, or Cloud Deploy deploy-parameter selects a
named runtime template and typed, schema-validated parameters — never a raw
shell command or expression to `eval`. Any change to a workflow or composite
action MUST pass `actionlint` and `zizmor` before merge.

**Rationale**: descriptors and CI inputs are attacker-reachable surface the
moment a PR can edit them; this principle forecloses injection by construction
rather than by review discipline alone.

### VIII. The Bot Proposes, People Decide

The release bot (GitHub App, zero GCP identity of its own) performs only
mechanical work: cherry-picking approved tickets onto `release/<id>` with
`cherry-pick -x` trailers, opening the release PR with machine-readable
sections, and fast-forwarding `main` only after a production deploy succeeds. A
release manager edits the ticket selection via the fixed slash-command grammar;
a second person — never the initiator — approves the release PR and, later, the
production promotion.

**Rationale**: automation should remove toil, not remove the human decision of
*what* ships; keeping the bot's authority mechanical keeps every release
decision attributable to a named person.

### IX. Parity Before Strictness

Onboarding or migrating a service onto this platform follows staged shadow
validation before cutover: shadow CI before `ci-gate` becomes required, shadow
Cloud Deploy before it replaces the old deploy path, and a parity diff reviewed
before old workflows are deleted. New security or quality gates start
report-only and become blocking only after an explicit pilot period recorded in
`policy/exceptions.yml` or the migration plan — this is how existing behaviour is
protected during migration, and it is not license to skip gates on new work
built directly on this platform.

**Rationale**: the seven service repos must keep deploying throughout the
migration; parity-checked shadow phases are what make cutover reversible instead
of a leap of faith.

### X. Specification and Release Traceability

Every change to this repository traces: specification → acceptance criteria →
task → test → (where applicable) a release manifest record
(`delivery-records/releases/<id>.yaml`) and a test-result record for every stage
deploy. Every UAT-escaped defect MUST gain a regression test before the next
release cut that touches the same area.

**Rationale**: this is the direct fix for "bugs reach UAT and don't become
regression tests" — traceability is only useful if it is enforced as a gate, not
kept as a convention.

### XI. Layered, Escalating Security Scanning

Every build is scanned (Snyk Open Source/Code/Container/IaC as the primary
scanner, plus gitleaks, Hadolint, Trivy, and SBOM generation; cosign signing in a
later phase). A Critical-severity finding or a verified secret blocks the PR or
release outright. The move from report-only to blocking for any given scanner or
severity class is itself governed by `policy/exceptions.yml` and the rollout
plan, not by local, ad hoc suppression in a single repo's workflow.

**Rationale**: no scanning, SBOM, or signing exists in the current state; this
principle commits to closing that gap on a managed schedule instead of leaving
it indefinite.

### XII. The Engine CLI Is the Only Path to GCP

The `radic-delivery` Python/uv/typer CLI in `engine/` is the single supported
code path to `gcloud deploy` and `gcloud run` operations; no workflow YAML may
shell out to `gcloud`/Terraform directly. Every CLI command supports
`--format json|text`, uses the fixed exit-code contract (`0` success, `2`
invalid input, `3` policy failure, `4` infra error), and MUST NOT print secret
values or the contents of `.env`, `gcs-service-account.json`, or any
service-account credential file. Python services use `uv` + `ruff` + `mypy` +
`pytest`; Node services use their existing `eslint`/`tsc`/`vitest`/`playwright`
toolchain — no new toolchain is introduced without an amendment.

**Rationale**: a single, tested code path to GCP is what makes the fail-closed
and separated-identity principles actually enforceable instead of merely
documented.

## Security, Testing & Operational Standards

**Security**: WIF only, never long-lived GCP keys; least-privilege, per-duty
service accounts (Principle IV); secret values are never read, logged, or
echoed by any agent, workflow, or CLI command; files named or shaped like
`.env`, `gcs-service-account.json`, or `Service Account Radic.rtf` MUST NOT be
opened or quoted under any circumstance, in this repo or any service repo this
platform touches.

**Testing**: the test pyramid required per service is unit, integration,
contract (where a workflow/caller is itself a contract), end-to-end, and
UAT-escape regression (Principle X). Coverage floors are declared per service in
its descriptor and MAY only ratchet upward (never lowered) by up to 2 points per
quarter. A flaky test may be quarantined for at most 7 days and at most 2% of a
repo's tests at any time; beyond that it must be fixed, deleted, or covered by a
dated exception.

**Delivery and operations**: rollback to the previous digest targets ≤10 minutes
and is rehearsed monthly; a hotfix is cut on `release/<id>-hf` from the
production line and backported into `dev` via `cherry-pick -x` within 1 working
day of prod success; SEV1 incidents get a 15-minute response and freeze further
deploys, SEV2 gets 1 hour during working hours; every SEV1/SEV2 gets a
post-incident review within 5 working days.

## Development Workflow & Quality Gates

Every change in this repository follows the Spec Kit lifecycle: constitution →
specify → (clarify, if ambiguity survives) → plan → tasks → analyze → implement.
No implementation PR merges without a specification it traces to.

A PR into `dev` here must pass `ci-gate` and a human review before merge; `dev`
is squash-merge-only trunk. Task execution follows the fixed task-prompt shape
established in the program's Implementation Pack: `Repo:` + branch off `dev`,
`Read first:`, `Task:`, `Exit criteria:`, `Verify:` (exact shell commands), and a
`Do NOT:` guardrail list — one task per branch, verified against its exit
criteria and verify commands before being reported done.

This repository's own `CLAUDE.md`, and the template it propagates into each
service repo, MUST stay consistent with these principles; a change to either
that would contradict a principle above requires a constitution amendment first.

## Governance

This constitution supersedes ad hoc practice in this repository. It is a
formalisation of the architecture already approved in Confluence space RAITSDA
(`Centralised CI/CD: Overview and Architecture` and its linked Technical Design,
GCP Environments and Components, Release and Operations Runbook, Quality/
Security/Governance, Migration and Cut-over Plan, Implementation Pack, and
Reference 1/1b/1c/2/3 pages) — it must not contradict that documentation. If an
engineering need surfaces that would require deviating from the Confluence-
documented design, the Confluence pages are amended first (or the deviation is
recorded as a dated, approved exception), and only then is this constitution
amended to match.

Amendments require Tech Lead approval, a stated rationale, and a version bump
following semantic versioning: MAJOR for a backward-incompatible removal or
redefinition of a principle, MINOR for a new principle or materially expanded
guidance, PATCH for wording or clarification only. Every PR and every
`/speckit-plan` Constitution Check must verify compliance with the principles
above; a violation must be justified in that plan's Complexity Tracking table or
the plan is rejected.

**Version**: 1.0.0 | **Ratified**: 2026-10-29 | **Last Amended**: 2026-10-29
