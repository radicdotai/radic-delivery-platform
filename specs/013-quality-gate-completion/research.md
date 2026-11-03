# Phase 0 Research: Quality Gate Completion

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| `gate evaluate --mode release-gate` CLI surface: `--results-dir PATH` (new, named in Reference 3's own worked example) — worked example: `radic-delivery gate evaluate --mode release-gate --results-dir results/ --format json` → `{"gate": "release-gate", "result": "failure", "reasons": [{"check": "stage_regression", "status": "missing", "detail": "no test-result record for sha256:0000...0003"}], ...}` | Reference 3, §6 worked example |
| `ci` workflow's "`release-gate` additionally requires the stage test-result record for the exact digest" (Reference 2 §3.1); the release-PR checklist lists `release-gate green` as a *separate* item from the Cloud-Deploy-rollout-succeeded fact, which stays `promote`'s own concern (Reference 2 §3.7) | Reference 2, §3.1 and §3.7 |
| `migrations check` CLI surface: `--descriptor PATH`; `--checks LIST` — "Runs `alembic_check`, `migration_graph`, `migrations_frozen` (port of `check_migrations_frozen.py`, reads descriptor `migrations`)" | Reference 3, §6 CLI table |
| Descriptor `migrations` schema: `enabled` (bool, required), `tool` (enum `alembic`/`django-manage`/`alembic+manage`), `job_name` (string), `checks` (enum array: `alembic_check`/`migration_graph`/`migrations_frozen`/`schema_check`), `hooks`, `frozen_check_workflow_files` (array of strings) | `schemas/service.schema.json` (specs/001, already correct) |
| `check_migrations_frozen.py`'s real behaviour: depends on the exact workflow filenames `deploy-dev.yml`/`deploy-stage.yml`/`deploy-prod.yml` and the job name `Run Database Migrations` staying present until migration stage S4 | Release and Operations Runbook, pageId 407535617 |
| "Migrations are forward-only and schema rollback is a separate decision" | Reference 2, §3.9 (rollback) |

## Design decisions made for this plan

### D1 — `release-gate` reuses `ci-gate`'s own checks, exactly, plus one new check

`gate/evaluator.py::evaluate()` currently short-circuits `release-gate` to
`GateResult(mode=mode, overall="not_implemented", checks=[])`.
**Decision**: remove that short-circuit; `release-gate` runs the identical
lint/typecheck/unit/coverage/skip_budget sequence `ci-gate` already runs
(same function, same code path — no duplicated logic, FR-001), then adds
one further check, `stage_regression` (a new `CheckName` value), which
`ci-gate` never runs. This keeps the two modes as one real, shared
evaluation rather than two divergent implementations of the same checks.

### D2 — The `stage_regression` check reads an already-stored record, never re-validates it

Reference 3's own worked example's output shape
(`{"gate", "result", "reasons", "skipped_tests", "coverage"}`) differs
cosmetically from this platform's already-established `GateResult` shape
(`mode`/`overall`/`checks`/...) that `ci-gate` already uses and every
caller of `gate evaluate` already consumes — the same "CLI table/examples
are abbreviated, not authoritative on exact field names" precedent
already applied repeatedly (specs/006 D7, specs/008 D3, specs/011 D1).
**Decision**: `release-gate` keeps the one, already-established
`GateResult` shape rather than introducing a second, divergent output
format for one mode only; the worked example's specific *fact*
(a missing record names `stage_regression` as the failing check, with a
detail naming the digest) is preserved exactly, just inside the existing
`checks: [...]` list.

**New required input**: `--results-dir PATH` (per Reference 3's own
worked example) and `--digest DIGEST` (new, flagged — the worked example
names a specific digest in its failure detail, but the CLI table doesn't
show the flag that supplies it; without it there is no way to know which
stage record is "the exact digest being evaluated", FR-002/FR-003). The
check scans every `*.json` file under `--results-dir` recursively (the
same `releases/<id>/test-results/*.json` tree `records put-test-result`
(specs/010) already writes — this feature reads what that one already
produces, never re-implements writing it), looking for a record with
`environment == "stage"` and `digest == --digest`. **Decision, flagged**:
if more than one such record exists, the first one found is used (spec
Edge Case) — this platform has no other rule for "the" stage record per
digest, and inventing a tie-breaker beyond "first found" would be
asserting a convention nothing currently requires.

When found, the check passes only if `scope == "full"`,
`result == "pass"`, and `counts.skipped == 0` (Reference 2's "no skipped
tests in required suites"); any other shape found (wrong scope, a fail,
or a nonzero skip count) fails the check, naming specifically which
condition wasn't met. The record is trusted as already-valid (it was
schema-validated when `records put-test-result` wrote it) — this feature
never re-runs `records/validator.py` against it, the same "trust an
already-produced artifact" discipline `release finalise` (specs/011)
already applies to an incoming release manifest.

