# Implementation Plan: Release Cut Workflow

**Branch**: `014-release-cut-workflow` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-release-cut-workflow/spec.md`

## Summary

Adds this platform's fourth reusable GitHub Actions workflow,
`release-cut.yml` (Reference 2 §3.4) — the next of 12 after `ci`,
`security`, `release-commands` — bundled with a new, small, genuinely
real engine command the workflow depends on: `radic-delivery release
render-pr-body`, which deterministically renders Reference 3's own
release PR template from an already-produced release manifest and
specs/007's change-note records. The workflow's two jobs (`propose` on
manual dispatch, `cut` on an approving `pull_request_review`) are thin
orchestration over already-real engine commands (`release propose`,
`release cut`, `release render-pr-body`); this sandbox cannot execute
GitHub Actions, Jira, or GCP calls, so the workflow itself is validated
statically (`actionlint`/`zizmor`), the same bar every prior reusable
workflow in this platform was already built to.

## Technical Context

**Language/Version**: Python 3.11 (the new `render-pr-body` command,
same `engine/` package); YAML (the new workflow + updated caller
template)

**Primary Dependencies**: none new in the engine — reuses
`release/git_history.py` (extended with one new primitive) and reads
specs/007's change-note records and specs/008's release-manifest shape
directly; the workflow itself uses `gh`/`curl`/`jq`, the same tools
every prior reusable workflow already uses

**Storage**: `render-pr-body` reads (never writes) a release manifest and
change-note record files; the workflow reads/writes GitHub PR state via
the GitHub API (through the already-established delivery-bot App token
pattern `release-commands.yml` already uses)

**Testing**: `pytest` for `render-pr-body` (hand-built manifest/
change-note fixtures covering every acceptance scenario, a determinism
test, and a real git fixture for the deploy-files-changed computation);
`actionlint`/`zizmor` for the workflow YAML — no live execution of any
kind, the same boundary `ci.yml`/`security.yml`/`release-commands.yml`
already accepted

**Target Platform**: developer workstation (the engine command) and
GitHub-hosted Actions runners (the workflow, once this platform actually
triggers it from a real service repo — not exercised live here)

**Project Type**: single CLI tool, extended in place (`release/`
subpackage); plus one new top-level reusable workflow file and an update
to an existing caller template

**Performance Goals**: not applicable — one deterministic rendering pass
and a handful of real GitHub/Jira API calls per workflow run

**Constraints**: zero database/Cloud-Deploy call anywhere in this
feature (spec FR-008); rendering is 100% deterministic (spec FR-003,
SC-002); the cut job never runs `release cut` without first confirming
the approving reviewer isn't the initiator and the non-Jira-PR gate is
satisfied (spec FR-006, FR-007); automatic re-propose-after-edit and
automatic dev-green-failed/migrations-chain resolution are explicitly
out of scope (spec Assumptions, research.md D2/D3)

**Scale/Scope**: one new engine command (`release render-pr-body`), one
new `git_history.py` primitive (`changed_paths`), one new reusable
workflow (`release-cut.yml`, two jobs), one updated caller template
(`templates/callers/release.yml`, two new jobs added), two new test
files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise Implementation, Decentralise Configuration | PR-body rendering — the one piece of non-trivial logic this feature introduces — lives once in the engine (`render-pr-body`), not duplicated as inline workflow shell/template logic (research.md D2) | PASS |
| II. Build Once, Promote the Verified Digest | Not applicable — this feature touches no build artifact or digest | PASS (N/A) |
| III. Fail-Closed Quality Gates, Zero Skip Budget | The cut job refuses outright (never a partial or best-effort cut) when the non-Jira-PR gate isn't satisfied, naming why (spec FR-007) | PASS |
| IV. Keyless, Separated-Duty Identity | The cut job's own approval check (reviewer ≠ initiator) is this feature's version of separated-duty identity for the release-PR approval step itself | PASS |
| V. Human-and-Machine Approval for Production | Not applicable to this feature's own scope — this is the release-PR approval step, upstream of prod approval (`promote`), not prod approval itself | PASS (N/A) |
| VI. Terraform and Cloud Deploy Ownership Boundary | Not applicable | PASS (N/A) |
| VII. No Arbitrary Commands in Configuration | Every workflow step is a fixed, named operation (a specific `gh`/`curl`/`jq` invocation or an engine CLI call with typed flags) — never a caller-suppliable command string; `render-pr-body` only ever reads files it's pointed at, never executes anything | PASS |
| VIII. The Bot Proposes, People Decide | The entire feature is a direct implementation of this principle: the bot proposes (opens the PR), a human (not the initiator) decides (approves it), only then does the bot act (cuts the branch) | PASS |
| IX. Parity Before Strictness | Not applicable — no phased rollout in this feature | PASS (N/A) |
| X. Specification and Release Traceability | `render-pr-body`'s gates checklist is a direct, traceable rendering of the manifest's own recorded gate state — the release PR becomes a live view of the manifest's traceability chain, not a separate, divergent record | PASS |
| XI. Layered, Escalating Security Scanning | Not applicable — no build, image, or scan artifact | PASS (N/A) |
| XII. The Engine CLI Is the Only Path to GCP | Reconfirmed: zero `gcloud`/GCP SDK calls anywhere in this feature; the workflow's own GitHub/Jira calls are not GCP calls and don't go through the engine, consistent with every prior workflow (`release-commands.yml`'s own `gh api` calls for team-membership resolution) | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/014-release-cut-workflow/
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
├── cli.py                           # MODIFIED: add `release render-pr-body` to the existing
│                                      # release_app
└── release/
    ├── git_history.py                # MODIFIED: add `changed_paths(repo_dir, base, head)`
    └── render_pr_body.py             # NEW: render(manifest, *, change_notes_dir, repo_dir,
                                       #   migrations_chain) -> RenderPrBodyResult (research.md D2)

.github/workflows/release-cut.yml      # NEW: propose (workflow_dispatch) + cut
                                        #   (pull_request_review) jobs (research.md D1, D3)
templates/callers/release.yml          # MODIFIED: add the `cut` (propose) and `cut-approved`
                                        #   jobs alongside the existing `commands` job

engine/tests/unit/
├── test_release_render_pr_body.py     # every acceptance scenario + the determinism test
└── test_release_git_history_diff.py   # changed_paths() against a real git fixture
```

**Structure Decision**: `render_pr_body.py` is a new sibling module inside
the existing `release/` subpackage (same module-per-concern shape as
`candidates.py`/`cut.py`/`finalise.py`/`verify_promotion.py`) —
`git_history.py` is extended in place rather than duplicated, matching
every prior feature's own precedent. The workflow and caller-template
files live at the fixed repository locations this platform's own layout
(CLAUDE.md) and prior features (`ci.yml`, `security.yml`,
`release-commands.yml`) already established — no new directory
structure needed.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
