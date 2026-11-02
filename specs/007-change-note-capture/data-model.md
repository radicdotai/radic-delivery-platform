# Phase 1 Data Model: Change-Note Record Capture and Release-Note Gate

## Entity: Change-Note Record (`schemas/change-note.schema.json`, tightened per research.md D1)

The schema-valid JSON object this feature constructs and validates:

- `schema_version`: `1` (const, required)
- `repo`: `radicdotai/<name>` pattern, required
- `sha`: 40-hex commit SHA, required
- `pr_number`: integer, optional
- `type`: one of `feature`/`fix`/`improvement`/`chore`/`security`/`docs`/`internal`, required
- `audience`: one of `customer`/`internal`/`none`, required
- `title`: 3-140 characters, required
- `summary`: up to 1000 characters, required
- `jira_key`: either the ticket-key pattern `^[A-Z]{2,10}-[0-9]+$` or the
  exact literal `"None"` (research.md D1's schema correction), required
- `linked_prs`: array of cross-repo references, each matching
  `^radicdotai/[A-Za-z0-9_.-]+#[0-9]+$`, optional
- `migration`: boolean, default `false`, optional
- `uat_escape`: boolean, optional
- `regression_test_added`: boolean, optional
- `author`: string, optional
- `merged_at`: ISO 8601 date-time, optional
- `dev_deploy`: optional nested object (`digest`, `cd_release`,
  `post_deploy_result`) — accepted by the schema, never populated by this
  feature (spec Assumptions; a later feature's concern)

`additionalProperties: false` (research.md D1).

## Entity: ChangeNoteBuildResult (internal, `notes/builder.py`)

- `ok`: bool
- `record`: the validated record dict, or `None` when `ok` is `False`
- `issues`: list of `{path, message}` — which field, and why, when invalid
  (mirrors `descriptor/validator.py`'s `ValidationIssue` shape exactly, for
  consistency across the CLI)

## Entity: WriteResult (internal, `notes/writer.py`)

- `local_path`: the path the record was actually written to (always
  populated on success)
- `upload_status`: always `"not_available"` (research.md D4) — never
  omitted, never fabricated as `"uploaded"`

## Entity: ReleaseNoteCheckResult (internal, `notes/check.py`) — the feature's second primary output

- `classification`: `has_jira_key` | `explicit_none` | `incomplete`
  (research.md D2's parsing convention)
- `jira_key`: the normalised (upper-cased) ticket key, when
  `classification == "has_jira_key"`, else `None`
- `blocking`: bool — whether `--require-jira-key` was set for this run
- `passed`: bool — `True` for `has_jira_key`/`explicit_none` always;
  for `incomplete`, `True` when not blocking, `False` when blocking (spec
  FR-008/FR-009)
- `detail`: human-readable explanation, always populated for
  `incomplete`, naming exactly what's missing

## Relationship to prior features' entities

None — like feature 005, this feature has no dependency on any descriptor,
exceptions-ledger, gate/security/deploy-lint, or release-command entity.
Its only external contract is the change-note record schema itself
(already present, now tightened) and the two CLI subcommands' own inputs.
A future feature (`release propose`, per Technical Design's documented
dependency) will read change-note records this feature produces, but does
not yet exist and is not built by this feature.
