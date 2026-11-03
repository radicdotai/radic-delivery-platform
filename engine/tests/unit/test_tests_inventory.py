"""Tests for tests_inventory/inventory.py, against this platform's own
existing real fixture repos (research.md D1, D3, D7)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from radic_delivery.policy.quarantine import QuarantineEntry
from radic_delivery.tests_inventory.inventory import inventory

FIXTURES = Path(__file__).parent.parent / "fixtures" / "sample-repos"


def _load_descriptor(repo_dir: Path) -> dict:
    with (repo_dir / ".radic" / "service.yml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_clean_fixture_reports_accurate_counts() -> None:
    repo_dir = FIXTURES / "python-sample"
    descriptor = _load_descriptor(repo_dir)

    result = inventory(
        descriptor, repo_dir=repo_dir, quarantine_entries=[], as_of=date(2026, 11, 3)
    )

    assert result.launched is True
    assert result.suite == "unit"
    assert result.total == 2
    assert result.passed == 2
    assert result.failed == 0
    assert result.skipped == 0


def test_skipped_test_fixture_reports_skipped_count() -> None:
    repo_dir = FIXTURES / "python-sample-broken-skip"
    descriptor = _load_descriptor(repo_dir)

    result = inventory(
        descriptor, repo_dir=repo_dir, quarantine_entries=[], as_of=date(2026, 11, 3)
    )

    assert result.total == 3
    assert result.passed == 2
    assert result.failed == 0
    assert result.skipped == 1


def test_quarantine_ledger_active_vs_expired() -> None:
    repo_dir = FIXTURES / "python-sample-broken-skip"
    descriptor = _load_descriptor(repo_dir)
    entries = [
        QuarantineEntry(
            service="sample",
            test_id="tests/test_sample.py::test_add_again",
            reason="flaky",
            jira_key="RAD-9001",
            quarantined_since=date(2026, 10, 30),
        )
    ]

    active_result = inventory(
        descriptor, repo_dir=repo_dir, quarantine_entries=entries, as_of=date(2026, 11, 3)
    )
    expired_result = inventory(
        descriptor, repo_dir=repo_dir, quarantine_entries=entries, as_of=date(2026, 11, 10)
    )

    assert (active_result.quarantined_active, active_result.quarantined_expired) == (1, 0)
    assert (expired_result.quarantined_active, expired_result.quarantined_expired) == (0, 1)


def test_unlaunchable_test_command_reports_launched_false(tmp_path: Path) -> None:
    descriptor = {
        "service": {"name": "sample"},
        "quality": {"unit": {"runner": "pytest"}},
    }

    result = inventory(
        descriptor, repo_dir=tmp_path / "nonexistent-dir", quarantine_entries=[], as_of=date(2026, 11, 3)
    )

    assert result.launched is False
    assert result.total is None
    assert result.passed is None
    assert result.failed is None
    assert result.skipped is None
    assert result.detail != ""


@pytest.mark.parametrize("field", ["total", "passed", "failed", "skipped"])
def test_launch_failure_never_reports_all_zero(field: str) -> None:
    descriptor = {
        "service": {"name": "sample"},
        "quality": {"unit": {"runner": "pytest"}},
    }
    result = inventory(
        descriptor, repo_dir=Path("/nonexistent"), quarantine_entries=[], as_of=date(2026, 11, 3)
    )
    assert getattr(result, field) is None, "a launch failure must report None, never 0"
