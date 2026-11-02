# Implementation Plan: Test-Result Record Capture

**Branch**: `010-test-result-capture` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-test-result-capture/spec.md`

## Summary

Add `radic-delivery records put-test-result`: reads a complete test-result
record from a file, validates it against a now-corrected `schemas/
test-result.schema.json` (including the zero-skip-budget rule and the
stage-environment completeness rule, both expressed as schema-level
conditionals), cross-checks the record's own `release_id` against the
caller's `--release-id` when both are present, and — on success — stores
it locally, mirroring the real `releases/<id>/test-results/<environment>-
<repo>-<suite>.json` key structure exactly (a release-less dev record is
stored under a fixed `dev` segment instead). This is the third and last
of feature 001's intentionally loose placeholder schemas to be corrected
and given its first real consumer, after `change-note.schema.json`
(specs/007) and `release-manifest.schema.json` (specs/008).

## Technical Context

**Language/Version**: Python 3.11 (same `engine/` package, extended again)

**Primary Dependencies**: `jsonschema` (already present, same
`Draft202012Validator` pattern as `descriptor/validator.py`, specs/007's
`notes/builder.py`, and specs/008's `release/manifest.py`) — no new
dependency

**Storage**: reads a local file (`--file PATH`); on success, writes a
local file mirroring the real `releases/.../test-results/...` key
structure under a local root (`--out-dir`) — the real
`radicdotai/delivery-records` upload is out of scope, reported
`not_available` (spec FR-009), the same precedent as specs/007's `notes
write`

**Testing**: `pytest` — this has no real external dependency to exercise
or fake at all (like specs/007, specs/009): real local file reads/writes,
real schema validation, inline record fixtures for every conditional rule

**Target Platform**: developer workstation and GitHub-hosted Actions
runners; no server, no long-running process

**Project Type**: single CLI tool, unchanged — adds a new `records/`
subpackage, replacing the `records` not-implemented stub

**Performance Goals**: not applicable — one schema validation over one
small JSON document

**Constraints**: zero external network call of any kind (FR-010); never
claims the real upload happened (FR-009); a record is rejected, and
nothing is stored, on any validation failure (FR-002) — no partial write

**Scale/Scope**: one new command group (`records`, with `put-test-result`
as its one real subcommand), ~4 new engine modules, one schema file
substantially corrected (not replaced — `$id`/`title` unchanged)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise Implementation, Decentralise Configuration | The record's validation rules (skip-budget, stage-completeness) live once in the engine's schema + command, not reimplemented per service repo's CI | PASS |
| II. Build Once, Promote the Verified Digest | Not applicable — no image or digest is built here; the record's `digest`/`cloud_deploy` fields are trusted input, never independently verified (FR-010) | PASS (N/A) |
| III. Fail-Closed Quality Gates, Zero Skip Budget | This feature is a direct, schema-level enforcement of this exact principle: a skipped test can never be paired with an overall passing result (FR-006, User Story 2) | PASS |
| IV. Keyless, Separated-Duty Identity | Not applicable — no GCP identity; this feature calls no external API of any kind | PASS (N/A) |
| V. Human-and-Machine Approval for Production | Not applicable — this is a record-capture step, not a deploy or approval path | PASS (N/A) |
| VI. Terraform and Cloud Deploy Ownership Boundary | Not applicable | PASS (N/A) |
| VII. No Arbitrary Commands in Configuration | Not directly applicable — no command construction happens in this feature at all | PASS (N/A) |
| VIII. The Bot Proposes, People Decide | Not applicable — no release bot interaction occurs in this feature | PASS (N/A) |
| IX. Parity Before Strictness | Not applicable — this is a one-shot validation, no phased rollout | PASS (N/A) |
| X. Specification and Release Traceability | This feature produces the test-result record a future release-gate feature will read (Technical Design already documents this dependency, the same kind specs/008 already found and recorded for change-note records) | PASS |
| XI. Layered, Escalating Security Scanning | Not applicable — no build, image, or scan artifact | PASS (N/A) |
| XII. The Engine CLI Is the Only Path to GCP | Reconfirmed: zero `gcloud`/GCP SDK calls; zero GitHub API calls — this feature only reads and writes local files | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/010-test-result-capture/
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
schemas/
└── test-result.schema.json          # MODIFIED: corrected per research.md D1 — $id/title unchanged

engine/src/radic_delivery/
├── cli.py                           # MODIFIED: replace the `records` stub with a real command group
└── records/
    ├── __init__.py
    ├── schema_loader.py              # load_test_result_schema() — same pattern as the other
    │                                   # schema_loader.py modules
    ├── result.py                     # PutResult / RecordIssue dataclasses, JSON (de)serialisation
    ├── validator.py                  # pure: record dict + optional --release-id -> validation
    │                                   # issues (schema + the release-id cross-check, FR-007)
    └── writer.py                     # writes a validated record to the local mirrored path
                                        # (research.md D2); always reports not_available upload

engine/tests/unit/
├── test_records_validator.py         # pure validation tests: every conditional rule, the
│                                       # release-id cross-check, ordinary field-shape rejections
├── test_records_writer.py            # real filesystem write test (tmp_path): the mirrored path,
│                                       # including the release-less dev case
└── test_records_cli.py               # CLI-level: exit codes, --format json|text
```

**Structure Decision**: a new, self-contained subpackage, following the
same "validate, then write" shape as specs/007's `notes/` subpackage —
this feature reads a complete record from a file rather than building one
from explicit CLI fields (research.md D3's rationale), so there is no
`builder.py` analogue, only a pure `validator.py`.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
