# Implementation Plan: Prereqs and Depends-On Tracking and Enforcement

**Branch**: `019-prereqs-depends-on` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-prereqs-depends-on/spec.md`

## Summary

Adds `prereqs`/`depends_on` fields to the change-note schema, a pure
parser for a PR body's `Prereqs:` checklist and `Depends-on:` trailer,
and wires the parsed data through three consumers: `notes.builder`
(computes both fields from a supplied PR body, never free input — the
same discipline specs/017's migration flag established), `release cut`
(a new confirming guard, refuse-only per the spec's scope correction),
and both `render_pr_body` (a new PR-body section) and `gate evaluate
--mode release-gate` (two new checks). All local-git/text-parsing logic;
no GCP, Docker, or live Jira/GitHub call anywhere.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: stdlib only (`re`, `json`, `pathlib`) — no new
third-party dependency

**Storage**: N/A — reads local change-note/manifest files and PR-body
text already on disk or supplied explicitly

**Testing**: `pytest`, real local git fixtures and real PR-body text
fixtures (no mocking)

**Target Platform**: Linux CI runner / local developer machine

**Project Type**: CLI library (`radic-delivery` Typer app, `engine/`)

**Performance Goals**: N/A — short text parses and list scans per
invocation

**Constraints**: No GCP, Docker, or live Jira/GitHub/delivery-records
call anywhere in this feature

**Scale/Scope**: One new parser module; edits to `notes/builder.py`,
`release/cut.py`, `release/result.py`, `release/render_pr_body.py`,
`gate/evaluator.py`, `gate/result.py`, `schemas/change-note.schema.json`,
and `cli.py`'s `notes write`, `release cut`, `gate evaluate` commands —
no new CLI command group

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I**: PASS — all logic centralized in `engine/`; the
  known-in-production set remains an explicit, calling-workflow-supplied
  input, not a forked per-repo mechanism.
- **Principle III (Fail-Closed Quality Gates)**: PASS — both new
  release-gate checks fail specifically and by name; neither can be
  silently skipped (no new skip-exception path is introduced).
- **Principle VII (No Arbitrary Commands in Configuration)**: PASS — pure
  text parsing of a fixed, documented format; no command execution of any
  kind is derived from PR body text.
- **Principle X (Traceability)**: PASS — every Prereqs/Depends-on fact
  traces directly to the PR body text it was parsed from, carried
  unchanged onto the change-note record.
- **No violation requiring the Complexity Tracking table.**

## Project Structure

### Documentation (this feature)

```text
specs/019-prereqs-depends-on/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md             # /speckit-tasks — not yet created
```

### Source Code (repository root)

```text
schemas/
└── change-note.schema.json          # EDIT: add prereqs, depends_on

engine/src/radic_delivery/notes/
├── pr_body_fields.py                 # NEW: parse_prereqs(), parse_depends_on()
├── builder.py                        # EDIT: build_record() accepts pr_body
└── result.py                         # (unchanged — no new result dataclass needed here)

engine/src/radic_delivery/release/
├── cut.py                            # EDIT: new depends_on confirming guard
├── result.py                         # EDIT: new CutReason "unmet_dependency"
└── render_pr_body.py                 # EDIT: new Prereqs/Depends-on section

engine/src/radic_delivery/gate/
├── evaluator.py                      # EDIT: two new release-gate checks
└── result.py                         # EDIT: two new CheckName values

engine/src/radic_delivery/
└── cli.py                            # EDIT: notes write, release cut, gate evaluate

engine/tests/unit/
├── test_notes_pr_body_fields.py      # NEW
├── test_notes_builder.py             # EDIT
├── test_release_cut.py               # EDIT
├── test_release_cut_cli.py           # EDIT
├── test_release_render_pr_body.py    # EDIT
├── test_gate_release_mode.py         # EDIT (release-gate-specific tests live here, specs/013)
└── test_gate_cli.py                  # EDIT
```

**Structure Decision**: single project (unchanged `engine/` CLI library
structure) — one new parser module, edits to five existing modules plus
the CLI, no new top-level package.

## Complexity Tracking

*No constitution violations — table not needed.*
