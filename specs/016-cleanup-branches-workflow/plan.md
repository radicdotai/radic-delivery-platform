# Implementation Plan: Cleanup Workflow (branches scope only)

**Branch**: `016-cleanup-branches-workflow` | **Spec**: [spec.md](./spec.md) | **Date**: 2026-11-04

**Input**: Feature specification from `/specs/016-cleanup-branches-workflow/spec.md`

## Summary

This platform's sixth reusable GitHub Actions workflow, `cleanup.yml`
(Reference 2 §3.11), implementing only its `branches` scope — deleting
merged, expired `release/**` branches — bundled with the new, real,
pytest-tested engine command it depends on: `radic-delivery cleanup
branches`. Both are testable entirely with real local git (no GCP, no
Docker, no live GitHub API in the engine command itself); the workflow
pushes the actual remote deletion and is validated statically
(`actionlint`/`zizmor`).

## Technical Context

**Language/Version**: Python 3.11 (`uv`, `typer`), matching every prior
engine feature.
**Primary Dependencies**: `engine/src/radic_delivery/release/git_history.py`
(reused: `is_ancestor`, `commit_timestamp`, `delete_branch`,
`current_branch`; extended with a new branch-listing primitive).
**Testing**: `pytest`, real local git fixtures (no mocking), matching
specs/009/011/015's own discipline.
**Target Platform**: CLI (engine) + GitHub Actions reusable workflow
(static validation only — no runner in this sandbox).
**Project Type**: single Python package + workflow YAML, matching every
prior feature.
**Scale/Scope**: one new engine subcommand (`cleanup branches`), one new
reusable workflow file (`cleanup.yml`).

## Constitution Check

- Principle I (centralize logic): all branch-selection/age/protection
  logic lives in the engine; `cleanup.yml` only sequences the one CLI
  call plus the real `git push --delete` steps. PASS.
- Principle VII (no arbitrary commands): the workflow runs a fixed,
  parameterised `radic-delivery cleanup branches` invocation and a fixed
  `git push origin --delete <branch>` per reported deletion — never an
  arbitrary command built from input. PASS.
- Principle XI/XII (engine is the only path to GCP; N/A here): this
  feature makes zero GCP calls anywhere. PASS (trivially — out of scope
  by design, research.md D1).
- No violation requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/016-cleanup-branches-workflow/
├── spec.md
├── checklists/requirements.md
├── research.md
├── data-model.md
├── quickstart.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
engine/src/radic_delivery/
├── cleanup/
│   ├── __init__.py
│   ├── result.py          # CleanupBranchesResult, KeptBranch
│   └── branches.py        # cleanup_branches(...)
├── release/
│   └── git_history.py     # extended: list_branches(repo_dir, pattern)
└── cli.py                 # new cleanup_app, `cleanup branches` command

engine/tests/unit/
└── test_cleanup_branches.py

.github/workflows/
└── cleanup.yml             # new
```

**Structure Decision**: new top-level `cleanup/` subpackage (sibling to
`release/`, `rollback/`, `migrations/`, `tests_inventory/`), matching
every prior feature's own-subpackage-per-domain convention; one shared
primitive (`list_branches`) added to the existing, reused
`release/git_history.py` rather than duplicated.

## Phase 0: Outline & Research

See [research.md](./research.md) — D1 (branches-only scope, `all`
refused), D2 (merged = ancestor of `main`), D3 (14-day retention default,
flagged), D4 (protected-branch exclusion), D5 (local delete + workflow
push), D6 (exit codes), D7 (testing strategy).

## Phase 1: Design & Contracts

See [data-model.md](./data-model.md) (`CleanupBranchesResult`,
`KeptBranch`, CLI surface) and [quickstart.md](./quickstart.md) (full
dry-run/real-run demo plus `actionlint`/`zizmor` validation commands).

No `/contracts/` directory: this feature's only external interface is the
CLI (documented in data-model.md) and the workflow YAML itself (reviewed
directly, validated statically) — consistent with specs/014/015's own
choice not to duplicate workflow-contract documentation into a separate
contracts folder.
