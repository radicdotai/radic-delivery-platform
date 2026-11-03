# Implementation Plan: Quality Gate Completion

**Branch**: `013-quality-gate-completion` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-quality-gate-completion/spec.md`

## Summary

Adds two small, unrelated CLI commands, bundled into one feature per the
project's explicit request to combine related, independently small
slices and reduce per-feature process overhead: `radic-delivery gate
evaluate --mode release-gate` (removes the existing `not_implemented`
short-circuit; reuses `ci-gate`'s own real lint/typecheck/unit/coverage/
skip-budget checks unchanged, adding one new `stage_regression` check
that reads an already-stored local test-result record for the exact
digest being evaluated) and `radic-delivery migrations check`
(`migrations_frozen`, a faithful local port of
`check_migrations_frozen.py`; `migration_graph`, a new Alembic-style
migration-chain soundness check; `alembic_check`/`schema_check` accepted
but always reported `not_available`, since both fundamentally need a live
database connection this sandbox cannot make). This closes out the
entire `gate`/quality-check command family — only the six GCP-calling
`deploy` subcommands remain unimplemented after this feature.

## Technical Context

**Language/Version**: Python 3.11 (same `engine/` package, extended again)

**Primary Dependencies**: none new — `release-gate` reuses
`gate/evaluator.py`, `gate/commands.py`, `gate/parsers.py`,
`gate/runner.py` directly; `migrations check` uses stdlib `ast` (parsing
migration files without executing them) and `pyyaml` (already a
dependency, for the frozen-workflow-file check)

**Storage**: `release-gate` reads (never writes) already-stored
test-result record files under `--results-dir` (specs/010's own output
tree); `migrations check` reads (never writes) local migration `.py`
files and workflow `.yml` files

**Testing**: `pytest` — `release-gate` exercised against this platform's
own existing real fixture repos plus small, hand-written stage
test-result record files (`tmp_path`); `migrations check` exercised
against a new small fixture directory
(`engine/tests/fixtures/migrations/`: sound/forked/cyclical migration
chains, an intact/altered workflow YAML pair)

**Target Platform**: developer workstation and GitHub-hosted Actions
runners; no server, no long-running process

**Project Type**: single CLI tool, unchanged — extends the existing
`gate/` subpackage in place; adds a new `migrations/` subpackage (the
`migrations` command group's first real subcommand)

**Performance Goals**: not applicable — a handful of real tool
executions, local file reads, and small graph computations

**Constraints**: zero external network call, zero database connection in
either command (FR-007); `alembic_check`/`schema_check` are always
`not_available`, regardless of whether requested — accepted for contract
compatibility only, the same "accept the flag, don't fake the behaviour"
precedent this platform has applied repeatedly (research.md D3);
`migration_graph` is scoped to Alembic-style `revision`/`down_revision`
files only, not Django-style numbered migrations (spec Assumptions)

**Scale/Scope**: one mode completed within the existing `gate evaluate`
command (`release-gate` — the `gate` command group now has no stubs
left), one command group completed (`migrations` — its stub replaced
with a real `check` subcommand), one new `migrations/` subpackage, one
new small fixture directory, three new test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise Implementation, Decentralise Configuration | `release-gate` reuses `ci-gate`'s check logic exactly once, in the engine; `migrations check`'s parsing/comparison logic lives once, keyed off the descriptor's own `migrations` block | PASS |
| II. Build Once, Promote the Verified Digest | `release-gate`'s whole `stage_regression` check exists to confirm the *exact digest* being promoted was the one actually tested in stage — a direct implementation of this principle | PASS |
| III. Fail-Closed Quality Gates, Zero Skip Budget | A missing or failing stage regression record always fails `release-gate` (FR-002, FR-003), never silently passes; `stage_regression` also fails on any nonzero skip count in the stage record, enforcing zero-skip-budget at the release-gate level too | PASS |
| IV. Keyless, Separated-Duty Identity | Not applicable — no GCP identity in either command | PASS (N/A) |
| V. Human-and-Machine Approval for Production | Not applicable to this feature's own scope — `release-gate` is a fact-check feeding the real approval, not the approval itself (consistent with specs/011's own framing of `finalise`) | PASS (N/A) |
| VI. Terraform and Cloud Deploy Ownership Boundary | Not applicable | PASS (N/A) |
| VII. No Arbitrary Commands in Configuration | `migrations check` parses migration/workflow files with `ast`/`yaml`, never executes them; every check it runs is a fixed, named operation, never a descriptor-supplied command string | PASS |
| VIII. The Bot Proposes, People Decide | Not applicable — both commands report facts; neither decides or acts on anything | PASS (N/A) |
| IX. Parity Before Strictness | Not applicable — these are deterministic correctness checks, not a phased rollout | PASS (N/A) |
| X. Specification and Release Traceability | `release-gate`'s `stage_regression` check is the one place this platform's CLI actually enforces that a release's test-result record (specs/010) must exist and pass before promotion proceeds | PASS |
| XI. Layered, Escalating Security Scanning | Not applicable — no build, image, or scan artifact | PASS (N/A) |
| XII. The Engine CLI Is the Only Path to GCP | Reconfirmed: zero `gcloud`/database/GCP SDK calls in either command; the two pieces that would need one (`alembic_check`, `schema_check`) are explicitly not implemented, not worked around (research.md D3) | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/013-quality-gate-completion/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── checklists/
│   └── requirements.md  # Spec quality checklist (already produced by /speckit-specify)
└── tasks.md              # Phase 2 output (/speckit-tasks — not created by this plan)
```

### Source Code (repository root)

```text
engine/src/radic_delivery/
├── cli.py                           # MODIFIED: add --results-dir/--digest to `gate evaluate`;
│                                      # replace the `migrations` stub with a real migrations_app
│                                      # (`check` subcommand)
├── gate/
│   ├── evaluator.py                  # MODIFIED: remove the release-gate not_implemented
│   │                                  # short-circuit; add the stage_regression check
│   └── result.py                     # MODIFIED: add "stage_regression" to CheckName
└── migrations/
    ├── __init__.py                   # NEW
    ├── result.py                     # NEW: MigrationGraphResult, MigrationFreezeResult,
    │                                  # MigrationsCheckResult
    ├── graph.py                      # NEW: parses Alembic-style migration files, checks
    │                                  # soundness (research.md D3)
    └── frozen.py                     # NEW: migrations_frozen port (research.md D3)

engine/tests/fixtures/migrations/
├── sound/{0001_initial.py, 0002_add_table.py, 0003_add_column.py}
├── forked/{0001_initial.py, 0002a_branch_a.py, 0002b_branch_b.py}
├── cyclical/{0001_a.py, 0002_b.py}
├── deploy-dev-intact.yml
└── deploy-dev-altered.yml

engine/tests/unit/
├── test_gate_release_mode.py          # release-gate: reused checks + stage_regression,
│                                        # all four acceptance scenarios
├── test_migrations_graph.py           # sound/forked/cyclical chain tests
├── test_migrations_frozen.py          # intact/missing/altered workflow-file tests
└── test_quality_gate_completion_cli.py  # CLI-level: exit codes, --format json|text, both commands
```

**Structure Decision**: `release-gate` extends the existing `gate/`
subpackage in place (same module, same `GateResult` type — research.md
D1/D2); `migrations/` is a new, self-contained subpackage, matching the
"one subpackage per command group" convention every prior feature has
followed (most recently `rollback/` in specs/011, `tests_inventory/` in
specs/012).

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
