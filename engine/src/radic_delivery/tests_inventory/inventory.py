"""`tests inventory`: run a service's own descriptor-driven unit-test
command for real, reusing `gate evaluate`'s own command construction and
output parsing, and report total/passed/failed/skipped plus a quarantine-
ledger lookup (research.md D1-D3).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from radic_delivery.gate.commands import unit_command
from radic_delivery.gate.parsers import parse_test_run
from radic_delivery.gate.runner import run as run_invocation
from radic_delivery.policy.quarantine import QuarantineEntry, classify_for_service
from radic_delivery.tests_inventory.result import TestInventoryResult

# quality.quarantine.max_percent_of_tests is a fixed platform constant
# (schemas/service.schema.json) — reported here informationally only.
_MAX_QUARANTINE_SHARE_PERCENT = 2.0


def inventory(
    descriptor: dict[str, Any],
    *,
    repo_dir: Path,
    quarantine_entries: list[QuarantineEntry],
    as_of: date,
) -> TestInventoryResult:
    outcome = run_invocation(unit_command(descriptor), repo_dir)

    if not outcome.launched:
        return TestInventoryResult(
            launched=False,
            detail=f"Could not execute the unit test tool: {outcome.stderr or 'launch failed'}",
        )

    test_run = parse_test_run(descriptor["quality"]["unit"]["runner"], outcome.stdout)
    total = test_run.passed + test_run.failed + test_run.skipped

    service_name = descriptor["service"]["name"]
    active, expired = classify_for_service(quarantine_entries, service_name, as_of)

    within_cap: bool | None = None
    if total > 0:
        within_cap = ((active + expired) / total) * 100 <= _MAX_QUARANTINE_SHARE_PERCENT

    return TestInventoryResult(
        launched=True,
        total=total,
        passed=test_run.passed,
        failed=test_run.failed,
        skipped=test_run.skipped,
        quarantined_active=active,
        quarantined_expired=expired,
        within_quarantine_share_cap=within_cap,
    )
