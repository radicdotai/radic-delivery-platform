# Phase 1 Data Model: Prereqs and Depends-On Tracking and Enforcement

## `prereqs` (new change-note schema field)

```json
"prereqs": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["item", "done"],
    "properties": {
      "item": { "type": "string" },
      "done": { "type": "boolean" }
    }
  },
  "default": []
}
```

Parsed from a PR body's `Prereqs:` checklist block
(`pr_body_fields.parse_prereqs`); order preserved as written.

## `depends_on` (new change-note schema field)

```json
"depends_on": {
  "type": "array",
  "items": { "type": "string", "pattern": "^[A-Z]{2,10}-[0-9]+$" },
  "default": []
}
```

Parsed from a PR body's `Depends-on:` trailer
(`pr_body_fields.parse_depends_on`); order preserved, duplicates
collapsed.

## `CutReason` (extended, `release/result.py`)

New member: `"unmet_dependency"`. Existing members unchanged (now
includes `"release_already_open"` from the immediately prior spec).

## `known_prod_tickets` (new, explicit input to `cut()` and `evaluate()`)

`list[str] | None` — ticket keys the calling workflow already knows are
in production (a live fact this sandbox cannot look up itself). Consumed
identically by `release cut`'s confirming guard and `gate evaluate
--mode release-gate`'s `depends_on` check.

## `CheckName` (extended, `gate/result.py`)

Two new members: `"prereqs"`, `"depends_on"`. Both `release-gate`-only,
following `"stage_regression"`'s own precedent exactly (report
`not_executable` when the release-gate-only inputs — `manifest`,
`change_notes_dir` — aren't supplied).

## Relationships

- **Change-Note Record** (specs/007, extended specs/017): gains
  `prereqs`/`depends_on`, computed from a supplied PR body — never free
  CLI input, the same rule specs/017 established for `migration`.
- **Release Manifest** (`selection.tickets[]`): unchanged shape — Prereqs/
  Depends-on data is read from each ticket's own change-note record(s) at
  cut/render/gate time, not duplicated onto the manifest itself.
- **Release PR body**: gains a "Prereqs and dependencies" section (one
  row per selected ticket) and a new Gates checklist line, both reading
  the same change-note data the cut guard and gate checks consume.
