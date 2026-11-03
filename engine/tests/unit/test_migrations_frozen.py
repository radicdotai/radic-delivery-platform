"""Tests for migrations/frozen.py: a faithful local port of
check_migrations_frozen.py, against this feature's own real fixture
workflow files (research.md D3, D5)."""

from __future__ import annotations

from pathlib import Path

from radic_delivery.migrations.frozen import check_frozen

ENGINE_ROOT = Path(__file__).parent.parent.parent


def _descriptor(*workflow_files: str) -> dict:
    return {
        "migrations": {
            "job_name": "Run Database Migrations",
            "frozen_check_workflow_files": list(workflow_files),
        }
    }


def test_intact_workflow_file_reports_intact() -> None:
    result = check_frozen(
        _descriptor("tests/fixtures/migrations/deploy-dev-intact.yml"), ENGINE_ROOT
    )

    assert result.ok is True
    assert result.checks[0].status == "intact"
    assert result.checks[0].file == "tests/fixtures/migrations/deploy-dev-intact.yml"


def test_missing_workflow_file_reports_missing_naming_the_file() -> None:
    result = check_frozen(
        _descriptor("tests/fixtures/migrations/does-not-exist.yml"), ENGINE_ROOT
    )

    assert result.ok is False
    assert result.checks[0].status == "missing"
    assert "does-not-exist.yml" in result.checks[0].detail


def test_altered_workflow_file_reports_altered_naming_the_file() -> None:
    result = check_frozen(
        _descriptor("tests/fixtures/migrations/deploy-dev-altered.yml"), ENGINE_ROOT
    )

    assert result.ok is False
    assert result.checks[0].status == "altered"
    assert "deploy-dev-altered.yml" in result.checks[0].detail


def test_multiple_files_each_reported_independently() -> None:
    result = check_frozen(
        _descriptor(
            "tests/fixtures/migrations/deploy-dev-intact.yml",
            "tests/fixtures/migrations/deploy-dev-altered.yml",
            "tests/fixtures/migrations/does-not-exist.yml",
        ),
        ENGINE_ROOT,
    )

    statuses = {check.file: check.status for check in result.checks}
    assert statuses["tests/fixtures/migrations/deploy-dev-intact.yml"] == "intact"
    assert statuses["tests/fixtures/migrations/deploy-dev-altered.yml"] == "altered"
    assert statuses["tests/fixtures/migrations/does-not-exist.yml"] == "missing"
    assert result.ok is False
