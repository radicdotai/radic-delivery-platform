# Phase 0 Research: Prereqs and Depends-On Tracking and Enforcement

## Decisions taken directly from the approved architecture

| Decision | Source |
|---|---|
| A `Prereqs:` checklist block in the PR body lists non-code actions; every item must be ticked before `prod.yml` runs | Confluence RAITSDA Runbook §3.1, §3.2, §5.2; Reference 3 §2, §5 (review comment C7) |
| An optional `Depends-on: RAD-11` trailer; closed over like a migration dependency; `/release remove` refused while a depended-on ticket is selected | Runbook §1.2, §3.1, §3.3; Reference 3 §2 (review comment C5) |
| `release-gate` passes only when "every selected ticket has all Prereqs ticked and its Depends-on tickets are in prod or in the release" | Reference 2 §4 (required checks table) |
| `notes/check.py`'s existing `_JIRA_LINE_RE`/`_MIGRATIONS_LINE_RE` line-regex convention for an optional, explicitly-labeled PR-body declaration | `engine/src/radic_delivery/notes/check.py` (specs/007, specs/017) |
| `release/cut.py`'s existing early-guard-then-refuse pattern (never auto-mutates the selection); `release-manifest.schema.json`'s `selection.tickets[].origin` enum already includes `"migration-dependency"`, a precedent value for a ticket pulled in by a dependency — set by a selector/propose-stage mechanism, not by `cut` | `engine/src/radic_delivery/release/cut.py`; `schemas/release-manifest.schema.json` |

## Design decisions made for this plan

### D1 — Parser: a new module, mirroring `notes/check.py`'s line-regex style

**Decision**: new `engine/src/radic_delivery/notes/pr_body_fields.py`:

```python
def parse_prereqs(pr_body: str) -> list[dict[str, Any]]:
    # Finds a "Prereqs:" heading (case-insensitive), then reads every
    # immediately-following "- [ ] text" / "- [x] text" line as one item:
    # {"item": text, "done": bool}. Stops at the first non-checklist line.
    # Empty/whitespace-only item text is skipped (spec Edge Case 2).

def parse_depends_on(pr_body: str) -> list[str]:
    # Finds a "Depends-on: KEY, KEY" line (case-insensitive label,
    # comma-separated), same whole-line-regex family as _JIRA_LINE_RE.
    # Returns keys in the order written, de-duplicated (spec Edge Case 1).
```

Both return an empty result (never raise) when their marker is absent
(spec FR-003). Kept in `notes/` rather than `release/`, since both parse
the same kind of artifact (`notes/check.py`'s PR body text) and should
sit beside the existing Jira/migration-declaration parsers rather than
starting a second parsing module.

### D2 — `notes/builder.py`: `prereqs`/`depends_on` computed from a supplied PR body

Mirroring specs/017's migration-flag discipline exactly: a field whose
source of truth is a real artifact (the PR body a human actually wrote)
is computed by this platform, never re-typed as a separate CLI flag that
could drift from what the PR body actually says.

**Decision**: `build_record()` gains an optional `pr_body: str | None =
None` parameter. When supplied, `prereqs`/`depends_on` are populated via
`pr_body_fields.parse_prereqs`/`parse_depends_on`; when omitted, both
default to empty (never an error — most non-release-affecting PRs have
neither). The `notes write` CLI command gains an optional `--pr-body-file`
option (matching `notes check`'s existing option name and shape exactly)
read once and passed through.

### D3 — `release cut`'s Depends-on guard: refuse-only, a corrected scope from the original roadmap

The original roadmap plan's wording ("cut.py resolves Depends-on: auto-add
or refuse") is corrected here, explicitly, after determining what
"auto-add" would actually require: pulling a dependency ticket's own
commits into the release branch means discovering which commits belong to
that ticket — a capability `release propose`'s selector already has
(it reads change-note records across the whole repo to build a
candidate pool) but `release cut` does not (it only ever operates on
shas the manifest already names). Building that discovery capability into
`cut.py` would duplicate `selector.py`'s own job and cross a boundary this
platform's `cut()` has never crossed (every existing guard in `cut()`
refuses; none of them mutate the selection).

**Decision**: `cut()` gains a confirming guard only. For each selected
ticket, read its own change-note record(s) via the already-used
`change_notes_dir` convention (`_missing_change_note`'s own path pattern,
`change-notes/<repo>/<sha>.json`), collect `depends_on` keys, and for
each one: it is satisfied if it equals the ticket's own key (self-
dependency, spec Edge Case 1), appears among `manifest["selection"]
["tickets"]`'s own keys, or appears in a new explicit optional
`known_prod_tickets: list[str] | None = None` parameter (the
"already in prod" case — no live lookup, matching `other_manifests`'
precedent from the immediately prior spec in this roadmap). Unsatisfied:
refuse with a new `CutReason`, `"unmet_dependency"`, naming the specific
ticket and its missing dependency. This guard sits alongside the existing
`other_manifests` guard (same position: after `missing_change_note`,
before branch creation).

