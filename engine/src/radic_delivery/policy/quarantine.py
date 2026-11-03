"""Load, validate, and classify policy/quarantine.yml — the single ledger
of tests currently quarantined under the platform's quarantine policy
(research.md D2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import jsonschema
import yaml

from radic_delivery.paths import policy_dir
from radic_delivery.policy.quarantine_schema_loader import load_quarantine_schema

_MAX_QUARANTINE_DAYS = 7


class QuarantineFileError(ValueError):
    """The quarantine ledger itself is malformed (schema violation)."""


@dataclass(frozen=True)
class QuarantineEntry:
    service: str
    test_id: str
    reason: str
    jira_key: str
    quarantined_since: date


def _parse_entry(raw: dict[str, object]) -> QuarantineEntry:
    return QuarantineEntry(
        service=str(raw["service"]),
        test_id=str(raw["test_id"]),
        reason=str(raw["reason"]),
        jira_key=str(raw["jira_key"]),
        quarantined_since=date.fromisoformat(str(raw["quarantined_since"])),
    )


def load(path: Path | None = None) -> list[QuarantineEntry]:
    """Load and schema-validate the quarantine ledger."""
    quarantine_path = path if path is not None else policy_dir() / "quarantine.yml"
    with quarantine_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    schema = load_quarantine_schema()
    try:
        jsonschema.validate(instance=raw, schema=schema)
    except jsonschema.ValidationError as exc:
        field_path = ".".join(str(p) for p in exc.absolute_path) or "(root)"
        raise QuarantineFileError(f"{field_path}: {exc.message}") from exc

    return [_parse_entry(item) for item in raw["quarantine"]]


def classify_for_service(
    entries: list[QuarantineEntry], service: str, as_of: date
) -> tuple[int, int]:
    """Return (active, expired) counts for `service`'s quarantined tests.

    `active` means still within the fixed 7-day quarantine window from
    `quarantined_since`; `expired` means past it. Entries for a different
    service are excluded entirely.
    """
    active = 0
    expired = 0
    for entry in entries:
        if entry.service != service:
            continue
        if entry.quarantined_since + timedelta(days=_MAX_QUARANTINE_DAYS) >= as_of:
            active += 1
        else:
            expired += 1
    return active, expired
