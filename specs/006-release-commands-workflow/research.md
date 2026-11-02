# Phase 0 Research: Release-Commands Reusable Workflow

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| Caller job triggers on `issue_comment: types: [created]`, gated to only run when the comment is on a pull request; calls `release-commands.yml@v1.0.0` with inputs `descriptor`, `issue_number`, `comment_id`, `actor` | Reference 2: Workflow Contracts, §2.3 "release.yml caller" |
| Reusable workflow inputs `issue_number`/`comment_id`/`actor` (+`descriptor`); outputs `command` (`remove\|add\|nonjira\|abort\|waive\|none`), `outcome` (`applied\|rejected\|ignored`), `reply_comment_id`; secrets `DELIVERY_BOT_APP_ID`, `DELIVERY_BOT_PRIVATE_KEY`, `ATLASSIAN_URL`, `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN`; permissions `issues: write`, `pull-requests: write`, `contents: write` | Reference 2: Workflow Contracts, §3.5 "release-commands contract" |
| Comment body passed to the parser via a file/environment variable, never interpolated into a `run:` shell string; a team-membership check against `release-managers`, using the release App token; every command acknowledged by a PR reply comment; processing is idempotent, keyed by comment id | Reference 2: Workflow Contracts, §3.3 "Technical Design" |
| The already-built classification/authorization logic (six forms, case-insensitive verb, first-line-only, Tech-Lead-only `waive dev-green`) is unchanged by this feature | specs/005-release-command-parser (merged) |

## Design decisions made for this plan

### D1 — Split the GitHub-API mechanics (untestable here) from the outcome mapping (pure, testable)

Every prior GitHub-Actions-adjacent feature (002, 003) drew the same line:
real subprocess/tool execution gets a real, unmocked test wherever the tool
is actually available in this sandbox; anything that needs a live external
service this sandbox doesn't have credentials for gets written for real and
validated structurally instead. Fetching a comment, resolving team
membership, resolving the Tech Lead, and posting a reply are all real
GitHub API calls — none of them can be exercised end-to-end here, since
there is no GitHub App installation or webhook delivery in this sandbox.

What *can* and must be tested for real is the decision logic sitting
between "feature 005 already told us the classification" and "the workflow
needs three specific typed facts" — mapping a `CommandCheckResult` onto
`command`/`outcome` and composing the reply text. That mapping has two real
edge cases (D2 below) that are easy to get wrong silently, so it is written
as one pure function, `release_commands/workflow_outcome.py::map_outcome`,
fully unit-tested with no fixture, no subprocess, no network — the same
simplicity feature 005 established for `grammar.py`/`authorization.py`.

It is exposed by adding three keys (`workflow_command`, `workflow_outcome`,
`reply_body`) to `release command`'s existing JSON payload, computed
unconditionally alongside the existing `classification`/`form`/`args`/
`detail` fields. This is additive, not a breaking change to feature 005's
`CommandCheckResult.to_dict()` shape or its own tests (which only assert
specific keys are present with specific values, never that the payload has
*exactly* those keys) — so the new workflow's steps read everything they
need from one existing CLI invocation via `jq`, with zero new CLI
subcommands and zero changes to feature 005's own test files beyond adding
assertions for the new keys.

### D2 — The `command`/`outcome` mapping table, including the two gaps the architecture's contract leaves open

| `CommandCheckResult.classification` | `form` | `workflow_command` | `workflow_outcome` | reply posted? |
|---|---|---|---|---|
| `not_a_command` | — | `none` | `ignored` | No — FR-006 requires silence |
| `malformed` | — (never set) | `none` | `rejected` | Yes, naming what was invalid |
| `unauthorized` | `release_remove`/`release_add`/`release_nonjira`/`release_abort`/`release_waive_dev_green` | mapped 1:1 to its short verb (`remove`/`add`/`nonjira`/`abort`/`waive`) | `rejected` | Yes, naming the authorization reason |
| `unauthorized` | `research_close` | `none` (see gap below) | `rejected` | Yes |
| `accepted` | one of the five `release_*` forms | mapped 1:1 to its short verb | `applied` | Yes, confirming what was applied |
| `accepted` | `research_close` | `none` (see gap below) | `applied` | Yes |

Two real gaps in the architecture's own contract, both flagged for
Tech-Lead/platform-maintainer confirmation the same way feature 004's
`parity.allow` convention was flagged and later formalized:

- **`research_close` has no slot in the `command` output enum.** The
  enum (`remove|add|nonjira|abort|waive|none`) only has room for the five
  `/release` verbs, yet Reference 2 §3.3's own prose says this workflow
  "also handles `/research close`." **Decision**: report `research_close`
  as `command: none` regardless of whether it was accepted or refused,
  since `none` already means "no release-train command" and
  `research close` is not a release-train action — it closes the research
  phase, a different lifecycle concept the architecture doesn't fold into
  the release-command enum. `outcome` still reports `applied`/`rejected`
  accurately, and the reply comment (the actual detail channel a human
  reads) always states the real command name. Nothing here loses
  information a human sees; it only coarsens the one machine-readable
  summary field down to what its enum can actually express. **Not**
  silently extending the enum, per Reference 2 §1's own rule that a
  workflow contract's typed outputs are a breaking-change surface.
