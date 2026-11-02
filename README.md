# radic-delivery-platform

Radic's centralised software delivery platform: reusable CI/CD workflows,
release-train tooling, security gates and Cloud Deploy & Cloud Run
deployment infrastructure for all seven service repos (`fastapi-backend`,
`web-bff`, `design_service`, `image-studio`, `brand_research`,
`frontend-v2`, `operations-console`), on GCP projects `radicai` (non-prod)
and `radicai-production` (prod), region `us-central1`.

Instead of each service repo holding its own CI/CD logic, every repo
holds only a thin descriptor (`.radic/service.yml`) and a thin caller
workflow; the actual pipeline logic — quality gates, security scanning,
deploy manifests, the release train, and the Cloud Deploy/Cloud Run
rollout itself — lives once, here, as a single versioned, exact-tag-pinned
engine and a set of reusable GitHub Actions workflows.

**Authoritative design source**: Confluence space **RAITSDA**, page tree
rooted at "Centralised CI/CD: Overview and Architecture". This repo's
constitution (`.specify/memory/constitution.md`) formalises that design
into 12 non-negotiable principles — read it first if you're changing
anything here.

## How this repo is built

Every feature here is built through [GitHub Spec
Kit](https://github.com/github/spec-kit)'s specification-driven workflow:
a feature spec (`spec.md`) is written and validated *before* any
implementation plan (`plan.md`) or task breakdown (`tasks.md`) exists, and
every line of code traces back to a specific task, requirement, and test.
Each feature's full paper trail — spec, research decisions, data model,
quickstart, tasks — lives under `specs/<NNN>-<feature-name>/`.

Where the approved architecture leaves an implementation detail
unspecified, each feature documents an explicit, flagged convention in its
own `research.md` (and flags it for confirmation) rather than guessing
silently or blocking on it — the same discipline applied consistently from
feature 001 onward.

## Status

Engine features shipped so far, each merged to `dev` through its own PR:

| Feature | What it added |
|---|---|
| `001-engine-scaffold` | The `radic-delivery` CLI skeleton, service descriptor schema, policy exceptions ledger |
| `002-ci-gate-workflow` | `gate evaluate --mode ci-gate` + the reusable `ci.yml` workflow |
| `003-security-scanning` | `security scan` (gitleaks/hadolint/trivy, report-only) + the reusable `security.yml` workflow |
| `004-deploy-yaml-lint` | `deploy lint` for Cloud Run service YAML |
| `005-release-command-parser` | `release command`'s slash-command grammar + authorization check |
| `006-release-commands-workflow` | Wires `release command` into the real `release-commands.yml` reusable workflow |
| `007-change-note-capture` | `notes write`/`notes check` — change-note records and the release-note completeness gate |
| `008-release-propose` | `release propose` — selects ready tickets/commits into a draft release manifest |

See `engine/README.md` for the full CLI command-surface table (what's
implemented vs. pending, including known option-surface gaps against the
architecture) and the count of reusable workflows built vs. pending.

## Getting started

```bash
cd engine
uv sync                              # install engine dependencies
uv run radic-delivery --help         # list every command group (implemented and planned)
uv run pytest -q                     # engine unit tests
uv run ruff check . && uv run mypy src/
```

See `engine/README.md` for each command's behaviour and exit-code
contract, and `specs/<feature>/quickstart.md` for a runnable walkthrough
of any individual feature.

## Repo layout

```text
.github/workflows/     # reusable workflows (workflow_call) + this repo's own CI
actions/               # composite actions (setup-engine, setup-security-tools, ...)
engine/                # the radic-delivery CLI (Python, typer) — see engine/README.md
schemas/               # service/release-manifest/change-note/test-result JSON Schemas
templates/callers/     # thin example caller workflows for service repos
policy/                # exceptions.yml — the one skip-budget exceptions ledger
specs/                 # Spec Kit feature specs: spec.md, plan.md, tasks.md per feature
.specify/              # Spec Kit tooling + this repo's constitution
```

## Non-negotiable rules

See `CLAUDE.md` for the full list (pipeline logic lives only here and is
exact-tag pinned; build once and promote only by digest; fail-closed with
zero skip budget; keyless WIF-only identity; separated human+machine
approval for prod; the engine CLI is the only path to `gcloud`/Terraform)
and `.specify/memory/constitution.md` for the rationale behind each one.
