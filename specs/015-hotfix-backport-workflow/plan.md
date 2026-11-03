# Implementation Plan: Hotfix Backport Workflow

**Branch**: `015-hotfix-backport-workflow` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-hotfix-backport-workflow/spec.md`

## Summary

Adds this platform's fifth reusable GitHub Actions workflow,
`hotfix-backport.yml` (Reference 2 §3.8), bundled with a new, small,
genuinely real engine command: `radic-delivery release backport`, which
cherry-picks a succeeded hotfix's already-cut commits back onto `dev`,
continuing past any individually-conflicting commit (never aborting the
whole operation the way `release cut` does) and naming exactly which
commits conflicted. The workflow itself is a single job gated on a
successful `prod` `workflow_run` for a hotfix branch, validated
statically (`actionlint`/`zizmor`) like every prior reusable workflow —
this sandbox has no GitHub Actions runner, live Jira, or live GCP access
to execute it against.

## Technical Context

**Language/Version**: Python 3.11 (the new `backport` command, same
`engine/` package); YAML (the new workflow file)

**Primary Dependencies**: none new — reuses `release/git_history.py`'s
existing `cherry_pick`/`abort_cherry_pick`/`create_branch_from`/
`commit_timestamp` primitives unchanged (specs/009)

**Storage**: `release backport` reads (never writes) a release manifest;
operates entirely on a real local git checkout

**Testing**: `pytest` for `release backport`, mirroring `release cut`'s
own real-git-fixture test style exactly (a clean case, a partial-conflict
case, an all-conflict case); `actionlint`/`zizmor` for the workflow YAML
— no live execution of any kind

**Target Platform**: developer workstation (the engine command) and
GitHub-hosted Actions runners (the workflow, not exercised live here)

**Project Type**: single CLI tool, extended in place (`release/`
subpackage); plus one new reusable workflow file

**Performance Goals**: not applicable — a handful of real git operations

**Constraints**: zero external network call beyond real local git and
the GitHub API needed to open the PR (spec FR-007); a conflicting commit
never aborts the rest of the backport (spec FR-002, SC-001); the PR is
never opened ready-for-review when any commit conflicted (spec FR-006,
SC-004)

**Scale/Scope**: one new engine command (`release backport`), one new
reusable workflow (`hotfix-backport.yml`, one job), one new test file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise Implementation, Decentralise Configuration | The cherry-pick/conflict-handling logic lives once in the engine (`release backport`), reusing `git_history.py`'s existing primitives — not duplicated in workflow shell script | PASS |
| II. Build Once, Promote the Verified Digest | Not applicable — this feature touches no build artifact or digest | PASS (N/A) |
| III. Fail-Closed Quality Gates, Zero Skip Budget | Not applicable in the usual sense — a backport conflict is a reported fact (never silently dropped, FR-003), not a quality gate | PASS (N/A) |
| IV. Keyless, Separated-Duty Identity | Not applicable — no GCP identity in this feature | PASS (N/A) |
| V. Human-and-Machine Approval for Production | Not applicable — this feature runs strictly after prod success, never gates it | PASS (N/A) |
| VI. Terraform and Cloud Deploy Ownership Boundary | Not applicable | PASS (N/A) |
| VII. No Arbitrary Commands in Configuration | Every git operation is a fixed, parameterised call (cherry-pick, abort, branch creation) — never a caller-suppliable command string | PASS |
| VIII. The Bot Proposes, People Decide | A conflicted backport opens a draft PR, never auto-merged — a human resolves the remaining commits by hand | PASS |
| IX. Parity Before Strictness | Not applicable | PASS (N/A) |
| X. Specification and Release Traceability | The backport PR traces directly back to the hotfix's own manifest and its recorded `release_sha` values — no separate, divergent record | PASS |
| XI. Layered, Escalating Security Scanning | Not applicable — no build, image, or scan artifact | PASS (N/A) |
| XII. The Engine CLI Is the Only Path to GCP | Reconfirmed: zero `gcloud`/GCP SDK calls anywhere in this feature | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/015-hotfix-backport-workflow/
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
├── cli.py                           # MODIFIED: add `release backport` to the existing release_app
└── release/
    └── backport.py                   # NEW: BackportResult, backport(manifest, *, repo_dir,
                                       #   into) -> BackportResult (research.md D1-D3)

.github/workflows/hotfix-backport.yml  # NEW: one job, workflow_run-gated (research.md D5)

engine/tests/unit/
└── test_release_backport.py          # every acceptance scenario, real git fixtures
```

**Structure Decision**: `backport.py` is a new sibling module inside the
existing `release/` subpackage (same module-per-concern shape as
`cut.py`/`finalise.py`/`render_pr_body.py`); the workflow file lives at
the fixed repository location this platform's own layout (CLAUDE.md) and
every prior workflow already established.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
