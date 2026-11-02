"""Pure validation: a test-result record + optional --release-id ->
issues (data-model.md, research.md D1/D4)."""

from __future__ import annotations

from typing import Any

import jsonschema

from radic_delivery.records.result import RecordIssue
from radic_delivery.records.schema_loader import load_test_result_schema


def validate(record: dict[str, Any], release_id: str | None) -> list[RecordIssue]:
    schema = load_test_result_schema()
    validator = jsonschema.Draft202012Validator(schema)
    issues = [
        RecordIssue(path=".".join(str(p) for p in error.absolute_path) or "(root)", message=error.message)
        for error in sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path))
    ]

    record_release_id = record.get("release_id")
    if release_id is not None and record_release_id is not None and record_release_id != release_id:
        issues.append(
            RecordIssue(
                path="release_id",
                message=(
                    f"record's release_id '{record_release_id}' does not match "
                    f"--release-id '{release_id}'."
                ),
            )
        )

    return issues
