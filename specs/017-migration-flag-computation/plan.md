# Implementation Plan: Migration Flag Computation

**Branch**: `017-migration-flag-computation` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-migration-flag-computation/spec.md`

## Summary

Replace the free-form, caller-supplied `migration` boolean on the
change-note record with a value computed automatically from a real git
diff — `none`, `expand`, or `contract` — per Confluence Reference 3 §2
(C4). A new `notes/migration_flag.py` module reuses the existing
`release/git_history.py` diffing infrastructure (extended with one new
primitive, `added_paths`, since the existing `changed_paths` doesn't
distinguish additions from modifications/deletions) to find qualifying
added migration files, detects a `# phase: contract` marker (the
resolved, confirmed convention — see research.md D1 for the real
`-- phase: contract` SQL-syntax contradiction this corrects), and reports
the computed value. `notes/builder.py` and the `notes write` CLI command
stop accepting `migration` as free input; `notes/check.py` and the
`notes check` CLI command gain an optional cross-check against a
`Migrations:` line in a PR body, failing closed on a mismatch.

## Technical Context

**Language/Version**: Python 3.11 (matches the rest of `engine/`)

**Primary Dependencies**: `jsonschema` (schema validation, already a
dependency), stdlib `subprocess`/`re`/`pathlib` — no new third-party
dependency

**Storage**: N/A — this feature reads real local git state and a schema
file already on disk; it has no storage of its own

**Testing**: `pytest`, real local git fixtures (no mocking), matching
every prior feature in this repo

**Target Platform**: Linux CI runner / local developer machine (same as
the rest of `engine/`)

**Project Type**: CLI library (`radic-delivery` Typer app, `engine/`)

**Performance Goals**: N/A — a single diff + file-scan per invocation;
no performance-sensitive path

**Constraints**: No GCP, Docker, or live Jira/GitHub API call anywhere in
this feature — pure local git and schema logic (same boundary as every
merged feature to date)

**Scale/Scope**: One new module (~40-60 lines), one new `git_history.py`
primitive, edits to two existing `notes/` modules, one schema field
change, two CLI command surface changes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Centralise Implementation, Decentralise Configuration)**:
  PASS. The computation lives entirely in `engine/`; the only
  per-repo-variable inputs (`legacy_dir`, `phase_header_required`) are
  explicit function parameters a descriptor will supply in a later spec —
  no logic is forked or duplicated per service.
- **Principle II (Build Once, Promote the Verified Digest)**: N/A — this
  feature has no build/promotion surface.
- **Principle III (Fail-Closed Quality Gates, Zero Skip Budget)**: PASS.
  The new PR-body cross-check fails closed on a mismatch (FR-008); when
  the optional declaration line is simply absent, the check passes
  (FR-009) — this is a deliberate "optional cross-check," not a silent
  skip, since the computed value (the actual fact) is unaffected either
  way and always wins (FR-010).
- **Principle VII (No Arbitrary Commands in Configuration)**: PASS — no
  new descriptor-driven command execution of any kind.
- **Principle XII (Engine CLI is the only path to GCP)**: N/A — no GCP
  call in this feature.
- **No violation requiring the Complexity Tracking table.**

## Project Structure

### Documentation (this feature)

```text
specs/017-migration-flag-computation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks — not yet created)
```

### Source Code (repository root)

```text
schemas/
└── change-note.schema.json          # migration: boolean -> enum

engine/src/radic_delivery/
├── notes/
│   ├── migration_flag.py            # NEW: compute()
│   ├── builder.py                   # EDIT: migration becomes computed, not free input
│   └── check.py                     # EDIT: new PR-body migration cross-check
├── release/
│   └── git_history.py               # EDIT: new added_paths() primitive
└── cli.py                           # EDIT: notes write / notes check command surface

engine/tests/
├── fixtures/
│   └── migrations/
│       └── flag_computation/        # NEW: real git fixtures for this feature
└── unit/
    ├── test_notes_migration_flag.py # NEW
    ├── test_notes_builder.py        # EDIT: migration now computed
    ├── test_notes_check.py          # EDIT: new mismatch-check tests
    └── test_notes_cli.py            # EDIT: CLI surface change
```

**Structure Decision**: single project (this is `engine/`'s existing CLI
library structure, unchanged) — a new module alongside the existing
`notes/` package, one new `git_history.py` primitive reused from the
existing `release/` package, no new top-level directories.

## Complexity Tracking

*No constitution violations — table not needed.*
