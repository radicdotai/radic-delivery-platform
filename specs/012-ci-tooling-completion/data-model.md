# Phase 1 Data Model: CI Tooling Completion

## Entity: QuarantineEntry (`policy/quarantine.py`, new, parallels `ExceptionEntry`)

Loaded from `policy/quarantine.yml`, validated against
`schemas/quarantine.schema.json`:

- `service`: string — matches a descriptor's `service.name`
- `test_id`: string — free-form, human-readable; never cross-checked
  against a real test run (research.md D2)
- `reason`: string
- `jira_key`: string
- `quarantined_since`: date

## Entity: TestInventoryResult (`tests_inventory/result.py`, new)

- `launched`: bool — `false` means the descriptor's unit-test command
  could not even be run; every count below is `None` in that case
  (research.md D3)
- `suite`: `"unit"` (fixed label, research.md D1)
- `total` / `passed` / `failed` / `skipped`: `int | None`
- `quarantined_active` / `quarantined_expired`: `int | None` — counts of
  this service's `QuarantineEntry` rows still within, and past, the fixed
  7-day window (research.md D2)
- `within_quarantine_share_cap`: `bool | None` —
  `(quarantined_active + quarantined_expired) / total <= 2%`, `None` when
  `total` is `None` or `0`
- `detail`: human-readable detail (populated on a launch failure)

## Entity: RulesetsDiffResult (`policy/rulesets_diff.py`, new)

- `repo`: string — `--repo` carried through for context only
  (research.md D4)
- `unchanged`: `list[str]` — ruleset names identical (on the meaningful-
  fields projection) in both committed and live
- `missing_from_live`: `list[str]` — names present in `--dir`, absent from
  `--live-file`
- `added_in_live`: `list[str]` — names present in `--live-file`, absent
  from `--dir`
- `changed`: `list[{"name": str, "detail": str}]` — names present in both,
  differing on the meaningful-fields projection; `detail` names which
  field(s) differ
- `ok`: bool — `True` only when `missing_from_live`, `added_in_live`, and
  `changed` are all empty (no drift at all)

## Entity: Ruleset JSON files (`rulesets/*.json`, new, not Python)

Five files, each the verbatim JSON body from Reference 2 §5.1-§5.5:
`dev-trunk.json`, `main-prod-line.json`, `release-branches.json`,
`product-tags.json`, `platform-tags.json`. Top-level shape (the five
fields `rulesets-diff`'s comparison actually uses, per research.md D4):
`name`, `target`, `enforcement`, `conditions`, `bypass_actors`, `rules`.

## Relationship to prior features' entities

Neither command reads or writes any prior feature's entity. `tests
inventory` reuses `gate/commands.py::unit_command()` (made public by this
feature, alongside the existing `build_commands()`),
`gate/runner.py::run()`, and `gate/parsers.py::parse_test_run()` directly
(specs/002) rather than duplicating them, and reuses
`descriptor/validator.py::validate()` (specs/001) to resolve/validate the
service descriptor at `--repo-dir`, the same way `gate evaluate`'s own CLI
wiring does. `policy/quarantine.py` is a new sibling module to
`policy/exceptions.py` (specs/001/002), following its exact loading
pattern, but an entirely separate ledger file and schema — no shared
entity.
