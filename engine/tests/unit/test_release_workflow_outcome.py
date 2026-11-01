"""Pure mapping tests: CommandCheckResult -> WorkflowOutcome (data-model.md)."""

from __future__ import annotations

import pytest

from radic_delivery.release_commands.result import CommandCheckResult
from radic_delivery.release_commands.workflow_outcome import map_outcome

# --- US1: accepted commands (all six forms) and not_a_command ---------------

_ACCEPTED_FORMS = [
    ("release_remove", {"key": "RAD-123"}, "remove"),
    ("release_add", {"key": "RAD-123", "reason": "needed for hotfix"}, "add"),
    ("release_nonjira", {"pr": "456", "reason": "quick typo fix"}, "nonjira"),
    ("release_abort", {}, "abort"),
    ("release_waive_dev_green", {"reason": "ci is flaky today"}, "waive"),
]


@pytest.mark.parametrize(("form", "args", "expected_command"), _ACCEPTED_FORMS)
def test_accepted_release_forms_map_to_their_short_verb_and_applied(
    form: str, args: dict[str, str], expected_command: str
) -> None:
    result = CommandCheckResult(classification="accepted", form=form, args=args)  # type: ignore[arg-type]
    outcome = map_outcome(result)
    assert outcome.command == expected_command
    assert outcome.outcome == "applied"
    assert outcome.reply_body is not None
    assert form.removeprefix("release_") in outcome.reply_body or "waive" in outcome.reply_body


def test_accepted_research_close_maps_to_command_none_but_outcome_applied() -> None:
    result = CommandCheckResult(classification="accepted", form="research_close", args={})
    outcome = map_outcome(result)
    assert outcome.command == "none"
    assert outcome.outcome == "applied"
    assert outcome.reply_body is not None
    assert "research close" in outcome.reply_body.lower()


def test_not_a_command_maps_to_none_ignored_and_no_reply() -> None:
    result = CommandCheckResult(classification="not_a_command")
    outcome = map_outcome(result)
    assert outcome.command == "none"
    assert outcome.outcome == "ignored"
    assert outcome.reply_body is None


# --- US2: malformed and unauthorized -----------------------------------------

_UNAUTHORIZED_FORMS = [
    ("release_remove", {"key": "RAD-123"}, "remove"),
    ("release_add", {"key": "RAD-123", "reason": "needed"}, "add"),
    ("release_nonjira", {"pr": "456", "reason": "quick fix"}, "nonjira"),
    ("release_abort", {}, "abort"),
    ("release_waive_dev_green", {"reason": "ci is flaky"}, "waive"),
]


def test_malformed_maps_to_command_none_rejected_with_detail_in_reply() -> None:
    result = CommandCheckResult(
        classification="malformed",
        detail="'/release frobnicate' does not match any recognized form.",
    )
    outcome = map_outcome(result)
    assert outcome.command == "none"
    assert outcome.outcome == "rejected"
    assert outcome.reply_body is not None
    assert "frobnicate" in outcome.reply_body


@pytest.mark.parametrize(("form", "args", "expected_command"), _UNAUTHORIZED_FORMS)
def test_unauthorized_release_forms_map_to_their_short_verb_and_rejected(
    form: str, args: dict[str, str], expected_command: str
) -> None:
    result = CommandCheckResult(
        classification="unauthorized",
        form=form,  # type: ignore[arg-type]
        args=args,
        detail="author is not on the release-managers team.",
    )
    outcome = map_outcome(result)
    assert outcome.command == expected_command
    assert outcome.outcome == "rejected"
    assert outcome.reply_body is not None
    assert "release-managers" in outcome.reply_body


def test_unauthorized_research_close_maps_to_command_none_rejected() -> None:
    result = CommandCheckResult(
        classification="unauthorized",
        form="research_close",
        args={},
        detail="author is not on the release-managers team.",
    )
    outcome = map_outcome(result)
    assert outcome.command == "none"
    assert outcome.outcome == "rejected"


def test_malformed_and_unauthorized_and_accepted_replies_are_distinguishable() -> None:
    malformed = map_outcome(
        CommandCheckResult(classification="malformed", detail="bad shape")
    ).reply_body
    unauthorized = map_outcome(
        CommandCheckResult(
            classification="unauthorized",
            form="release_remove",
            args={"key": "RAD-123"},
            detail="author is not on the release-managers team.",
        )
    ).reply_body
    accepted = map_outcome(
        CommandCheckResult(classification="accepted", form="release_remove", args={"key": "RAD-123"})
    ).reply_body
    assert len({malformed, unauthorized, accepted}) == 3
