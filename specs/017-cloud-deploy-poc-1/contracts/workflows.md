# Contract: `build.yml` and `deploy.yml` (PoC-1 subset of Reference 2)

Both are `on: workflow_call`, validate the descriptor first, and fail
closed. No step calls `gcloud` or `terraform`; GCP access is WIF only.

## build.yml (Reference 2 §3.3, subset)

| Item | PoC-1 contract |
|---|---|
| Inputs | `descriptor` (default `.radic/service.yml`); `environment` (`dev` only in this feature); `wif_provider`, `service_account` (strings) |
| Outputs | `digest` (`sha256:…`); `image_ref` (`…@sha256:…`); `commit_tag` (40 hex) |
| Permissions | `contents: read`, `id-token: write` |
| Steps | checkout; descriptor validate; WIF auth (`token_format: access_token`); registry login; build and push with tag `<40-hex sha>`; emit digest from build metadata |
| Deferred to the real build feature | `reuse_if_tree_equal`, human tags, SBOM, scan, attestation, `release_id`, `cd_release_name` |

## deploy.yml (Reference 2 §3.6, subset)

| Item | PoC-1 contract |
|---|---|
| Inputs | `descriptor`; `environment` (`dev` only); `digest` (required); `image_ref` (required); `wif_provider`, `service_account` |
| Outputs | `cd_release`, `cd_rollout`, `cd_rollout_state`, `deployed_digest`, `duration_seconds` |
| Permissions | `contents: read`, `id-token: write`, `deployments: write` |
| Job | `environment: ${{ inputs.environment }}` so the WIF `environment` claim is set |
| Steps | checkout at `github.sha`; descriptor validate; `deploy lint`; WIF auth; `setup-engine`; `deploy release --env dev --image <image_ref> --commit <sha> --run-number <run_number> --run-url <url> --initiator <actor>`; `deploy status --env dev`; JSON to the job summary |
| Deferred | migrations, change-note, Slack, post-deploy suites, test-result record, stage mode |

## Caller (operations-console, branch `poc/cloud-deploy-1`)

```yaml
on: { push: { branches: [poc/cloud-deploy-1] } }
concurrency: { group: cd-cdpoc, cancel-in-progress: false }
permissions: { contents: read, id-token: write, deployments: write }
jobs:
  build:  uses: radicdotai/radic-delivery-platform/.github/workflows/build.yml@v1-canary
  deploy: needs: build
          uses: radicdotai/radic-delivery-platform/.github/workflows/deploy.yml@v1-canary
```

WIF provider and SA names are passed as inputs (they are identifiers, not
secrets).
