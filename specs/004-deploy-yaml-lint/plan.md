# Implementation Plan: Deploy YAML Lint

**Branch**: `004-deploy-yaml-lint` | **Date**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-deploy-yaml-lint/spec.md`

## Summary

Add a `deploy` command group to the existing `radic-delivery` engine with
exactly one real subcommand, `deploy lint`, that reads a descriptor's
declared Cloud Run service YAML files for dev/stage/prod, checks each
against four content rules (placeholder image, no traffic key, startup
probe present, no inline secret — the last reusing specs/003's gitleaks
integration directly rather than reimplementing secret detection), and
checks the three files against each other for unexplained drift beyond
what the descriptor's `parity.allow` permits. Wires the real result into
specs/002's `ci.yml` reusable workflow, replacing its hardcoded
`deploy_lint: not_available` placeholder. Every other `deploy` subcommand
remains unimplemented, same as every other GCP-touching command group.

## Technical Context

**Language/Version**: Python 3.11 (same `engine/` package, extended again)

**Primary Dependencies**: `typer`, `jsonschema`, `pyyaml` (unchanged); reuses
`gitleaks` (already a dependency of the CI environment from specs/003) for
inline-secret detection rather than introducing a second detection method;
no new Python dependency

**Storage**: none — reads the descriptor and its declared manifest files;
writes nothing

**Testing**: `pytest` for the rule-checking and diff logic (pure, no
subprocess, except the secret-detection rule which does invoke `gitleaks`
for real, exactly as specs/003 established); a real, fully-executed
end-to-end test against purpose-built sample manifest fixtures (one clean
service, and one deliberately-broken variant per rule)

**Target Platform**: developer workstation and GitHub-hosted Actions
runners; no server, no long-running process

**Project Type**: single CLI tool, unchanged — extends `engine/` with one
more subpackage plus a small edit to `.github/workflows/ci.yml`

**Performance Goals**: not performance-sensitive; this is static file
analysis over a handful of small YAML files

**Constraints**: zero GCP SDK or `gcloud` call anywhere in this feature;
this feature only implements the `lint` subcommand — `release`, `promote`,
`approve`, `rollback`, `status`, `drift` remain exactly as unimplemented as
before; Cloud Run **Jobs** (`job_yaml`) are explicitly out of scope for
this increment (research.md D4) — only `service_yaml` is checked

**Scale/Scope**: one new command group (`deploy`, with `lint` as its one
real subcommand), ~4 new engine modules, 2 new sample-repo fixtures (clean
deploy manifests, broken variants covering all 5 rules), 1 edit to
`.github/workflows/ci.yml`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise implementation, decentralise configuration | One centrally defined lint, applied identically to every service's manifests; nothing service-repo-specific is hardcoded | PASS |
| II. Build once, promote by digest | This feature *enforces* the `image: app` placeholder convention that build-once/promote-by-digest depends on, but does not itself build or promote anything | PASS |
| III. Fail-closed, zero skip budget | A lint failure is reported, not silently tolerated; there is no severity/report-only concept here (spec explicitly: a bad manifest is simply wrong, not advisory) — stricter than fail-closed, not a violation of it | PASS |
| IV. Keyless, separated-duty identity | Not applicable — no GCP identity is used | PASS (N/A) |
| V. Human + machine approval for prod | Not applicable — this is a static file check, not a deploy or promotion path | PASS (N/A) |
| VI. Terraform/Cloud Deploy ownership boundary | This feature directly enforces the boundary's practical consequence (the committed YAML is the complete desired state; no `traffic` key, no real image ref) | PASS |
| VII. No arbitrary commands in configuration | The lint reads YAML structure and runs one fixed, already-established tool (`gitleaks`) against a file path — nothing here interprets descriptor or manifest content as a shell command | PASS |
| VIII. Bot proposes, people decide | Not applicable — no release bot interaction | PASS (N/A) |
| IX. Parity before strictness | Not applicable in the report-only sense (this check is binary, not a phased rollout) — but the feature itself enforces environment *parity* in its User Story 2, which is the principle's name, applied literally here as a file-content invariant | PASS |
| X. Specification and release traceability | Traces to spec.md's FRs/SCs; closes a previously-flagged deferred output (`deploy_lint`) from specs/002, which is exactly what traceability is for | PASS |
| XI. Layered security scanning | Reuses, does not duplicate, specs/003's gitleaks integration for the inline-secret rule — one scanning mechanism, two call sites | PASS |
| XII. Engine CLI is the only path to GCP | Reconfirmed: zero `gcloud`/GCP SDK calls anywhere in this feature | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/004-deploy-yaml-lint/
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
├── cli.py                           # MODIFIED: add a new `deploy` command group (deploy lint only)
└── deploy/
    ├── __init__.py
    ├── rules.py                      # pure: one parsed manifest dict -> list[ManifestCheck] (4 content rules)
    ├── parity.py                     # pure: 3 parsed manifests + parity.allow -> list[ManifestCheck] (drift rule)
    ├── linter.py                     # orchestrates: load descriptor's manifest paths, read files, call
    │                                   rules.py + parity.py + security/runner.py (for the secret rule),
    │                                   -> DeployLintResult
    └── result.py                     # ManifestCheck / DeployLintResult dataclasses, JSON (de)serialisation

engine/tests/
├── unit/
│   ├── test_deploy_rules.py          # pure content-rule tests against in-memory manifest dicts
│   ├── test_deploy_parity.py         # pure parity-diff tests against in-memory manifest dicts
│   ├── test_deploy_linter.py         # orchestration tests (secret rule uses the real gitleaks binary,
│   │                                   same precedent as specs/003 — no fake-runner needed here since
│   │                                   gitleaks is the only subprocess this feature invokes)
│   └── test_deploy_cli.py            # CLI-level: exit codes, --format json|text, real end-to-end runs
└── fixtures/sample-repos/
    ├── python-sample/deploy/         # NEW: clean deploy manifests added to the existing specs/002 fixture
    │   ├── skaffold.yaml
    │   └── run/{dev,stage,prod}.yaml
    └── python-sample-bad-deploy/     # NEW: a full fixture copy with one seeded violation per rule,
                                        # selected per test case (not one fixture per rule, since the
                                        # five rules are independent checks over the same small file set)

.github/workflows/
└── ci.yml                            # MODIFIED: deploy_lint output now comes from `deploy lint`'s real result
```

**Structure Decision**: extends `engine/` with one more subpackage
(`deploy/`), mirroring `gate/` and `security/`'s shape. Deploy manifest
fixtures are added directly under the existing `python-sample` fixture
(since a service's deploy manifests live alongside its code in the real
architecture) rather than as a wholly separate sample-repo.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
