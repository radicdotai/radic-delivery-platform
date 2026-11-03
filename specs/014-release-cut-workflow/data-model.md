# Phase 1 Data Model: Release Cut Workflow

## Entity: RenderPrBodyResult (`release/render_pr_body.py`, new)

- `body`: str — the full, deterministic markdown document
- `deploy_files_changed`: `list[str] | None` — `None` when not yet
  determinable (no `release_head`), else the (possibly empty) list of
  changed deploy-relevant paths
- `to_dict()`: `{"ok": True, "body": ..., "deploy_files_changed": ...}`

## Internal shape: ChangeNoteLookup

Not a persisted entity — a per-call lookup over already-written
change-note records (specs/007): for each ticket/non-Jira-PR's first
`dev_sha`, reads `<change-notes-dir>/change-notes/<repo>/<dev_sha>.json`
and extracts `title`/`type`. Missing record → both rendered as `(unknown)`
rather than raising, since a change-note record not yet existing for a
given commit is a real, recoverable state (not every commit necessarily
has one at render time), not a fatal error.

## Relationship to prior features' entities

Reads (never writes) a release manifest (specs/008's corrected
`schemas/release-manifest.schema.json`) and change-note records
(specs/007's `schemas/change-note.schema.json`) — both already-real,
already-validated artifacts this feature trusts as given, the same
discipline `release finalise` (specs/011) already applies to an incoming
manifest. Extends `release/git_history.py` (specs/009/011) with one new
primitive, `changed_paths(repo_dir, base, head) -> set[str]`, a real
`git diff --name-only` call.

## Entity: Release Cut Workflow (`.github/workflows/release-cut.yml`, new — not a Python entity)

Two jobs, per research.md D3:
- `propose`: `workflow_dispatch` — resolves ticket readiness via a real
  Jira JQL query, calls `release propose` + `release render-pr-body`,
  opens/updates the release PR
- `cut`: `pull_request_review` (`submitted`) — validates the approval
  (reviewer ≠ initiator, PR recognised, non-Jira-PR gate satisfied), then
  calls `release cut` for real and updates the PR body

`templates/callers/release.yml` (this repo's own example caller) gains
both jobs alongside its already-existing `commands` job.
