# Phase 0 Research: Release Selection and Draft Manifest

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| Release manifest fields: `schema_version`, `release_id`, `kind`, `status`, `repo`, `created_at`, `initiator`, `base`, `selection` (`tickets[]`/`non_jira_prs[]`/`held_back[]`), `approvals`, `digests`, `cloud_deploy`, `gates`, `main`, `backport`, `rollback`, `platform_tag` | Reference 3: Schemas, Identity and Commands, §3 "Release manifest" |
| `release_id` pattern `^[0-9]{4}\.[0-9]{2}\.[0-9]{2}-[0-9]+(-hf)?$`; `status` enum including `proposed` (this feature's only output status) | Reference 3, §3 |
| `release propose` CLI surface: `--repo SLUG`; `--base dev or main`; `--tickets KEYS`; `--non-jira-prs NUMBERS`; `--dry-run` — "Select tickets and commits, apply the dev-green gate, validate and add the listed non-Jira PRs, write the draft manifest" | Reference 3, §6 CLI table |
| Selection algorithm, three steps: collect merged `dev` commits since the last release marker, grouped by Jira key *through the change-note records*; filter to eligible work (Jira "Ready for Review", all PRs of the ticket merged, dev-green); finalize the selection | Technical Design, §8 |
| dev-green reads the dev test-result records; a commit is eligible only if its dev deploy (or a later one) passed regression and e2e | Technical Design, §6.2 |
| A commit with no change-note record stops the cut (`release cut`'s concern, not this feature's, since this feature only ever considers commits that already have a record) | Release and Operations Runbook |
| `held_back` reason text example: `"not Ready for Review"` | Reference 3, §6 worked example |
| `non_jira_prs[]` entries show `"reason": "MISSING"` / `"second_approver": null` before `release command nonjira` fills them in | Reference 3, §6 worked example |

## Design decisions made for this plan

### D1 — Correct `schemas/release-manifest.schema.json`: the architecture's own schema conflates pipeline stages

Like `change-note.schema.json` before specs/007, this schema is feature
001's intentionally loose placeholder ("a stable contract for a later
feature"). Porting Reference 3's full, authoritative version verbatim
would make it **impossible for this feature to ever produce a valid
`proposed` manifest**, because that schema's required-ness describes the
manifest's shape across its *entire* lifecycle, not what exists at
proposal time specifically:

- Top-level `required` includes `approvals`, `digests`, `gates` — but
  `approvals.release_pr` (itself required) needs `number`/`approver`,
  which don't exist until a release PR is opened and reviewed; `digests`
  needs a stage/prod digest that doesn't exist until a build happens.
  Nothing at proposal time can populate these.
- `selection.tickets[].commits[]` requires `release_sha` — but a commit
  isn't cherry-picked onto a release branch (and so has no `release_sha`)
  until `release cut` runs, a separate, later feature.
- `selection.non_jira_prs[].second_approver` is typed as a plain string
  (required) — but the architecture's own worked example shows it as
  `null` before someone approves the release PR, which is itself typed
  wrong in the source schema (the same class of gap as specs/007 D1's
  `jira_key`/`None` contradiction).

**Decision**, flagged for confirmation exactly like specs/007's D1 (and,
like that one, to be proposed back to Confluence once this feature
lands, not asserted as already-settled):

- Drop `approvals`, `digests`, `gates` from the top-level `required` array
  — keep them as optional properties with their full nested shape intact,
  for `release cut`/later features to populate and require once those
  stages are real.
