# Quickstart: Central CI Reusable Workflow (`ci-gate` mode)

```bash
cd engine
uv sync

# Evaluate the gate against a sample service that passes everything
uv run radic-delivery gate evaluate --mode ci-gate \
  --descriptor tests/fixtures/sample-repos/python-sample/.radic/service.yml \
  --format json

# Evaluate against a sample service seeded with one failure per check
uv run radic-delivery gate evaluate --mode ci-gate \
  --descriptor tests/fixtures/sample-repos/python-sample-broken/.radic/service.yml \
  --format text

# release-gate mode is visibly not implemented yet
uv run radic-delivery gate evaluate --mode release-gate \
  --descriptor tests/fixtures/sample-repos/python-sample/.radic/service.yml

# Quality gates for this feature itself
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

Expected exit codes: `0` when the passing fixture's gate reports `pass`, `3`
(policy failure) when the broken fixture's gate reports `fail` — distinct
from `2` (invalid input), which `gate evaluate` only returns when the
descriptor itself fails validation, before any check runs — and `64` (the
same not-implemented code every other stub command group uses) when a
release-gate request reports `not_implemented` in its JSON/text output
without crashing (see data-model.md's `GateResult.overall`).

## Validating the GitHub Actions artifacts

The `.github/workflows/ci.yml`, `actions/setup-engine/action.yml`, and
`templates/callers/ci.yml` files cannot be executed end-to-end in this
repository (there is no real service repo to act as a caller). Validate them
statically instead:

```bash
actionlint .github/workflows/ci.yml templates/callers/ci.yml
```

Both pass `actionlint` with no findings. `actionlint` only understands workflow
files, not composite `action.yml` files, so `actions/setup-engine/action.yml`
is instead checked for valid YAML and the composite-action shape
(`runs.using: composite`, `inputs`, `outputs`) — see its own validation in
tasks.md T041.
