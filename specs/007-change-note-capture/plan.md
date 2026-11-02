# Implementation Plan: Change-Note Record Capture and Release-Note Gate

**Branch**: `007-change-note-capture` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-change-note-capture/spec.md`

## Summary

Add a new `notes` command group with two real subcommands: `notes write`,
which constructs a change-note record from fully-explicit CLI inputs,
validates it against a tightened `schemas/change-note.schema.json`, and
writes it to a local path (the real `gs://radicai-release-records/...`
upload is reported `not_available`, never attempted or faked); and `notes
check`, which reads a PR body from a file and classifies it as having a
Jira reference, an explicit `Jira: None` opt-out, or neither — warning by
default, blocking only when `--require-jira-key` is passed, implementing
this platform's report-only-before-blocking rollout discipline for this
one specific gate. This feature also tightens
`schemas/change-note.schema.json` from feature 001's intentionally loose
placeholder to the architecture's fully-specified shape, since this is the
first feature to actually validate against it.

## Technical Context

**Language/Version**: Python 3.11 (same `engine/` package, extended again)

**Primary Dependencies**: `jsonschema` (already present, reused exactly as
`descriptor/validator.py` already uses it — `Draft202012Validator` +
`iter_errors`), `pyyaml` not needed (records are JSON, not YAML)

**Storage**: a local file per change-note record, written under a path
this command controls (not the real `gs://radicai-release-records/...`
bucket — no credentials for it exist in this environment, and the upload
is reported `not_available` rather than attempted or silently skipped)

**Testing**: `pytest` — `notes write`'s construction+validation logic is
pure (a dict of explicit inputs in, a validated record or specific
rejection out) and fully unit-testable with no fixture beyond inline
literals; the local file write is a real, unmocked filesystem operation
exercised in `tmp_path`; `notes check`'s PR-body classification is pure
text parsing against inline fixture strings, the same simplicity as
feature 005's grammar tests

**Target Platform**: developer workstation and GitHub-hosted Actions
runners; no server, no long-running process

**Project Type**: single CLI tool, unchanged — replaces the `notes`
not-implemented stub with a new subpackage

**Performance Goals**: not applicable — schema validation and text parsing
over small inputs

**Constraints**: zero GitHub API call (FR-010 — every input to `notes
write` is explicit; no PR title/body/author is fetched by this feature);
PR body text is read only from `--pr-body-file`, never a raw CLI text
argument (FR-005, same script-injection-avoidance discipline as feature
005's `--comment-file`); the real cloud-storage upload is out of scope and
reported honestly, not faked (FR-004)

**Scale/Scope**: one new command group (`notes`, two real subcommands),
~5 new engine modules, one schema file tightened (not replaced — its
`$id`/title stay the same), zero new sample-repo fixtures (inline
literals and small PR-body text fixtures suffice)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise Implementation, Decentralise Configuration | Replaces whatever ad hoc per-repo "capture scripts" exist today with one centrally-defined record shape and one centrally-defined completeness check | PASS |
| II. Build Once, Promote the Verified Digest | Not applicable — no image or digest involved | PASS (N/A) |
| III. Fail-Closed Quality Gates, Zero Skip Budget | Not directly applicable (no test-skip concept); this feature's own fail-closed posture is FR-002: an invalid record is rejected and never written, never partially written | PASS |
| IV. Keyless, Separated-Duty Identity | Not applicable — no GCP identity; this feature calls no external API at all | PASS (N/A) |
| V. Human-and-Machine Approval for Production | Not applicable — no deploy or promotion path | PASS (N/A) |
| VI. Terraform and Cloud Deploy Ownership Boundary | Not applicable | PASS (N/A) |
| VII. No Arbitrary Commands in Configuration | The PR body is read from a file and only ever pattern-matched against a fixed, documented convention — never executed, never interpolated into a shell string (FR-005) | PASS |
| VIII. The Bot Proposes, People Decide | Not applicable — no release bot interaction occurs in this feature | PASS (N/A) |
| IX. Parity Before Strictness | This is a direct, textbook application of this principle: `notes check` is explicitly a warn-then-block staged rollout (User Story 3), the same discipline already used for the CI gate and security scanning | PASS |
| X. Specification and Release Traceability | Traces to spec.md's FRs/SCs; a change-note record is itself a traceability artifact (commit → ticket → release), produced here for the first time | PASS |
| XI. Layered, Escalating Security Scanning | Not applicable — no build, image, or scan artifact exists in this feature | PASS (N/A) |
| XII. The Engine CLI Is the Only Path to GCP | Reconfirmed: zero `gcloud`/GCP SDK calls; this feature also makes zero GitHub API calls, the same "no external call" posture as feature 005 | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/007-change-note-capture/
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
└── change-note.schema.json          # MODIFIED: tightened to the architecture's full shape
                                        # (research.md D1) — $id/title unchanged

engine/src/radic_delivery/
├── cli.py                           # MODIFIED: replace the `notes` stub with a real command group
└── notes/
    ├── __init__.py
    ├── schema_loader.py              # load_change_note_schema() — same pattern as
    │                                   # descriptor/schema_loader.py
    ├── result.py                     # ChangeNoteBuildResult / WriteResult /
    │                                   # ReleaseNoteCheckResult dataclasses, JSON (de)serialisation
    ├── builder.py                    # pure: explicit field inputs -> validated record dict,
    │                                   # or a specific rejection (reuses jsonschema
    │                                   # Draft202012Validator exactly as descriptor/validator.py does)
    ├── writer.py                     # writes a validated record to a local path; reports the
    │                                   # real GCS upload as not_available (never attempted)
    └── check.py                      # pure: PR-body text -> Jira-reference classification,
                                        # then classification + require_jira_key -> ReleaseNoteCheckResult

engine/tests/unit/
├── test_notes_builder.py             # pure construction+validation tests: valid inputs, the
│                                       # Jira "None" escape hatch, each rejection case
├── test_notes_writer.py              # real filesystem write test (tmp_path), not_available
│                                       # upload status always reported
├── test_notes_check.py               # pure PR-body classification tests: has-key, explicit-none,
│                                       # neither, warning vs. blocking mode
└── test_notes_cli.py                 # CLI-level: exit codes, --format json|text
```

**Structure Decision**: a new, self-contained subpackage, following the
same shape as every prior command group (`gate/`, `security/`,
`deploy/`, `release_commands/`) — construction/validation logic, a
thin writer for the one real side effect this feature has (a local file
write), and a separate pure classifier for the second subcommand, wired
into `cli.py` exactly like every other command group.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
