"""Validate a .radic/service.yml descriptor (spec FR-004 through FR-007,
Edge Cases 1-3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from radic_delivery.descriptor.schema_loader import load_service_schema
from radic_delivery.policy.exceptions import ExceptionsFileError
from radic_delivery.policy.exceptions import check as check_exception


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    category: str  # "parse_error" | "schema_error" | "cross_document_error"


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    document: dict[str, Any] | None
    issues: list[ValidationIssue] = field(default_factory=list)


def _load_yaml(descriptor_path: Path) -> tuple[dict[str, Any] | None, ValidationIssue | None]:
    try:
        with descriptor_path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        return None, ValidationIssue(path="(file)", message=f"Not valid YAML: {exc}", category="parse_error")
    except OSError as exc:
        return None, ValidationIssue(
            path="(file)", message=f"Could not read descriptor file: {exc}", category="parse_error"
        )
    if not isinstance(raw, dict):
        return None, ValidationIssue(
            path="(file)",
            message="Descriptor must parse to a YAML mapping at the top level.",
            category="parse_error",
        )
    return raw, None


def _schema_issues(document: dict[str, Any]) -> list[ValidationIssue]:
    schema = load_service_schema()
    validator = jsonschema.Draft202012Validator(schema)
    issues: list[ValidationIssue] = []
    for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        issues.append(ValidationIssue(path=path, message=error.message, category="schema_error"))
    return issues


def _cross_document_issues(document: dict[str, Any], as_of: date | None) -> list[ValidationIssue]:
    """Rules the JSON Schema alone cannot express (data-model.md)."""
    issues: list[ValidationIssue] = []
    post_deploy = document.get("quality", {}).get("post_deploy", {})
    suites = post_deploy.get("suites", [])
    if not suites:
        exception_id = post_deploy.get("exception_id")
        if not exception_id:
            # Already caught by the schema's if/then, but guard defensively.
            return issues
        try:
            status = check_exception(exception_id, as_of=as_of)
        except ExceptionsFileError as exc:
            issues.append(
                ValidationIssue(
                    path="quality.post_deploy.exception_id",
                    message=f"policy/exceptions.yml is invalid: {exc}",
                    category="cross_document_error",
                )
            )
            return issues
        if status != "active":
            issues.append(
                ValidationIssue(
                    path="quality.post_deploy.exception_id",
                    message=(
                        f"Exception '{exception_id}' is {status}, "
                        "so quality.post_deploy.suites cannot be left empty."
                    ),
                    category="cross_document_error",
                )
            )
    return issues


def validate(descriptor_path: Path, as_of: date | None = None) -> ValidationResult:
    document, parse_issue = _load_yaml(descriptor_path)
    if parse_issue is not None:
        return ValidationResult(ok=False, document=None, issues=[parse_issue])
    assert document is not None

    issues = _schema_issues(document)
    if issues:
        return ValidationResult(ok=False, document=document, issues=issues)

    issues = _cross_document_issues(document, as_of)
    if issues:
        return ValidationResult(ok=False, document=document, issues=issues)

    return ValidationResult(ok=True, document=document, issues=[])