- **A `malformed` attempt has no recognizable form at all.** `ParsedCommand`
  (feature 005) only sets `form` on `status="recognized"` — a malformed
  attempt's detail names the verb that was *tried*, but that's prose, not
  a typed value. **Decision**: `command: none` for every malformed case,
  consistent with "a command only occupies the `command` slot once it's
  been recognized as one of the six forms" — not ambiguous, just recorded
  here for completeness of the table.

### D3 — An identity-lookup failure is a workflow step failure, not a fourth `outcome` value

Spec FR-008 requires that a failure to resolve team membership or the
Tech Lead be distinguishable from an ordinary "unauthorized" refusal — but
the architecture's `outcome` enum (`applied|rejected|ignored`) has no slot
for "could not determine authorization" either, and inventing a fourth
value would be the same kind of silent contract-breaking change D2 already
ruled out for `command`. **Decision**: when the team-membership or
Tech-Lead lookup step itself fails (the GitHub API call errors, or the
Tech-Lead-identity source described in D4 is unset/unreadable), that step
fails the job outright — visible in the Actions run as a failed step,
distinct from any of the three typed `outcome` values a *completed* check
can produce — after first posting a reply telling the commenter the check
could not be completed and to retry or contact the platform team. The
engine is never invoked in this path at all (it requires `--release-
managers`/`--tech-lead` as resolved, non-empty values), so no engine code
needs to special-case this; it is purely a workflow-YAML control-flow
decision (fail the step; still attempt a best-effort reply first).

### D4 — Team-membership and Tech-Lead-identity lookup mechanism (flagged convention)

The architecture specifies only that there is "a team-membership check...
with the release App token" (Reference 2 §3.3) — not the exact API call,
not where the Tech Lead's identity comes from at all. **Decision**,
flagged for confirmation exactly like feature 004's `parity.allow`
mapping:

