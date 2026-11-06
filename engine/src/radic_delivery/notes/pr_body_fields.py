"""Parse a PR body's optional `Prereqs:` checklist and `Depends-on:`
trailer (specs/019 research.md D1; Confluence RAITSDA Reference 3 §2,
review comments C5/C7). Both are cross-checks only, present or absent
without either state alone being a failure — mirroring `check.py`'s own
`_JIRA_LINE_RE`-style optional-declaration convention.
"""

from __future__ import annotations

import re
from typing import Any

_PREREQS_HEADING_RE = re.compile(r"^Prereqs:\s*$", re.IGNORECASE | re.MULTILINE)
_CHECKLIST_ITEM_RE = re.compile(r"^-\s*\[( |x|X)\]\s*(.*)$")
_DEPENDS_ON_LINE_RE = re.compile(r"^Depends-on:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def parse_prereqs(pr_body: str) -> list[dict[str, Any]]:
    heading = _PREREQS_HEADING_RE.search(pr_body)
    if heading is None:
        return []

    items: list[dict[str, Any]] = []
    for line in pr_body[heading.end() :].splitlines():
        match = _CHECKLIST_ITEM_RE.match(line)
        if match is None:
            if line.strip() == "":
                continue
            break
        text = match.group(2).strip()
        if not text:
            continue
        items.append({"item": text, "done": match.group(1).lower() == "x"})
    return items


def parse_depends_on(pr_body: str) -> list[str]:
    match = _DEPENDS_ON_LINE_RE.search(pr_body)
    if match is None:
        return []

    keys: list[str] = []
    for raw in match.group(1).split(","):
        key = raw.strip().upper()
        if key and key not in keys:
            keys.append(key)
    return keys
