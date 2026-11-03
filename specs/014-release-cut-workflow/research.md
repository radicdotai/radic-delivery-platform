# Phase 0 Research: Release Cut Workflow

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| `release-cut` reusable workflow contract: inputs `base`, `tickets`, `non_jira_prs`, `dry_run`, `hotfix`, `release_id`, `initiator`; outputs `release_id`, `release_branch`, `pr_number`, `selection_count`, `held_back`, `non_jira_prs`, `manifest_path`; secrets `DELIVERY_BOT_APP_ID`/`DELIVERY_BOT_PRIVATE_KEY`/`ATLASSIAN_URL`/`ATLASSIAN_EMAIL`/`ATLASSIAN_API_TOKEN`; permissions `contents: write`, `pull-requests: write`, `issues: write`, `id-token: write` | Reference 2, §3.4 |
| The release PR body template, verbatim (header line, Selection table, "Released without a Jira key" section, Held back table, Migrations/Deploy-files sections, Gates checklist, Commands reference, Links, UAT) | Reference 3, §5 (release PR template) |
| Technical Design §8's strictly-ordered 9-step sequence: propose (step 4) → human gate 1, second-person PR approval (step 5) → cherry-pick onto `release/<id>` (step 6, "happens only after step 5") → verify/stage (step 7) → prod approval (step 8) → advance `main` (step 9) | Technical Design, §8 |
| The bot's subscribed events include `pull_request_review`; its permissions table says "Pull requests: Read and write — open and update the release PR... **read approvals**" | Reference 3, bot-identity section |
| `templates/callers/release.yml` (this repo) currently wires only the `commands` job (`release-commands.yml`, specs/006); the `cut` job Reference 2 §2.3's own fuller example shows was deliberately deferred, not forgotten (specs/006 spec.md Assumptions) | This repo, `templates/callers/release.yml` |
| Change-note records (specs/007) already carry per-commit `title`/`type`/`jira_key`, written regardless of whether a commit has a Jira key (`jira_key: "None"` for non-Jira PRs) | `schemas/change-note.schema.json`, specs/007 |
| The release-manifest schema (specs/008, already corrected) already has `approvals.release_pr.approver`, `approvals.waivers[].kind`, `gates.release_gate.result`, `gates.stage_regression.result`, `cloud_deploy.{project,pipeline,release,rollouts.stage.{state,verify}}`, `main.tag`, `non_jira_prs[].pr_author` — richer than this feature first assumed | `schemas/release-manifest.schema.json` |

## Design decisions made for this plan

### D1 — The post-approval cut trigger: `pull_request_review`, flagged

Reference 2 §2.3's own `release.yml` caller example shows only
`workflow_dispatch` and `issue_comment` triggers — no event that could
plausibly fire the actual cherry-pick after a human approves the release
PR. This is the same kind of "caller template is abbreviated, not
exhaustive" gap this project has repeatedly found and flagged (specs/006
D7, specs/008 D3, specs/011 D1). **Decision**: add a
`pull_request_review` trigger (`types: [submitted]`) to both the caller
template and a new job in `release-cut.yml` itself — supported by two
independent, directly-citable facts (not asserted from nothing): Reference
3's bot-identity page lists `pull_request_review` among the bot's
subscribed events and names "read approvals" in its own permissions
table; and none of specs/005's six already-implemented slash-command
forms (`remove`/`add`/`nonjira`/`abort`/`waive dev-green`/`close`, in
`release_commands/grammar.py`) semantically correspond to "now cut" —
confirming the trigger isn't a slash command at all. Recorded here for
confirmation, the same "flagged, not self-evidently correct" treatment
every comparably-sized gap in this project has received.

### D2 — `release render-pr-body`: a new, real, pytest-tested engine command

Rendering Reference 3's PR template is genuinely non-trivial (seven
distinct sections, a dynamic gates checklist, two data tables) — building
it as inline workflow shell/heredoc would both violate this platform's
own centralise-implementation principle and be effectively untestable in
this sandbox. **Decision**: a new engine command,
`release render-pr-body --manifest PATH --change-notes-dir PATH
--repo-dir PATH [--migrations-chain LIST] [--out PATH] --format json|text`,
pure and deterministic given its inputs (spec FR-003) — the workflow's
only job is to call it and hand its output to `gh pr create`/`gh pr
edit --body-file`.

