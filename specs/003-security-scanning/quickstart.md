# Quickstart: Central Security Scanning Workflow (report-only)

Requires `gitleaks`, `hadolint`, and `trivy` on `PATH` (installing them is
this feature's new composite action's job in CI; for local development:
`brew install gitleaks hadolint trivy` on macOS).

```bash
cd engine
uv sync

# Scan a clean sample service — expect zero findings, scan_result still "completed"
uv run radic-delivery security scan --scope all \
  --descriptor tests/fixtures/sample-repos/python-sample/.radic/service.yml \
  --format json

# Scan a sample service with a planted secret — expect one critical finding,
# and the command still exits 0
uv run radic-delivery security scan --scope source \
  --descriptor tests/fixtures/sample-repos/python-sample-secret/.radic/service.yml \
  --format text
echo "exit=$?"

# Scan a sample service with a misconfigured Dockerfile — expect hadolint
# and/or trivy findings, iac scope reported "checked"
uv run radic-delivery security scan --scope iac \
  --descriptor tests/fixtures/sample-repos/python-sample-bad-dockerfile/.radic/service.yml \
  --format text

# A service with no Dockerfile requesting iac scope — expect "not_applicable",
# not an error and not a false "zero findings"
uv run radic-delivery security scan --scope iac \
  --descriptor tests/fixtures/sample-repos/python-sample/.radic/service.yml \
  --format json

# Quality gates for this feature itself
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

Expected exit code in every case above: `0`. The only way this command
exits non-zero is an invalid descriptor (exit `2`), never a finding.

## Validating the new GitHub Actions artifacts

```bash
cd /path/to/delivery-platform
actionlint .github/workflows/security.yml templates/callers/ci.yml
```

`actions/setup-security-tools/action.yml` is checked for valid YAML and the
composite-action shape, the same way `actions/setup-engine/action.yml` was
in specs/002 (`actionlint` does not lint composite action files).