- **Release-managers team membership**: GitHub's REST API "Get team
  membership for a user" endpoint (`GET /orgs/{org}/teams/release-
  managers/memberships/{username}`) — a single, precise check for the one
  username that matters (the commenter), not a full roster listing — called
  once per triggering comment using the release bot's GitHub App
  installation token (minted from `DELIVERY_BOT_APP_ID`/
  `DELIVERY_BOT_PRIVATE_KEY`). A `404` response means "not a member" (an
  ordinary, expected outcome); any other non-2xx response is treated as a
  lookup failure per D3, not silently folded into "not a member." No
  caching — this is a low-frequency, human-triggered event, not a hot path.
- **Tech Lead identity**: a repository **variable** (`vars.RELEASE_TECH_LEAD`,
  not a secret — a GitHub username is not sensitive), since the
  architecture names no other candidate source and this platform already
  distinguishes secrets from non-sensitive configuration elsewhere (e.g.
  `policy/exceptions.yml` is a plain, non-secret file).

Both are genuinely new conventions this feature invents to fill a gap the
architecture leaves open, not something this plan treats as settled until
a platform maintainer confirms it (same treatment, same confidence level,
as feature 004's D3 before its own confirmation).

### D5 — The comment-fetch/reply composite action stays declarative; all branching logic stays in the engine

`actions/post-release-command-reply/action.yml` does exactly two things:
fetch a comment's body by id into a file (via `gh api`, output redirected
to a file — never captured into a shell variable that could be
re-interpolated), and post a reply (via `gh api` or `gh pr comment`,
reading the reply text from a file/input, never a shell-interpolated
string built from untrusted content). This mirrors feature 005's research
D4 concern exactly, just on the posting side rather than the parsing side:
a composite action with "almost no logic" is also almost impossible to get
an injection vulnerability into. Every branch (what the reply says, which
outputs get set) is decided beforehand, in the engine, per D1.

### D6 — Testing strategy, closing the `engine-ci.yml`/`zizmor` gap, and a discovered pre-existing backlog (scope correction)

Confirmed in this sandbox: `uvx zizmor <path>` runs zizmor 1.31.1 with no
system package install required (`brew`/apt not needed), so there is no
reason this repo's own `engine-ci.yml` can't run it for real, the same way
it already runs `actionlint` since feature 001. `CLAUDE.md`'s own command
list has documented `actionlint && zizmor .github/workflows/` since the
repo's very first commit, but `engine-ci.yml` only ever wired up
`actionlint` — this feature closes that gap.

Running `zizmor` against this feature's own new files
(`.github/workflows/release-commands.yml`,
`actions/post-release-command-reply/action.yml`,
`templates/callers/release.yml`) during implementation surfaced real,
fixable findings — every `${{ }}` expression originally written directly
into a `run:` block (high-confidence `template-injection`), the minted
GitHub App token not being scoped to specific permissions (`github-app`),
and the caller job having no explicit `permissions:` block
(`excessive-permissions`) — all fixed in this feature's own files (routed
through `env:` blocks; added `permission-issues`/`permission-pull-
requests`/`permission-contents` to `create-github-app-token`; added an
explicit `permissions:` block to the caller). Two lower-severity,
precedent-matching findings were suppressed with documented inline `#
zizmor: ignore[...]` comments rather than silently worked around:
`unpinned-uses` on the `radicdotai/...@v1.0.0` reusable-workflow reference
and on `actions/create-github-app-token@v1` (this repo pins third-party and
own-platform actions by tag, not hash — a deliberate, repo-wide convention,
not an oversight specific to this feature; see Principle I's explicit
"exact-tag pinned" language), and `dangerous-triggers` on the caller's
`issue_comment` trigger (a real pattern match, but this workflow's whole
design — no checkout of PR code, comment body only ever read via API into
a file, never executed — is the documented mitigation, per D1/D5).

**Scope correction discovered during this step**: running `zizmor` against
the *entire* `.github/workflows/`/`actions/`/`templates/callers/` tree (not
just this feature's new files) surfaces a substantial **pre-existing**
backlog in specs/001-004's already-merged workflow artifacts: unredacted
`template-injection` findings in `ci.yml`, `security.yml`,
`actions/setup-engine/action.yml`, and `actions/setup-security-tools/
action.yml` (the same "interpolate `${{ inputs.* }}` directly into `run:`"
pattern this feature's own D1 fix addresses, written before this
convention was zizmor-verified), plus the same tag-vs-hash `unpinned-uses`
pattern on `actions/checkout@v4`, `astral-sh/setup-uv@v3`, `actions/setup-
node@v4`, and `raven-actions/actionlint@v2`, and a missing `persist-
credentials: false` on every `actions/checkout` call (`artipacked`). This
is real and worth fixing, but it spans four already-reviewed, already-
merged features — fixing it here would be scope creep into work this
feature did not touch and was not asked to revisit. **Decision**: the new
`engine-ci.yml` step runs `zizmor` scoped to only this feature's three new
files (not the whole tree), at `--min-severity medium` (the pre-existing
`self-repository` "help"-tier style suggestion on `./actions/...`
references — already present in `ci.yml`/`security.yml` too — stays below
that threshold and isn't treated as a failure here or there). The
pre-existing backlog above is recorded here, explicitly, as a flagged gap
for a dedicated future "workflow security hardening" pass across specs/
001-004's artifacts — not fixed, and not silently left undiscovered.

### D7 — Post-merge correction: `--actor` flag naming, confirmed against Confluence (2026-11-02)

While researching the next feature (release propose/cut), Confluence
Reference 3: Schemas, Identity and Commands (pageId 419954699) was read
directly for the first time against this feature's actual CLI contract —
it had only been read secondhand (via a research fork's summary) when
specs/005 was specified. Reference 3's command table names this command's
author-identity flag `--actor LOGIN`; this feature (and specs/005 before
it) had instead built `--author`. There is no substantive reason for the
divergence — it is a naming inconsistency, not a deliberate improvement —
so the CLI, its tests, `release-commands.yml`, and both specs' quickstart
docs were corrected to `--actor` to match the authoritative source exactly,
rather than carrying the inconsistency forward or rewriting Confluence to
match an arbitrary choice.

By contrast, two other differences found in the same comparison — this
feature's `--release-managers`/`--tech-lead` explicit-identity-input design
(Confluence's table shows no such flags, implying the engine would resolve
identity itself) and its `classification`/`form`/`args`/`workflow_command`/
`workflow_outcome`/`reply_body` field shape (Confluence's illustrative
example shows a flatter `command`/`key`/`outcome`/`reply` shape) — were
reviewed and confirmed as genuine, deliberate improvements over Confluence's
illustrative sketch: the explicit-identity-input split keeps this command's
core logic pure and unit-testable with zero GitHub API dependency (the same
split already used for `gate evaluate` not installing a toolchain and
`security scan` not installing scanners), and the richer field shape
actually generalizes across all six command forms, where a flat `key` field
would not (e.g. `release nonjira`'s `pr`/`reason` pair has no natural `key`).
These were pushed back into Confluence itself (Reference 3 §6, new §6.1)
rather than into this codebase, per the architecture's own stated
precedence (CLAUDE.md: Confluence is the authoritative design source) and
the same confirm-before-formalizing treatment given to specs/004's
`parity.allow` convention.
