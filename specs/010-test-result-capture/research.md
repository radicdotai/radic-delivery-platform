# Phase 0 Research: Test-Result Record Capture

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| Test-result record fields: `schema_version`, `repo`, `environment`, `release_id`, `digest`, `commit`, `suite`, `runner`, `scope`, `target_url`, `started_at`, `finished_at`, `result`, `counts`, `skip_budget`, `tags_run`, `seeded_tenant`, `cloud_deploy`, `run_url`, `report_uri` | Reference 3: Schemas, Identity and Commands, §1 "Test-result record" |
| `records put-test-result` CLI surface: `--file PATH`; `--release-id ID` — "Validate and store a test-result record beside the manifest" | Reference 3, §6 CLI table |
| Storage location: `releases/<id>/test-results/<environment>-<repo>-<suite>.json` in `radicdotai/delivery-records` | Reference 3, §1 |
| "Prod approval requires every suite named in the descriptor for stage to have a record with `result: pass` for the exact digest; a missing record is a failure" (why these records matter downstream) | Reference 3, §1 |

## Design decisions made for this plan

### D1 — Correct `schemas/test-result.schema.json`: the same class of placeholder gap as specs/007/008

Feature 001 wrote this schema as a deliberately loose stub (same
"stable contract for a later feature" description as the other two
schemas this platform has now corrected). Porting Reference 3 §1's full
schema verbatim, this feature corrects real mismatches, not just
omissions:

| Field | Feature 001's stub | Reference 3's actual schema | This feature |
|---|---|---|---|
| `release_id` | `{"type": "string", "pattern": ...}`, always required alongside everything else | `{"type": ["string", "null"], "pattern": ...}` | corrected to nullable — a dev-environment run happens continuously, often before any release has even been proposed |
| `scope` | absent entirely | `{"enum": ["regression", "full", "smoke"]}` | added |
| `target_url` | absent | `{"type": "string", "format": "uri"}` | added |
| `tags_run` | absent | `{"type": "array", "items": {"type": "string"}}` | added |
| `seeded_tenant` | absent | `{"type": "string"}` | added |
| `cloud_deploy.verify` | `{"type": "boolean"}` | `{"enum": ["pass", "fail", "not-run"]}` | corrected to the real three-value enum — a boolean can't represent "not yet run" |
| `cloud_deploy` required | none (whole object loosely typed) | `["pipeline", "release", "rollout", "rollout_state"]` | tightened — a `cloud_deploy` object with none of its identifying fields present isn't meaningfully "a Cloud Deploy record" |
| conditional rules | one (`environment == "stage"` → `scope: "full"` required) | two — the above, **plus** `counts.skipped >= 1` → `result` must be `"fail"` | the second rule (this platform's zero-skip-budget principle, expressed at the schema level) was missing entirely from the stub — added via `allOf` |
| `additionalProperties` | `true` | (not stated either way in the captured schema text, but every other schema this platform ships uses `false`) | tightened to `false`, matching specs/007's and specs/008's own corrections |

Both conditional rules are expressed as two independent entries in an
`allOf` array (rather than one combined `if`/`then`), since they trigger
on unrelated conditions (`environment` vs. `counts.skipped`) and can both
apply to the same record simultaneously — combining them into a single
condition would make one rule silently depend on the other being
evaluated first, which the architecture never implies.

Flagged for confirmation and a future Confluence proposal, the same
"confirm before formalizing" treatment given to every prior schema
correction (specs/007's `jira_key`/`None`, specs/008's `approvals`/
`digests`/`gates`/`release_sha` relaxation).

### D2 — Local storage path for a release-less (dev) record (flagged, new)

The architecture's own storage path (`releases/<id>/test-results/...`)
has no defined form when `release_id` is `null` — a dev-environment run
has no `<id>` to key by. **Decision**, flagged for confirmation: store
such a record under a fixed `dev` segment in place of `<id>` —
`<out_dir>/releases/dev/test-results/<environment>-<repo>-<suite>.json`
(`<repo>` is the repository's short name without the `radicdotai/` org
prefix, matching Reference 3's own worked example
`stage-frontend-v2-e2e-full-stage.json` exactly) — rather than inventing
a synthetic release identifier or a differently-shaped path. Since `environment` is always `"dev"` for a release-less
record (the schema's stage rule makes a release-less stage record
impossible — D1), the directory segment and the filename's own
environment prefix both read `dev`, which is a deliberate, visible
redundancy rather than a bug: it keeps the path's shape identical to a
real release's regardless of branch, so nothing downstream needs a
special case to find either kind.

### D3 — No `builder.py`: this command reads a complete record, it doesn't construct one

Unlike specs/007's `notes write` (which builds a record from several
explicit CLI flags, since a PR's title/summary/etc. are small, typeable
facts), this record has far more fields, several of them nested objects
(`counts`, `skip_budget`, `cloud_deploy`) — Confluence's own CLI table
reflects this by giving `records put-test-result` only `--file PATH`,
never per-field flags. The calling CI step that captures a test run
already has the complete record as a file from whatever test runner
produced it; this feature's job is purely to validate and store it, not
to assemble it from parts.

### D4 — The `--release-id` cross-check (FR-007)

When the record's own `release_id` is present and `--release-id` is also
given, they must match exactly, refused otherwise — the same consistency
discipline specs/009's `release cut` already applies to its own
`--release-id`. When the record's `release_id` is `null` (a dev run) and
`--release-id` is given anyway, this is **not** treated as a mismatch —
a dev run can legitimately be associated with a prospective future
release by the caller without the record itself needing to assert one;
only an actual value-vs-value disagreement is refused.

### D5 — Exit codes and testing strategy

Any validation failure (a schema violation, the skip-budget rule, the
stage-completeness rule, or the `--release-id` cross-check) is
`ExitCode.INVALID_INPUT` — the same classification `notes write`/
`release cut` already give their own structurally-invalid inputs. A
successful store is `ExitCode.OK`. Like specs/007 and specs/009, this
feature has no external-dependency boundary at all: every test is a real,
unmocked local file read/write and a real schema validation call, with
inline fixtures covering each conditional rule individually.
