# engine

The `radic-delivery` CLI: the single supported code path for inspecting and
validating this platform's service descriptors and policy exceptions, for
evaluating a service's CI quality gate, for scanning a service for security
findings, and for linting a service's Cloud Deploy manifests. See
`specs/001-engine-scaffold/`, `specs/002-ci-gate-workflow/`,
`specs/003-security-scanning/`, and `specs/004-deploy-yaml-lint/` for the
full specification, plan, and design rationale behind this package.

## Command surface

```text
radic-delivery descriptor validate <path>              # implemented
radic-delivery descriptor show <path>                   # implemented
radic-delivery policy exceptions check <id>              # implemented
radic-delivery gate evaluate --mode ci-gate <...>         # implemented
radic-delivery gate evaluate --mode release-gate <...>    # not implemented yet (reports as such)
radic-delivery security scan --scope source|iac|all <...> # implemented (report-only — never blocks)
radic-delivery deploy lint <...>                          # implemented (binary — fails on a bad manifest)

radic-delivery notes ...        # not implemented yet
radic-delivery tests ...        # not implemented yet
radic-delivery release ...      # not implemented yet (top-level release-train group)
radic-delivery deploy release|promote|approve|rollback|status|drift   # not implemented yet (calls real Cloud Deploy)
radic-delivery records ...      # not implemented yet
radic-delivery rollback ...     # not implemented yet
radic-delivery migrations ...   # not implemented yet
```

`gate evaluate --mode ci-gate` runs the service's own descriptor-declared
lint/type-check/unit-test tools (assumed already installed — installing a
service's own toolchain is the calling workflow's job, not this command's),
and reports one pass/fail Gate Result covering: lint, type-check, unit
tests, the descriptor's coverage floor, and the zero-skip-budget rule
(skips must be covered by an active, unexpired exception in
`policy/exceptions.yml` with `scope: quality.unit.skip`). It never calls
`gcloud` or any GCP API. See `specs/002-ci-gate-workflow/data-model.md` for
the full `GateResult` shape.

`security scan` runs `gitleaks` (hardcoded secrets), `hadolint`
(Dockerfile lint), and `trivy` in config-scanning mode (Dockerfile/IaC
misconfiguration — only when a Dockerfile actually exists on disk at the
descriptor's declared path), and reports every finding, severity-classified,
in one `SecurityScanResult`. This is the report-only rollout phase: **a
finding, at any severity, never fails this command** — the only way it
exits non-zero is the descriptor itself failing validation, before any scan
runs. Container-image scanning and Snyk are always reported as
`not_available`, never silently omitted — see
`specs/003-security-scanning/data-model.md` for the full result shape.

`deploy lint` reads a descriptor's declared Cloud Run service YAML files for
dev/stage/prod and checks each against five rules: the required placeholder
image reference (`image: app`), no `traffic` key, a startup probe present,
no inline secret (reusing `security scan`'s `gitleaks` integration rather
than a second detection method), and the three environment files matching
exactly except for the specific keys the descriptor's own
`cloud_deploy.deployables[].parity.allow` permits to differ. Unlike
`security scan`, this is a **binary correctness check, not an advisory
report**: a bad manifest fails the command (exit `2`), the same as an
invalid descriptor — Cloud Deploy applies these files exactly as committed,
so there is no report-only phase for them. Only `deploy lint` is
implemented; every other `deploy` subcommand calls real Cloud Deploy and
remains unimplemented. See `specs/004-deploy-yaml-lint/data-model.md` for
the full `DeployLintResult` shape.

Every "not implemented yet" command exits with a distinct code (64) that is
never one of the four real outcomes below, so a caller can tell "this isn't
built yet" apart from "this failed."

## Exit code contract

| Code | Meaning |
|---|---|
| 0 | success |
| 2 | invalid input (a descriptor or exception id failed validation) |
| 3 | policy failure (e.g. an expired policy exception) |
| 4 | infrastructure/environment error |
| 64 | the command is not implemented yet |

Every implemented command supports `--format json` and `--format text`,
reporting identical facts in both.

## Adding a new descriptor fixture

Real service descriptor fixtures live in `tests/fixtures/<service-name>.yml`
and are asserted valid in `tests/unit/test_descriptor_validate.py`'s
`REAL_SERVICE_FIXTURES` list. Deliberately invalid fixtures exercising a
specific failure mode live in `tests/fixtures/broken/`. To add a new one:

1. Add the YAML file under the appropriate directory.
2. If it is a real service's descriptor, add its filename to
   `REAL_SERVICE_FIXTURES` in `test_descriptor_validate.py`.
3. If it is a deliberately broken fixture, add a test asserting which
   specific `ValidationIssue.category` and field path it must produce.

## Development

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run mypy src/
```
