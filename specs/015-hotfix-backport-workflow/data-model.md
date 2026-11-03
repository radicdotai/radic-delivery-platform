# Phase 1 Data Model: Hotfix Backport Workflow

## Entity: BackportResult (`release/backport.py`, new)

- `branch`: str — the new branch created from `--into` (e.g. `dev`)
- `picked_commits`: `list[str]` — the `release_sha` values that
  cherry-picked cleanly, in chronological order
- `conflicted_commits`: `list[str]` — the `release_sha` values whose
  cherry-pick conflicted and were skipped (research.md D1)
- `conflicts`: bool (property) — `len(conflicted_commits) > 0`,
  matching Reference 2's own named output exactly

## Relationship to prior features' entities

Reads (never writes) an already-cut, succeeded hotfix release manifest
(specs/008/009's shape) — trusted as given, the same discipline
`release finalise` (specs/011) and `gate evaluate --mode release-gate`
(specs/013) already apply to an incoming manifest. Reuses
`release/git_history.py`'s existing `cherry_pick`, `abort_cherry_pick`,
`create_branch_from`, and `commit_timestamp` primitives unchanged
(specs/009) — no new git primitive needed.

## Entity: Hotfix Backport Workflow (`.github/workflows/hotfix-backport.yml`, new — not a Python entity)

One job, `workflow_run` of `prod` (research.md D5): gated on
`conclusion == 'success'` and the originating branch ending `-hf`; calls
`release backport`, pushes the resulting branch, opens a PR into `dev`
(draft, naming conflicted commits, when `conflicts` is true).
