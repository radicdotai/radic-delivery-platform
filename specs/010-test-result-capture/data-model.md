# Phase 1 Data Model: Test-Result Record Capture

## Entity: Test-Result Record (`schemas/test-result.schema.json`, corrected per research.md D1)

The schema-valid JSON object this feature validates and stores — every
field already defined by the architecture, now fully enforced:

- `schema_version`: `1` (const, required)
- `repo`: `radicdotai/<name>` pattern, required
- `environment`: `"dev"` or `"stage"`, required
- `release_id`: a `YYYY.MM.DD-N`(-hf) string, **or `null`** (research.md D1
  — required key, nullable value)
- `digest`: `sha256:<64-hex>`, required
- `commit`: 40-hex commit SHA, required
- `suite`: non-empty string, required
- `runner`: `"pytest"` or `"playwright"`, required
- `scope`: `"regression"` | `"full"` | `"smoke"`, optional in general, but
  required and fixed to `"full"` specifically when `environment ==
  "stage"` (added, D1)
- `target_url`: URI, optional (added, D1)
- `started_at` / `finished_at`: ISO 8601 date-time, required
- `result`: `"pass"` | `"fail"` | `"error"` | `"timeout"`, required
- `counts`: required object — `total`/`passed`/`failed`/`skipped`/
  `quarantined`, all non-negative integers, all required
- `skip_budget`: required object — `allowed` (const `0`), `exceptions`
  (array of `EXC-####` strings)
- `tags_run`: array of strings, optional (added, D1)
- `seeded_tenant`: string, optional (added, D1)
- `cloud_deploy`: required object (every environment, including dev, is
  Cloud-Deploy-managed), itself requiring `pipeline`, `release`,
  `rollout`, `rollout_state` (tightened, D1); `verify` is `"pass"` |
  `"fail"` | `"not-run"` (corrected from boolean, D1)
- `run_url`: URI, required
- `report_uri`: string, optional

Conditional rules (`allOf`, D1):
1. `environment == "stage"` → `release_id` is a real string (not `null`)
   and `scope == "full"`, both required.
2. `counts.skipped >= 1` → `result == "fail"`, required.

`additionalProperties: false` (D1).

## Entity: PutResult (internal, `records/result.py`)

- `ok`: bool
- `local_path`: the path the record was written to, or `None` when `ok`
  is `False`
- `result`: the record's own `result` field value, carried through for
  convenience, or `None` when `ok` is `False`
- `issues`: list of `{path, message}` — which part of the record was
  invalid, and why (mirrors specs/007's/008's `BuildIssue`/`ManifestIssue`
  shape for consistency across the CLI)
- `upload_status`: always `"not_available"` on success (research.md,
  spec FR-009) — never omitted, never fabricated as `"uploaded"`

## Relationship to prior features' entities

No dependency on specs/002-006/008-009's gate/security/deploy/release-
command/release-propose/release-cut entities. Mirrors specs/007's
`ChangeNoteBuildResult`/`WriteResult` shape and precedent exactly
(validate-then-write, local-path-mirrors-real-path, honest
`not_available` upload reporting) applied to a different, larger record.
A future release-gate feature (not built here) will read the records this
feature writes — Technical Design already documents this dependency, the
same kind specs/008 recorded for change-note records feeding `release
propose`.
