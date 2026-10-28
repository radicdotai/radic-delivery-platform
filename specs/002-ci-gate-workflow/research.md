# Phase 0 Research: Central CI Reusable Workflow (`ci-gate` mode)

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| Reusable workflow name `ci`, inputs `mode` (`ci-gate`/`release-gate`), `run_mutation`, `descriptor` (default `.radic/service.yml`); outputs `gate_result`, `coverage_total`, `test_inventory_uri`, `skipped_count`, `deploy_lint` | Reference 2: Workflow Contracts and Caller Templates |
| Thin per-service caller workflows pin the reusable workflow to an exact tag (`@v1.x.y`) | Technical Design; Reference 2 |
| Zero skip budget; a skip is only acceptable via a dated, approved exception | Quality, Security and Governance (constitution Principle III) |
| Per-service tools are declared in the descriptor, not hardcoded by the platform | Reference 1 (feature 001's schema: `quality.lint.tool`, `quality.typecheck.tool`, `quality.unit.runner`) |

## Design decisions made for this plan

### D1 — Command construction is a pure function, separate from execution

`gate/commands.py` maps a validated descriptor to a list of `ToolInvocation`
(`check_name`, `argv: list[str]`) values — one each for lint, type-check, and
unit tests — using only the descriptor's own typed fields:

| Descriptor says | Command constructed |
|---|---|
| `quality.lint.tool: ruff` | `["uv", "run", "ruff", "check", "."]` |
| `quality.lint.tool: eslint` | `["npm", "run", "lint"]` (service repos are expected to expose a `lint` script; a service's own `package.json` owns the exact eslint invocation — this platform does not hardcode eslint flags) |
| `quality.typecheck.tool: mypy` | `["uv", "run", "mypy", "."]` |
| `quality.typecheck.tool: tsc` | `["npm", "run", "typecheck"]` |
| `quality.unit.runner: pytest`, no `marker_expr` | `["uv", "run", "pytest", "--cov", "-q"]` |
| `quality.unit.runner: pytest`, `marker_expr: "not slow"` | `["uv", "run", "pytest", "--cov", "-q", "-m", "not slow"]` |
| `quality.unit.runner: vitest`, no `script` | `["npx", "vitest", "run", "--coverage"]` |
| `quality.unit.runner: vitest`, `script: "test:coverage"` | `["npm", "run", "test:coverage"]` |

This keeps Principle VII intact: nothing here interprets a descriptor field
as a shell string — every branch is a fixed, reviewed argv list keyed off an
already-schema-constrained enum or (for `marker_expr`) an already
regex-constrained string substituted as one argv element, never concatenated
into a shell line.

**Rationale**: separating "what command would this descriptor produce" from
"actually run it" makes the former exhaustively unit-testable (both
toolchains, every branch) without needing either toolchain installed.

**Alternatives considered**: a single templated shell string per tool — rejected,
since it reintroduces exactly the "arbitrary command in configuration" shape
Principle VII forbids, even if the template itself lives in this repo rather
than the descriptor.

### D2 — Coverage and skip-count parsing: small regex parser, no new dependency

`gate/parsers.py` extracts:
- Coverage percentage(s) from `pytest-cov`'s terminal summary (a `TOTAL`
  line ending in a percentage) and from `vitest --coverage`'s summary table
  (`% Lines`/`% Stmts`/`% Branch`/`% Funcs` row) — each via one targeted,
  unit-tested regex against captured sample output, not a general-purpose
  parser.
- The skipped-test count from `pytest`'s own one-line result summary
  (`N passed, M skipped, ...`) and from `vitest`'s summary (`Tests  N passed
  | M skipped`).

**Rationale**: consistent with feature 001's "small, deterministic, no
heavyweight dependency" approach (research.md there made the same call for
`jsonschema` vs. inventing one). A structured report (`--cov-report=json`,
`pytest-json-report`) would be more robust but adds a dependency this
platform would then have to mandate every Python service repo install,
which is itself a scope decision belonging to a later feature (descriptor
schema changes), not this one.

**Alternatives considered**: requiring `--cov-report=json`/`pytest-json-report`
system-wide — rejected for this feature as an undiscussed new mandatory
per-service dependency; regex parsing against the tool's own default,
already-stable terminal output needs nothing new from any service repo.

**Risk accepted and documented**: a regex parser is more brittle to a tool's
output-format changes than a structured report would be. This is an
accepted, documented trade-off for this increment, not an oversight — revisit
if a future feature needs more than "did it pass the floor" fidelity.

### D3 — GitHub Actions mechanics: local-path `uses:` in a reusable workflow

Verified Actions behavior (not a guess): when workflow `A` in repository `X`
calls a reusable workflow via `uses: radicdotai/delivery-platform/.github/
workflows/ci.yml@v1.x.y`, and that reusable workflow (`ci.yml`, defined in
`delivery-platform`) itself contains a step `uses: ./actions/setup-engine`,
that local-path reference resolves against **delivery-platform at the exact
ref the caller pinned** — not against the caller's own repository — with no
explicit checkout needed purely to resolve the action reference itself.

However, resolving the *action* this way does not put this repository's
*files* (`engine/`, `schemas/`, `policy/`) on the runner's filesystem — those
are plain files the CLI reads at runtime, not something Actions stages for
you. So `actions/setup-engine/action.yml` must itself:

1. `actions/checkout` `radicdotai/delivery-platform` at `${{
   github.action_ref }}` (the exact ref under which this composite action is
   executing — this correctly carries through the ref chain even though the
   *caller's* own checkout, done separately by `ci.yml`, is of the *caller's*
   repository, not this one) into a subdirectory, by convention
   `.platform-engine/`.
2. Install `uv` (`astral-sh/setup-uv`).
3. `uv sync --project .platform-engine/engine`.

`ci.yml` therefore has two checkouts in sequence: the default
`actions/checkout@v4` (no `repository:`/`ref:` — checks out the *calling*
service repo's own ref, which is what needs linting/testing) happens first,
then `actions/setup-engine` performs the second, scoped checkout of this
platform's own code. Both coexist in the same job without conflict because
they target different paths.

**Rationale**: this is the only mechanism that lets a service repo's thin
caller (`templates/callers/ci.yml`) pin an exact platform version with a
single `uses: ...@v1.x.y` line and nothing else, per Principle I — the
engine's code at that exact version is fetched by the reusable workflow
itself, not by the caller.

### D4 — `paths.py`'s repo-root search already generalises; no change needed

Feature 001's `engine/src/radic_delivery/paths.py` finds the repository root
by walking upward from **both** `Path(__file__).resolve()` (the installed
package's own location) and `Path.cwd()`, accepting the first candidate
whose directory contains both `schemas/` and `policy/`.

In the real deployment this feature designs for, the workflow runs `uv run
--project .platform-engine/engine radic-delivery gate evaluate --descriptor
.radic/service.yml` with its working directory left at the *caller* repo's
checkout root (so the relative `--descriptor` path resolves correctly there).
`Path.cwd()` in that case is the caller repo root — which does **not**
contain `schemas/`/`policy/` and correctly fails that candidate. But
`Path(__file__).resolve()` is wherever `uv` placed the installed
`radic_delivery` package, which is always somewhere inside
`.platform-engine/` (this platform's own checkout) — walking upward from
there correctly finds `.platform-engine/schemas/` and `.platform-engine/
policy/`.

**Conclusion**: confirmed by re-reading the existing implementation; no
change to `paths.py` is needed for this feature. This is recorded here so a
future reader does not "fix" this into a single-candidate search and quietly
break the real deployment shape.

### D5 — Scope boundary: this feature runs tools, it does not install them

`gate evaluate` assumes `ruff`/`mypy`/`pytest` (or `eslint`/`tsc`/`vitest`,
reached via `npm run <script>`) are already on `PATH` / resolvable via the
service's own project manager. `ci.yml` is responsible for getting there
(installing language runtimes and the service's own declared dependencies)
*before* invoking `gate evaluate` — this split keeps `gate evaluate` testable
locally (as this feature's test suite does) without needing a full CI runner,
exactly as feature 001's commands needed no GCP access to be fully testable.

### D6 — Which exception covers a unit-test skip is a new, documented convention

The approved architecture defines `quality.post_deploy.exception_id` for
deployed-environment regression suites, but does not say how an exception
covering a *unit-test* skip (the one this feature's gate actually observes)
should be identified. This feature adopts a specific, narrow convention
(data-model.md: an exception with `scope: quality.unit.skip` owned by the
service) rather than leaving the behaviour unspecified or silently reusing
`quality.post_deploy.exception_id` for an unrelated purpose. This is flagged
for Tech Lead confirmation, same treatment as feature 001's 30-vs-60-day
exception-expiry discrepancy — not a blocking ambiguity, since zero skips
(the overwhelmingly common case) needs no exception lookup at all.

## Open items carried forward (not resolved by this feature)

- `release-gate` mode and `run_mutation` remain unimplemented by design (spec
  FR-011/FR-012) until their dependencies (a stage test-result record; the
  `quality.mutation` config) exist.
- `deploy_lint` and `test_inventory_uri` outputs remain placeholders until
  the `deploy lint` and `tests inventory` engine commands are built.
