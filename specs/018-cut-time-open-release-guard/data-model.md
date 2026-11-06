# Phase 1 Data Model: Cut-Time Open-Release Guard

## `other_manifests` (new `cut()` parameter)

`list[dict[str, Any]] | None` — zero or more already-loaded release
manifests (the same shape `cut()`'s own `manifest` parameter already
takes), representing every other manifest the calling workflow already
knows about for potentially-the-same service. Not validated against the
full release-manifest schema by this feature (the caller is assumed to
have already produced or loaded valid manifests via existing tooling);
only `repo`, `release_id`, and `status` are read.

## Open-Release Filter (new, pure logic inside `cut.py`)

An other manifest `m` is a **blocker** against cutting `manifest` with a
given `release_id` when all three hold:

| Condition | Field comparison |
|---|---|
| Same service | `m["repo"] == manifest["repo"]` |
| Different release | `m["release_id"] != release_id` |
| Still open | `m["status"] not in {"finalised", "aborted", "failed"}` |

## `CutReason` (extended, `result.py`)

New member: `"release_already_open"`. Existing members
(`release_id_mismatch`, `hotfix_mismatch`, `status_mismatch`,
`missing_change_note`, `cherry_pick_conflict`, `git_error`) are
unchanged.

## `CutResult` (unchanged shape, new reason value)

No new fields — `reason="release_already_open"` and a `detail` string
naming the blocking release's id and status flow through the existing
`ok`/`manifest`/`reason`/`detail`/`failed_sha`/`dry_run` shape exactly as
every other refusal reason already does.
