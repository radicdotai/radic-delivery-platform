# Contract: `radic-delivery deploy` commands

All commands: `--descriptor PATH` (default `.radic/service.yml`),
`--deployable NAME` (required when the descriptor lists more than one),
`--format json|text`. Pipeline, target, service and project names come only
from the descriptor. Output shapes are in [data-model.md](../data-model.md).
Exit codes: `0` ok, `2` invalid input, `3` policy failure (deploy did not
reach the required state), `4` infrastructure error.

| Command | Inputs | gcloud calls (in order) | Success |
|---|---|---|---|
| `deploy release` | `--env dev\|stage`, `--image REF@sha256:…`, `--source DIR` (default `deploy/`), `--commit SHA40`, `--run-number N` (dev) or `--release-id ID` (stage), `--run-url URL`, `--initiator LOGIN`, `--timeout SECONDS` | `deploy releases create` (dev pipeline for `dev`, rel pipeline with initial rollout to the stage target for `stage`); `deploy rollouts list --release`; poll `deploy rollouts describe`; `run services describe` | rollout `SUCCEEDED` and serving digest equals the image digest |
| `deploy promote` | `--release NAME`, `--to prod`, `--timeout` | `deploy releases describe`; `deploy releases promote --to-target=<prod target>`; poll until `PENDING_APPROVAL` | rollout `PENDING_APPROVAL` (never approves) |
| `deploy approve` | `--release NAME`, `--rollout NAME`, `--timeout` | `deploy rollouts approve`; poll `deploy rollouts describe`; `run services describe` | rollout `SUCCEEDED` |
| `deploy rollback` | `--env`, `--release NAME` (optional), `--expect-digest sha256:…` (optional), `--reason TEXT`, `--timeout` | `deploy releases describe` (when `--release` and `--expect-digest`); `deploy targets rollback --rollout-id=rb-<ts>`; poll; `run services describe` | rollout `SUCCEEDED` and serving digest equals the chosen release's digest; mismatch of `--expect-digest` is exit `2` before any change |
| `deploy status` | `--env` | `deploy rollouts list` (latest for the target); `run services describe` | read-only; exit `0` when Ready and the serving digest equals the last successful rollout's digest, else `3` |
| `deploy drift` | `--env` | `deploy rollouts list`; `deploy releases describe`; `storage cat <rendered manifest>`; `run services describe --format=export` | read-only; exit `0` with no differences, `3` with differences |

`deploy lint` is unchanged.

Not in this feature: canary advance, `retry-job`, deploy policies, any
call to `radicai-production`.
