# Implementation Plan: Cut-Time Open-Release Guard

**Branch**: `018-cut-time-open-release-guard` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/018-cut-time-open-release-guard/spec.md`

## Summary

`release cut` gains a new, explicit, optional `other_manifests` input
representing every other already-known manifest for the same service
repo. Before any git branch operation, the cut refuses — a new,
specifically-named `CutReason` — when any of those manifests shares the
same `repo` but a different `release_id` and has a status that isn't yet
`finalised`, `aborted`, or `failed` (Confluence Reference 2 §3.4,
review comment C11). Omitted or empty, behavior is unchanged. A new CLI
option (`--other-manifests`, comma-separated paths, matching this
codebase's existing multi-value-input convention) exercises it
end-to-end.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: stdlib only (`json`, `pathlib`) — no new
third-party dependency

**Storage**: N/A — reads local manifest files already on disk, supplied
explicitly; no storage of its own

**Testing**: `pytest`, real local git fixtures (no mocking)

**Target Platform**: Linux CI runner / local developer machine

**Project Type**: CLI library (`radic-delivery` Typer app, `engine/`)

**Performance Goals**: N/A — a short list scan per cut invocation

**Constraints**: No GCP, Docker, or live Jira/GitHub/delivery-records
call anywhere in this feature

**Scale/Scope**: One new guard clause in `cut.py`, one new `CutReason`
value, one new CLI option — no new module

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Centralise Implementation, Decentralise Configuration)**:
  PASS — the guard logic lives entirely in `engine/`; discovering the
  actual set of other manifests remains the calling workflow's job.
- **Principle III (Fail-Closed Quality Gates, Zero Skip Budget)**: PASS —
  an open conflicting release is a specifically-named refusal, never a
  silent allow.
- **Principle VII (No Arbitrary Commands in Configuration)**: PASS — no
  new descriptor-driven command execution.
- **Principle XII (Engine CLI is the only path to GCP)**: N/A — no GCP
  call in this feature.
- **No violation requiring the Complexity Tracking table.**

## Project Structure

### Documentation (this feature)

```text
specs/018-cut-time-open-release-guard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md             # /speckit-tasks — not yet created
```

### Source Code (repository root)

```text
engine/src/radic_delivery/release/
├── cut.py                # EDIT: new other_manifests param + guard
└── result.py              # EDIT: new CutReason value

engine/src/radic_delivery/
└── cli.py                 # EDIT: release cut gains --other-manifests

engine/tests/unit/
└── test_release_cut.py    # EDIT: new guard tests (reuses existing fixture style)
```

**Structure Decision**: single project (unchanged `engine/` CLI library
structure) — edits to two existing release-package files and the CLI, no
new module.

## Complexity Tracking

*No constitution violations — table not needed.*
