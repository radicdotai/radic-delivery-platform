# Implementation Plan: Engine Scaffold & Service Descriptor Validation

**Branch**: `001-engine-scaffold` | **Date**: 2026-10-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-engine-scaffold/spec.md`

## Summary

Scaffold the `engine/` Python package that becomes the single supported CLI
(`radic-delivery`) for this platform, with every command group from the
approved architecture declared in `--help` (most as explicit "not implemented
yet" stubs), and fully implement the three commands this feature's spec
requires: `descriptor validate`, `descriptor show`, and `policy exceptions
check`. Ship the service descriptor JSON Schema, three further record schemas
(release-manifest, change-note, test-result) as stable-but-unused contracts,
a seeded `policy/exceptions.yml`, and one real descriptor fixture per service
repo. No GCP call, no workflow change, and no release/deploy logic is in
scope — this is the offline foundation every later workflow will depend on
(constitution Principle I and XII).

## Technical Context

**Language/Version**: Python 3.11 (engine runtime; descriptor fixtures declare
their own service runtime versions independently, e.g. 3.11/3.12/node20 — not
relevant to the engine's own interpreter choice)

**Primary Dependencies**: `uv` (packaging/dependency management), `typer`
(CLI framework), `jsonschema` (draft 2020-12 validation against
`schemas/*.schema.json`, plus the `referencing` library it uses internally
for `$ref`/`oneOf` resolution), `pyyaml` (descriptor/exceptions YAML parsing)

**Storage**: none — this feature reads YAML files from the working tree
(`.radic/service.yml` fixtures, `policy/exceptions.yml`) and JSON Schema files
from `schemas/`; it writes nothing

**Testing**: `pytest` (unit tests per command, one test per edge case in the
spec), golden fixture tests (7 real descriptor fixtures + deliberately broken
variants), `ruff` (lint), `mypy` (type check)

**Target Platform**: developer workstation and GitHub Actions runner (Linux),
invoked as a CLI — no server, no long-running process

**Project Type**: single CLI tool (Python package) living inside this
monorepo-style platform repo, alongside non-code assets (`schemas/`,
`templates/`, `policy/`)

**Performance Goals**: a single descriptor validation completes in well under
1 second of CPU time (SC-001's "under 10 seconds of tool runtime" is a
generous ceiling that includes Python interpreter startup — the implementation
should land far inside it)

**Constraints**: zero network access required for any command in this
feature; zero GCP SDK or `gcloud` invocation (constitution Principle XII
reserves that surface for later features); must never read or print
`.env`, `gcs-service-account.json`, `Service Account Radic.rtf`, or any
Secret Manager value, even incidentally while walking the working tree

**Scale/Scope**: 7 descriptor fixtures, 4 schema files, 1 seeded exceptions
file with 3 entries, 3 fully-implemented commands, remaining command groups
stubbed (not implemented)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Centralise implementation, decentralise configuration | This feature *is* the centralising mechanism (the schema + validator); no service-repo-specific logic is hardcoded into the engine itself — all per-service variance lives in the descriptor fixtures | PASS |
| II. Build once, promote by digest | Not applicable — this feature builds nothing and deploys nothing | PASS (N/A) |
| III. Fail-closed, zero skip budget | Schema requires `quality.skip_budget == 0`; `additionalProperties: false` everywhere; unresolvable/expired exception references fail descriptor validation | PASS |
| IV. Keyless, separated-duty identity | Not applicable — no GCP identity is used or required by this feature | PASS (N/A) |
| V. Human + machine approval for prod | Not applicable — no deploy/promote path exists yet | PASS (N/A) |
| VI. Terraform/Cloud Deploy ownership boundary | Not applicable — no infrastructure is touched | PASS (N/A) |
| VII. No arbitrary commands in configuration | Schema defines only typed, enumerated fields; the one free-text-shaped field (`quality.post_deploy.suites[].target`) is constrained by a fixed regex, matching the approved architecture, not an open shell string | PASS |
| VIII. Bot proposes, people decide | Not applicable — no release bot interaction in this feature | PASS (N/A) |
| IX. Parity before strictness | The three seeded exceptions are exactly the sanctioned "no suite yet" migration gaps from the approved architecture, each dated and attributed, not an undocumented shortcut | PASS |
| X. Specification and release traceability | This plan traces to spec.md's FRs/SCs; tasks.md (next) will trace every task back to an FR; no release manifest exists yet to connect to, which is expected at this stage | PASS |
| XI. Layered security scanning | Not applicable — no build or image artifact exists in this feature | PASS (N/A) |
| XII. Engine CLI is the only path to GCP | This feature establishes that CLI's shape; it deliberately implements zero GCP-touching commands yet, consistent with staging the surface before the capability | PASS |

No violations requiring the Complexity Tracking table.

## Project Structure

### Documentation (this feature)

```text
specs/001-engine-scaffold/
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
engine/
├── pyproject.toml                  # uv-managed package, console-script entry point "radic-delivery"
├── src/radic_delivery/
│   ├── __init__.py
│   ├── cli.py                      # typer app; registers every command group, stubs vs. implemented
│   ├── exit_codes.py                # OK=0, INVALID_INPUT=2, POLICY_FAILURE=3, INFRA_ERROR=4
│   ├── descriptor/
│   │   ├── __init__.py
│   │   ├── schema_loader.py        # loads schemas/service.schema.json
│   │   ├── validator.py             # jsonschema-backed validate(), used by `descriptor validate`
│   │   └── resolver.py              # applies schema defaults, used by `descriptor show`
│   └── policy/
│       ├── __init__.py
│       ├── exceptions_schema_loader.py
│       └── exceptions.py            # load/validate policy/exceptions.yml, check(id, as_of)
└── tests/
    ├── unit/
    │   ├── test_descriptor_validate.py
    │   ├── test_descriptor_show.py
    │   └── test_policy_exceptions_check.py
    └── fixtures/
        ├── fastapi-backend.yml
        ├── web-bff.yml
        ├── design_service.yml
        ├── image-studio.yml
        ├── brand_research.yml
        ├── frontend-v2.yml
        ├── operations-console.yml
        └── broken/                  # one deliberately-invalid variant per failure category in spec Edge Cases

schemas/
├── service.schema.json
├── release-manifest.schema.json     # shape only, unused until a later feature
├── change-note.schema.json          # shape only, unused until a later feature
├── test-result.schema.json          # shape only, unused until a later feature
└── exceptions.schema.json           # schema for policy/exceptions.yml itself

policy/
└── exceptions.yml                   # seeded with EXC-0001 (web-bff), EXC-0002 (image-studio), EXC-0003 (brand_research)
```

**Structure Decision**: single Python project (`engine/`) at the repo root,
alongside non-code platform assets (`schemas/`, `policy/`). No `backend/`
`frontend/` split applies — this is a CLI tool, not a web application. Fixture
descriptors live under `engine/tests/fixtures/` (test data owned by the
engine's own test suite) rather than under `schemas/`, since they exist to
exercise the validator, not to define the contract.

## Complexity Tracking

*No entries — Constitution Check recorded no violations.*
