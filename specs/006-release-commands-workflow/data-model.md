# Phase 1 Data Model: Release-Commands Reusable Workflow

## Entity: WorkflowOutcome (new, `release_commands/workflow_outcome.py`)

The pure mapping of a feature-005 `CommandCheckResult` onto the three facts
the GitHub Actions contract actually needs. Produced by
`map_outcome(result: CommandCheckResult) -> WorkflowOutcome`, a total
function — every possible `CommandCheckResult` maps to exactly one
`WorkflowOutcome`, per research.md D2/D3.

- `command`: `"remove"` | `"add"` | `"nonjira"` | `"abort"` | `"waive"` |
  `"none"` — the architecture's typed `command` output. `research_close`
  and `malformed` both map to `"none"` (research.md D2); `not_a_command`
  also maps to `"none"`.
- `outcome`: `"applied"` | `"rejected"` | `"ignored"` — the architecture's
  typed `outcome` output. `accepted` → `applied`; `malformed` and
  `unauthorized` → `rejected`; `not_a_command` → `ignored`.
- `reply_body`: `str | None` — the exact text to post back on the pull
  request, or `None` when `classification == "not_a_command"` (no reply is
  ever posted for that case, per spec FR-006). Always names the specific
  command/reason for every other classification, drawing on
  `CommandCheckResult.form`/`args`/`detail`.

This is exposed as three additive keys —  `workflow_command`,
`workflow_outcome`, `reply_body` — on `radic-delivery release command
--format json`'s existing payload, alongside feature 005's unchanged
`classification`/`form`/`args`/`detail` keys.

## Mapping table (authoritative; see research.md D2 for the two flagged gaps)

| `classification` | `form` | `command` | `outcome` | reply posted |
|---|---|---|---|---|
| `not_a_command` | — | `none` | `ignored` | no |
| `malformed` | — | `none` | `rejected` | yes |
| `unauthorized` | `release_remove` | `remove` | `rejected` | yes |
| `unauthorized` | `release_add` | `add` | `rejected` | yes |
| `unauthorized` | `release_nonjira` | `nonjira` | `rejected` | yes |
| `unauthorized` | `release_abort` | `abort` | `rejected` | yes |
| `unauthorized` | `release_waive_dev_green` | `waive` | `rejected` | yes |
| `unauthorized` | `research_close` | `none` | `rejected` | yes |
| `accepted` | `release_remove` | `remove` | `applied` | yes |
| `accepted` | `release_add` | `add` | `applied` | yes |
| `accepted` | `release_nonjira` | `nonjira` | `applied` | yes |
| `accepted` | `release_abort` | `abort` | `applied` | yes |
| `accepted` | `release_waive_dev_green` | `waive` | `applied` | yes |
| `accepted` | `research_close` | `none` | `applied` | yes |

## External contract entities (not engine code — the GitHub Actions surface this feature implements)

These are the architecture's own typed names (Reference 2 §3.5); this
feature's job is to make the engine's output line up with them exactly,
not to invent new ones.

- **`release-commands` reusable workflow inputs**: `descriptor`,
  `issue_number`, `comment_id`, `actor` — all caller-supplied, typed
  strings/numbers, never free-text shell content.
- **`release-commands` reusable workflow outputs**: `command`, `outcome`
  (both populated directly from `WorkflowOutcome` above), `reply_comment_id`
  (the id GitHub assigns to the posted reply — populated by the new
  composite action, not the engine, since the engine never calls the
  GitHub API).
- **Secrets**: `DELIVERY_BOT_APP_ID`, `DELIVERY_BOT_PRIVATE_KEY` (used to
  mint the GitHub App installation token for every API call this workflow
  makes); `ATLASSIAN_URL`/`ATLASSIAN_EMAIL`/`ATLASSIAN_API_TOKEN` (declared
  and threaded through per the architecture's contract; not called by any
  real integration in this feature — see spec.md Assumptions).

## Relationship to prior features' entities

Builds directly on feature 005's `CommandCheckResult` (consumed, never
modified) and reuses feature 002's `setup-engine` composite action
unchanged. No descriptor, exceptions-ledger, gate/security/deploy-lint
entity is involved.
