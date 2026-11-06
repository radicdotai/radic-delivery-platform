# Phase 1 Data Model: Migration Flag Computation

## Migration Flag

A computed fact about one diff, replacing the previous free-form
`migration: boolean` field on the change-note record.

| Value | Meaning |
|---|---|
| `none` | The diff adds no qualifying migration file. |
| `expand` | The diff adds at least one qualifying migration file, and either none of them carry the contract marker, or `phase_header_required` is `False` (detection not attempted). |
| `contract` | The diff adds at least one qualifying migration file whose first non-blank line is the contract marker (`# phase: contract`), and `phase_header_required` is `True`. |

A "qualifying" added file: present in `added_paths(repo_dir, base, head)`
(D2 — a genuine addition, never a modification or deletion), located
under `migrations/versions/`, and **not** located under the configured
`legacy_dir` (default `"migrations/legacy"`).

## `MigrationCheckResult` (new, `notes/result.py`)

The outcome of cross-checking a computed Migration Flag against an
optional PR-body declaration.

| Field | Type | Notes |
|---|---|---|
| `computed` | `Literal["none", "expand", "contract"]` | Always populated — the real, diff-derived value. |
| `declared` | `Literal["none", "expand", "contract"] \| None` | `None` when no `Migrations:` line was present in the PR body. |
| `matched` | `bool` | `True` when `declared is None` or `computed == declared`. |
| `passed` | `bool` | Always equal to `matched` — there is no separate blocking/non-blocking mode for this check, unlike the existing Jira classification's `blocking` flag; a mismatch is always a failure (Confluence's own wording: a PR that disagrees with reality "fails the check"). |
| `detail` | `str` | Empty when `passed`; otherwise names both values, e.g. `"PR body declares 'none' but the diff computes to 'expand'."` |

`to_dict()` mirrors every other result dataclass in this package.

## Relationships

- **Change-Note Record** (existing, specs/007): its `migration` field's
  type changes from `boolean` to the Migration Flag enum above; its value
  is always `migration_flag.compute(...)`'s output, never caller-supplied.
- **`notes check` CLI output**: when `--repo-dir`/`--base`/`--head` are
  supplied, the existing Jira `ReleaseNoteCheckResult` and the new
  `MigrationCheckResult` are reported side by side — two independent
  checks under one command, neither affecting the other's `passed` value.
