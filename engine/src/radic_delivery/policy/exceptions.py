"""Load, validate, and check policy/exceptions.yml — the single ledger of
approved, time-boxed exceptions to a fail-closed gate (spec FR-009, FR-010).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import jsonschema
import yaml

from radic_delivery.paths import policy_dir
from radic_delivery.policy.exceptions_schema_loader import load_exceptions_schema

ExceptionStatus = Literal["active", "expired", "not_found"]


class ExceptionsFileError(ValueError):
    """The exceptions ledger itself is malformed (schema violation or duplicate id)."""


@dataclass(frozen=True)
class ExceptionEntry:
    id: str
    scope: str
    owner: str
    approver: str
    reason: str
    jira_key: str
    created: date
    expires: date


def _parse_entry(raw: dict[str, object]) -> ExceptionEntry:
    return ExceptionEntry(
        id=str(raw["id"]),
        scope=str(raw["scope"]),
        owner=str(raw["owner"]),
        approver=str(raw["approver"]),
        reason=str(raw["reason"]),
        jira_key=str(raw["jira_key"]),
        created=date.fromisoformat(str(raw["created"])),
        expires=date.fromisoformat(str(raw["expires"])),
    )


def load(path: Path | None = None) -> list[ExceptionEntry]:
    """Load and schema-validate the exceptions ledger.

    Raises ExceptionsFileError if the file fails schema validation or
    contains a duplicate exception id (spec Edge Case: "two exception
    entries share the same id").
    """
    exceptions_path = path if path is not None else policy_dir() / "exceptions.yml"
    with exceptions_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    schema = load_exceptions_schema()
    try:
        jsonschema.validate(instance=raw, schema=schema)
    except jsonschema.ValidationError as exc:
        field_path = ".".join(str(p) for p in exc.absolute_path) or "(root)"
        raise ExceptionsFileError(f"{field_path}: {exc.message}") from exc

    entries = [_parse_entry(item) for item in raw["exceptions"]]

    seen: set[str] = set()
    duplicates: set[str] = set()
    for entry in entries:
        if entry.id in seen:
            duplicates.add(entry.id)
        seen.add(entry.id)
    if duplicates:
        raise ExceptionsFileError(
            f"policy/exceptions.yml contains duplicate exception id(s): {sorted(duplicates)}"
        )

    return entries


def check(exception_id: str, as_of: date | None = None, path: Path | None = None) -> ExceptionStatus:
    """Return whether exception_id is active, expired, or not recorded."""
    as_of_date = as_of if as_of is not None else date.today()
    entries = load(path)
    for entry in entries:
        if entry.id == exception_id:
            return "expired" if entry.expires < as_of_date else "active"
    return "not_found"
