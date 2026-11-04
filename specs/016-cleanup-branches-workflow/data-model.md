# Phase 1 Data Model: Cleanup Workflow (branches scope only)

## `CleanupBranchesResult`

Returned by `backport(...)`-style pure function `cleanup_branches(...)` in
`engine/src/radic_delivery/cleanup/branches.py`.

| Field | Type | Notes |
|---|---|---|
| `deleted` | `list[str]` | Branch names actually deleted (empty on a dry run, per research.md D-decisions) |
| `kept` | `list[KeptBranch]` | Every evaluated candidate not deleted, with its reason |
| `dry_run` | `bool` | Echoes the run mode back in the result, so a report is self-describing |

### `KeptBranch`

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | The branch name |
| `reason` | `Literal["not_yet_merged", "too_recent"]` | FR-004's two specific, named reasons |

Protected branches (`main`, `dev`, the currently checked-out branch) are
never added to either `deleted` or `kept` — they are excluded before
evaluation (research.md D4), not reported as a third kind of "kept"
outcome, since they were never real candidates.

`to_dict()` shape (for `--format json`):

```json
{
  "deleted": ["release/2026.10.01-1"],
  "kept": [
    {"name": "release/2026.11.01-1", "reason": "not_yet_merged"},
    {"name": "release/2026.10.28-1", "reason": "too_recent"}
  ],
  "dry_run": false
}
```

## CLI surface

`radic-delivery cleanup branches --repo-dir PATH [--retention-days N] [--dry-run/--no-dry-run] [--format json|text]`

- `--retention-days` default `14` (research.md D3)
- `--dry-run` default `true` (spec FR-005, Reference 2's own stated default)
- Exit codes: `OK` always once candidates are evaluated; `INFRA_ERROR` on
  an unresolvable `--repo-dir` or git failure (research.md D6)
