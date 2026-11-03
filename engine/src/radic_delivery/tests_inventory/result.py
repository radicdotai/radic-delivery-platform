"""TestInventoryResult (data-model.md)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TestInventoryResult:
    launched: bool
    suite: str = "unit"
    total: int | None = None
    passed: int | None = None
    failed: int | None = None
    skipped: int | None = None
    quarantined_active: int | None = None
    quarantined_expired: int | None = None
    within_quarantine_share_cap: bool | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "launched": self.launched,
            "suite": self.suite,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "quarantined_active": self.quarantined_active,
            "quarantined_expired": self.quarantined_expired,
            "within_quarantine_share_cap": self.within_quarantine_share_cap,
            "detail": self.detail,
        }
