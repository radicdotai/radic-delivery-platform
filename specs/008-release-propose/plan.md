# Implementation Plan: Release Selection and Draft Manifest

**Branch**: `008-release-propose` | **Date**: 2026-11-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-release-propose/spec.md`

## Summary

Add `radic-delivery release propose`: given a local directory of
already-captured change-note records (specs/007's exact `change-notes/
<repo>/<sha>.json` layout) and a real local git checkout, it filters
candidates to those reachable from `--base`'s HEAD and not already
behind a prior release marker, groups them by Jira ticket, splits them
into a proposed selection and a held-back list using explicit,
caller-supplied readiness and dev-green facts (never a live Jira or
test-results call), folds in any explicitly-listed ticket-less PRs, and
produces a manifest validated against a now-tightened `schemas/
release-manifest.schema.json`. This feature also corrects that schema,
which — like `change-note.schema.json` before specs/007 — was an
intentionally loose feature-001 placeholder, and whose authoritative
version (Reference 3 §3) turns out to conflate several *later* pipeline
stages' required fields (approvals, a cherry-picked `release_sha`, a
filled-in `second_approver`) with what a freshly-`proposed` manifest can
possibly contain.

## Technical Context

**Language/Version**: Python 3.11 (same `engine/` package, extended again)

**Primary Dependencies**: `jsonschema` (already present, same
`Draft202012Validator` pattern as `descriptor/validator.py` and specs/007's
`notes/builder.py`); no new dependency — git operations shell out to the
system `git` binary via `subprocess`, the same mechanism `gate/runner.py`
already uses for arbitrary tool invocation

**Storage**: change-note records are read from a local directory tree
(the same layout `notes write` already produces); the produced manifest
is optionally written locally, mirroring the real `releases/<id>.yaml`
key structure exactly (research.md D4, continuing specs/007 D4's
precedent) — the real `radicdotai/delivery-records` repository is never
touched

**Testing**: `pytest` — candidate-grouping and selection logic are pure
functions over inline dict/dataclass fixtures (no real dependency to
exercise); the git-reachability filter is the one real, unmocked
dependency this feature has, exercised against a real local git
repository built in `tmp_path` (real `git init`/`commit`/branch
operations, real `subprocess` calls — not mocked), the same "real tool,
real fixture" discipline as specs/002's sample-repo tests

**Target Platform**: developer workstation and GitHub-hosted Actions
runners; no server, no long-running process

**Project Type**: single CLI tool, unchanged — adds a new `release/`
subpackage (distinct from specs/005's `release_commands/`, exactly the
split that feature's own research.md reserved this name for)

**Performance Goals**: not applicable — candidate counts are small
(commits since the last release), and git operations are simple
ancestry queries

**Constraints**: zero live Jira/ticket-tracking call, zero live
`delivery-records`/GCS call (FR-010); ticket readiness and dev-green
status are explicit CLI input, never looked up (spec Assumptions — this
platform's largest external-dependency boundary so far); this feature
creates no branch, no PR, no commit (FR-011)

**Scale/Scope**: one new command group member (`release propose`,
alongside the already-implemented `release command`), ~6 new engine
modules, one schema file substantially corrected (not replaced — `$id`
unchanged), one new git-fixture-based test file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise Implementation, Decentralise Configuration | The selection algorithm (grouping, ready/held-back split) lives once in the engine; no service repo or workflow reimplements it | PASS |
| II. Build Once, Promote the Verified Digest | Not applicable — no image or digest is built here; `digests` stays unpopulated at the `proposed` stage (research.md D1) | PASS (N/A) |
| III. Fail-Closed Quality Gates, Zero Skip Budget | This feature's own fail-closed posture: a candidate ticket not explicitly supplied as ready is held back by default, never silently promoted (spec FR-005/FR-006) | PASS |
| IV. Keyless, Separated-Duty Identity | Not applicable — no GCP identity; this feature calls no external API of any kind | PASS (N/A) |
| V. Human-and-Machine Approval for Production | Not applicable — this is a pre-cut draft, produced before any approval step exists to satisfy; `approvals` is deliberately left unpopulated (research.md D1) | PASS (N/A) |
| VI. Terraform and Cloud Deploy Ownership Boundary | Not applicable | PASS (N/A) |
| VII. No Arbitrary Commands in Configuration | Every git operation this feature performs is a fixed, parameterised ancestry query (`git log`/`rev-list`-style), never a caller-supplied command string | PASS |
| VIII. The Bot Proposes, People Decide | This feature *is* the bot's proposal step — every selected ticket's `origin` is `bot-proposal` (manual `added`/`migration-dependency` origins remain specs/005-006's `release command add`/future features' concern); nothing here is auto-approved or auto-cut | PASS |
| IX. Parity Before Strictness | Not applicable — no phased rollout for a one-shot computation; the readiness/dev-green explicit-input boundary is a scope decision, not a strictness rollout | PASS (N/A) |
| X. Specification and Release Traceability | This feature produces the first real release-manifest artifact; it also corrects that artifact's own schema, now actually exercised for the first time | PASS |
| XI. Layered, Escalating Security Scanning | Not applicable — no build, image, or scan artifact | PASS (N/A) |
| XII. The Engine CLI Is the Only Path to GCP | Reconfirmed: zero `gcloud`/GCP SDK calls; zero GitHub/Jira API calls — the strictest "no external call" posture, matching specs/005 and specs/007 | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/008-release-propose/
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
└── release-manifest.schema.json     # MODIFIED: corrected per research.md D1 — $id/title unchanged

engine/src/radic_delivery/
├── cli.py                           # MODIFIED: add `release propose` to the existing `release_app`;
│                                       # remove "propose" from `_RELEASE_NOT_IMPLEMENTED`
└── release/
    ├── __init__.py
    ├── schema_loader.py              # load_release_manifest_schema() — same pattern as
    │                                   # descriptor/ and notes/ schema_loader.py
    ├── result.py                     # Candidate / Selection / ProposeResult dataclasses,
    │                                   # JSON (de)serialisation
    ├── candidates.py                 # pure: change-notes directory + repo -> list[Candidate]
    │                                   # (reads local JSON, never GCS — research.md D3)
    ├── git_history.py                 # the one real, unmocked dependency: real `git` subprocess
    │                                   # calls -> the set of commit SHAs reachable from --base
    │                                   # and not already behind --since-sha (research.md D2)
    ├── selector.py                    # pure: candidates (already git-filtered) + explicit
    │                                   # ready-tickets/dev-green-failed/non-jira-prs inputs ->
    │                                   # Selection (proposed/held_back/non_jira_prs)
    └── manifest.py                    # pure: Selection + repo/base/release_id/initiator ->
                                         # full manifest dict, validated via jsonschema -> ProposeResult

engine/tests/unit/
├── test_release_propose_candidates.py  # pure candidate-loading tests (repo filter, malformed
│                                         # record handling)
├── test_release_propose_git_history.py  # real git fixture (tmp_path, real `git init`/commit/
│                                         # branch): reachability + since-sha exclusion
├── test_release_propose_selector.py    # pure grouping/ready/held-back/non-jira-pr tests
├── test_release_propose_manifest.py    # pure manifest construction + schema validation tests
└── test_release_propose_cli.py        # CLI-level: exit codes, --dry-run, --format json|text
```

**Structure Decision**: a new, self-contained `release/` subpackage,
exactly the one specs/005's research.md reserved this name for
("a future `release` subpackage covering `propose`/`cut`/`verify-
promotion`/`finalise`"). It is wired into the *existing* `release_app`
Typer group `release command` already registered in `cli.py`, not a new
group — `propose` simply stops being a stub alongside `cut`/`verify-
promotion`/`finalise`, which remain unimplemented.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
