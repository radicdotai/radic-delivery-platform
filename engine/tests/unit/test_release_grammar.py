"""Pure grammar tests: comment text -> ParsedCommand (no authorization, no CLI)."""

from __future__ import annotations

import pytest

from radic_delivery.release_commands.grammar import parse

# --- US1: all six forms recognized, case-insensitive verb, whitespace tolerant --

_SIX_FORMS = [
    ("/release remove RAD-123", "release_remove", {"key": "RAD-123"}),
    (
        "/release add RAD-123 reason: needed for hotfix",
        "release_add",
        {"key": "RAD-123", "reason": "needed for hotfix"},
    ),
    (
        "/release nonjira 456 reason: quick typo fix",
        "release_nonjira",
        {"pr": "456", "reason": "quick typo fix"},
    ),
    ("/release abort", "release_abort", {}),
    (
        "/release waive dev-green reason: ci is flaky today",
        "release_waive_dev_green",
        {"reason": "ci is flaky today"},
    ),
    ("/research close", "research_close", {}),
]


@pytest.mark.parametrize(("comment", "form", "args"), _SIX_FORMS)
def test_each_exact_form_is_recognized_with_correct_args(
    comment: str, form: str, args: dict[str, str]
) -> None:
    parsed = parse(comment)
    assert parsed.status == "recognized"
    assert parsed.form == form
    assert parsed.args == args


@pytest.mark.parametrize(("comment", "form", "args"), _SIX_FORMS)
def test_uppercase_or_mixed_case_verb_still_recognized(
    comment: str, form: str, args: dict[str, str]
) -> None:
    noun, verb_and_rest = comment[1:].split(" ", 1)
    parts = verb_and_rest.split(" ", 1)
    mixed_verb = "".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(parts[0]))
    mixed_comment = f"/{noun} {mixed_verb}" + (f" {parts[1]}" if len(parts) > 1 else "")

    parsed = parse(mixed_comment)
    assert parsed.status == "recognized"
    assert parsed.form == form
    assert parsed.args == args


def test_extra_whitespace_between_tokens_is_tolerated() -> None:
    parsed = parse("/release   remove   RAD-123  ")
    assert parsed.status == "recognized"
    assert parsed.form == "release_remove"
    assert parsed.args == {"key": "RAD-123"}


def test_trailing_whitespace_is_tolerated() -> None:
    parsed = parse("/research close   \n")
    assert parsed.status == "recognized"
    assert parsed.form == "research_close"


# --- US2: ordinary comments are quietly not_a_command -----------------------


def test_ordinary_conversation_text_is_not_a_command() -> None:
    parsed = parse("looks good to me, thanks!")
    assert parsed.status == "not_a_command"


def test_text_merely_mentioning_release_is_not_a_command() -> None:
    parsed = parse("can we release this next week?")
    assert parsed.status == "not_a_command"


def test_multiline_comment_whose_first_line_is_not_a_command_is_not_a_command() -> None:
    parsed = parse("some commentary here\n/release remove RAD-123")
    assert parsed.status == "not_a_command"


def test_empty_comment_body_is_not_a_command() -> None:
    assert parse("").status == "not_a_command"


def test_whitespace_only_comment_body_is_not_a_command() -> None:
    assert parse("   \n  ").status == "not_a_command"


# --- US3: attempted-but-broken commands are malformed, with a detail -------


def test_unrecognized_verb_is_malformed() -> None:
    parsed = parse("/release frobnicate RAD-123")
    assert parsed.status == "malformed"
    assert "frobnicate" in parsed.detail


def test_release_add_without_reason_is_malformed() -> None:
    parsed = parse("/release add RAD-123")
    assert parsed.status == "malformed"
    assert "add" in parsed.detail


def test_release_waive_without_exact_dev_green_literal_is_malformed() -> None:
    parsed = parse("/release waive staging reason: testing")
    assert parsed.status == "malformed"
    assert "waive" in parsed.detail


def test_research_with_verb_other_than_close_is_malformed() -> None:
    parsed = parse("/research reopen")
    assert parsed.status == "malformed"
    assert "reopen" in parsed.detail