### D3 — `migrations check`'s real scope: `migrations_frozen` and `migration_graph`; `alembic_check`/`schema_check` explicitly not available

Both the literal `alembic check` command and `schema_check` fundamentally
compare migration state against a live database — there is no
file-only, local substitute that would actually test the same thing, and
building a look-alike that merely resembles them would misrepresent what
passed. **Decision**: both are accepted as valid `--checks` values (so a
caller requesting them isn't met with an unknown-flag error) but always
reported `not_available` — never attempted, never approximated — the
same "accept the input, don't fake the result" precedent specs/003's
scanning, specs/008's readiness checks, and specs/011's
Cloud-Deploy-digest check already established. Only `migrations_frozen`
and `migration_graph` are built for real (spec Assumptions).

`migrations_frozen` is a direct, faithful port of
`check_migrations_frozen.py`'s real behaviour: for every path in the
descriptor's `migrations.frozen_check_workflow_files`, confirm the file
exists under `--repo-dir` (new, flagged — `gate evaluate`'s own
`repo_root = descriptor.parent.parent` convention would force every
descriptor to live at `<root>/.radic/service.yml`; `migrations check`
instead takes the repository root as its own explicit input, default
`.`, so its descriptor can be tested standalone without that layout),
parse it as YAML, and confirm some job in its
`jobs:` mapping has `name: <migrations.job_name>` exactly — reporting
specifically which file is missing (FR-005, Acceptance Scenario 4) or
present-but-altered (no matching job name — Acceptance Scenario 5),
never a single undifferentiated failure.

`migration_graph` is scoped to Alembic-style migration files only (a
`revision = "..."` / `down_revision = "..."` header pair per file, the
only migration-chain shape this platform's descriptor schema's `tool`
enum concretely names in a way this feature can parse without a live
tool) — spec Assumptions. **New, flagged input**: `--migrations-dir PATH`
(Reference 3's own table has no flag naming where migration files live;
without one, `migration_graph` has nothing to read). Each `*.py` file
under it is parsed (via Python's own `ast` module — reading, never
executing, the file — Principle VII) for its own `revision`/
`down_revision` literal assignments. The graph is sound when exactly one
file has `down_revision = None` (the root) and every other file's
`down_revision` points at exactly one other file's `revision`, with no
file's `down_revision` value shared by two different files (a fork,
Acceptance Scenario 2, naming both files) and no cycle (a chain that
never reaches the root, Acceptance Scenario 3). An empty directory is
trivially sound (spec Edge Case).

### D4 — Exit codes

`release-gate`: `ExitCode.POLICY_FAILURE` when `overall == "fail"` (the
same classification `ci-gate` already gives a failing check);
`ExitCode.OK` on a full pass; an invalid descriptor is
`ExitCode.INVALID_INPUT` (the same ordering `gate evaluate` already uses
for `ci-gate`).

`migrations check`: `ExitCode.POLICY_FAILURE` when `migrations_frozen` or
`migration_graph` reports a real failure (a missing/altered safeguard, or
a fork/cycle); `ExitCode.OK` when every requested, actually-checkable
check passes (a request for `alembic_check`/`schema_check` alone, with no
other check requested, is still `ExitCode.OK` — "not available" is not a
failure, the same honesty precedent as `verify-promotion`'s always-
`not_available` Cloud-Deploy fact never failing that command either); a
service with `migrations.enabled: false` reports this plainly and exits
`ExitCode.OK` (spec Edge Case, nothing to check is not an error); an
invalid descriptor is `ExitCode.INVALID_INPUT`.

### D5 — Testing strategy

`release-gate` is tested against this platform's own existing real
fixture repos (`engine/tests/fixtures/sample-repos/`) for its reused
lint/typecheck/unit/coverage/skip_budget checks (no new fixtures needed
there), plus small, local, hand-written stage test-result record files
(`tmp_path`) for the new `stage_regression` check's four acceptance
scenarios — no git, no external call. `migrations check` is tested
against a small, new fixture (`engine/tests/fixtures/migrations/`): a
handful of real, hand-written Alembic-style `.py` migration files (a
sound chain, a forked chain, a cyclical chain) and a small real workflow
YAML file, following the same "real fixture repo" pattern every prior
feature has used rather than mocking file contents inline.
