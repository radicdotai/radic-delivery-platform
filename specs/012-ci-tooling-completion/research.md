# Phase 0 Research: CI Tooling Completion

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| `tests inventory` CLI surface: `--repo-dir PATH`; `--out PATH` — "Count tests per suite, including skipped and quarantined" | Reference 3, §6 CLI table |
| `policy rulesets-diff` CLI surface: `--repo SLUG`; `--dir PATH` — "Compare live rulesets with committed JSON" | Reference 3, §6 CLI table |
| `ci` workflow's `test_inventory_uri` output: "artifact name of per-suite counts including skips" — confirms this command's output is a consumed CI artifact, not itself a gate | Reference 2, §3.1 |
| Rulesets applied via `gh api` "from `delivery-platform/rulesets/`"; "A nightly job runs `gh api repos/radicdotai/<repo>/rulesets` and diffs against the committed files (drift report)" | Reference 2, §5 |
| The five real ruleset JSON bodies (`dev-trunk`, `main-prod-line`, `release-branches`, `product-tags`, `platform-tags`) | Reference 2, §5.1-§5.5, verbatim |
| Worked invocation: `radic-delivery policy rulesets-diff --repo $REPO --dir rulesets/ --format json`, run right after `gh api repos/$REPO/rulesets --jq '.[] | {id, name, enforcement}'` | Reference 2, §5.6 |
| `quality.quarantine` policy: `max_days` const `7`, `max_percent_of_tests` const `2` | `schemas/service.schema.json` (specs/001) |
| Real pytest/vitest command construction and terminal-summary parsing already exist | `engine/src/radic_delivery/gate/{commands,parsers,runner}.py` (specs/002) |

## Design decisions made for this plan

### D1 — `tests inventory` reuses `gate evaluate`'s own test machinery, independently

Reference 2's `test_inventory_uri` output suggests the `ci` workflow produces
this artifact from the same unit-test run `gate evaluate`'s own `unit` check
already executes — but this platform's command groups are each
independently invocable (no command silently depends on another already
having run in the same process). **Decision**: `tests inventory` builds and
runs its own, separate real invocation of the descriptor's unit-test
command. `gate/commands.py`'s own `_unit_command()` was private and only
reachable through `build_commands()`, which also requires a full
lint+typecheck+unit descriptor shape this feature has no business
depending on — **decision**: made public as `unit_command()`, used
directly here alongside `gate/runner.py::run()` and `gate/parsers.py::
parse_test_run()` — no duplicated logic, but a genuinely separate process
execution, consistent with every other command in this platform being
runnable entirely on its own. `total` is computed as
`passed + failed + skipped` (Reference 2/3 don't give `total` a separate
source, and this is the only internally consistent definition available).

Reference 2's "per-suite" wording has no concrete multi-suite mechanism
anywhere in this platform (a descriptor's `quality.unit` names exactly one
runner/command) — **decision, flagged**: this feature treats a service's
one unit-test command as exactly one suite, reported under the fixed label
`"unit"`. A real multi-suite descriptor shape is out of scope; nothing here
forecloses adding one later.

### D2 — The quarantine ledger: a new, flagged convention

