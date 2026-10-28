# Implementation Plan: Central Security Scanning Workflow (report-only)

**Branch**: `003-security-scanning` | **Date**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-security-scanning/spec.md`

## Summary

Add a `security` command group to the existing `radic-delivery` engine
(`security scan --scope source|iac|all`) that runs `gitleaks` (hardcoded
secrets) and `hadolint` + `trivy config` (Dockerfile/IaC misconfiguration),
aggregates every finding into one severity-classified
`SecurityScanResult`, and — by design, for the entirety of this feature —
never fails regardless of what it finds. Wires this into a new reusable
workflow (`.github/workflows/security.yml`) that posts the findings to the
pull request's own job summary (visible without opening raw logs) and adds
a second job to the existing example caller
(`templates/callers/ci.yml`) so a service repo gets both `ci-gate` and
`security` from the one caller file. Image scanning and Snyk are visibly
reported as not-yet-available, never silently omitted.

## Technical Context

**Language/Version**: Python 3.11 (same `engine/` package, extended again)

**Primary Dependencies**: `typer`, `jsonschema`, `pyyaml` (unchanged); no new
Python dependency — this feature shells out to three external CLI tools
(`gitleaks`, `hadolint`, `trivy`) exactly as feature 002 shelled out to
`ruff`/`mypy`/`pytest`/`eslint`/`tsc`/`vitest`. Installing those three tools
on the runner is the calling workflow's job (via a new composite action),
mirroring the split already established in feature 002 (the engine runs
tools, it does not install them)

**Storage**: none — reads the descriptor and the service's own source tree;
writes nothing

**Testing**: `pytest` for parser/aggregation unit tests (pure, no
subprocess); a real, fully-executed end-to-end test using the `gitleaks`,
`hadolint`, and `trivy` binaries installed on this development machine
against small, purpose-built sample fixtures — a planted secret, a
misconfigured Dockerfile, and a clean service with neither — mirroring
feature 002's "real tools, not mocks" standard wherever the tool is
actually available in this environment

**Target Platform**: developer workstation and GitHub-hosted Actions
runners; still no server, no long-running process

**Project Type**: single CLI tool, unchanged — this feature adds Python
modules under the same `engine/` package plus one more GitHub Actions
workflow and composite action

**Performance Goals**: not performance-sensitive; scan wall-clock time is
dominated by the external tools themselves, which this feature does not
control

**Constraints**: zero GCP SDK or `gcloud` call anywhere in this feature;
zero blocking/failing behavior of any kind, for any finding, at any
severity (FR-006 — this is the hard constraint this whole feature exists to
honour); container-image scanning and Snyk are out of scope and MUST be
reported as not-yet-available rather than omitted (FR-007, FR-008)

**Scale/Scope**: one new command group (`security`, with `scan` as its one
subcommand), ~4 new engine modules (parsers for the three tools' JSON
output, an aggregator, a result/report module), 3 new sample-repo fixtures
(clean, planted-secret, misconfigured-Dockerfile), 1 new reusable workflow,
1 new composite action, 1 edit to the existing example caller

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise implementation, decentralise configuration | Scanning logic lives only in the engine + this reusable workflow; the caller gains one more job line, nothing more | PASS |
| II. Build once, promote by digest | Not applicable — no image is built or promoted here | PASS (N/A) |
| III. Fail-closed, zero skip budget | Not applicable to this feature's own scope — this feature intentionally never fails (FR-006), which is itself the architecture's documented, time-boxed exception to fail-closed during the report-only rollout window, not a violation of it | PASS |
| IV. Keyless, separated-duty identity | Not applicable — no GCP identity is used | PASS (N/A) |
| V. Human + machine approval for prod | Not applicable — this is a PR-time advisory report, not a deploy/promotion path | PASS (N/A) |
| VI. Terraform/Cloud Deploy ownership boundary | Not applicable — no infrastructure is touched | PASS (N/A) |
| VII. No arbitrary commands in configuration | The scan's tool invocations are fixed argv lists constructed in code, not derived from descriptor free text; the descriptor only supplies a Dockerfile *path* (already schema-constrained by feature 001), never a command | PASS |
| VIII. Bot proposes, people decide | Not applicable — no release bot interaction | PASS (N/A) |
| IX. Parity before strictness | This feature **is** the report-only phase the principle describes — new scanning starting advisory-only before any blocking is turned on, on the architecture's own documented schedule | PASS |
| X. Specification and release traceability | Traces to spec.md's FRs/SCs; no release manifest exists yet to connect to, which is expected at this stage | PASS |
| XI. Layered security scanning | This feature is a direct, partial implementation of this principle (secrets + Dockerfile/IaC layers now; image + Snyk layers explicitly deferred and visibly reported as such) | PASS |
| XII. Engine CLI is the only path to GCP | Reconfirmed: zero `gcloud`/GCP SDK calls anywhere in this feature | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/003-security-scanning/
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
├── cli.py                           # MODIFIED: replace the `security`-shaped gap with a real command group
│                                       (there was no pre-existing "security" stub — this feature adds the
│                                       group fresh, same as "gate" was added fresh in specs/002)
└── security/
    ├── __init__.py
    ├── tools.py                       # pure: descriptor -> which ToolInvocations apply for a requested scope
    ├── runner.py                      # executes a ToolInvocation via subprocess (reuses gate/runner.py's shape)
    ├── parsers.py                     # pure: gitleaks/hadolint/trivy JSON output -> list[Finding]
    ├── aggregator.py                  # orchestrates tools.py + runner.py + parsers.py -> SecurityScanResult
    └── result.py                      # Finding / SecurityScanResult dataclasses, JSON (de)serialisation

engine/tests/
├── unit/
│   ├── test_security_tools.py        # pure tool-selection tests (which scopes apply to which descriptor)
│   ├── test_security_parsers.py      # parser tests against captured sample tool JSON output
│   ├── test_security_aggregator.py   # orchestration tests with a fake runner (no real subprocess)
│   └── test_security_cli.py          # CLI-level: exit codes, --format json|text, real end-to-end runs
└── fixtures/sample-repos/
    ├── python-sample-secret/          # copy of python-sample (specs/002) + one planted fake secret
    └── python-sample-bad-dockerfile/  # copy of python-sample + a Dockerfile with a seeded misconfiguration
    # python-sample itself (specs/002, already clean, already has no Dockerfile) continues to serve as
    # the "nothing to find" / "no Dockerfile declared" case for this feature — no new fixture needed for it

actions/setup-security-tools/
└── action.yml                        # NEW: composite action — installs gitleaks, hadolint, trivy on the runner

.github/workflows/
└── security.yml                      # NEW: the reusable workflow (workflow_call), report-only, never fails

templates/callers/
└── ci.yml                            # MODIFIED: add a second job calling the new security.yml workflow
```

**Structure Decision**: extends the existing single-project `engine/`
package with one more subpackage (`security/`), mirroring `gate/`'s shape
exactly (tools/runner/parsers/aggregator/result). New GitHub Actions
artifacts follow the same `actions/<name>/action.yml` convention feature
002 established. `templates/callers/ci.yml` is edited in place rather than
duplicated, since the architecture's own caller-file count (8 per service
repo) has no dedicated security caller — security is a second job in the
existing one.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
