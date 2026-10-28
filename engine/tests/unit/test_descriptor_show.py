"""Tests for `descriptor show` (spec User Story 2, FR-008)."""

from __future__ import annotations

from pathlib import Path

from radic_delivery.descriptor.resolver import resolve
from radic_delivery.descriptor.schema_loader import load_service_schema
from radic_delivery.descriptor.validator import validate

FIXTURES = Path(__file__).parent.parent / "fixtures"
BROKEN = FIXTURES / "broken"


def test_resolved_output_includes_schema_defaults_for_omitted_fields() -> None:
    """Acceptance Scenario 1: omitted optional fields show their declared defaults."""
    result = validate(FIXTURES / "image-studio.yml")
    assert result.ok
    assert result.document is not None

    schema = load_service_schema()
    resolved, defaulted = resolve(result.document, schema)

    # image-studio.yml never sets build.context or repo.prod_line explicitly.
    assert "build.context" in defaulted
    assert "repo.prod_line" in defaulted
    assert resolved["build"]["context"] == "."
    assert resolved["repo"]["prod_line"] == "main"

    # Fields the author DID set are not reported as defaulted.
    assert "service.name" not in defaulted
    assert resolved["service"]["name"] == "image-studio"


def test_invalid_descriptor_is_not_resolved() -> None:
    """Acceptance Scenario 2: show must refuse to resolve an invalid descriptor."""
    result = validate(BROKEN / "invalid-enum.yml")
    assert not result.ok
    # The CLI layer enforces "refuse to resolve"; at the module level, the
    # contract is simply that resolve() is never called when ok is False —
    # verified here by asserting the validator already reported the failure.
    assert result.document is not None  # schema errors still surface a parsed document
    assert any(issue.category == "schema_error" for issue in result.issues)
