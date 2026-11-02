"""Pure PR-body classification tests: text -> Jira-reference classification
(research.md D2) and the warn-vs-block pass/fail decision (research.md D5)."""

from __future__ import annotations

import pytest

from radic_delivery.notes.check import classify
from radic_delivery.notes.result import build_check_result

# --- US2: has_jira_key / explicit_none / incomplete classification ----------


@pytest.mark.parametrize(
    "body",
    [
        "Kind: fix\nJira: RAD-1234\n\nFixes the thing.",
        "Kind: fix\njira: rad-1234\n\nFixes the thing.",
        "Some text\nJIRA: Rad-1234\nmore text",
    ],
)
def test_pr_body_with_jira_reference_classifies_as_has_jira_key(body: str) -> None:
    classification, jira_key = classify(body)
    assert classification == "has_jira_key"
    assert jira_key == "RAD-1234"


@pytest.mark.parametrize(
    "body",
    ["Kind: chore\nJira: None\n\nDependency bump.", "Jira: none", "Jira: NONE\nmore text"],
)
def test_pr_body_with_explicit_none_classifies_as_explicit_none(body: str) -> None:
    classification, jira_key = classify(body)
    assert classification == "explicit_none"
    assert jira_key is None


@pytest.mark.parametrize(
    "body",
    [
        "Just a quick fix, no ticket.",
        "",
        "Jira: see Slack thread",
        "Kind: fix\nJira: not-a-real-key\n",
    ],
)
def test_pr_body_with_neither_classifies_as_incomplete(body: str) -> None:
    classification, jira_key = classify(body)
    assert classification == "incomplete"
    assert jira_key is None


# --- US3: warn-vs-block pass/fail decision -----------------------------------


def test_incomplete_in_warning_mode_passes() -> None:
    result = build_check_result("incomplete", None, blocking=False)
    assert result.passed is True
    assert result.detail


def test_incomplete_in_blocking_mode_fails() -> None:
    result = build_check_result("incomplete", None, blocking=True)
    assert result.passed is False
    assert result.detail


@pytest.mark.parametrize("blocking", [False, True])
def test_has_jira_key_always_passes(blocking: bool) -> None:
    result = build_check_result("has_jira_key", "RAD-1234", blocking=blocking)
    assert result.passed is True


@pytest.mark.parametrize("blocking", [False, True])
def test_explicit_none_always_passes(blocking: bool) -> None:
    result = build_check_result("explicit_none", None, blocking=blocking)
    assert result.passed is True
