"""Tests for `descriptor validate` (spec User Story 1, FR-004 through FR-007)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from radic_delivery.descriptor.validator import validate

FIXTURES = Path(__file__).parent.parent / "fixtures"
BROKEN = FIXTURES / "broken"

REAL_SERVICE_FIXTURES = [
    "fastapi-backend.yml",
    "web-bff.yml",
    "design_service.yml",
    "image-studio.yml",
    "brand_research.yml",
    "frontend-v2.yml",
    "operations-console.yml",
]


@pytest.mark.parametrize("fixture_name", REAL_SERVICE_FIXTURES)
def test_real_service_descriptors_are_valid(fixture_name: str) -> None:
    """Acceptance Scenario 5 / SC-002: every one of the 7 real descriptors validates."""
    result = validate(FIXTURES / fixture_name)
    assert result.ok, f"{fixture_name} failed: {result.issues}"


def test_valid_descriptor_reports_success() -> None:
    """Acceptance Scenario 1."""
    result = validate(FIXTURES / "web-bff.yml")
    assert result.ok
    assert result.issues == []
    assert result.document is not None


def test_missing_required_field_reports_exact_path() -> None:
    """Acceptance Scenario 2."""
    result = validate(BROKEN / "missing-required-field.yml")
    assert not result.ok
    assert any(
        issue.category == "schema_error" and "prod" in issue.message and issue.path == "environments"
        for issue in result.issues
    )


def test_disallowed_extra_field_is_named() -> None:
    """Acceptance Scenario 3."""
    result = validate(BROKEN / "extra-field.yml")
    assert not result.ok
    assert any("nickname" in issue.message for issue in result.issues)


def test_invalid_enum_value_is_named_with_allowed_set() -> None:
    """Acceptance Scenario 4."""
    result = validate(BROKEN / "invalid-enum.yml")
    assert not result.ok
    issue = next(i for i in result.issues if i.path == "service.kind")
    assert "not-a-real-kind" in issue.message
    assert "api" in issue.message and "bff" in issue.message


def test_invalid_yaml_is_a_distinct_parse_error() -> None:
    """Edge Case 1: parse error must be distinguishable from a schema violation."""
    result = validate(BROKEN / "invalid-yaml.yml")
    assert not result.ok
    assert len(result.issues) == 1
    assert result.issues[0].category == "parse_error"


def test_unresolvable_exception_reference_fails_validation() -> None:
    """Edge Case 2: an exception_id that does not resolve fails the descriptor."""
    result = validate(BROKEN / "unresolvable-exception.yml")
    assert not result.ok
    assert any(issue.category == "cross_document_error" for issue in result.issues)


def test_expired_exception_reference_fails_validation() -> None:
    """Edge Case 2, expired variant: web-bff references EXC-0001, which is seeded
    with a real expiry date — checking far enough in the future must fail."""
    result = validate(FIXTURES / "web-bff.yml", as_of=date(2099, 1, 1))
    assert not result.ok
    assert any(issue.category == "cross_document_error" for issue in result.issues)


def test_active_exception_reference_passes_as_of_seed_date() -> None:
    result = validate(FIXTURES / "web-bff.yml", as_of=date(2026, 11, 1))
    assert result.ok
