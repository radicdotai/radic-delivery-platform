# Phase 0 Research: Migration Flag Computation

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| The `migration` value is computed from the PR diff, never typed by the author: `expand`/`contract` when the diff adds a file under `migrations/versions/` (files under `migrations/legacy/` excluded), otherwise `none`; a PR declaring `Migrations: none` while actually adding a migration fails the check; the PR-body line is a cross-check only | Confluence RAITSDA Reference 3 §2 (revised 2026-11-03, review comment C4) |
| `release/git_history.py` already has a real, tested diff primitive (`changed_paths`, specs/014) this feature reuses | `engine/src/radic_delivery/release/git_history.py` |
| `notes/check.py` already has a real, tested line-parsing convention for an optional PR-body declaration (`_JIRA_LINE_RE`, specs/007) this feature's own `Migrations:` line parser follows | `engine/src/radic_delivery/notes/check.py` |

## Design decisions made for this plan

### D1 — Contract-marker syntax: `# phase: contract`, resolving a real documentation contradiction

Confluence's current text says the contract phase is "set from the
migration file's header" using `-- phase: contract` — SQL-comment syntax.
Migration files in every affected repo are Python (`migrations/versions/
*.py`), where `--` is not a comment and would never be recognized by any
tool scanning file content; a literal port of the documented syntax would
simply never match. **This is a genuine inconsistency in the source
documentation, not a gap to quietly interpret around.**

**Decision, confirmed directly with the Confluence page owner** (not
guessed): the engine recognizes `# phase: contract` — the first
non-blank line of the migration `.py` file — as the contract marker. The
page owner has agreed and will update Reference 3 §2, the Runbook,
Technical Design §8.1, and Reference 1b to the corrected syntax
separately; this repo's code and tests implement the corrected form now
rather than waiting on that edit.

**Alembic docstring note**: Alembic-generated migration files normally
open with a module docstring (emitted by each service repo's own
`script.py.mako` template). "First non-blank line" therefore requires the
marker to sit *above* that docstring. Each service repo's own
`script.py.mako` will need updating to emit the marker automatically for
new migrations — an action for the service repos, explicitly out of scope
for this platform's own code, but recorded here so it is not silently
missed when those repos onboard.

**Edge case, resolved**: a diff adding both an expand-phase and a
contract-phase migration file in the same change computes as `contract`
— the stricter value wins. There is no scenario in this platform's model
where a mixed PR should be treated as merely `expand`.

### D2 — `added_paths`: a new git primitive, since `changed_paths` doesn't distinguish additions

`release/git_history.py::changed_paths(repo_dir, base, head)` runs
`git diff --name-only base head`, which returns every path touched by the
diff regardless of whether it was added, modified, or deleted. Reference
3's own wording is specific: "adds a file under `migrations/versions/`" —
a migration file that already existed and was merely modified (for
example, a comment fix) must never be treated as a new migration. Reusing
`changed_paths` as-is would over-match.

