# Phase 1 Data Model: Release Selection and Draft Manifest

## Entity: Candidate (internal, `release/candidates.py`)

One already-captured change-note record being considered, after the
repo filter (research.md D3) but before the git-reachability filter
(D2) or the readiness/dev-green split (D4):

- `sha`: commit SHA (from the record's `sha` field)
- `jira_key`: the record's `jira_key` — either a real ticket key or the
  literal `"None"` (specs/007's established sentinel)
- `pr_number`: the record's `pr_number`, when present
- `title`: the record's `title` (carried through for the manifest's own
  tickets list, which the architecture's release PR body template
  displays alongside each ticket)

## Entity: Selection (internal, `release/selector.py`)

The output of grouping and splitting candidates:

- `tickets`: list of `{key, title, commits: [sha, ...]}` — every ready
  ticket, one entry per key, with every one of its commits
- `held_back`: list of `{key, reason}` — `reason` is exactly
  `"not Ready for Review"` or a dev-green-specific message naming the
  failing commit (research.md D4)
- `non_jira_prs`: list of `{pr_number, sha}` for every explicitly-listed,
  change-note-confirmed ticket-less PR
- `non_jira_prs_not_found`: list of PR numbers explicitly listed but with
  no matching candidate — reported distinctly (spec FR-008), never
  silently merged into `non_jira_prs`

## Entity: ProposeResult (internal, `release/manifest.py`)

- `ok`: bool
- `manifest`: the validated manifest dict, or `None` when `ok` is `False`
- `issues`: list of `{path, message}`, the same shape as specs/007's
  `BuildIssue`, for consistency across the CLI

## Entity: Release Manifest (`schemas/release-manifest.schema.json`, corrected per research.md D1)

The schema-valid JSON object this feature constructs — only the fields
this feature actually populates are listed; every other field from
Reference 3 §3 (`approvals`, `digests`, `cloud_deploy`, `gates`, `main`,
`backport`, `rollback`, `platform_tag`) remains in the schema, optional,
for later features:

- `schema_version`: `1` (const, required)
- `release_id`: `YYYY.MM.DD-N` or `...-N-hf`, required
- `kind`: `"release"` or `"hotfix"`, required
- `status`: always `"proposed"` for this feature's output, required
- `repo`: `radicdotai/<name>` pattern, required
- `created_at`: ISO 8601 date-time, required
- `initiator`: string, required
- `base`: `{branch: "dev"|"main", sha: <40-hex>}`, required (research.md
  D1 — corrected from feature 001's bare-string placeholder)
- `selection`: required
  - `tickets[]`: `{key, origin: "bot-proposal", commits: [{dev_sha}, ...]}`
    — `release_sha`/`cherry_pick_x` omitted (not yet meaningful; D1)
  - `held_back[]`: `{key, reason}`
  - `non_jira_prs[]`: `{pr, reason: "MISSING", second_approver: null,
    commits: [{dev_sha}, ...]}` (D1's `second_approver` type correction;
    `reason` literal `"MISSING"` matches the architecture's own worked
    example exactly)

## Relationship to prior features' entities

Reads specs/007's change-note records (`Classification`/`ChangeNoteBuildResult`
are not reused directly — this feature only reads the records'
already-validated JSON shape off disk, it does not re-run specs/007's
construction logic). Produces the first real instance of feature 001's
`release-manifest.schema.json`, now corrected. No dependency on specs/002-006's
gate/security/deploy/release-command entities.
