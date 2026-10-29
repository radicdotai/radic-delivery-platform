# Phase 1 Data Model: Deploy YAML Lint

## Entity: ManifestCheck

One per individual check performed:

- `deployable`: the name of the deployable this check belongs to (from
  `cloud_deploy.deployables[].name`)
- `rule`: `image_placeholder` | `no_traffic_key` | `startup_probe` |
  `no_inline_secret` | `parity`
- `status`: `pass` | `fail` | `missing_file` | `parse_error` |
  `not_applicable` (the last only for `job_yaml`-only deployables,
  research.md D4)
- `file`: the manifest path involved (for `parity`, a comma-joined pair,
  e.g. `"run/dev.yaml, run/prod.yaml"`)
- `detail`: human-readable description of what was found

## Entity: DeployLintResult — the feature's primary output

- `overall`: `pass` | `fail` (pass only if every `ManifestCheck.status` is
  `pass` or `not_applicable`)
- `checks`: `list[ManifestCheck]`

This is the JSON shape `radic-delivery deploy lint --format json` emits,
and the shape `.github/workflows/ci.yml` reads back to replace its
`deploy_lint` output's current fixed `not_available` value with the real
`overall` result.

## Relationship to prior features' entities

- `DeployLintResult` is computed from a **Service Descriptor** (feature
  001) that must already pass `descriptor validate` — `deploy lint` reuses
  that validator directly, exactly as `gate evaluate` and `security scan`
  already do.
- The `no_inline_secret` rule's execution reuses feature 003's gitleaks
  `RunOutcome`/parsing machinery (`security/runner.py`,
  `security/parsers.py::parse_gitleaks`) directly — it does not define a
  second `Finding`-shaped entity; a gitleaks hit on a manifest file is
  translated straight into a failing `ManifestCheck`.
- The `parity` rule reads `cloud_deploy.deployables[].parity.allow`
  exactly as feature 001's schema already defines it (research.md D3's
  mapping table interprets those string values; it does not change the
  schema).
