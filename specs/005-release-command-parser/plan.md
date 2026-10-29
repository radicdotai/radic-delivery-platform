# Implementation Plan: Release Slash-Command Parser and Authorization Check

**Branch**: `005-release-command-parser` | **Date**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-release-command-parser/spec.md`

## Summary

Add one real subcommand, `radic-delivery release command`, to a new
`release` command group: it reads a PR comment's first line from stdin (or
a file, for convenience), classifies it against the architecture's fixed
six-form grammar, and — for a syntactically valid form — checks the
author against explicitly-supplied release-managers/Tech-Lead identity
before reporting an accepted/unauthorized/malformed/not-a-command result.
Pure text classification: no filesystem access beyond reading its input, no
subprocess, no network, no GCP call. Every other `release` subcommand
(`propose`, `cut`, `verify-promotion`, `finalise`) remains unimplemented.

## Technical Context

**Language/Version**: Python 3.11 (same `engine/` package, extended again)

**Primary Dependencies**: none new — this feature is pure standard-library
regex/string logic, no YAML/subprocess/GCP dependency at all (the first
engine feature with zero external tool or filesystem dependency beyond
reading the descriptor-free input it's given)

**Storage**: none

**Testing**: `pytest` only — every test is a pure function call with string
input and a structured result, no fixture files, no subprocess, no
`tmp_path`. This is the simplest test surface of any feature so far.

**Target Platform**: developer workstation and GitHub-hosted Actions
runners; no server, no long-running process

**Project Type**: single CLI tool, unchanged — adds one new subpackage

**Performance Goals**: not applicable — a handful of regex matches against
one short line of text

**Constraints**: zero GCP SDK or `gcloud` call; zero GitHub API call; team
membership and Tech Lead identity are supplied as explicit CLI input, never
looked up by this feature (research.md D1); the comment body is read from
stdin or a file, never accepted as a raw command-line argument, specifically
to avoid the well-known GitHub Actions pitfall of interpolating untrusted
`${{ github.event.comment.body }}` content directly into a shell command
(research.md D4 — directly relevant to Principle VII even though this
feature doesn't build the workflow that would make that mistake)

**Scale/Scope**: one new command group (`release`, with `command` as its
one real subcommand), ~3 new engine modules, zero new fixture files (all
tests use inline string literals)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise implementation, decentralise configuration | One centrally defined grammar and authorization rule, not reimplemented per service repo or per workflow | PASS |
| II. Build once, promote by digest | Not applicable — no build or image involved | PASS (N/A) |
| III. Fail-closed, zero skip budget | Not directly applicable (no test-skip concept here), but the feature's own default is fail-closed in spirit: anything not an exact grammar match is rejected, never guessed at or partially honoured | PASS |
| IV. Keyless, separated-duty identity | Not applicable — no GCP identity; the human "identity" inputs (author, release-managers, Tech Lead) are supplied explicitly by the caller, never minted or looked up here | PASS (N/A) |
| V. Human + machine approval for prod | Not applicable — this is a comment-classification step, not a deploy or promotion path | PASS (N/A) |
| VI. Terraform/Cloud Deploy ownership boundary | Not applicable | PASS (N/A) |
| VII. No arbitrary commands in configuration | This feature is a direct, new application of this principle to free-text human input: exactly six fixed forms are ever recognized, nothing else, no matter what text is supplied — and the comment body is deliberately never passed as a raw shell argument (research.md D4) | PASS |
| VIII. Bot proposes, people decide | This feature is the mechanism by which a *person's* instruction (not the bot's) is recognized and authorized — consistent with the principle's spirit that people, not automation, decide what a release contains | PASS |
| IX. Parity before strictness | Not applicable — no phased rollout concept here; this is a binary classification, same precedent as specs/004's deploy lint | PASS |
| X. Specification and release traceability | Traces to spec.md's FRs/SCs; this feature deliberately produces no release-manifest side effect yet (FR-011), which is the correctly scoped slice | PASS |
| XI. Layered security scanning | Not applicable — no build or scan artifact exists in this feature | PASS (N/A) |
| XII. Engine CLI is the only path to GCP | Reconfirmed: zero `gcloud`/GCP SDK calls; also zero GitHub API calls, the strictest "no external call" feature so far | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/005-release-command-parser/
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
├── cli.py                           # MODIFIED: add a new `release` command group (command only)
└── release_commands/
    ├── __init__.py
    ├── grammar.py                     # pure: one stripped first-line string -> ParsedCommand
    ├── authorization.py               # pure: ParsedCommand + author/team/tech_lead -> CommandCheckResult
    └── result.py                      # ParsedCommand / CommandCheckResult dataclasses, JSON (de)serialisation

engine/tests/unit/
├── test_release_grammar.py           # pure grammar tests: all 6 forms, case-insensitivity, malformed
│                                       # shapes, "not a command", first-line-only, whitespace tolerance
├── test_release_authorization.py     # pure authorization tests: team membership, Tech-Lead-only rule
└── test_release_cli.py               # CLI-level: stdin/file input, exit codes, --format json|text
```

**Note on package naming**: the subpackage is `release_commands` (plural,
with an underscore) rather than `release`, to avoid shadowing the `release`
name already used for the CLI's command-group registration in `cli.py` and
to leave room for a future `release` subpackage covering `propose`/`cut`/
`verify-promotion`/`finalise` without a rename collision.

**Structure Decision**: a new, intentionally small subpackage — this is the
first engine feature with no filesystem/subprocess dependency at all, so it
needs none of `gate`/`security`/`deploy`'s runner/tools-selection
machinery. No existing module is reused because none of the prior features'
logic (YAML parsing, subprocess execution, descriptor validation) applies
here.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
