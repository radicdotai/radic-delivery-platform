# engine

The `radic-delivery` CLI: the single supported code path for inspecting and
validating this platform's service descriptors and policy exceptions, and
for evaluating a service's CI quality gate. See `specs/001-engine-scaffold/`
and `specs/002-ci-gate-workflow/` for the full specification, plan, and
design rationale behind this package.

## Command surface

```text
radic-delivery descriptor validate <path>              # implemented
radic-delivery descriptor show <path>                   # implemented
radic-delivery policy exceptions check <id>              # implemented
radic-delivery gate evaluate --mode ci-gate <...>         # implemented
radic-delivery gate evaluate --mode release-gate <...>    # not implemented yet (reports as such)

radic-delivery notes ...        # not implemented yet
radic-delivery tests ...        # not implemented yet
radic-delivery release ...      # not implemented yet
radic-delivery deploy ...       # not implemented yet
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
