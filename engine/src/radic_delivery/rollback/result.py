"""RollbackPlan (data-model.md) — a pure computation result, no I/O."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RollbackPlan:
    environment: str
    current_release: str
    current_digest: str
    target_release: str
    target_digest: str
    estimated_minutes: int
    migrations_reverted: bool
    no_op: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "current_release": self.current_release,
            "current_digest": self.current_digest,
            "target_release": self.target_release,
            "target_digest": self.target_digest,
            "estimated_minutes": self.estimated_minutes,
            "migrations_reverted": self.migrations_reverted,
            "no_op": self.no_op,
        }
