# Phase 1 Data Model: Release Slash-Command Parser and Authorization Check

## Entity: ParsedCommand (internal, `release_commands/grammar.py`)

The output of grammar matching alone, before authorization:

- `status`: `not_a_command` | `malformed` | `recognized`
- `form`: one of `release_remove`, `release_add`, `release_nonjira`,
  `release_abort`, `release_waive_dev_green`, `research_close`, or `None`
  (when `status` is not `recognized`)
- `args`: `dict[str, str]` — populated per form:
  - `release_remove`: `{"key": "RAD-123"}`
  - `release_add`: `{"key": "RAD-123", "reason": "..."}`
  - `release_nonjira`: `{"pr": "42", "reason": "..."}`
  - `release_waive_dev_green`: `{"reason": "..."}`
  - `release_abort`, `research_close`: `{}`
- `detail`: human-readable reason, populated when `status` is `malformed`
  (e.g. "verb 'remve' is not recognized for /release", "missing required
  'reason:' text")

## Entity: CommandCheckResult — the feature's primary output

Wraps a `ParsedCommand` with the authorization decision:

- `classification`: `not_a_command` | `malformed` | `unauthorized` |
  `accepted` (data-model.md's FR-001 four-way split — `unauthorized` only
  ever follows a `recognized` `ParsedCommand`)
- `form`: carried through from `ParsedCommand` when `recognized`/`accepted`,
  else `None`
- `args`: carried through from `ParsedCommand`
- `detail`: human-readable reason — for `unauthorized`, names which rule
  applied (`"author is not on the release-managers team"` vs `"this
  command is restricted to the Tech Lead"`), satisfying spec FR-009's
  "distinguishable from the general release-managers authorization rule"

This is the JSON shape `radic-delivery release command --format json`
emits.

## Relationship to prior features' entities

None — this is the first engine feature with no dependency on any entity
from specs/001-004 (no descriptor, no exceptions ledger, no gate/security/
deploy result). Its only inputs are the comment text and the
author/release-managers/Tech-Lead strings supplied on the command line.
