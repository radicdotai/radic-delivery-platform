# Implementation Plan: Release-Commands Reusable Workflow

**Branch**: `006-release-commands-workflow` | **Date**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-release-commands-workflow/spec.md`

## Summary

Wire feature 005's already-built, already-tested `radic-delivery release
command` into a real GitHub Actions contract: a new reusable workflow
(`.github/workflows/release-commands.yml`), a new composite action that
safely fetches a PR comment's body and safely posts a reply (never
interpolating comment text into a shell command), and the `commands` job
section of `templates/callers/release.yml`, triggered on `issue_comment`
and gated to pull requests only. The one piece of new *logic* this feature
adds — mapping feature 005's `CommandCheckResult` onto the architecture's
typed `command`/`outcome` workflow outputs and the reply text a release
manager sees — is a small, pure, fully unit-tested addition to the engine
(`release_commands/workflow_outcome.py`), exposed as additive JSON fields
on the existing `release command` CLI output. Team-membership lookup,
Tech-Lead identity, comment fetching, and reply posting are real GitHub API
calls this sandbox cannot execute live; those steps are written for real,
per the architecture's contract, and verified structurally with
`actionlint`/`zizmor`, the same testing asymmetry already used for
`ci.yml` (002) and `security.yml` (003).

## Technical Context

**Language/Version**: Python 3.11 (same `engine/` package, extended again —
one new pure module, no new runtime dependency)

**Primary Dependencies**: none new for the engine. The workflow YAML uses
the GitHub CLI (`gh`, preinstalled on GitHub-hosted runners) for the
GitHub API calls (fetching a comment, listing team members, posting a
reply) rather than a new SDK dependency, consistent with keeping the
engine itself free of any GitHub API client.

**Storage**: none

**Testing**: `pytest` for the new pure mapping function
(`workflow_outcome.py`) and its CLI exposure — every case has a known
input `CommandCheckResult` and a known expected output, no fixtures, no
subprocess, no network, matching feature 005's testing simplicity.
`actionlint` (already wired into this repo's own `engine-ci.yml` since
feature 001) and `zizmor` (documented in `CLAUDE.md`'s command list since
feature 001 but never actually wired into `engine-ci.yml` until now — this
feature closes that gap) structurally validate the new/changed workflow
YAML; `zizmor` is run via `uvx zizmor` (no system package needed, already
confirmed to work in this sandbox) rather than requiring a `brew`/apt
install step on the Actions runner.

**Target Platform**: GitHub-hosted Actions runners (the new reusable
workflow and composite action); developer workstation (the engine's new
pure module, same as always)

**Project Type**: single CLI tool, unchanged — this feature adds one pure
engine module plus GitHub Actions YAML under the repo root (reusing the
`actions/`, `templates/callers/` directories feature 002 established)

**Performance Goals**: not applicable — the new engine logic is a handful
of dict lookups against an already-computed `CommandCheckResult`; the
workflow's own run time is dominated by GitHub API round-trips this
feature does not control

**Constraints**: zero GCP SDK or `gcloud` call anywhere in this feature
(Principle XII); the raw PR comment body is fetched into a file and passed
to `radic-delivery release command` via `--comment-file`, never
interpolated into a `run:` shell string at any point in the new workflow or
composite action (direct continuation of feature 005's research.md D4); no
new CLI subcommand is added — the existing `release command` invocation's
JSON output gains additive fields only, so feature 005's own CLI/grammar/
authorization tests remain valid unmodified; an identity-lookup failure
(team membership or Tech Lead unresolvable) is surfaced by letting that
workflow step fail outright, never silently treated as "unauthorized" or
"authorized" (spec FR-008) — this is a workflow-YAML behavior, not new
engine code, since the engine is simply never invoked with unresolved
identity inputs.

**Scale/Scope**: one new pure engine module (`workflow_outcome.py`), one
small CLI output change (additive), one new reusable workflow, one new
composite action, one caller-template job section; zero new descriptor
schema changes; zero new sample-repo fixtures (all new tests are inline
`CommandCheckResult` literals, same style as feature 005)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise Implementation, Decentralise Configuration | The command/outcome/reply-text mapping — real branching logic with real edge cases (research_close, malformed) — lives once in the engine, not duplicated as shell/jq across this workflow or any future one; the caller template stays a thin `uses:` pin plus typed inputs | PASS |
| II. Build Once, Promote the Verified Digest | Not applicable — no image is built, pushed, or promoted by this feature | PASS (N/A) |
| III. Fail-Closed Quality Gates, Zero Skip Budget | Not directly applicable (no test-skip concept here); the feature's fail-closed posture shows up as FR-008: an identity-lookup failure must never default to "authorized" | PASS |
| IV. Keyless, Separated-Duty Identity | The workflow authenticates as the release bot's declared GitHub App identity (`DELIVERY_BOT_APP_ID`/`DELIVERY_BOT_PRIVATE_KEY`, already named in the architecture's contract) rather than a long-lived PAT; no GCP identity or WIF is involved | PASS |
| V. Human-and-Machine Approval for Production | Not applicable — this is a PR-comment reply loop, not a deploy or promotion path; FR-011 explicitly keeps this feature from mutating any release state | PASS (N/A) |
| VI. Terraform and Cloud Deploy Ownership Boundary | Not applicable — no infrastructure, Terraform, or Cloud Deploy object is touched | PASS (N/A) |
| VII. No Arbitrary Commands in Configuration | Direct continuation of feature 005's own application of this principle: the comment body is read into a file and passed via a typed CLI option, never interpolated into a `run:` shell string, in either the new composite action or the new workflow | PASS |
| VIII. The Bot Proposes, People Decide | This feature is exactly the mechanism by which a *release manager's* instruction (not the bot's) is recognized, authorized, and acknowledged; FR-011 keeps it from acting on a release unilaterally — a human-authored command is acknowledged, not auto-executed into a release change | PASS |
| IX. Parity Before Strictness | Not applicable — no phased/report-only rollout concept for a comment-reply loop; "not a command" is deliberately always silent (FR-006), not a staged strictness level | PASS (N/A) |
| X. Specification and Release Traceability | Traces to spec.md's FRs/SCs; FR-010's "Command Outcome Report" is produced for every reacted-to comment, but writing it to the platform's durable audit trail (`delivery-records`) remains a separate, not-yet-built capability, documented not silently assumed | PASS |
| XI. Layered, Escalating Security Scanning | Not applicable to the engine change (no build/image/scan artifact); the new workflow YAML itself is scanned by `zizmor` for script-injection risk, same as every reusable workflow this platform ships | PASS |
| XII. The Engine CLI Is the Only Path to GCP | Reconfirmed: zero `gcloud`/GCP SDK calls anywhere in this feature; GitHub API calls (team lookup, comment fetch/reply) are a GitHub-native concern this principle doesn't govern, same precedent as feature 002's `setup-engine` checkout | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/006-release-commands-workflow/
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
├── cli.py                           # MODIFIED: `release command`'s JSON/text output gains additive
│                                       # workflow_command/workflow_outcome/reply_body fields
└── release_commands/
    ├── result.py                     # UNCHANGED (feature 005)
    ├── grammar.py                    # UNCHANGED (feature 005)
    ├── authorization.py              # UNCHANGED (feature 005)
    └── workflow_outcome.py           # NEW: pure CommandCheckResult -> WorkflowOutcome
                                        # (command/outcome/reply_body), per research.md D2

engine/tests/unit/
├── test_release_workflow_outcome.py  # NEW: pure mapping tests — all 4 classifications, the
│                                       # research_close gap, and the malformed/not_a_command cases
├── test_release_grammar.py           # UNCHANGED (feature 005)
├── test_release_authorization.py     # UNCHANGED (feature 005)
└── test_release_cli.py               # MODIFIED: additional assertions for the new additive
                                        # output fields; existing assertions remain valid unmodified

.github/workflows/
├── engine-ci.yml                     # MODIFIED: add a zizmor structural-scan step (closes the
│                                       # feature 001/002/003 gap between CLAUDE.md's documented
│                                       # command list and what engine-ci.yml actually runs)
└── release-commands.yml              # NEW: the reusable workflow (workflow_call)

actions/
├── setup-engine/                     # UNCHANGED (feature 002) — reused as-is
└── post-release-command-reply/
    └── action.yml                    # NEW: composite action — fetch comment body to a file,
                                        # post the reply, both via typed inputs, never shell-
                                        # interpolated comment text

templates/callers/
└── release.yml                       # NEW: the `commands` job section — issue_comment trigger,
                                        # gated to pull requests, calling release-commands.yml@v1.0.0
```

**Structure Decision**: extends the existing single-project `engine/`
package with exactly one new pure module inside feature 005's
`release_commands` subpackage — no new subpackage, since this feature adds
one function's worth of real logic, not a new domain. The GitHub Actions
artifacts reuse the `actions/`, `templates/callers/` directories feature
002 established and add one new composite action, following that same
"composite action for the GitHub-API-touching mechanics, pure engine
function for the branching logic" split.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
