# Research: Cloud Deploy PoC-1 (operations-console sandbox)

Decisions taken while planning. Each one records what was chosen, why, and
what else was considered. Facts marked **observed** were read from GCP,
GitHub or the repos on 2026-11-06.

## Observed starting state

- `radicai`: Cloud Deploy, Cloud Build, Artifact Registry and Cloud Run APIs
  are enabled; **no delivery pipelines exist**.
- `radicai-production`: Cloud Deploy API **disabled**, no WIF pool. Live
  prod runs here behind load balancer `34.49.73.199` (RAD-736, 4 Nov).
  Not touched by this feature.
- `operations-console-dev` (live): Next.js on port 3000, 1 CPU / 512Mi,
  `cpu_idle`, 0 to 10 instances, a startup probe, two literal env vars
  (`NODE_ENV`, `BFF_URL`), **no secrets**, runtime SA
  `github-actions-deployer@radicai` (the shared deployer, a known
  over-privilege), public `allUsers` invoker, domain `dev-console.radic.ai`.
  Terraform: `terraform/envs/dev/main.tf`, full apply, state
  `radicai-terraform-state-dev/operations-console-dev`.
- Image repo: `us-central1-docker.pkg.dev/radicai/operations-console/operations-console`
  (the test fixture's `radic-operations-console` repository name is wrong).
- WIF in `radicai`: pools `github-pool` and `github-actions-pool`; the
  operations-console provider trusts `attribute.repository ==
  'radicdotai/operations-console'` only (any workflow, any branch).
- `radicdotai/radic-delivery-platform` is a **public** repository with **no
  tags**. The design calls it `delivery-platform`; WIF conditions must use
  the real name.
- Engine exit codes are `0/2/3/4` (`engine/src/radic_delivery/exit_codes.py`);
  the Confluence pages say `0/10/20/30`. The code wins for this feature; the
  doc needs a correction.
- The two GitHub CLI accounts on the maintainer's machine cannot see
  private `radicdotai` repos (environments API returns 404). Creating the
  `dev` Environment in `operations-console` needs an account with admin on
  that repo.

## D1. Sandbox shape

**Decision**: three new Cloud Run services in `radicai`, cloned from the
live `operations-console-dev` spec: `ops-console-cdpoc-dev`,
`ops-console-cdpoc-stage`, `ops-console-cdpoc-prod`. Each runs as a new
runtime SA `cdpoc-runtime@radicai` with no roles beyond logging. No
`allUsers` invoker and no domain mapping; `run.invoker` is granted only to
the PoC operator, so the sandbox is not a second public console.

**Rationale**: the user chose a sandbox (6 Nov) so the real dev console is
never touched. Three services let the release pipeline exercise a
stage-like and a prod-like target with approval. A private sandbox keeps a
copy of the console off the internet.

**Alternatives**: one sandbox service shared by all targets (cannot test
per-target state or rollback semantics); public invoker like the real dev
service (exposes a second console for no PoC benefit).

**Consequence**: U2's domain-mapping half cannot be tested on the sandbox
and is `deferred` to the real dev cut-over. U2's IAM-policy and ingress
halves are tested.

## D2. Plane placement

**Decision**: both pipelines in `radicai`: `ops-console-cdpoc-dev` (one
target) and `ops-console-cdpoc-rel` (stage-like then prod-like with
`requireApproval: true`). Nothing is created in `radicai-production`.

**Rationale**: user decision of 6 Nov. Approval, identity separation and
rollback behave the same within one project.

**Deferred**: U11 (cross-project image pull) and OI-5 (release plane in
`radicai-production`) go to a follow-up run that needs prod-project access.

## D3. Identities

**Decision**: one service account per duty, all prefixed `cdpoc-` so they
never collide with the real names the rollout will create later:

| SA | Duty | Key grants |
|---|---|---|
| `cdpoc-build` | push images | `artifactregistry.writer` on repo `operations-console` only |
| `cdpoc-rel-dev` | create dev releases | releaser on `ops-console-cdpoc-dev` pipeline; `actAs` on `cdpoc-exec-dev`; object create on the source bucket |
| `cdpoc-rel-stage` | create rel releases + stage rollout | custom role (releases create/get/list, rollouts get/list), `rollouts.create` with condition `rolloutTarget == ops-console-cdpoc-stage`; `actAs` on `cdpoc-exec-stage` |
| `cdpoc-prod-promoter` | prod-like rollout | `rollouts.create` with condition `rolloutTarget == ops-console-cdpoc-prod`; `actAs` on `cdpoc-exec-prod` |
| `cdpoc-prod-approver` | approve | `clouddeploy.approver` with the same condition |
| `cdpoc-rollback` | rollback | `rollouts.rollback` + rollout create on the named targets |
| `cdpoc-exec-{dev,stage,prod}` | execution | `clouddeploy.jobRunner`; `run.developer` **on its one service only** (U26); `serviceAccountUser` on `cdpoc-runtime` only |
| `cdpoc-runtime` | container runtime | logging only |

The PoC operator (Aditya) gets `iam.serviceAccountTokenCreator` on each of
these, so the U-scripts can act as each identity with
`--impersonate-service-account`. This grant is PoC-only and is destroyed
with the sandbox.

**Rationale**: matches Technical Design §10.3, so U9, U25 and U26 are tested
against the real design. Separate names keep teardown clean.

**Alternatives**: reuse real names now (`cd-rel-dev`) — rejected: the real
rollout must create them from its own Terraform, not inherit PoC leftovers.

## D4. Workload Identity Federation

**Decision**: a new pool `gh-delivery` with provider `gh-delivery-dev` in
`radicai`. Attribute mapping: `google.subject`, `repository`,
`repository_owner`, `environment`, `ref`, `job_workflow_ref`. Condition:

```text
assertion.repository_owner == 'radicdotai'
&& assertion.repository == 'radicdotai/operations-console'
&& assertion.environment == 'dev'
&& assertion.job_workflow_ref.startsWith('radicdotai/radic-delivery-platform/.github/workflows/')
&& assertion.job_workflow_ref.endsWith('@refs/tags/v1-canary')
```

Only `cdpoc-build` and `cdpoc-rel-dev` are bound to this provider (the
dev-loop identities). The stage, promoter, approver and rollback identities
are exercised by the U-scripts through impersonation, not from GitHub (FR-019).

**Rationale**: the design's condition (Technical Design §10.2) is repository
plus workflow ref plus environment, never repository only. A new pool
leaves the existing pools, which live deploys depend on, untouched.

**Alternatives**: add a provider to `github-pool` — rejected so a mistake
cannot affect the existing providers. `ref == refs/heads/<branch>` —
rejected; it trusts the caller's branch, not the platform's code.

## D5. Platform ref for the PoC

**Decision**: the PoC callers pin `@v1-canary`, a tag on this feature's
branch head, moved forward during the PoC.

**Rationale**: the design allows `v1-canary` for `operations-console` in
dev and stage; no other repo uses it yet, and the repo has no tags at all.

**Needs agreement**: Vijit, as platform maintainer, should confirm that
`v1-canary` can point at an unmerged PoC branch until the PoC merges.
Fallback: a throwaway tag `poc1-canary` with the WIF condition changed to
match.

## D6. Terraform layout and apply path

**Decision**:

- `terraform/modules/cloud-deploy`: takes a map of deployables and creates,
  per deployable, 2 pipelines, 3 targets (labels, `executionConfigs`,
  `deploy_parameters`, `requireApproval` on prod), and the pipeline- and
  target-level IAM of D3. This is the module the real rollout reuses.
- `terraform/modules/wif`: pool, provider, SA bindings (D4).
- `terraform/environments/poc-1`: the sandbox root. It calls both modules
  and owns the three sandbox Cloud Run shells (placeholder image,
  `lifecycle { ignore_changes = [template, traffic, ...] }`), the SAs, the
  source bucket `radicai-cd-source-cdpoc`, and the operator grants.
- State: existing bucket `radicai-terraform-state-dev`, prefix
  `delivery-platform/poc-1`. No new hand-made resource.
- Apply: from the maintainer's machine (no `infra.yml` yet). Every apply
  and destroy is logged in `poc/results.md`. See Complexity Tracking.

**Rationale**: FR-010; Technical Design §9.3 "Cloud Deploy machinery".

## D7. Engine boundary to gcloud

**Decision**: one module, `engine/src/radic_delivery/deploy/gcloud.py`,
holds the only `subprocess` call to `gcloud`. It takes a fixed argv list
built from typed inputs, always adds `--format=json`, parses stdout, and
raises `GcloudError` (carrying stderr) on a non-zero exit. Commands receive
a `Gcloud` protocol object; tests pass a fake that records argv and returns
canned JSON from `engine/tests/fixtures/cloud_deploy/`.

**Rationale**: same pattern as `release/git_history.py` (fixed,
parameterised argv; Principle VII). One boundary makes the fake trivial and
keeps Principle XII true.

**Identity**: the engine never chooses an identity. In workflows, the auth
step sets credentials before the engine runs; in U-scripts the operator
sets `CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT`.

## D8. Waiting and outcome mapping

**Decision**: `deploy release`, `promote`, `approve` and `rollback` poll
`gcloud deploy rollouts describe` every 10 s until a terminal state or
`--timeout` (default 900 s). Mapping:

| Outcome | Exit |
|---|---|
| `SUCCEEDED` (or `PENDING_APPROVAL` for `promote`) | `0` |
| `FAILED`, `CANCELLED`, `REJECTED`, timeout | `3` policy failure (the deploy did not happen as required) |
| bad input (tag instead of digest, unknown pipeline, digest mismatch) | `2` |
| gcloud error, permission denied, unparsable output | `4` |

**Rationale**: fail closed (Principle III): a timeout is never a pass.

## D9. Descriptor for the sandbox

**Decision**: add an optional `cloud_deploy.sandbox: true` to
`schemas/service.schema.json`. With an `if/then`, a sandbox descriptor may
set `planes.release` to `radicai`; a non-sandbox descriptor must still set
`radicai-production`. Pipeline names of a sandbox must contain `-cdpoc-`.

**Rationale**: the real schema stays strict; the sandbox is explicit and
cannot be mistaken for a real service. Also fixes the fixture's image
repository name.

**Alternatives**: a `--project` override flag on every command — rejected:
it moves configuration onto the command line, against Principle I.

## D10. Health for a private sandbox

**Decision**: `health.mode: gcloud-ready` (already in the schema). `deploy
status` reports the Ready condition and checks that the latest ready
revision's image ends in the expected digest. The HTTP verify container is
PoC-2 (U3).

## D11. Workflows

**Decision**: two reusable workflows, `build.yml` and `deploy.yml`, shaped
on Reference 2 §3.3 and §3.6 but only with the inputs the sandbox needs.

- `build.yml`: checkout, WIF auth as `cdpoc-build` (`google-github-actions/auth`
  with `token_format: access_token`), `docker/login-action` with that token,
  `docker/build-push-action` with tag `<40-hex sha>`, output `digest` from
  the build metadata. No `gcloud` in the workflow.
- `deploy.yml`: checkout the caller at the built commit, WIF auth as
  `cdpoc-rel-dev`, `actions/setup-engine`, then `radic-delivery deploy
  release` and `radic-delivery deploy status` (health), with JSON written to
  the job summary.

Out of scope here: migrations, change-note upload, Slack, regression
suites, SBOM and scanning in `build` (they arrive with the real `build.yml`
feature; `security.yml` already exists).

## D12. The caller in operations-console

**Decision**: branch `poc/cloud-deploy-1` in `radicdotai/operations-console`
holds `.radic/service.yml` (sandbox descriptor), `deploy/skaffold.yaml`,
`deploy/run/{dev,stage,prod}.yaml` (cloned spec, sandbox names,
`image: app`, startup probe, `serviceAccountName: cdpoc-runtime@...`), and
`.github/workflows/cd-cdpoc.yml` (push to that branch only, job
`environment: dev`, calls `build.yml` then `deploy.yml` at `@v1-canary`).
A GitHub Environment `dev` must exist in `operations-console`.

**Rationale**: FR-017. The real `dev` branch and its workflows never change.

**Prerequisite**: someone with admin on `operations-console` creates the
`dev` Environment (see Observed: current CLI accounts cannot).

## D13. PoC record

**Decision**: `poc/README.md` (how to run), `poc/results.md` (one row per U
item plus the apply/destroy log), and `poc/Uxx/run.sh` per item. Scripts are
bash, idempotent where possible, and write `poc/Uxx/evidence.txt` with
command output limited to resource names, states, timings and digests. They
never print env values or secret references' contents.

**Note**: the repo is public, so evidence must hold nothing beyond project
ids and resource names.

U-scripts may call `gcloud` directly for checks the engine does not own
(IAM policy reads, `terraform plan`, Monitoring queries). Principle XII is
about the pipeline path (engine and workflows); the PoC harness is evidence
tooling and is deleted or kept as `poc/` reference after the exit review.

## D14. Item-by-item approach

| U | How it is tested | Expected record |
|---|---|---|
| U1 | 3 rollouts via engine, then `terraform plan -detailed-exitcode` on `poc-1` | pass/fail |
| U2 | `get-iam-policy`, ingress, labels before and after 3 rollouts | partial (domain mapping deferred) |
| U6 | target `deploy_parameters` with a string (`BFF_URL`) and a number (max instances) via `# from-param:`; `skaffold render` locally | pass/fail |
| U9 | `cdpoc-rel-stage` attempts `rollouts approve` on a pending prod-like rollout | recorded either way |
| U10 | 3 `deploy release` calls within 2 minutes on the dev pipeline | behaviour recorded |
| U11 | — | deferred (D2) |
| U13 | release labels accepted; revision label visible in a Monitoring query | pass/fail |
| U14 | console edit of an env var on the dev sandbox, then `deploy drift` | pass/fail |
| U15 | release creation by `cdpoc-rel-dev` with only the D3 bucket grant | pass + minimal role set |
| U17 | `releases describe` output contains the `--images` digest | pass/fail |
| U19 | change a target parameter after release creation, then promote | behaviour recorded |
| U20 | bucket lifecycle reviewed; re-promote the oldest PoC release at exit | partial (90-day check deferred) |
| U25 | `cdpoc-rel-stage` tries a rollout to the prod-like target | pass/fail |
| U26 | execution SA with service-scoped `run.developer` completes a replace | pass/fail |
| U27 | release with `--skaffold-version` pinned | pass/fail |
| U28 | render without deploying (`--disable-initial-rollout` + render, or `skaffold render`) | finding recorded |
| U30 | timings of 5 dev and 5 stage rollouts, Cloud Build minutes | numbers recorded |

## D15. Drift comparison

**Decision**: `deploy drift` reads the last successful rollout's rendered
manifest path from `releases describe` (`targetArtifacts`), reads it with
`gcloud storage cat`, reads the live service with `gcloud run services
describe --format=export`, and compares a fixed field set: container image,
env names and values, resources, probes, ports, service account,
scaling and template annotations. Live-only fields (status, generated
annotations) are ignored by an explicit allowlist.

## D16. Teardown

**Decision**: `terraform destroy` of `environments/poc-1` (Cloud Deploy
pipelines are deleted with `force` so their releases go too), delete the
`poc/cloud-deploy-1` branch and the `dev` Environment if it was created
only for the PoC, and delete sandbox image tags from Artifact Registry. A
final listing (SC-005) is recorded.

## D17. Cost

Single-target pipelines are free; the one multi-target pipeline is billed
monthly (prorated) per Cloud Deploy pricing; Cloud Build minutes for render
and deploy jobs are recorded by U30. Expected total for the PoC window:
under USD 20 (estimate, not measured).
