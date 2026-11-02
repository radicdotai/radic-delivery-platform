# Implementation Plan: Release Pipeline Completion

**Branch**: `011-release-pipeline-completion` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-release-pipeline-completion/spec.md`

## Summary

Adds three related commands, bundled into one feature per the project's
explicit request to combine small, related slices and reduce per-feature
process overhead: `radic-delivery release verify-promotion` (three
independent, real local-git facts — ancestry, tree, tag — plus an
always-`not_available` Cloud-Deploy-digest fact), `radic-delivery release
finalise` (fast-forwards `main` to a finalised release's head, creates a
real semver tag, updates the manifest to `status: "finalised"`), and
`radic-delivery rollback plan` (a pure computation over fully explicit
input, performing no action). All three extend specs/009's `release/`
subpackage and its `git_history.py` module rather than introducing new
infrastructure.

## Technical Context

**Language/Version**: Python 3.11 (same `engine/` package, extended again)

**Primary Dependencies**: none new — more real `git` subprocess calls via
the existing `release/git_history.py` pattern; `rollback plan` has no
dependency at all (pure computation over explicit input)

**Storage**: `verify-promotion` and `finalise` read (and `finalise`
rewrites in place) the same local manifest file convention specs/008/009
already established; `rollback plan` reads and writes nothing

**Testing**: `pytest` — like specs/009, every git-touching behaviour is
exercised against a real local git repository (real commits, branches,
and tags) rather than mocked; `rollback plan`'s tests are pure function
calls over inline fixtures, the simplest of the three

**Target Platform**: developer workstation and GitHub-hosted Actions
runners; no server, no long-running process

**Project Type**: single CLI tool, unchanged — extends the existing
`release/` subpackage; adds a new `rollback/` subpackage for `rollback
plan` (a distinct top-level command group per Reference 3, not nested
under `release`)

**Performance Goals**: not applicable — a handful of git operations and
one pure computation, each over a small amount of data

**Constraints**: zero external network call in any of the three commands
(FR-008); `verify-promotion`'s Cloud-Deploy-digest fact is always
`not_available`, regardless of whether `--cd-release` was supplied —
accepted for contract compatibility only, the same "accept the flag,
don't fake the behaviour" precedent specs/003 set for its own
not-yet-implemented inputs; `finalise` refuses rather than forces a
non-fast-forward move (FR-005); `rollback plan` performs no action at all
(FR-006)

**Scale/Scope**: two commands added to the existing `release` group
(`verify-promotion`, `finalise` — `release` now has no stubs left except
nothing, since `propose`/`cut`/`command` are already real and this
feature completes the group), one new command group (`rollback`, with
`plan` as its one real subcommand), ~4 new/extended engine modules, one
new git-fixture test file per command

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise Implementation, Decentralise Configuration | The ancestry/tree/tag verification logic, the fast-forward+tag logic, and the rollback-plan shape all live once in the engine | PASS |
| II. Build Once, Promote the Verified Digest | `verify-promotion` is a direct implementation of this principle's own enforcement mechanism — confirming what's promoted is exactly what was built, by digest and by git fact, never a mutable tag | PASS |
| III. Fail-Closed Quality Gates, Zero Skip Budget | `verify-promotion` reports each fact distinctly rather than a single pass that could mask one failing check (FR-001); `finalise` refuses on any mismatch rather than proceeding optimistically | PASS |
| IV. Keyless, Separated-Duty Identity | Not applicable — no GCP identity; `finalise`'s "bot only" restriction is a calling-workflow identity concern, not this command's (spec Assumptions) | PASS (N/A) |
| V. Human-and-Machine Approval for Production | Not applicable to this feature's own scope — approval already happened before `finalise` runs (it consumes an already-`prod-deployed` manifest); this feature doesn't gate an approval itself | PASS (N/A) |
| VI. Terraform and Cloud Deploy Ownership Boundary | Not applicable | PASS (N/A) |
| VII. No Arbitrary Commands in Configuration | Every git operation across all three commands is a fixed, parameterised query or action (ancestry check, tree comparison, tag read/create, fast-forward-only merge) — never a caller-suppliable command string | PASS |
| VIII. The Bot Proposes, People Decide | Not applicable — these commands execute already-decided outcomes (an approved promotion, a succeeded release), they don't themselves decide anything | PASS (N/A) |
| IX. Parity Before Strictness | Not applicable — these are one-shot verifications/actions, no phased rollout | PASS (N/A) |
| X. Specification and Release Traceability | `finalise` is the manifest's last real status transition this platform's CLI drives (`prod-deployed` → `finalised`), closing the traceability chain specs/008/009 began | PASS |
| XI. Layered, Escalating Security Scanning | Not applicable — no build, image, or scan artifact | PASS (N/A) |
| XII. The Engine CLI Is the Only Path to GCP | Reconfirmed: zero `gcloud`/GCP SDK calls in any of the three commands; the one piece that would need one (`--cd-release`'s digest check) is explicitly not implemented, not worked around | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/011-release-pipeline-completion/
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
├── cli.py                           # MODIFIED: add `release verify-promotion`/`finalise` to the
│                                       # existing `release_app` (removing both from
│                                       # `_RELEASE_NOT_IMPLEMENTED`); replace the `rollback` stub
│                                       # with a real `rollback_app` group (`plan` subcommand)
├── release/
│   ├── result.py                     # MODIFIED: add `PromotionVerification`, `FinaliseResult`
│   ├── git_history.py                # MODIFIED: add `tree_sha`, `is_ancestor`, `tag_exists_at`,
│   │                                   # `list_version_tags`, `create_tag`, `fast_forward_branch`
│   │                                   # (research.md D1)
│   ├── verify_promotion.py            # NEW: ancestry/tree/tag checks against a release's own
│   │                                   # recorded manifest (research.md D2)
│   └── finalise.py                    # NEW: validate manifest status, fast-forward + tag,
│                                        # update manifest to "finalised" (research.md D3)
└── rollback/
    ├── __init__.py
    ├── result.py                      # RollbackPlan dataclass
    └── planner.py                     # pure: explicit inputs -> RollbackPlan (research.md D4)

engine/tests/unit/
├── test_release_verify_promotion.py   # real git fixture: ancestry/tree/tag checks, each failure
│                                        # mode independently
├── test_release_finalise.py           # real git fixture: successful finalise, already-finalised
│                                        # refusal, non-fast-forward refusal
├── test_rollback_planner.py           # pure: RollbackPlan construction
└── test_release_pipeline_completion_cli.py  # CLI-level: exit codes, --format json|text, for
                                               # all three commands
```

**Structure Decision**: `verify-promotion` and `finalise` extend the
existing `release/` subpackage (same module-per-concern shape as
`candidates.py`/`selector.py`/`manifest.py`/`cut.py`); `rollback plan`
gets its own small subpackage since `rollback` is a distinct top-level
command group per Reference 3's own CLI table, not a `release`
subcommand — matching the same "one subpackage per command group"
convention every prior feature has followed.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
