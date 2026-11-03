"""Tests for policy/quarantine.py: ledger loading + active/expired
classification (research.md D2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from radic_delivery.policy.quarantine import (
    QuarantineEntry,
    QuarantineFileError,
    classify_for_service,
    load,
)


def _write_ledger(tmp_path: Path, entries: list[dict]) -> Path:
    import yaml

    path = tmp_path / "quarantine.yml"
    path.write_text(yaml.safe_dump({"schema_version": 1, "quarantine": entries}))
    return path


def test_entry_within_window_classifies_active(tmp_path: Path) -> None:
    path = _write_ledger(
        tmp_path,
        [
            {
                "service": "sample",
                "test_id": "tests/test_sample.py::test_flaky",
                "reason": "flaky",
                "jira_key": "RAD-1",
                "quarantined_since": "2026-10-30",
            }
        ],
    )
    entries = load(path)
    active, expired = classify_for_service(entries, "sample", date(2026, 11, 3))
    assert (active, expired) == (1, 0)


def test_entry_past_window_classifies_expired(tmp_path: Path) -> None:
    path = _write_ledger(
        tmp_path,
        [
            {
                "service": "sample",
                "test_id": "tests/test_sample.py::test_flaky",
                "reason": "flaky",
                "jira_key": "RAD-1",
                "quarantined_since": "2026-10-30",
            }
        ],
    )
    entries = load(path)
    active, expired = classify_for_service(entries, "sample", date(2026, 11, 10))
    assert (active, expired) == (0, 1)


def test_entries_for_a_different_service_are_excluded(tmp_path: Path) -> None:
    path = _write_ledger(
        tmp_path,
        [
            {
                "service": "other-service",
                "test_id": "tests/test_sample.py::test_flaky",
                "reason": "flaky",
                "jira_key": "RAD-1",
                "quarantined_since": "2026-10-30",
            }
        ],
    )
    entries = load(path)
    active, expired = classify_for_service(entries, "sample", date(2026, 11, 3))
    assert (active, expired) == (0, 0)


def test_empty_ledger_loads_to_empty_list(tmp_path: Path) -> None:
    path = _write_ledger(tmp_path, [])
    assert load(path) == []


def test_malformed_ledger_raises_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "quarantine.yml"
    path.write_text("schema_version: 1\nquarantine:\n  - service: sample\n")
    with pytest.raises(QuarantineFileError):
        load(path)


def test_quarantine_entry_fields_parsed_correctly(tmp_path: Path) -> None:
    path = _write_ledger(
        tmp_path,
        [
            {
                "service": "sample",
                "test_id": "tests/test_sample.py::test_flaky",
                "reason": "flaky under parallel CI runners",
                "jira_key": "RAD-9001",
                "quarantined_since": "2026-10-30",
            }
        ],
    )
    entries = load(path)
    assert entries == [
        QuarantineEntry(
            service="sample",
            test_id="tests/test_sample.py::test_flaky",
            reason="flaky under parallel CI runners",
            jira_key="RAD-9001",
            quarantined_since=date(2026, 10, 30),
        )
    ]