Fields the manifest/real-git/change-notes already make available for
real, with no further invented input:
- **Title/Type** per ticket (and per non-Jira PR): looked up from the
  existing change-note record for that ticket/PR's first commit
  (`<change-notes-dir>/change-notes/<repo>/<dev_sha>.json`, specs/007's
  own file convention, reused unchanged) — change-note records carry
  `title`/`type` regardless of `jira_key`, so this covers both tables
  with one mechanism, not two.
- **Dev-green** per ticket: always rendered `pass`. `release propose`
  (specs/008) already excludes dev-green-failed commits from selection
  before a manifest is ever produced — a ticket appearing in
  `selection.tickets` at all is, by construction, already dev-green; this
  feature reflects that structural fact rather than inventing a per-ticket
  field the schema doesn't have.
- **Platform tag**: `main.tag` when present, else `TBD` (not yet
  finalised).
- **Gates checklist** (spec FR-002), each independently sourced:
  - "Dev-green gate" — always checked (see above); its "(waived: …)"
    parenthetical reflects whether `approvals.waivers` contains a
    `kind: "dev-green"` entry.
  - "Release PR approved…" — checked iff `approvals.release_pr.approver`
    is present.
  - "Every non-Jira PR has a reason and a second approver…" — checked
    when `selection.non_jira_prs` is empty (rendered as "not applicable",
    matching the real template's own parenthetical) or every entry has a
    non-`"MISSING"` reason and a non-null `second_approver`.
  - "release-gate green…" — checked iff `gates.release_gate.result ==
    "pass"`.
  - "Cloud Deploy stage rollout SUCCEEDED and verify passed" — checked
    iff `cloud_deploy.rollouts.stage.state == "SUCCEEDED"` and
    `.verify == "pass"`.
  - "Stage full regression record… present and green" — checked iff
    `gates.stage_regression.result == "pass"`.
- **Deploy files changed**: real `git diff --name-only <base.sha>
  <release_head>` (new `git_history.py::changed_paths()`), filtered to
  `deploy/skaffold.yaml` and `deploy/run/*.yaml` — the exact paths the
  descriptor's own `cloud_deploy` block names. `None` (rendered "not yet
  determinable") when `release_head` isn't in the manifest yet (spec
  Edge Case, FR-004).
- **Links**: the manifest path (`radicdotai/delivery-records/releases/
  <release_id>.yaml`, a fixed, known naming convention — no live
  `delivery-records` read needed to construct it), the Cloud Deploy
  block when present, and a Jira filter built from the selected tickets'
  own keys (no live Jira call needed to construct the filter string
  itself).

The one field genuinely not derivable from any real source: **"Contains
migrations"** and its chain-order list. **Decision, flagged**: a new,
optional `--migrations-chain LIST` input (comma-separated revision ids,
default empty → "Contains migrations: no") — the same "accept it, don't
fake it" treatment this project gives every fact it cannot compute for
real (e.g. specs/011's `--expected-tag`, specs/013's `alembic_check`).

### D3 — `release-cut.yml`: two jobs, matching Technical Design §8's own ordering

- **`propose`** (`if: github.event_name == 'workflow_dispatch'`, matching
  the existing caller template's own `cut:` job parameterisation by
  `dry_run`): checks out `radicdotai/delivery-records` with the bot App
  token (research.md D4); resolves ticket readiness via a real Jira JQL
  query (`project = <jira_project from the selected tickets' own key
  prefix> AND status = "Ready for Review"`, via `curl`/Basic auth against
  `${ATLASSIAN_URL}/rest/api/3/search`) feeding `--tickets`; calls
  `radic-delivery release propose`; commits the resulting manifest to
  `delivery-records`; calls `release render-pr-body`; opens or updates
  the release PR (`gh pr create`/`gh pr edit --body-file`) against a
  dedicated, disposable `release-proposal/<id>` head branch (research.md
  D5), idempotently (checked for an existing open PR with that exact head
  first). Resolving dev-green-failed commits automatically from a live
  GCS read is explicitly out of scope (spec Assumptions) —
  `--dev-green-failed` is accepted as a manual `workflow_dispatch` input
  instead, empty by default.
