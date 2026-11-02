"""Pure construction+validation tests: explicit fields -> ChangeNoteBuildResult."""

from __future__ import annotations

import pytest

from radic_delivery.notes.builder import build_record

_VALID_KWARGS = {
    "repo": "radicdotai/web-bff",
    "sha": "2222222222222222222222222222222222222222",
    "pr_number": 123,
    "type": "fix",
    "audience": "customer",
    "title": "Return a clear error when the upstream is unavailable",
    "summary": "The BFF now answers 503 with a retry hint instead of a generic 500.",
    "jira_key": "RAD-1234",
}


def test_complete_valid_inputs_build_a_schema_valid_record() -> None:
    result = build_record(**_VALID_KWARGS)
    assert result.ok is True
    assert result.issues == []
    assert result.record is not None
    assert result.record["schema_version"] == 1
    assert result.record["repo"] == "radicdotai/web-bff"
    assert result.record["jira_key"] == "RAD-1234"


@pytest.mark.parametrize("jira_key", ["None", "none", "NONE", "NoNe"])
def test_explicit_none_jira_key_is_accepted_and_normalised(jira_key: str) -> None:
    kwargs = {**_VALID_KWARGS, "jira_key": jira_key}
    result = build_record(**kwargs)
    assert result.ok is True
    assert result.record is not None
    assert result.record["jira_key"] == "None"


def test_invalid_type_is_rejected_naming_the_field() -> None:
    kwargs = {**_VALID_KWARGS, "type": "not-a-real-type"}
    result = build_record(**kwargs)
    assert result.ok is False
    assert result.record is None
    assert any("type" in issue.path for issue in result.issues)


def test_empty_title_is_rejected() -> None:
    kwargs = {**_VALID_KWARGS, "title": "x"}
    result = build_record(**kwargs)
    assert result.ok is False
    assert any("title" in issue.path for issue in result.issues)


def test_jira_key_matching_neither_pattern_nor_none_is_rejected() -> None:
    kwargs = {**_VALID_KWARGS, "jira_key": "not-a-ticket"}
    result = build_record(**kwargs)
    assert result.ok is False
    assert any("jira_key" in issue.path for issue in result.issues)


def test_missing_required_field_is_rejected() -> None:
    kwargs = dict(_VALID_KWARGS)
    kwargs["summary"] = ""
    result = build_record(**kwargs)
    assert result.ok is False
    assert any("summary" in issue.path for issue in result.issues)


def test_optional_fields_are_included_when_provided() -> None:
    result = build_record(
        **_VALID_KWARGS,
        linked_prs=["radicdotai/frontend-v2#456"],
        migration=True,
        uat_escape=True,
        regression_test_added=True,
        author="example-user",
        merged_at="2026-11-02T14:03:11Z",
    )
    assert result.ok is True
    assert result.record is not None
    assert result.record["linked_prs"] == ["radicdotai/frontend-v2#456"]
    assert result.record["migration"] is True
    assert result.record["author"] == "example-user"


def test_invalid_linked_pr_reference_is_rejected() -> None:
    kwargs = {**_VALID_KWARGS, "linked_prs": ["456"]}
    result = build_record(**kwargs)
    assert result.ok is False
    assert any("linked_prs" in issue.path for issue in result.issues)
