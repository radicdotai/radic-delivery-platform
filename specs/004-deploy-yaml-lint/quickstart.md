# Quickstart: Deploy YAML Lint

Requires `gitleaks` on `PATH` (same requirement as specs/003's `security
scan`, reused here for the inline-secret rule).

```bash
cd engine
uv sync

# Lint a service with clean deploy manifests — expect an overall pass
uv run radic-delivery deploy lint \
  --descriptor tests/fixtures/sample-repos/python-sample/.radic/service.yml \
  --format json

# Lint a service with one seeded violation per rule — expect failures
# naming the file and the rule
uv run radic-delivery deploy lint \
  --descriptor tests/fixtures/sample-repos/python-sample-bad-deploy/.radic/service.yml \
  --format text

# Quality gates for this feature itself
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

Expected exit codes: `0` when `overall == "pass"`, `2` when `overall ==
"fail"` or the descriptor itself is invalid (both are `INVALID_INPUT` —
unlike `gate evaluate`, there is no separate "policy failure" category
here: a bad deploy manifest and a bad descriptor are both, simply, invalid
input to a deploy that must not happen).

## Validating the `ci.yml` change

```bash
cd /path/to/delivery-platform
actionlint .github/workflows/ci.yml
```