- **`cut`** (`if: github.event_name == 'pull_request_review'`, filtered
  to `types: [submitted]` at the caller): refuses immediately (no
  `release cut` call at all) unless the review `state` is `approved`, the
  reviewer is not the PR's own recorded initiator, and the PR is
  recognised as this platform's own release PR (its head branch matches
  the `release-proposal/<id>` convention and a matching manifest exists
  in `delivery-records`) — spec FR-006, Edge Case. Re-renders the gates
  checklist via `release render-pr-body` first and refuses the cut
  outright if the non-Jira-PR gate isn't satisfied (spec FR-007), naming
  why, before ever calling `release cut`. On success, calls `release cut`
  for real, pushes the resulting `release/<id>` branch (a new push — the
  engine itself never pushes, research.md D5), commits the updated
  manifest back to `delivery-records`, and updates the PR body once more
  to reflect the new `cut` status.

Both jobs are added to `templates/callers/release.yml` alongside the
already-existing `commands` job (research.md context: that job already
wires `release-commands.yml`).

### D4 — The release manifest's real store is a GitHub repo, not GCS

Reference 2 §3.4's own permissions comment distinguishes two different
stores: *"id-token: write (**delivery-records access through the App**;
**GCS read of change notes through WIF**)"* — delivery-records (the
release manifest's real home) is accessed through the delivery-bot GitHub
App's own installation token, not WIF; only change-note records are
GCS-backed. This is also the only reading consistent with the PR
template's own Links section, which renders the manifest path in
`owner/repo/path` form (`radicdotai/delivery-records/releases/
2026.11.03-1.yaml`) — a GitHub repository path, not a bucket URI.
**Decision**: both workflow jobs check out `radicdotai/delivery-records`
using the same bot App token `release-commands.yml` already mints, read/
write the manifest YAML there directly (a plain commit + push with the
bot's own identity — no PR needed for this internal record, the same
direct-write trust this architecture already gives the bot for
fast-forwarding `main`), never a live GCS/WIF call. Fetching change-note
records from their own real GCS store remains out of scope (no GCS
upload path exists yet either — specs/007's own Assumptions already
defer it); `render-pr-body`'s `--change-notes-dir` degrades gracefully
to `(unknown)` titles/types when nothing is there yet (already built and
tested in US1), so this gap costs nothing beyond slightly thinner
rendering until a real sync exists.

### D5 — The release PR's head is a dedicated, disposable proposal branch

`release cut` (specs/009, already built and tested) creates
`release/<id>` itself via `create_branch_from()`, which fails outright if
a branch of that name already exists — so the propose job cannot create
`release/<id>` early just to have something to open a PR against, and
`release cut` itself never pushes anything (pushing is deliberately left
to the caller, the same "engine does real work, workflow does real-world
side effects" split this platform draws everywhere else). **Decision,
flagged**: the propose job creates a small, disposable
`release-proposal/<id>` branch (one empty commit from `base`, pushed
once, never force-updated) purely to host the PR/review/approval
mechanism GitHub requires a real head ref for; `release/<id>` itself is
created and pushed only by the cut job, after `release cut` succeeds —
entirely decoupled from the proposal PR's own head, avoiding any
branch-reuse conflict with the already-built engine code. Recorded here
for confirmation, not asserted as self-evidently correct — the
authoritative architecture doesn't spell out this specific mechanism.

### D6 — Testing strategy

`release render-pr-body` (US1) is tested the way every other real engine
command in this project is: `pytest`, against hand-built manifest/
change-note fixtures covering every acceptance scenario, plus a
determinism test (render twice, assert byte-identical output) and a real
git fixture for the deploy-files-changed computation. Verified directly: `ci.yml` itself still carries several
`template-injection`/`unpinned-uses`/`artipacked` findings today, left
unaddressed by specs/002 — this feature's own workflow actually achieves
zero findings on both tools (confirmed by running `zizmor` against each
file before and after fixing), a stricter bar than "the same as before"
literally implies. The one remaining `help`-severity suggestion
(`self-repository`, on `uses: ./actions/setup-engine`) matches the
exact, already-accepted pattern in `ci.yml`/`security.yml` and is left
as-is for consistency, not fixed selectively in only this one feature.

`release-cut.yml`
(US2) is validated the same way `ci.yml`/`security.yml`/
`release-commands.yml` already are — `actionlint` and `zizmor`, zero
findings — since this sandbox has no GitHub Actions runner, live Jira, or
live GCP access to execute it against; this is not a lower bar invented
for this feature, it is the bar every prior reusable workflow in this
platform was already held to.
