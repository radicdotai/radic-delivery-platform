# Implementation Plan: Central CI Reusable Workflow (`ci-gate` mode)

**Branch**: `002-ci-gate-workflow` | **Date**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-ci-gate-workflow/spec.md`

## Summary

Add a `gate` command group to the existing `radic-delivery` engine (replacing
its feature-001 not-implemented stub) that evaluates a service's descriptor-
declared lint, type-check, unit-test, coverage-floor, and skip-budget checks
and reports one structured pass/fail Gate Result — fully for `mode: ci-gate`,
visibly deferred for `mode: release-gate` and for mutation testing. Then wire
that command into this platform's first real reusable GitHub Actions
workflow (`.github/workflows/ci.yml`), a composite action that fetches and
installs the pinned engine onto a caller's runner
(`actions/setup-engine/action.yml`), and one example thin caller template
(`templates/callers/ci.yml`) demonstrating how a service repo invokes it.
No GCP call, Cloud Deploy interaction, or WIF identity is used anywhere in
this feature.

## Technical Context

**Language/Version**: Python 3.11 (unchanged from feature 001 — same `engine/`
package, extended, not replaced)

**Primary Dependencies**: `typer`, `jsonschema`, `pyyaml` (all already present
from feature 001); no new runtime dependency — coverage and skip-count
figures are parsed from `pytest`/`pytest-cov`'s own terminal summary lines
with a small regex parser, not a new structured-report dependency (research.md)

**Storage**: none — same as feature 001; this feature reads the descriptor
and the exceptions ledger (both already supported) and writes nothing

**Testing**: `pytest` for the engine's own test suite; a real, fully-executed
integration test against a small self-contained python-uv sample project
fixture (`engine/tests/fixtures/sample-repos/python-sample/`) that actually
runs `ruff`/`mypy`/`pytest`, since those are already engine dev-dependencies
and need no network access; the Node command-construction path is unit-tested
for correct command generation only — this repo's own test suite does not
install or run a real `eslint`/`tsc`/`vitest` toolchain (research.md records
this asymmetry explicitly, it is not an oversight)

**Target Platform**: developer workstation (for the engine command) and
GitHub-hosted Actions runners (for the reusable workflow); still no server,
still no long-running process

**Project Type**: single CLI tool, unchanged — this feature adds Python
modules under the same `engine/` package plus GitHub Actions YAML under the
repo root (`.github/workflows/`, `actions/`, `templates/callers/`)

**Performance Goals**: a `gate evaluate` run's own overhead (excluding the
time the service's own lint/typecheck/test tools take to run) stays under a
few seconds of CPU time — command construction and output parsing are the
only work this feature adds beyond invoking the service's own tools

**Constraints**: zero GCP SDK or `gcloud` call anywhere in this feature
(Principle XII is reserved for a later feature); the engine assumes the
service's own toolchain is already installed and on `PATH` — installing a
service's dependencies is the calling workflow's job, never `gate evaluate`'s
(spec Assumptions); `gate evaluate` must not require network access itself

**Scale/Scope**: one new command group (`gate`, with `evaluate` as its one
real subcommand), ~5 new engine modules, 2 new sample-repo fixtures (one
passing, one with each failure mode seeded), 3 new GitHub Actions YAML files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise implementation, decentralise configuration | The entire point of this feature is to move a required check out of per-repo CI and into one reusable workflow + one engine command; the example caller template is intentionally thin (a `uses:` pin plus two inputs) | PASS |
| II. Build once, promote by digest | Not applicable — no image is built or promoted by this feature | PASS (N/A) |
| III. Fail-closed, zero skip budget | FR-008/FR-009 and User Story 3 implement exactly this: a skipped test fails the gate unless an active, unexpired, feature-001 exception covers it | PASS |
| IV. Keyless, separated-duty identity | Not applicable — no GCP identity is used; the only "identity" concept here is GitHub's own `github.action_ref` resolution for pinning the engine checkout, which is a GitHub Actions mechanism, not a GCP one | PASS (N/A) |
| V. Human + machine approval for prod | Not applicable — this is a PR-time gate, not a deploy or promotion path | PASS (N/A) |
| VI. Terraform/Cloud Deploy ownership boundary | Not applicable — no infrastructure, Terraform, or Cloud Deploy object is touched by this feature | PASS (N/A) |
| VII. No arbitrary commands in configuration | Command construction (research.md, data-model.md) is a pure function of the descriptor's typed, enum-constrained `quality.*.tool`/`runner` fields — never a free-text shell string from the descriptor; the one free-text-shaped descriptor field used (`quality.unit.marker_expr`/`script`) was already schema-constrained by feature 001's regex patterns | PASS |
| VIII. Bot proposes, people decide | Not applicable — no release bot interaction occurs in a `ci-gate` run | PASS (N/A) |
| IX. Parity before strictness | `release-gate` mode and mutation testing are visibly, not silently, deferred (FR-011/FR-012); this is exactly the "new gates start report-only / staged" discipline the constitution asks for, applied to the gate's own rollout | PASS |
| X. Specification and release traceability | This plan traces to spec.md's FRs/SCs; tasks.md (next) will trace every task back to one; this feature produces no release manifest yet (expected — that is a later feature) | PASS |
| XI. Layered security scanning | Not applicable — no build, image, or scan step exists in this feature (that is the `security`/`build` reusable workflows, out of scope here) | PASS (N/A) |
| XII. Engine CLI is the only path to GCP | Reconfirmed: this feature makes zero `gcloud`/GCP SDK calls; the reusable workflow only checks out code, installs toolchains, and invokes the engine CLI | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/002-ci-gate-workflow/
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
├── cli.py                           # MODIFIED: replace the `gate` stub with a real command group
├── gate/
│   ├── __init__.py
│   ├── commands.py                   # pure: descriptor -> list[ToolInvocation] (lint/typecheck/unit)
│   ├── runner.py                     # executes a ToolInvocation via subprocess, captures output+exit code
│   ├── parsers.py                    # pure: tool stdout/stderr -> CoverageResult / TestRunResult
│   ├── evaluator.py                  # orchestrates commands.py + runner.py + parsers.py -> GateResult
│   └── result.py                     # GateResult / CheckResult dataclasses, JSON (de)serialisation
└── (descriptor/, policy/, paths.py, exit_codes.py unchanged from feature 001)

engine/tests/
├── unit/
│   ├── test_gate_commands.py         # pure command-construction tests, both toolchains
│   ├── test_gate_parsers.py          # pure parser tests against captured sample tool output
│   ├── test_gate_evaluator.py        # orchestration tests with a fake runner (no real subprocess)
│   └── test_gate_cli.py              # CLI-level: exit codes, --format json|text
└── fixtures/sample-repos/
    ├── python-sample/                 # real, tiny python-uv project: passes lint/typecheck/tests/coverage
    │   ├── .radic/service.yml
    │   ├── pyproject.toml
    │   ├── src/sample/__init__.py
    │   └── tests/test_sample.py
    └── python-sample-broken/          # same shape, one seeded failure per check (lint/type/test/coverage/skip)

.github/workflows/
└── ci.yml                            # NEW: the reusable workflow (workflow_call), mode: ci-gate implemented

actions/setup-engine/
└── action.yml                        # NEW: composite action — checkout this repo at the pinned ref, uv sync

templates/callers/
└── ci.yml                            # NEW: example thin caller for a service repo (documentation/example only)
```

**Structure Decision**: extends the existing single-project `engine/` package
from feature 001 with one new subpackage (`gate/`) rather than creating a
second project — this is still one CLI tool. The GitHub Actions artifacts
are new top-level directories (`actions/`, `templates/callers/`) matching the
repository layout already declared in feature 001's `CLAUDE.md` and plan.md.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
