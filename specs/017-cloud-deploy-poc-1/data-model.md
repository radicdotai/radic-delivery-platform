# Data Model: Cloud Deploy PoC-1

## DeployResult (JSON output of every `deploy` command except `drift`)

| Field | Type | Notes |
|---|---|---|
| `command` | `release` \| `promote` \| `approve` \| `rollback` \| `status` | |
| `deployable` | string | from the descriptor |
| `pipeline` | string | from the descriptor, never a free argument |
| `target` | string | |
| `project` | string | the plane project from the descriptor |
| `release` | string \| null | Cloud Deploy release name |
| `rollout` | string \| null | |
| `state` | `SUCCEEDED` \| `PENDING_APPROVAL` \| `IN_PROGRESS` \| `FAILED` \| `CANCELLED` \| `REJECTED` \| `TIMED_OUT` \| null | `TIMED_OUT` is set by the engine, not Cloud Deploy |
| `failed_job` | string \| null | set when `state` is `FAILED` |
| `requested_digest` | string \| null | `sha256:...` passed in |
| `serving_digest` | string \| null | read from the service's latest ready revision |
| `ready` | bool \| null | Ready condition of the service |
| `duration_seconds` | number | wall time of the command |
| `outcome` | `pass` \| `fail` | `pass` only when the rules in research D8 hold |
| `error` | string \| null | raw gcloud stderr on exit `4` |

Validation: `requested_digest` must match `^sha256:[0-9a-f]{64}$`; an image
reference must be `<registry>/<project>/<repo>/<name>@sha256:<64 hex>`.

## DriftResult (`deploy drift`)

| Field | Type |
|---|---|
| `deployable`, `target`, `project` | string |
| `release`, `rollout` | string — the last successful rollout compared against |
| `differences` | list of `{field, expected, live}`; values for env vars are shown by name only plus `changed: true`, never the value |
| `outcome` | `pass` (no differences) \| `fail` |

## Release naming (from Technical Design §9.3)

- dev: `d-<sha7>-<run_number>`
- rel: `r-<release_id with dots to dashes>-<sha7>`
- labels: `svc`, `commit` (sha7), `release-id` (rel only)
- annotations: `commit` (40 hex), `digest`, `run-url`, `initiator`,
  `manifest` (rel only)

## Sandbox (one Terraform root, created and destroyed as a unit)

```text
deployable ops-console-cdpoc
├── pipeline ops-console-cdpoc-dev  → target ops-console-cdpoc-dev   → service ops-console-cdpoc-dev
└── pipeline ops-console-cdpoc-rel  → target ops-console-cdpoc-stage → service ops-console-cdpoc-stage
                                    → target ops-console-cdpoc-prod  → service ops-console-cdpoc-prod (requireApproval)
identities: cdpoc-build, cdpoc-rel-dev, cdpoc-rel-stage, cdpoc-prod-promoter,
            cdpoc-prod-approver, cdpoc-rollback, cdpoc-exec-{dev,stage,prod}, cdpoc-runtime
WIF: pool gh-delivery / provider gh-delivery-dev → cdpoc-build, cdpoc-rel-dev
bucket: radicai-cd-source-cdpoc
```

## PocItemResult (one row in `poc/results.md`)

| Field | Values |
|---|---|
| `id` | `U1` … `U30` (PoC-1 subset only) |
| `question` | copied from the Technical Design register |
| `script` | `poc/Uxx/run.sh` |
| `run_at` | ISO timestamp |
| `result` | `pass` \| `fail` \| `partial` \| `deferred` |
| `evidence` | link to `poc/Uxx/evidence.txt` |
| `fallback_adopted` | text, required unless `pass` |
| `deferred_to` | required when `deferred` (e.g. "PoC-1b, prod-project run") |

State transitions: `unrun → pass | fail | partial | deferred`; a `fail`
may move to `pass` only by re-running the script after a recorded change.
