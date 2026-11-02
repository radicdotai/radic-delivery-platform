"""Pure validation tests: record dict + optional --release-id -> issues
(data-model.md, research.md D1/D4)."""

from __future__ import annotations

import copy

import pytest

from radic_delivery.records.validator import validate

_VALID_STAGE_RECORD = {
    "schema_version": 1,
    "repo": "radicdotai/frontend-v2",
    "environment": "stage",
    "release_id": "2026.11.03-1",
    "digest": "sha256:" + "0" * 64,
    "commit": "1" * 40,
    "suite": "e2e-full-stage",
    "runner": "playwright",
    "scope": "full",
    "started_at": "2026-11-03T09:12:04Z",
    "finished_at": "2026-11-03T09:38:51Z",
    "result": "pass",
    "counts": {"total": 14, "passed": 14, "failed": 0, "skipped": 0, "quarantined": 0},
    "skip_budget": {"allowed": 0, "exceptions": []},
    "run_url": "https://github.com/radicdotai/frontend-v2/actions/runs/1",
    "cloud_deploy": {
        "pipeline": "frontend-rel",
        "release": "r-2026-11-03-1-1111111",
        "rollout": "frontend-rel-r-2026-11-03-1-1111111-to-frontend-stage-0001",
        "rollout_state": "SUCCEEDED",
        "verify": "pass",
    },
}

_VALID_DEV_RECORD = {
    "schema_version": 1,
    "repo": "radicdotai/web-bff",
    "environment": "dev",
    "release_id": None,
    "digest": "sha256:" + "0" * 64,
    "commit": "2" * 40,
    "suite": "unit",
    "runner": "pytest",
    "scope": "regression",
    "started_at": "2026-11-03T09:00:00Z",
    "finished_at": "2026-11-03T09:01:00Z",
    "result": "pass",
    "counts": {"total": 5, "passed": 5, "failed": 0, "skipped": 0, "quarantined": 0},
    "skip_budget": {"allowed": 0, "exceptions": []},
    "run_url": "https://example/run/2",
    "cloud_deploy": {
        "pipeline": "web-bff-dev",
        "release": "d-2222222-418",
        "rollout": "web-bff-dev-to-web-bff-dev-0001",
        "rollout_state": "SUCCEEDED",
        "verify": "pass",
    },
}


# --- US1: reliable capture ---------------------------------------------------


def test_complete_valid_stage_record_has_no_issues() -> None:
    issues = validate(_VALID_STAGE_RECORD, release_id="2026.11.03-1")
    assert issues == []


def test_complete_valid_dev_record_with_null_release_id_has_no_issues() -> None:
    issues = validate(_VALID_DEV_RECORD, release_id=None)
    assert issues == []


def test_release_id_mismatch_is_rejected() -> None:
    issues = validate(_VALID_STAGE_RECORD, release_id="2099.01.01-9")
    assert len(issues) == 1
    assert "release_id" in issues[0].path or "release_id" in issues[0].message


def test_release_id_supplied_but_record_is_null_is_not_a_mismatch() -> None:
    issues = validate(_VALID_DEV_RECORD, release_id="2026.11.03-1")
    assert issues == []


def test_missing_required_field_is_rejected() -> None:
    record = copy.deepcopy(_VALID_STAGE_RECORD)
    del record["digest"]
    issues = validate(record, release_id="2026.11.03-1")
    assert any("digest" in issue.message for issue in issues)


# --- US2: zero-skip-budget rule -----------------------------------------------


def test_skipped_test_with_overall_pass_is_rejected() -> None:
    record = copy.deepcopy(_VALID_DEV_RECORD)
    record["counts"]["skipped"] = 1
    record["result"] = "pass"
    issues = validate(record, release_id=None)
    assert len(issues) >= 1


def test_skipped_test_with_overall_fail_is_accepted() -> None:
    record = copy.deepcopy(_VALID_DEV_RECORD)
    record["counts"]["skipped"] = 1
    record["result"] = "fail"
    issues = validate(record, release_id=None)
    assert issues == []


@pytest.mark.parametrize("result", ["pass", "fail", "error", "timeout"])
def test_zero_skipped_is_unaffected_by_skip_rule(result: str) -> None:
    record = copy.deepcopy(_VALID_DEV_RECORD)
    record["counts"]["skipped"] = 0
    record["result"] = result
    issues = validate(record, release_id=None)
    assert issues == []


# --- US3: stage-completeness rule --------------------------------------------


def test_stage_record_with_null_release_id_is_rejected() -> None:
    record = copy.deepcopy(_VALID_STAGE_RECORD)
    record["release_id"] = None
    issues = validate(record, release_id=None)
    assert len(issues) >= 1


def test_stage_record_missing_scope_is_rejected() -> None:
    record = copy.deepcopy(_VALID_STAGE_RECORD)
    del record["scope"]
    issues = validate(record, release_id="2026.11.03-1")
    assert any("scope" in issue.path or "scope" in issue.message for issue in issues)


def test_stage_record_with_wrong_scope_is_rejected() -> None:
    record = copy.deepcopy(_VALID_STAGE_RECORD)
    record["scope"] = "smoke"
    issues = validate(record, release_id="2026.11.03-1")
    assert any("scope" in issue.path or "scope" in issue.message for issue in issues)


def test_stage_record_with_release_id_and_full_scope_is_unaffected() -> None:
    issues = validate(_VALID_STAGE_RECORD, release_id="2026.11.03-1")
    assert issues == []
