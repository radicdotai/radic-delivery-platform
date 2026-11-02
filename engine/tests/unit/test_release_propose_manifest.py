"""Pure manifest construction + schema validation tests."""

from __future__ import annotations

from radic_delivery.release.manifest import build_manifest
from radic_delivery.release.result import HeldBackTicket, NonJiraPr, ProposedTicket, Selection

_SHA = "1111111111111111111111111111111111111111"


def test_a_valid_selection_builds_a_schema_valid_proposed_manifest() -> None:
    selection = Selection(tickets=[ProposedTicket(key="RAD-1234", title="Fix it", commits=[_SHA])])
    result = build_manifest(
        selection,
        repo="radicdotai/web-bff",
        base_branch="dev",
        base_sha=_SHA,
        release_id="2026.11.02-1",
        initiator="alice",
        kind="release",
    )

    assert result.ok is True
    assert result.manifest is not None
    assert result.manifest["status"] == "proposed"
    assert result.manifest["schema_version"] == 1
    assert result.manifest["base"] == {"branch": "dev", "sha": _SHA}
    assert result.manifest["selection"]["tickets"][0]["key"] == "RAD-1234"


def test_held_back_and_non_jira_prs_are_included_in_the_manifest() -> None:
    selection = Selection(
        held_back=[HeldBackTicket(key="RAD-9999", reason="not Ready for Review")],
        non_jira_prs=[NonJiraPr(pr_number=142, commits=[_SHA])],
    )
    result = build_manifest(
        selection,
        repo="radicdotai/web-bff",
        base_branch="dev",
        base_sha=_SHA,
        release_id="2026.11.02-1",
        initiator="alice",
        kind="release",
    )

    assert result.ok is True
    assert result.manifest is not None
    assert result.manifest["selection"]["held_back"] == [
        {"key": "RAD-9999", "reason": "not Ready for Review"}
    ]
    assert result.manifest["selection"]["non_jira_prs"][0]["reason"] == "MISSING"
    assert result.manifest["selection"]["non_jira_prs"][0]["second_approver"] is None


def test_an_empty_selection_still_builds_a_valid_manifest() -> None:
    result = build_manifest(
        Selection(),
        repo="radicdotai/web-bff",
        base_branch="dev",
        base_sha=_SHA,
        release_id="2026.11.02-1",
        initiator="alice",
        kind="release",
    )
    assert result.ok is True
    assert result.manifest is not None
    assert result.manifest["selection"]["tickets"] == []
    assert result.manifest["selection"]["held_back"] == []


def test_invalid_release_id_format_fails_validation() -> None:
    result = build_manifest(
        Selection(),
        repo="radicdotai/web-bff",
        base_branch="dev",
        base_sha=_SHA,
        release_id="not-a-valid-id",
        initiator="alice",
        kind="release",
    )
    assert result.ok is False
    assert result.manifest is None
    assert any("release_id" in issue.path for issue in result.issues)