**If a future spec wants real auto-add**, it belongs in
`release/selector.py`/`release/propose.py`, using the `"migration-
dependency"`-style `origin` value already reserved in the schema for
exactly this kind of pulled-in ticket — not scheduled in this roadmap.

### D4 — `render_pr_body.py`: a new section, following Reference 3 §5's own table shape

Reference 3 §5 documents a "### Prereqs and dependencies" section with a
`| Jira | Prereqs (ticked / total) | Depends-on |` table and a Gates
checklist line: "Every selected ticket has all Prereqs ticked and its
Depends-on tickets are in prod or in this release."

**Decision**: a new `_prereqs_and_depends_on_section()` helper, reading
each ticket's change-note record(s) the same way `_selection_table()`
already does via `_lookup_change_note`'s path convention (extended to
also read `prereqs`/`depends_on`, not just `title`/`type`), rendering the
documented table shape exactly, plus a new line in the existing `###
Gates` checklist block.

### D5 — `gate evaluate --mode release-gate`: two new, separately-named checks

Matching this codebase's existing fine-grained-check style (`lint`,
`typecheck`, `unit`, `coverage`, `skip_budget`, `stage_regression` are
already separate `CheckName` values, never combined) rather than one
combined check that would obscure which half failed.

**Decision**: two new `CheckName` values, `"prereqs"` and `"depends_on"`,
appended in `evaluate()`'s existing `if mode == "release-gate":` block
(`gate/evaluator.py`, alongside `_check_stage_regression`). Both read the
same `manifest`/`change_notes_dir`/`known_prod_tickets` the CLI now
passes through (new optional `evaluate()` parameters, `None` by default).

**Correction, caught by running the existing test suite, not assumed**:
the original plan here was for both checks to report `not_executable`
when `manifest` is `None`, mirroring `_check_stage_regression`'s own
precedent. That breaks `overall_from_checks` (`all(c.status == "pass" for
c in checks)`) for every existing release-gate caller that doesn't yet
pass `--manifest` — confirmed directly: two pre-existing
`test_gate_release_mode.py` tests failed immediately, since
`not_executable` is not `"pass"` and drags the whole gate to `fail` for a
feature those callers never opted into. **Fixed**: the two new checks are
only appended to `checks` at all when `manifest is not None` — an
existing caller that never passes `--manifest` gets the exact same
`checks` list as before this feature, byte-for-byte. Only once `--manifest`
is supplied do the checks run, and only then can a missing
`--change-notes-dir` alongside it report `not_executable` (a real,
in-use-but-incomplete configuration, unlike simply never opting in).

### D6 — Testing strategy

Real PR-body text fixtures (plain Python strings, no mocking) for the
parser; real local git fixtures extending `test_release_cut.py`'s own
style for the cut guard; real manifest/change-note fixtures for
`render_pr_body` and the gate checks — the same discipline as every prior
feature. No GCP, Docker, or live Jira/GitHub call anywhere.
