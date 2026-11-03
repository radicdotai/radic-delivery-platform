# Phase 1 Data Model: Quality Gate Completion

## Entity: GateResult (extends specs/002's entity, `gate/result.py`)

No shape change — `release-gate` populates the exact same `GateResult`
`ci-gate` already does (research.md D1/D2):

- `checks`: now may include a `CheckResult` named `"stage_regression"`
  (a new `CheckName` value) in addition to `lint`/`typecheck`/`unit`/
  `coverage`/`skip_budget` — only ever present in `release-gate` mode,
  never `ci-gate`
- Every other field (`mode`, `overall`, `coverage`, `skipped_count`,
  `mutation`, `deploy_lint`, `test_inventory_uri`) unchanged

## Entity: MigrationGraphResult (`migrations/graph.py`, new)

- `sound`: bool
- `root`: `str | None` — the one file with `down_revision = None`,
  `None` only when the directory is empty or no root was found
- `forks`: `list[{"down_revision": str, "files": list[str]}]` — a
  `down_revision` value claimed by more than one file
- `cycles`: `list[list[str]]` — each a list of filenames forming a cycle
- `detail`: human-readable summary

## Entity: MigrationFreezeResult (`migrations/frozen.py`, new)

- `checks`: `list[{"file": str, "status": "intact" | "missing" |
  "altered", "detail": str}]` — one entry per
  `migrations.frozen_check_workflow_files` path
- `ok`: bool — `True` only when every entry is `"intact"`

## Entity: MigrationsCheckResult (`migrations/result.py`, new — the CLI-level aggregate)

- `enabled`: bool — mirrors the descriptor's `migrations.enabled`;
  `False` short-circuits everything else to not-checked (spec Edge Case)
- `migrations_frozen`: `MigrationFreezeResult | None` — `None` when not
  requested or `enabled` is `False`
- `migration_graph`: `MigrationGraphResult | None` — `None` when not
  requested, not enabled, or `--migrations-dir` wasn't supplied
- `alembic_check` / `schema_check`: always the literal string
  `"not_available"` when requested, `None` when not requested
  (research.md D3)
- `ok`: bool — `True` when every *actually-run* check (`migrations_frozen`,
  `migration_graph`) passed; a requested-but-`not_available` check never
  affects `ok`

## Relationship to prior features' entities

`release-gate`'s `stage_regression` check reads (never rewrites or
re-validates) a test-result record specs/010's `records put-test-result`
already wrote (`schemas/test-result.schema.json`'s `environment`,
`digest`, `scope`, `result`, `counts.skipped` fields) — trusted as already
valid, the same discipline `release finalise` (specs/011) already applies
to an incoming release manifest. `migrations check` has no relationship
to any prior feature's entity; it reads only a descriptor's `migrations`
block (specs/001's schema, unchanged by this feature) and local migration/
workflow files.
