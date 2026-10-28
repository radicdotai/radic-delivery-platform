# Phase 1 Data Model: Central CI Reusable Workflow (`ci-gate` mode)

## Entity: ToolInvocation (internal, `gate/commands.py`)

Not persisted; a pure value produced by command construction (research.md D1).

- `check_name`: one of `lint`, `typecheck`, `unit`
- `argv`: `list[str]` — the exact command to execute
- `cwd`: working directory the command should run in (the service repo root)

## Entity: CheckResult

One per executed check (`lint`, `typecheck`, `unit`) plus two derived checks
that don't run a subprocess of their own (`coverage`, `skip_budget`):

- `name`: `lint` | `typecheck` | `unit` | `coverage` | `skip_budget`
- `status`: `pass` | `fail` | `not_executable` | `not_implemented`
  (`not_executable` is FR-010's "tool could not be found/run at all," distinct
  from `fail`, which means the tool ran and reported a problem)
- `detail`: human-readable reason (e.g. which lint rule, which test failed,
  measured coverage vs. floor, how many tests skipped and which exception
  ids covered them)

## Entity: CoverageResult (internal, `gate/parsers.py`)

- Either `{"global": float}` or `{"statements": float, "branches": float,
  "functions": float, "lines": float}` — mirrors the two shapes
  `quality.coverage_floor` can take in the service descriptor (feature 001),
  so the comparison in `evaluator.py` is a direct, shape-matched comparison
  rather than a reinterpretation.

## Entity: TestRunResult (internal, `gate/parsers.py`)

- `passed`: int
- `failed`: int
- `skipped`: int
- `skipped_test_ids`: `list[str]` when the underlying tool reports them (best
  effort — used only for `detail` messages, never for the pass/fail decision
  itself, since the decision only needs the count and the exception lookup)

## Entity: GateResult (`gate/result.py`) — the feature's primary output

- `mode`: `ci-gate` | `release-gate`
- `overall`: `pass` | `fail` | `not_implemented` (the last only when
  `mode: release-gate`, per FR-011)
- `checks`: `list[CheckResult]`
- `coverage`: `CoverageResult | None`
- `skipped_count`: `int | None`
- `mutation`: `{"status": "not_implemented"}` always, in this feature
  (FR-012)
- `deploy_lint`: `{"status": "not_available"}` always, in this feature
  (FR-013)
- `test_inventory_uri`: `{"status": "not_available"}` always, in this
  feature (FR-013)

`GateResult.overall` is `pass` only when every `CheckResult` in `checks` is
`pass` — a single `fail` or `not_executable` anywhere makes the overall
result `fail` (FR-005, FR-010).

This is the JSON shape `radic-delivery gate evaluate --format json` emits,
and the shape the `ci.yml` reusable workflow reads back to set its own
`gate_result`, `coverage_total`, and `skipped_count` outputs (`test_inventory_uri`
and `deploy_lint` are passed through as their fixed not-available markers).

## Relationship to feature 001 entities

- `GateResult` is computed from a **Service Descriptor** (feature 001) that
  must already pass `descriptor validate` — `gate evaluate` reuses that
  validator directly rather than re-implementing any part of it (FR-002).
- The `skip_budget` `CheckResult` consults feature 001's **Policy Exception**
  ledger (`policy/exceptions.py`'s `check()`) — but for a *different*
  question than `descriptor validate` asks. `descriptor validate` checks
  `quality.post_deploy.exception_id`, a field scoped to deployed-environment
  regression suites. `gate evaluate` is checking *unit-test* skips observed
  in this run, which the approved architecture does not give an explicit
  exception-scoping convention for.

  **Documented assumption, flagged for Tech Lead confirmation** (same
  treatment as feature 001's expiry-discrepancy note): this feature looks up
  an exception whose `scope` field equals the literal string
  `quality.unit.skip` for the service named in the descriptor's `service.name`,
  and requires it to be active (not expired) for the gate to tolerate ANY
  non-zero skip count — it does not attempt to match individual skipped
  test ids. If no reviewer objects, a later feature should fold this
  convention into the descriptor/exceptions schema explicitly rather than
  leaving it as an engine-internal string constant.
