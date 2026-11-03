"""Tests for policy/rulesets_diff.py: the four drift outcomes, the
GitHub-housekeeping-field exclusion, and the duplicate-name refusal
(research.md D4)."""

from __future__ import annotations

import pytest

from radic_delivery.policy.rulesets_diff import DuplicateRulesetNameError, diff

_RULESET_A = {
    "name": "dev-trunk",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": ["refs/heads/dev"], "exclude": []}},
    "bypass_actors": [],
    "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
}

_RULESET_B = {
    "name": "main-prod-line",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
    "bypass_actors": [{"actor_type": "Integration", "actor_id": 0, "bypass_mode": "always"}],
    "rules": [{"type": "deletion"}],
}


def test_identical_committed_and_live_report_no_drift() -> None:
    result = diff("radicdotai/web-bff", [_RULESET_A, _RULESET_B], [_RULESET_A, _RULESET_B])

    assert result.ok is True
    assert result.unchanged == ["dev-trunk", "main-prod-line"]
    assert result.missing_from_live == []
    assert result.added_in_live == []
    assert result.changed == []


def test_ruleset_missing_from_live_is_reported_only_there() -> None:
    result = diff("radicdotai/web-bff", [_RULESET_A, _RULESET_B], [_RULESET_A])

    assert result.ok is False
    assert result.missing_from_live == ["main-prod-line"]
    assert result.added_in_live == []
    assert result.changed == []


def test_ruleset_added_in_live_is_reported_only_there() -> None:
    extra = {**_RULESET_A, "name": "unexpected-extra"}
    result = diff("radicdotai/web-bff", [_RULESET_A], [_RULESET_A, extra])

    assert result.ok is False
    assert result.missing_from_live == []
    assert result.added_in_live == ["unexpected-extra"]
    assert result.changed == []


def test_changed_ruleset_names_what_differs() -> None:
    changed_live = {**_RULESET_A, "rules": [{"type": "deletion"}]}
    result = diff("radicdotai/web-bff", [_RULESET_A], [changed_live])

    assert result.ok is False
    assert result.unchanged == []
    assert result.missing_from_live == []
    assert result.added_in_live == []
    assert len(result.changed) == 1
    assert result.changed[0].name == "dev-trunk"
    assert "rules" in result.changed[0].detail


def test_github_assigned_fields_never_cause_false_drift() -> None:
    live_with_housekeeping = {
        **_RULESET_A,
        "id": 12345,
        "node_id": "RS_xyz",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "source_type": "Repository",
        "source": "radicdotai/web-bff",
        "_links": {"self": {"href": "https://api.github.com/..."}},
        "current_user_can_bypass": "never",
    }
    result = diff("radicdotai/web-bff", [_RULESET_A], [live_with_housekeeping])

    assert result.ok is True
    assert result.unchanged == ["dev-trunk"]
    assert result.changed == []


def test_duplicate_committed_name_is_refused() -> None:
    duplicate = {**_RULESET_A}
    with pytest.raises(DuplicateRulesetNameError):
        diff("radicdotai/web-bff", [_RULESET_A, duplicate], [_RULESET_A])


def test_empty_committed_directory_reports_everything_live_as_added() -> None:
    result = diff("radicdotai/web-bff", [], [_RULESET_A, _RULESET_B])

    assert result.added_in_live == ["dev-trunk", "main-prod-line"]
    assert result.missing_from_live == []


def test_empty_live_file_reports_everything_committed_as_missing() -> None:
    result = diff("radicdotai/web-bff", [_RULESET_A, _RULESET_B], [])

    assert result.missing_from_live == ["dev-trunk", "main-prod-line"]
    assert result.added_in_live == []
