# PoC-1 results (2026-11-06)

Sandbox: `radicdotai/operations-console-cdpoc` (private copy of operations-console dev) →
`ops-console-cdpoc-{dev,stage,prod}` in `radicai`. Platform at tag `poc1-canary`.

## End-to-end

| Flow | Result | Evidence |
|---|---|---|
| Merge to `dev` → build → dev deploy by digest | pass | run 42189951698: release `d-40e2491-4` SUCCEEDED, serving digest = built digest, `/health` 200; build ~1m50s, deploy 64s |
| Pick release (CDP-4 held) → `release/2026.11.06-1` → stage | pass | `r-2026-11-06-1-6e59e4b` SUCCEEDED on stage, digest match |
| Unsafe pick (CDP-2 held, CDP-3 needs its migration) | blocked before GCP | run 42191685317: "Parent revision missing for 0003"; no stage release created |
| Promote to prod (promoter) → approve (approver) | pass | stopped at PENDING_APPROVAL; approved; prod SUCCEEDED in 80s, digest match |
| Rollback dev to previous release | pass | 54s; wrong `--expect-digest` exits 2 with no change |

## U-items

| U | Result | Finding |
|---|---|---|
| U1 | pass | `terraform plan` clean after 8 rollouts + rollback, once `ignore_changes` includes `scaling` and the provider sets `add_terraform_attribution_label = false` (rollouts strip `goog-terraform-provisioned`) |
| U2 | partial | invoker IAM, ingress survive; labels become manifest labels + `managed-by`. Domain mapping deferred (sandbox has none) |
| U9 | pass | promoter `rollouts approve` → 403 |
| U14 | pass | console env edit reported as `container.env.BFF_URL` changed, value not printed. Drift compares only fields the manifest sets (Cloud Run adds port name, probe timeout) |
| U15 | finding | releaser needs `storage.buckets.get` on the source bucket (`legacyBucketReader`), and source must be staged in a named bucket (`cloud_deploy.source_bucket`) or the default bucket needs project-wide create |
| U17 | pass | commit and digest read back from release annotations |
| U25 | partial | stage releaser cannot promote to prod, but it was stopped by act-as on the prod deployer before the `rolloutTarget` condition was evaluated; the condition alone is unproven |
| U26 | finding | execution SA needs `artifactregistry.reader` on the image repo (Cloud Run checks the deployer, not only the runtime) |
| U6, U10, U11, U13, U19, U20, U27, U28, U30 | not run | U11 deferred (no prod project) |

## Design findings

1. Pipeline-scoped `clouddeploy.releaser` lets an identity **create** releases but not **list** them or read the
   release operation. Needed a project-level read-only custom role (list/get releases, rollouts, pipelines,
   targets, operations). Write access stays pipeline/target scoped.
2. Creating a release renders every target, so the creator needs act-as on every target's RENDER identity.
   Splitting execution configs into one shared RENDER SA plus a per-target DEPLOY SA keeps the stage releaser
   off the prod deployer.
3. Release selection has no migration-chain rule: an unsafe hold-back is proposed and cut. Caught only by
   `migrations check` (which itself treated a missing parent as sound until this PoC) in the stage deploy gate.
4. Existing `release-*` workflows cannot run from a service repo: `./actions/setup-engine` resolves to the
   caller, they reference `radicdotai/delivery-platform` (does not exist) at `v1.0.0` (no tags), and
   `radicdotai/delivery-records` does not exist. New workflows resolve their own commit from the OIDC
   `job_workflow_sha`.
5. Re-running a failed GitHub run keeps the reusable-workflow version it first resolved, and re-runs the jobs
   the failed job depends on (the build ran again).
6. `deploy lint` needs gitleaks on the runner (fails closed without it).

## Safety

Baseline of 40 real services taken before apply. At the end no real service was changed by a `cdpoc-*`
identity. Three were changed during the PoC by the operator account via `gcloud run services update`
(operations-console, radic-brand-research-prod, radic-image-studio-prod in `radicai`, 08:10–08:12 UTC) —
not by the PoC tooling; to be confirmed by the account owner.
