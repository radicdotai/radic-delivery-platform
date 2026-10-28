"""Tests for `policy exceptions check` (spec User Story 3, FR-009, FR-010, FR-011)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from radic_delivery.policy.exceptions import ExceptionsFileError, check, load

BROKEN = Path(__file__).parent.parent / "fixtures" / "broken"


@pytest.mark.parametrize("exception_id", ["EXC-0001", "EXC-0002", "EXC-0003"])
def test_seeded_exceptions_are_active_on_creation_date(exception_id: str) -> None:
    """SC-004: all 3 seeded exceptions are active as of their creation date."""
    assert check(exception_id, as_of=date(2026, 10, 29)) == "active"


def test_future_expiry_is_reported_active() -> None:
    """Acceptance Scenario 1."""
    assert check("EXC-0001", as_of=date(2026, 11, 15)) == "active"


def test_past_expiry_is_reported_expired() -> None:
    """Acceptance Scenario 2."""
    assert check("EXC-0001", as_of=date(2099, 1, 1)) == "expired"


def test_unknown_id_is_reported_not_found() -> None:
    """Acceptance Scenario 3."""
    assert check("EXC-9999") == "not_found"


def test_duplicate_exception_id_makes_the_whole_file_invalid() -> None:
    """Edge Case 3."""
    with pytest.raises(ExceptionsFileError):
        load(BROKEN / "duplicate-exception-id.exceptions.yml")
