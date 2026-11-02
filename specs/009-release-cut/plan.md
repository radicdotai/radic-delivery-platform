# Implementation Plan: Release Branch Creation and Cherry-Pick

**Branch**: `009-release-cut` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-release-cut/spec.md`

## Summary

Add `radic-delivery release cut`: reads a local draft manifest (specs/008's
`release propose` output), validates it matches the caller's `--release-id`/
`--hotfix` and is still in the `proposed` status, re-verifies every
selected commit still has a local change-note record, then — for real,
against a real local git checkout — creates `release/<id>` from the
current tip of `main` and cherry-picks every selected commit onto it in
the order the commits actually occurred. Any cherry-pick conflict aborts
the whole operation and removes the attempted branch; nothing is left
half-done. On success, the manifest is updated in place: `release_branch`,
`release_head`, each commit's `release_sha`, and `status: "cut"`.
`--dry-run` validates and resolves everything (including the pending
commit order) without touching the repository or the manifest.

## Technical Context

**Language/Version**: Python 3.11 (same `engine/` package, extended again
— this feature adds to the existing `release/` subpackage from specs/008)

**Primary Dependencies**: none new — git operations shell out to the
system `git` binary via `subprocess`, extending specs/008's
`release/git_history.py` with branch/cherry-pick operations rather than
introducing a new dependency

**Storage**: reads and, on success, overwrites the local manifest file at
the path given (the same file specs/008's `release propose` produces);
re-reads local change-note records from the same local layout specs/007/
008 already use. No live Jira/GCS/`delivery-records` call anywhere.

**Testing**: `pytest` — this is the first feature with **no**
external-dependency boundary at all (unlike specs/005-008, each of which
had to draw one): every behaviour, including the conflict-abort path, is
exercised against a real local git repository built in `tmp_path` with
real `git branch`/`git cherry-pick` calls — a repository with a
deliberately diverging `main` and a cherry-picked commit crafted to
conflict with it, not mocked

**Target Platform**: developer workstation and GitHub-hosted Actions
runners; no server, no long-running process

**Project Type**: single CLI tool, unchanged — extends specs/008's
`release/` subpackage rather than adding a new one

**Performance Goals**: not applicable — a handful of git operations over
a small commit set

**Constraints**: zero GitHub/GCP/Jira call of any kind (FR-009); the
branch is only ever created from the fixed, literal production line
(`main`), never a caller-suppliable arbitrary ref (FR-004, Principle VII);
commit order is always the commits' actual chronological order, never
caller-specified (FR-005); a failed cut leaves no trace in the repository
(FR-006) or the manifest (FR-007)

**Scale/Scope**: one new command (`release cut`, replacing its stub
alongside the still-unimplemented `verify-promotion`/`finalise`), one new
engine module (`release/cut.py`) plus additions to the existing
`release/git_history.py` and `release/result.py`, one new git-conflict
fixture test file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise Implementation, Decentralise Configuration | The cherry-pick ordering and conflict-handling logic lives once in the engine; no service repo or workflow reimplements it | PASS |
| II. Build Once, Promote the Verified Digest | Not applicable — no image or digest is built here | PASS (N/A) |
| III. Fail-Closed Quality Gates, Zero Skip Budget | This feature's own fail-closed posture: a missing change-note record or a mismatched manifest stops the cut before anything is touched, never proceeds on an assumption (FR-003) | PASS |
| IV. Keyless, Separated-Duty Identity | Not applicable — no GCP identity; this feature calls no external API of any kind | PASS (N/A) |
| V. Human-and-Machine Approval for Production | Not applicable — cutting a branch is not a deploy or promotion path; no approval gate is this feature's concern | PASS (N/A) |
| VI. Terraform and Cloud Deploy Ownership Boundary | Not applicable | PASS (N/A) |
| VII. No Arbitrary Commands in Configuration | The branch's base (`main`) and the cherry-pick order (strict chronological) are both fixed, never caller-suppliable — the one place this principle most directly applies to a git-manipulating feature | PASS |
| VIII. The Bot Proposes, People Decide | This feature acts only on a manifest a human has already had the chance to review (specs/008's `proposed` status, edited via specs/005-006's `release command` forms) — it never selects or changes what's being cut, only executes the already-decided selection | PASS |
| IX. Parity Before Strictness | Not applicable — a one-shot git operation, no phased rollout | PASS (N/A) |
| X. Specification and Release Traceability | This feature produces the manifest's first `cut`-status transition, with real `release_sha`/`release_branch`/`release_head` values traceable back to the exact commits approved | PASS |
| XI. Layered, Escalating Security Scanning | Not applicable — no build, image, or scan artifact | PASS (N/A) |
| XII. The Engine CLI Is the Only Path to GCP | Reconfirmed: zero `gcloud`/GCP SDK calls; zero GitHub API calls — this feature only touches a local git checkout and a local file | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/009-release-cut/
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
├── cli.py                           # MODIFIED: add `release cut` to the existing `release_app`;
│                                       # remove "cut" from `_RELEASE_NOT_IMPLEMENTED`
└── release/
    ├── result.py                     # MODIFIED: add `CutResult`
    ├── git_history.py                # MODIFIED: add `commit_timestamp`, `current_branch`,
    │                                   # `create_branch_from`, `checkout`, `cherry_pick`,
    │                                   # `abort_cherry_pick`, `delete_branch` (research.md D1)
    └── cut.py                        # NEW: orchestrates validation, change-note re-verification,
                                         # chronological ordering, branch creation, cherry-picking,
                                         # conflict rollback, and manifest update -> CutResult

engine/tests/unit/
├── test_release_cut_git_history.py   # real git fixture: new git_history.py operations
├── test_release_cut.py               # real git fixture: full cut() orchestration, including the
│                                       # deliberate-conflict abort path and missing-change-note-record check
└── test_release_cut_cli.py           # CLI-level: exit codes, --dry-run, --format json|text
```

**Structure Decision**: extends specs/008's existing `release/` subpackage
with one new module (`cut.py`) rather than a new subpackage, continuing
the same "pure orchestration + real git subprocess helpers" split
`git_history.py`/`selector.py`/`manifest.py` already established.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