**Decision**: add a new primitive, `added_paths(repo_dir, base, head) ->
set[str]`, running `git diff --name-only --diff-filter=A base head`
(Git's own "added" filter) — mirroring `changed_paths`'s existing
implementation pattern exactly, including its `GitHistoryError` handling.
`migration_flag.compute()` uses this instead of `changed_paths`.

### D3 — `compute()`'s signature: explicit parameters, not hardcoded or descriptor-coupled

The real architecture makes `legacy_dir` and `phase_header_required`
per-repo descriptor fields (Reference 1b), but wiring the real descriptor
schema through is a later spec in this roadmap (schema-ownership
closure). Hardcoding `"migrations/legacy"` and `True` directly in this
feature's logic would force that later spec to rework this feature's
internals just to make them configurable.

**Decision**: `compute()` takes both as explicit keyword parameters with
the documented defaults from the start:

```python
def compute(
    repo_dir: Path,
    base: str,
    head: str,
    *,
    legacy_dir: str = "migrations/legacy",
    phase_header_required: bool = True,
) -> Literal["none", "expand", "contract"]:
```

A later spec supplies real per-repo values by simply passing them through
— no change to this function's body.

**`phase_header_required=False` semantic, stated explicitly**: when
`False`, contract-marker detection is not attempted at all (there's
nothing meaningful to scan for if the repo's own convention doesn't
guarantee the marker's presence or position) — any qualifying added
migration file always computes as `expand` in this mode. This is a
documented default-safe behavior, not a missing case: `expand` is the
less-restrictive of the two non-`none` values (recall from the roadmap's
own cross-reference: "a ticket with a contract step cannot be held back
on its own" — under-detecting `contract` as `expand` is the safe
direction of error, since it never blocks a hold-back that should be
allowed; it would only ever fail to apply a restriction, which is exactly
why `phase_header_required` exists as an explicit, opt-in-to-strictness
flag rather than a silent assumption).

### D4 — `notes/builder.py` and the `notes write` CLI: migration becomes computed, not supplied

specs/007's own `notes write` command docstring states "every field is
explicit input" (FR-010 of that spec) — this feature makes one narrow,
explicitly-flagged exception for exactly the `migration` field, per
Reference 3's own mandate that it must never be typed by the author. This
is not a reversal of specs/007's policy; it's the one field the
architecture itself says must stop being free input.

**Decision**: `build_record()` drops the `migration: bool | None`
parameter entirely and instead requires `repo_dir: Path`, `base: str`,
`head: str` (plus the same `legacy_dir`/`phase_header_required` pass-through
as D3), computing the value internally via `migration_flag.compute(...)`
before validating the record. The `notes write` CLI command's
`--migration/--no-migration` flag is replaced with required `--repo-dir`,
`--base`, `--head` options and optional `--legacy-dir` / `--phase-header
-required`/`--no-phase-header-required` options (defaults matching D3).

### D5 — `notes/check.py` and `notes check`: an optional, additive cross-check

Reference 3's own text is explicit that the PR-body `Migrations:` line is
"only a cross-check" — never authoritative, and its absence is not an
error (spec FR-009). This matches `check.py`'s own existing `_JIRA_LINE_RE`
precedent exactly: an optional declaration line, parsed with the same
case-insensitive, whole-line regex style, present or absent without
either state alone being a failure.

**Decision**: a new function in `check.py`,
`classify_migration_declaration(pr_body: str) -> Literal["none", "expand",
"contract"] | None` (returns `None` when no `Migrations:` line is
present, mirroring `classify()`'s own `None`-on-absence shape), plus a new
pure comparison function, `check_migration_match(computed, declared) ->
MigrationCheckResult` (new dataclass in `result.py`: `computed`,
`declared`, `matched: bool`, `passed: bool`, `detail: str` — `passed` is
always `True` when `declared is None`, and `computed == declared`
otherwise). The `notes check` CLI command gains optional `--repo-dir`,
`--base`, `--head` options; when all three are supplied, it computes the
real migration flag and runs this new check alongside the existing Jira
classification, reporting both; when omitted, the migration check is
skipped entirely (an explicit opt-in, not a silent default-pass — the
existing Jira-only behavior is fully preserved when these options aren't
given, so no caller of today's `notes check` breaks).

### D6 — Testing strategy

Real, unmocked local git fixtures throughout — a small real repo with
real added/modified/deleted files under `migrations/versions/` and
`migrations/legacy/`, with and without the `# phase: contract` marker (at
the correct first-line position and, as a negative case, after a leading
docstring to confirm it is *not* detected there) — mirroring every prior
feature's own fixture discipline (e.g. specs/013's `migrations/graph.py`
fixtures). Real JSON Schema validation for the `change-note.schema.json`
enum change. No GCP, Docker, or live Jira/GitHub call anywhere.
