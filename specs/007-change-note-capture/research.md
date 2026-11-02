# Phase 0 Research: Change-Note Record Capture and Release-Note Gate

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| Change-note record fields: `schema_version`, `repo`, `sha`, `pr_number`, `type`, `audience`, `title`, `summary`, `jira_key`, `linked_prs`, `migration`, `uat_escape`, `regression_test_added`, `author`, `merged_at`, `dev_deploy` | Reference 3: Schemas, Identity and Commands, §2 "Change-note record" |
| `notes write` CLI surface: `--repo SLUG`; `--sha SHA`; `--pr N`; `--bucket NAME` — "Write the change-note record (port of the existing capture scripts)" | Reference 3, §6 CLI table |
| `notes check` CLI surface: `--pr-body-file PATH`; `--require-jira-key` — "Release-note check (warning first, then blocking)" | Reference 3, §6 CLI table |
| Real storage location: `gs://radicai-release-records/change-notes/<repo>/<sha>.json` | Reference 3, §2 |
| "A PR with `Jira: None` is stored with `jira_key` set to `None` and is selectable only through the release input `non_jira_prs`" | Reference 3, §2 |

## Design decisions made for this plan

### D1 — Tighten `schemas/change-note.schema.json` to the architecture's full shape, correcting feature 001's placeholder

Feature 001 wrote this schema as a deliberately loose stub, explicitly
labelled in its own `description` field as "a stable contract for a later
feature; not read or written by the engine scaffold." This feature is that
later feature, so the schema is tightened to match Reference 3 §2's full
JSON Schema exactly, correcting several real mismatches the placeholder
got wrong (not just omissions):

| Field | Feature 001's stub | Reference 3's actual schema | This feature |
|---|---|---|---|
| `schema_version` | absent | `const: 1`, required | added, required |
| `pr_number` | absent | `type: integer` | added |
| `linked_prs` items | `{"type": "integer"}` | `{"type": "string", "pattern": "^radicdotai/[A-Za-z0-9_.-]+#[0-9]+$"}` | corrected to the string cross-repo-reference pattern — a bare PR number loses which repo it's in, which the architecture's own field (`linked_prs`, plural, cross-repo) exists specifically to carry |
| `migration` | `{"type": "object"}` | `{"type": "boolean", "default": false}` | corrected to boolean |
| `author` | absent | `{"type": "string"}` | added |
| `merged_at` | absent | `{"type": "string", "format": "date-time"}` | added |
| `dev_deploy` | `{"type": "object"}` (bare) | full nested shape (`digest`, `cd_release`, `post_deploy_result`) | tightened to the full shape now, even though this feature doesn't populate it (spec Assumptions) — no reason to leave it loose when the authoritative shape is already fully known, and it avoids a second reconciliation pass later |
| `additionalProperties` | `true` | `false` | tightened to `false`, matching every other schema this platform ships (`service.schema.json`, `exceptions.schema.json`) |

**The one genuine contradiction in the architecture itself**: Reference 3's
own formal JSON Schema for `jira_key` is `{"type": "string", "pattern":
"^[A-Z]{2,10}-[0-9]+$"}` — required, and with no accommodation for the
literal value `None` the same page's prose says gets stored for a PR
shipped without a ticket. A pattern-only schema would reject the literal
string `"None"` outright, contradicting the prose on the same page.
**Decision**: this feature's schema change relaxes `jira_key` to accept
either the ticket-key pattern or the exact literal string `"None"` (via
`anyOf`), so the documented behavior is actually representable — this is a
correction to the architecture's own formal schema, not an invented
convention, and (like feature 004's `parity.allow` enum and feature 006's
`--actor` naming) is flagged here for confirmation and will be proposed as
a Confluence correction once this feature lands, the same "confirm before
formalizing" treatment given to every previous such finding.

### D2 — The Jira-reference text convention `notes check` recognizes (flagged, new)

