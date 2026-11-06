"""Pure PR-body text -> Jira-reference classification (research.md D2).

Recognizes a `Jira: <value>` line anywhere in the body (case-insensitive
on the label), classifying the captured value as the explicit `None`
opt-out, a recognized ticket key (normalised upper-case), or — if the
label is present but the value matches neither, or the label is absent
entirely — incomplete.
"""

from __future__ import annotations

import re

from radic_delivery.notes.result import Classification, MigrationCheckResult, MigrationFlag

_JIRA_LINE_RE = re.compile(r"^Jira:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_TICKET_KEY_RE = re.compile(r"^[A-Z]{2,10}-[0-9]+$")
_MIGRATIONS_LINE_RE = re.compile(r"^Migrations:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_MIGRATION_FLAG_VALUES = {"none", "expand", "contract"}


def classify(pr_body: str) -> tuple[Classification, str | None]:
    match = _JIRA_LINE_RE.search(pr_body)
    if match is None:
        return "incomplete", None

    value = match.group(1).strip()
    if value.lower() == "none":
        return "explicit_none", None

    normalised = value.upper()
    if _TICKET_KEY_RE.match(normalised):
        return "has_jira_key", normalised

    return "incomplete", None


def classify_migration_declaration(pr_body: str) -> MigrationFlag | None:
    """Recognizes an optional `Migrations: none|expand|contract` line
    (specs/017 research.md D5) — a cross-check only, never authoritative.
    Returns `None` when no such line is present, or when present with a
    value that isn't one of the three recognized flags."""
    match = _MIGRATIONS_LINE_RE.search(pr_body)
    if match is None:
        return None
    value = match.group(1).strip().lower()
    if value not in _MIGRATION_FLAG_VALUES:
        return None
    return value  # type: ignore[return-value]


def check_migration_match(computed: MigrationFlag, declared: MigrationFlag | None) -> MigrationCheckResult:
    """A PR body's declared migration state is only a cross-check against
    the real, computed value — its absence always passes (spec FR-009);
    its presence must agree with reality, or the check fails (spec
    FR-008), never a separate blocking/non-blocking mode."""
    if declared is None:
        return MigrationCheckResult(computed=computed, declared=None, matched=True, passed=True)
    matched = computed == declared
    detail = "" if matched else f"PR body declares '{declared}' but the diff computes to '{computed}'."
    return MigrationCheckResult(
        computed=computed, declared=declared, matched=matched, passed=matched, detail=detail
    )