No prior feature or Confluence reference defines a concrete mechanism for
"which tests are currently quarantined" — only the *policy* exists
(`quality.quarantine.max_days`/`max_percent_of_tests`, both fixed
constants) and `schemas/test-result.schema.json`'s `counts.quarantined`
field description ("run non-blocking and reported"). **Decision**: a new
ledger, `policy/quarantine.yml` (validated against a new
`schemas/quarantine.schema.json`), following the exact same shape and
loading discipline as `policy/exceptions.yml`/`exceptions.py` (specs/001):
a flat list of entries, each naming `service` (matches a descriptor's
`service.name`), `test_id` (a free-form, human-readable string identifying
the test — informational only; this feature does **not** cross-check it
against the real test run's own output, the same "trusted as given"
discipline `policy/exceptions.yml`'s own `scope`/`owner` strings already
get), `reason`, `jira_key`, and `quarantined_since` (a date). `tests
inventory` filters the ledger to the service being inventoried, and
classifies each matching entry as `active` (still within the fixed 7-day
window from `quarantined_since`, as of `--as-of`, default today — new,
optional flag, same precedent as `policy exceptions check`'s own `--as-of`)
or `expired` (past it) — reusing `exceptions.py::check()`'s exact
date-comparison idiom. The percentage cap
(`max_percent_of_tests`, const `2`) is reported informationally as
`within_quarantine_share_cap` (`(active + expired) / total <= 2%`, using
the real run's own `total`) — a fact, not something this feature enforces
or blocks on (spec Assumptions: inventory reports, it doesn't gate).

This is a genuinely new convention, not derived from any existing
specification — flagged here explicitly for confirmation, the same
treatment given to every other platform-level gap this project has had to
fill in (e.g. specs/004's `parity.allow` mapping, specs/011's
`--expected-tag`).

### D3 — Launch failure is a distinct, named outcome

Mirroring `gate/runner.py::RunOutcome.launched` and `gate/evaluator.py`'s
own `"not_executable"` handling exactly: when the descriptor's unit-test
command cannot even be launched, `tests inventory` reports this
distinctly (`launched: false`, all counts `null`) rather than ever
reporting a launched-and-ran suite with all-zero counts (spec FR-003,
Edge Case). Exit code: `ExitCode.INFRA_ERROR`. A descriptor that fails its
own schema validation is a separate, earlier failure:
`ExitCode.INVALID_INPUT`, mirroring `gate evaluate`'s own ordering. A
successful launch is always `ExitCode.OK`, regardless of the pass/fail/
skip/quarantine facts it reports — `tests inventory` is a report, not a
gate (spec Assumptions).

### D4 — `rulesets-diff`'s comparison: keyed by `name`, projected to meaningful fields

GitHub's real `gh api repos/<repo>/rulesets` response carries fields a
locally-authored, not-yet-applied committed JSON file never has (`id`,
`node_id`, `created_at`, `updated_at`, `source_type`, `source`, `_links`,
`current_user_can_bypass`) — a raw deep-equality comparison would report
every ruleset as "changed" purely from these GitHub-assigned fields being
absent on the committed side (spec FR-005, Acceptance Scenario 5).
**Decision**: both the committed and the live rulesets are first projected
to the five fields the committed JSON itself defines —
`target`, `enforcement`, `conditions`, `rules`, `bypass_actors` — and only
this projection is compared, the same "ignore known housekeeping fields,
compare the meaningful subset" approach `deploy/parity.py` already
established for Cloud Run manifests (specs/004). Matching across the two
sides is by each ruleset's own `name` string (there is no earlier-created,
shared numeric id to match on — the committed side never has one). A
ruleset name appearing twice in the committed `--dir` is refused outright
(`ExitCode.INVALID_INPUT`, spec FR-006, Edge Case) rather than silently
picked from one file.

`--repo SLUG` (Reference 3's own flag) is accepted and carried through into
the result payload for context, but does not itself change the comparison
— the committed `--dir` is a shared template set (not repo-specific; the
same five files apply across every service repo plus this platform's own
repo for `platform-tags`), and the supplied `--live-file` is already
scoped to one repo by virtue of being that repo's own API response.
**Decision, flagged**: this feature does not itself know or enforce which
of the five rulesets are expected to apply to which specific `--repo` —
that judgment is left to whoever reads the report (spec Assumptions,
Principle VIII's bot-proposes/people-decide split).

### D5 — The live ruleset state is explicit file input, never a live call

`gh auth status` in this sandbox shows no authenticated GitHub host (no
`GH_TOKEN` either) — `gh api repos/<repo>/rulesets` cannot be made for
real here, the same external-dependency boundary every other live-GitHub/
GCP call in this platform already draws. **Decision**: a new, required,
flagged input, `--live-file PATH` — a local JSON file holding exactly the
array `gh api repos/<repo>/rulesets` would have returned — stands in for
the live call. `rulesets-diff` always exits `ExitCode.OK` once both inputs
are successfully read and compared (a drift report, never a gate per spec
Assumptions and Reference 2's own "drift report" framing); a missing/
unreadable `--dir` or `--live-file`, or a `--live-file` that isn't valid
JSON, is `ExitCode.INFRA_ERROR`.

### D6 — Seeding `rulesets/` with the five real files

`rulesets-diff --dir PATH` has nothing to compare against unless this
repository actually commits the five ruleset JSON files — `rulesets/` is
named in CLAUDE.md's own repo-layout target but nothing has created it yet
(confirmed: no such directory exists in this repo today). **Decision**:
this feature creates `rulesets/{dev-trunk,main-prod-line,release-branches,
product-tags,platform-tags}.json`, each byte-for-byte the JSON body
Reference 2 §5.1-§5.5 gives verbatim (spec FR-009, SC-004) — a
documentation/config-seeding task for this feature, not engine code,
exactly analogous to specs/001 seeding `policy/exceptions.yml`'s own real
bootstrap entries.

### D7 — Testing strategy

`tests inventory` is tested against this platform's own existing, real
fixture repos (`engine/tests/fixtures/sample-repos/python-sample` — a
clean pass; `python-sample-broken-skip` — a real, deliberately skipped
test) rather than inventing new ones, plus a small, local, temporary
quarantine-ledger fixture file per test (never this repo's own real,
currently-empty `policy/quarantine.yml`). `rulesets-diff` is tested
against small, inline, hand-written committed/live JSON fixtures (`tmp_path`
directories and files) covering each of the four drift outcomes plus the
GitHub-housekeeping-field and duplicate-name edge cases — no git, no
external call, pure local file I/O and comparison.
