# Implementation Plan: CI Tooling Completion

**Branch**: `012-ci-tooling-completion` | **Date**: 2026-11-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-ci-tooling-completion/spec.md`

## Summary

Adds two small, unrelated CLI commands, bundled into one feature per the
project's explicit request to combine related, independently small
slices and reduce per-feature process overhead: `radic-delivery tests
inventory` (runs a service's own descriptor-driven unit-test command for
real, reusing `gate evaluate`'s own command-construction and output-
parsing machinery, and reports total/passed/failed/skipped plus a new
quarantine-ledger lookup) and `radic-delivery policy rulesets-diff` (a
pure, local comparison of this platform's committed GitHub ruleset JSON
against an explicitly-supplied stand-in for the live `gh api
repos/<repo>/rulesets` response). This feature also seeds the `rulesets/`
directory — named in CLAUDE.md's repo layout but not yet created — with
the five real ruleset JSON bodies the approved architecture already
specifies verbatim.

## Technical Context

**Language/Version**: Python 3.11 (same `engine/` package, extended again)

**Primary Dependencies**: none new — `tests inventory` reuses
`gate/commands.py`, `gate/runner.py`, `gate/parsers.py`, and
`descriptor/validator.py` directly; `policy rulesets-diff` is pure local
JSON file comparison (stdlib `json` only)

**Storage**: a new ledger file, `policy/quarantine.yml` (validated
against a new `schemas/quarantine.schema.json`), following
`policy/exceptions.yml`'s exact shape and loading discipline; five new
static files under a new `rulesets/` directory; `rulesets-diff` itself
reads but writes nothing

**Testing**: `pytest` — `tests inventory` exercised against this
platform's own existing, real fixture repos
(`engine/tests/fixtures/sample-repos/`), no new fixtures invented;
`rulesets-diff` exercised against small, inline, hand-written committed/
live JSON fixtures (`tmp_path`), no git, no external call

**Target Platform**: developer workstation and GitHub-hosted Actions
runners; no server, no long-running process

**Project Type**: single CLI tool, unchanged — adds a new
`tests_inventory/` subpackage (the `tests` command group's first real
subcommand) and two new modules inside the existing `policy/` subpackage

**Performance Goals**: not applicable — one real test-suite execution and
one small, local JSON comparison

**Constraints**: zero external network call in either command (FR-007);
the live ruleset state is explicit `--live-file` input, never a live `gh
api` call (research.md D5); `tests inventory` never cross-checks a
quarantine ledger entry's `test_id` against the real test run's own
output (research.md D2); `rulesets-diff` always exits `OK` once its
inputs are read and compared — a drift report, never a gate (research.md
D5)

**Scale/Scope**: one command group completed (`tests inventory` — the
`tests` group's stub removed entirely), one command added to the
existing `policy` group (`rulesets-diff`), two new sibling modules in
`policy/` plus a new `tests_inventory/` subpackage, one new schema +
ledger file, five new static JSON files, four new test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise Implementation, Decentralise Configuration | Test-command construction, output parsing, and the ruleset-diff logic all live once in the engine; the five ruleset definitions are platform-owned config, not duplicated per service repo | PASS |
| II. Build Once, Promote the Verified Digest | Not applicable — neither command touches a build artifact or digest | PASS (N/A) |
| III. Fail-Closed Quality Gates, Zero Skip Budget | `tests inventory` reports skipped/quarantined distinctly rather than masking them in a single total (FR-001, FR-002); it does not itself relax the skip-budget gate `gate evaluate` already enforces | PASS |
| IV. Keyless, Separated-Duty Identity | Not applicable — no GCP identity in either command | PASS (N/A) |
| V. Human-and-Machine Approval for Production | Not applicable | PASS (N/A) |
| VI. Terraform and Cloud Deploy Ownership Boundary | Not applicable | PASS (N/A) |
| VII. No Arbitrary Commands in Configuration | `tests inventory` reuses `gate/commands.py`'s already-fixed, descriptor-keyed argv construction — no new command-construction path; `rulesets-diff` executes no command at all | PASS |
| VIII. The Bot Proposes, People Decide | `rulesets-diff` only ever reports drift; it never applies a ruleset or decides which of the five apply to a given repo (research.md D4) — that judgment is left to the person reading the report | PASS |
| IX. Parity Before Strictness | `rulesets-diff` is explicitly a report-only drift check, never a blocking gate (research.md D5), matching Reference 2's own "drift report" framing and this principle's own precedent | PASS |
| X. Specification and Release Traceability | Not directly applicable — neither command touches a release manifest or change-note | PASS (N/A) |
| XI. Layered, Escalating Security Scanning | Not applicable — no build, image, or scan artifact | PASS (N/A) |
| XII. The Engine CLI Is the Only Path to GCP | Reconfirmed: zero `gcloud`/GitHub-API/GCP SDK calls in either command; the one piece that would need a live GitHub call (`rulesets-diff`'s live state) is explicitly not implemented, not worked around (research.md D5) | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/012-ci-tooling-completion/
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
rulesets/                              # NEW: five real ruleset JSON files, verbatim
├── dev-trunk.json
├── main-prod-line.json
├── release-branches.json
├── product-tags.json
└── platform-tags.json

schemas/quarantine.schema.json          # NEW
policy/quarantine.yml                   # NEW: the one quarantine ledger (seeded empty)

engine/src/radic_delivery/
├── cli.py                              # MODIFIED: replace the `tests` stub with a real tests_app
│                                        # (`inventory` subcommand); add `rulesets-diff` to the
│                                        # existing policy_app
├── policy/
│   ├── quarantine_schema_loader.py      # NEW: mirrors exceptions_schema_loader.py
│   ├── quarantine.py                    # NEW: QuarantineEntry, load(), classify_for_service()
│   └── rulesets_diff.py                 # NEW: diff(committed, live) -> RulesetsDiffResult
└── tests_inventory/
    ├── __init__.py                      # NEW
    ├── result.py                        # NEW: TestInventoryResult
    └── inventory.py                     # NEW: inventory(descriptor, *, repo_dir,
                                          #   quarantine_entries, as_of) -> TestInventoryResult
                                          #   (reuses gate/commands.py, gate/runner.py,
                                          #   gate/parsers.py directly — research.md D1)

engine/tests/unit/
├── test_policy_quarantine.py            # ledger loading + active/expired classification
├── test_tests_inventory.py              # real fixture-repo runs (launch success + failure)
├── test_policy_rulesets_diff.py         # the four drift outcomes + housekeeping-field +
│                                         #   duplicate-name edge cases
└── test_ci_tooling_completion_cli.py    # CLI-level: exit codes, --format json|text, both commands
```

**Structure Decision**: `tests_inventory/` is a new, distinct subpackage
(not nested under `gate/`, since `tests` is its own top-level command
group per Reference 3, and it only *reuses* `gate/`'s modules rather than
extending them) — named `tests_inventory` rather than `tests` to avoid
colliding with this project's own `engine/tests/` test-suite directory
convention (flagged in the research fork's own findings). `quarantine.py`
and `rulesets_diff.py` are both new siblings inside the existing
`policy/` subpackage, matching `exceptions.py`'s own placement exactly —
each is a self-contained ledger/comparison module, not a shared one.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
