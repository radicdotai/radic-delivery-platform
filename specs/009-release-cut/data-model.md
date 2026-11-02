# Phase 1 Data Model: Release Branch Creation and Cherry-Pick

## Entity: CutResult (internal, `release/result.py`)

The outcome of one `release cut` attempt:

- `ok`: bool
- `manifest`: the updated manifest dict on success, or the **unchanged**
  original manifest dict when `ok` is `False` (never partially updated)
- `reason`: `None` on success, else one of `"release_id_mismatch"` |
  `"hotfix_mismatch"` | `"status_mismatch"` | `"missing_change_note"` |
  `"cherry_pick_conflict"` | `"git_error"`
- `detail`: human-readable detail naming the specific mismatch/commit
- `failed_sha`: the specific commit SHA responsible, when `reason` is
  `"missing_change_note"` or `"cherry_pick_conflict"`, else `None`
- `dry_run`: bool — whether this result came from a preview

## Entity: Release Manifest fields this feature populates (extends specs/008's entity)

On a successful, non-dry-run cut, these fields (already present in the
schema, left unpopulated by specs/008's `propose`) are set:

- `release_branch`: `"release/<release_id>"`
- `release_head`: the new branch's final commit SHA after every
  cherry-pick
- `status`: `"cut"`
- For every commit object under `selection.tickets[].commits[]` and
  `selection.non_jira_prs[].commits[]`: `release_sha` (the commit's new
  SHA on the release branch after `cherry-pick -x`) and
  `cherry_pick_x: true`

## Relationship to prior features' entities

Reads and rewrites specs/008's `release` manifest in place (the exact
schema specs/008 corrected — no further schema change needed by this
feature). Re-verifies specs/007's change-note records exist locally, by
path only (does not reconstruct or revalidate their own internal schema
— that already happened when they were written). No dependency on
specs/002-006's gate/security/deploy/release-command entities.
