"""Pure comment-text -> ParsedCommand (research.md D2, D3).

Six fixed, individually-authored patterns — not a generic noun/verb
cross-product, since `research` only ever pairs with `close` and
`release waive` only ever takes the literal `dev-green`. Only the verb
token is case-insensitive (via scoped inline-flag groups), matching the
architecture's statement that case-insensitivity applies to the verb,
not the whole command.
"""

from __future__ import annotations

import re

from radic_delivery.release_commands.result import Form, ParsedCommand

_LOOKS_LIKE_ATTEMPT_RE = re.compile(r"^/(release|research)(\s|$)")
_ATTEMPTED_VERB_RE = re.compile(r"^/(?:release|research)\s+(\S+)")

_FORM_PATTERNS: list[tuple[Form, re.Pattern[str]]] = [
    ("release_remove", re.compile(r"^/release\s+(?i:remove)\s+([A-Z]{2,10}-[0-9]+)\s*$")),
    (
        "release_add",
        re.compile(r"^/release\s+(?i:add)\s+([A-Z]{2,10}-[0-9]+)\s+reason:\s*(.+?)\s*$"),
    ),
    (
        "release_nonjira",
        re.compile(r"^/release\s+(?i:nonjira)\s+([0-9]+)\s+reason:\s*(.+?)\s*$"),
    ),
    ("release_abort", re.compile(r"^/release\s+(?i:abort)\s*$")),
    (
        "release_waive_dev_green",
        re.compile(r"^/release\s+(?i:waive)\s+dev-green\s+reason:\s*(.+?)\s*$"),
    ),
    ("research_close", re.compile(r"^/research\s+(?i:close)\s*$")),
]

_FORM_ARG_NAMES: dict[Form, tuple[str, ...]] = {
    "release_remove": ("key",),
    "release_add": ("key", "reason"),
    "release_nonjira": ("pr", "reason"),
    "release_abort": (),
    "release_waive_dev_green": ("reason",),
    "research_close": (),
}


def parse(comment_body: str) -> ParsedCommand:
    """Classify a PR comment. Only the first line is ever considered
    (spec FR-003) — content on later lines never affects the result."""
    first_line = comment_body.split("\n", 1)[0].strip()

    if not first_line or not _LOOKS_LIKE_ATTEMPT_RE.match(first_line):
        return ParsedCommand(status="not_a_command")

    noun = "release" if first_line.startswith("/release") else "research"
    applicable_forms = [
        (form, pattern)
        for form, pattern in _FORM_PATTERNS
        if (noun == "release") == form.startswith("release_")
    ]

    for form, pattern in applicable_forms:
        match = pattern.match(first_line)
        if match:
            arg_names = _FORM_ARG_NAMES[form]
            args = dict(zip(arg_names, match.groups(), strict=True))
            return ParsedCommand(status="recognized", form=form, args=args)

    attempted_verb_match = _ATTEMPTED_VERB_RE.match(first_line)
    attempted_verb = attempted_verb_match.group(1) if attempted_verb_match else "(none)"
    return ParsedCommand(
        status="malformed",
        detail=f"'/{noun} {attempted_verb}' does not match any recognized form "
        f"or is missing/has invalid required arguments.",
    )
