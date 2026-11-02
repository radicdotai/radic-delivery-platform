"""Pure PR-body text -> Jira-reference classification (research.md D2).

Recognizes a `Jira: <value>` line anywhere in the body (case-insensitive
on the label), classifying the captured value as the explicit `None`
opt-out, a recognized ticket key (normalised upper-case), or — if the
label is present but the value matches neither, or the label is absent
entirely — incomplete.
"""

from __future__ import annotations

import re

from radic_delivery.notes.result import Classification

_JIRA_LINE_RE = re.compile(r"^Jira:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_TICKET_KEY_RE = re.compile(r"^[A-Z]{2,10}-[0-9]+$")


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