- Relax `selection.tickets[].commits[]`'s and `selection.non_jira_prs
  []commits[]`'s required fields to `dev_sha` only — `release_sha`/
  `cherry_pick_x` stay in the schema (optional), populated only once
  `release cut` performs the actual cherry-pick.
- Correct `non_jira_prs[].second_approver`'s type to `["string", "null"]`
  — this feature writes `null` for every entry (never yet approved at
  proposal time), matching the architecture's own worked example exactly.
- `non_jira_prs[].reason` stays required; this feature writes the literal
  string `"MISSING"` when the caller hasn't supplied one yet — again
  matching the worked example verbatim, not inventing a new sentinel the
  way specs/007 had to for `jira_key`.
- Correct `base` from a bare `{"type": "string"}` (feature 001's stub
  guess) to the authoritative `{branch, sha}` object shape.
- Tighten `additionalProperties` to `false`, matching every other schema
  this platform ships, once the above relaxations make a real `proposed`
  manifest capable of validating at all.

Every *other* field's shape (full `selection`/`cloud_deploy`/`gates`
nesting) is ported verbatim from Reference 3 §3, unchanged — only the
required-ness conflicts above are corrected, and only because this
feature is the first to actually need the schema to validate something
real.

### D2 — Git reachability: the one real, unmocked dependency this feature has

FR-001's "commit reachable from `--base`'s HEAD" and the spec's own
Assumptions ("knowing where the previous release left off... supplied
explicitly... when not supplied, every available change-note record... is
a candidate") become, concretely: this feature runs against a real local
git checkout (`--repo-dir PATH`, reusing the exact flag name Reference
3's own `tests inventory` command already uses for the same concept — not
an invented name), and computes the set of commit SHAs reachable from
`--base`'s resolved HEAD, optionally excluding everything already an
ancestor of an explicit `--since-sha SHA` (the "last release marker" —
no mechanism for finding this automatically is described anywhere in the
architecture, per the Technical Design review already done for this
feature; omitted, it defaults to "no exclusion," per spec Edge Cases).
This is implemented as two plain `git log --format=%H <ref>` calls (base
HEAD; `--since-sha`, if given) and a set difference — no shelling out to
anything beyond fixed, parameterised git subcommands (Principle VII),
tested against a real local git repository built with real `git init`/
`commit`/branch commands in `tmp_path`, never mocked.

### D3 — Change-note records: read from the same local layout `notes write` already produces

Confirmed no new storage convention is invented: `--change-notes-dir PATH`
(default `.`) reads `<dir>/change-notes/<repo>/<sha>.json`, the exact
local-write structure specs/007's `notes write --out-dir` already
produces (specs/007 research.md D4). A record for a different `repo` than
requested, or a malformed/unreadable file, is skipped and reported, never
silently treated as a candidate nor a hard failure of the whole run.

### D4 — Readiness and dev-green: explicit input, with the most consequential default polarity choice this platform has made

Per spec Assumptions, this is the single biggest external-dependency
boundary drawn so far. Concretely:

- `--tickets KEYS` (Reference 3's own flag name, reused — not a new one):
  the explicit, caller-supplied list of ticket keys considered ready for
  this release. A candidate ticket grouped from change-note records but
  **not** in this list is held back with reason `"not Ready for Review"`
  (the architecture's own exact wording) — fail-closed by default,
  consistent with this platform's posture everywhere else (e.g. Principle
  III's zero skip budget): readiness must be asserted, never assumed.
- `--dev-green-failed SHAS` (new, flagged): the explicit, caller-supplied
  list of commit SHAs known to have failed the pre-release regression
  check. A candidate **not** listed here is assumed passing — the
  opposite default polarity from `--tickets`, deliberately: most commits
  that reach `dev` are expected to pass; requiring an allow-list here
  would make this feature unusable without exhaustively re-asserting
  passing status for every single commit, for no safety benefit (a
  missed `--dev-green-failed` entry is a caller error already visible in
  whatever upstream process tracks regression results, not a silent
  platform-side assumption).
- A ticket with any held-back commit (not ready, or failed dev-green) is
  held back as a whole, with the more specific of the two reasons stated
  when both could apply (not-ready is checked first, since it is the
  cheaper, more fundamental gate).

### D5 — `release_id` assignment: caller override, single-digit default, real sequencing deferred

No mechanism for finding "the next unused `-N` for today" is described
anywhere in the architecture (confirmed during this feature's own
Technical Design review, and already noted when specs/006 researched
`release_command`). **Decision**: `--release-id ID` (optional override,
for a human preparing a same-day second release or a hotfix id ending
`-hf`); when omitted, this feature computes `<today's date>-1` — always
`-1`, since there is no reachable shared history to count prior releases
against. Real cross-run sequencing is explicitly deferred, the same kind
of deferral specs/005 already recorded for comment-id idempotency.

### D6 — `--dry-run` gets real, testable meaning despite no live storage existing yet

Since the real `delivery-records` write is already out of scope (FR
scope, spec Assumptions) regardless of this flag, `--dry-run` is given a
locally meaningful effect rather than being a no-op: without it, the
validated manifest is also written to `<out-dir>/releases/<release_id>.json`
(mirroring the real `releases/<id>.yaml` key structure locally, the exact
same "mirror the real path, write locally" precedent as specs/007 D4);
with it, the manifest is only reported, never written anywhere. Every
proposal is still computed identically either way — `--dry-run` only
gates the local write, consistent with its name and the architecture's
own description of it as a preview mechanism.

### D7 — Testing strategy

Candidate-loading, grouping, and the ready/held-back/non-jira split are
pure functions over inline fixtures — no asymmetry, same simplicity as
specs/007. Git reachability (D2) is this feature's one real dependency,
exercised for real against a `tmp_path` git repository (real commits,
real branches) rather than mocked — the same "real tool where one
exists" discipline as specs/002's sample-repo tests and specs/003's
scanner tests, applied here to `git` itself.