The architecture states the *existence* of a `Jira: KEY` / `Jira: None`
convention (Reference 3 §2's prose) but never specifies its exact textual
shape in a PR body — is it a trailer line at the end, anywhere in the
body, case-sensitive, requiring the literal word "Jira"? **Decision**,
flagged for confirmation exactly like feature 006's team-membership-lookup
convention: `notes check` recognizes a line, anywhere in the PR body
(not restricted to a trailing position, since PR body templates in
practice put metadata at the top — see Reference 3 §5's release PR body
template style, which front-loads a `Kind: ... | Initiator: ... | Base:
...` metadata line), matching `^Jira:\s*(.+)$` case-insensitively on the
label. The captured value is then classified as: the explicit opt-out if
it case-insensitively equals `none`; a recognized Jira reference if it
matches the ticket-key pattern `^[A-Z]{2,10}-[0-9]+$` (case-insensitive on
input, normalised to upper — the same normalisation rule Reference 3 §4
already states for the slash-command grammar's own `key` token, reused
here for consistency); anything else present after `Jira:` (a typo, an
unrecognized shape) is treated the same as "neither" — present but not
recognizable, not silently accepted.

### D3 — `notes write`'s CLI surface: Confluence's four flags plus the explicit fields the schema actually requires

Reference 3's CLI table lists only `--repo`/`--sha`/`--pr`/`--bucket` for
`notes write`, but the change-note schema requires `type`, `audience`,
`title`, `summary`, and `jira_key` too — the table is abbreviated, the
same conclusion already reached for `release command` (feature 006's
research.md D7: "the table isn't necessarily exhaustive, only its *named*
flags are a hard contract"). Per FR-010, this feature never fetches a
PR's title/body/author from GitHub itself, so every schema-required field
needing a real value (type, audience, title, summary, jira_key) must be an
explicit CLI option, not derived. **Decision**: add `--type`, `--audience`,
`--title`, `--summary`, `--jira-key` as required options, and
`--linked-prs`, `--migration`/`--no-migration`, `--uat-escape`/`--no-uat-
escape`, `--regression-test-added`/`--no-regression-test-added`,
`--author`, `--merged-at` as optional ones mapping directly to the
schema's optional fields — exactly mirroring D7's precedent, not a new
pattern.

### D4 — Local write location: `--out-dir`, defaulting to the same relative path shape the real bucket uses

Since the real `gs://radicai-release-records/change-notes/<repo>/<sha>.json`
upload is out of scope (no credentials in this environment), `notes write`
needs a local write target. **Decision**: a `--out-dir PATH` option
(default `.`) under which the record is written at
`change-notes/<repo>/<sha>.json` — mirroring the real bucket's own key
structure exactly (just rooted locally instead of at `gs://radicai-
release-records/`), so a future feature that actually performs the real
upload only needs to add the upload step, not restructure how the record
is laid out on disk first. The result always reports the real upload
status as `not_available`, the same honest-reporting precedent as
specs/003's Snyk/image-scanning fields — never silently omitted, never
fabricated as successful.

### D5 — Exit codes: `notes write` follows the existing invalid-input precedent; `notes check` follows the existing gate precedent

`notes write`: a schema-invalid set of inputs is `ExitCode.INVALID_INPUT`
(2) — the same classification `descriptor validate`/`gate evaluate` already
give a malformed/invalid input, since nothing here is a policy judgment,
it's a structural validity check. A successful write is `ExitCode.OK`.

`notes check`: in non-blocking (warning) mode, the command always exits
`ExitCode.OK` regardless of completeness — the same "a report-only check
never fails the command" precedent specs/003's `security scan` already
established, consistent with Principle IX. In blocking mode
(`--require-jira-key`), an incomplete PR body exits `ExitCode.
POLICY_FAILURE` (3) — the same classification `gate evaluate` already
gives a failed quality gate, since this is a policy/completeness judgment
about otherwise-valid input, not a malformed-input case.

### D6 — Testing strategy: no asymmetry this time — everything here is really exercisable

Unlike features 002/003 (real-subprocess-tool asymmetry) or 006 (real
GitHub-API asymmetry), this feature has no untestable external dependency
at its core: schema validation is a real, local `jsonschema` call; the
local file write is a real, unmocked filesystem operation (exercised via
`tmp_path`); PR-body classification is real text parsing. The only
genuinely unexercisable path is the real GCS upload, which this feature
doesn't attempt at all (D4) rather than mocking a credential this sandbox
doesn't have.
