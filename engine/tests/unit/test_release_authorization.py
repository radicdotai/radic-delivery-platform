"""Authorization-layer tests: (ParsedCommand, identity) -> CommandCheckResult."""

from __future__ import annotations

from radic_delivery.release_commands.authorization import authorize
from radic_delivery.release_commands.grammar import parse

RELEASE_MANAGERS = ["alice", "bob"]
TECH_LEAD = "bob"


def test_not_a_command_passes_through_unchanged() -> None:
    parsed = parse("just a regular comment")
    result = authorize(parsed, "alice", RELEASE_MANAGERS, TECH_LEAD)
    assert result.classification == "not_a_command"


def test_malformed_passes_through_with_its_detail() -> None:
    parsed = parse("/release frobnicate RAD-123")
    result = authorize(parsed, "alice", RELEASE_MANAGERS, TECH_LEAD)
    assert result.classification == "malformed"
    assert result.detail == parsed.detail


# --- US1: an authorized release manager is accepted -------------------------


def test_recognized_command_from_a_release_manager_is_accepted() -> None:
    parsed = parse("/release remove RAD-123")
    result = authorize(parsed, "alice", RELEASE_MANAGERS, TECH_LEAD)
    assert result.classification == "accepted"
    assert result.form == "release_remove"
    assert result.args == {"key": "RAD-123"}


# --- US4: unauthorized authors are rejected with a specific, distinguishable reason --


def test_non_release_manager_is_unauthorized_with_team_rule_detail() -> None:
    parsed = parse("/release remove RAD-123")
    result = authorize(parsed, "eve", RELEASE_MANAGERS, TECH_LEAD)
    assert result.classification == "unauthorized"
    assert "release-managers" in result.detail


def test_release_manager_who_is_not_tech_lead_is_unauthorized_for_waive_dev_green() -> None:
    parsed = parse("/release waive dev-green reason: ci is flaky today")
    result = authorize(parsed, "alice", RELEASE_MANAGERS, TECH_LEAD)
    assert result.classification == "unauthorized"
    assert "Tech Lead" in result.detail


def test_waive_dev_green_detail_is_distinguishable_from_general_team_rule_detail() -> None:
    general = authorize(parse("/release remove RAD-123"), "eve", RELEASE_MANAGERS, TECH_LEAD)
    waive = authorize(
        parse("/release waive dev-green reason: ci is flaky today"), "alice", RELEASE_MANAGERS, TECH_LEAD
    )
    assert general.detail != waive.detail


def test_tech_lead_is_accepted_for_waive_dev_green() -> None:
    parsed = parse("/release waive dev-green reason: ci is flaky today")
    result = authorize(parsed, TECH_LEAD, RELEASE_MANAGERS, TECH_LEAD)
    assert result.classification == "accepted"
    assert result.form == "release_waive_dev_green"


def test_tech_lead_need_not_be_on_release_managers_list_for_waive_dev_green() -> None:
    parsed = parse("/release waive dev-green reason: ci is flaky today")
    result = authorize(parsed, "carol", RELEASE_MANAGERS, tech_lead="carol")
    assert result.classification == "accepted"
