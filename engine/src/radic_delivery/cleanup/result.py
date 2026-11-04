"""CleanupBranchesResult, KeptBranch (data-model.md) — pure computation
results, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

KeptReason = Literal["not_yet_merged", "too_recent"]


@dataclass(frozen=True)
class KeptBranch:
    name: str
    reason: KeptReason

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "reason": self.reason}


@dataclass(frozen=True)
class CleanupBranchesResult:
    dry_run: bool
    deleted: list[str] = field(default_factory=list)
    kept: list[KeptBranch] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "deleted": list(self.deleted),
            "kept": [k.to_dict() for k in self.kept],
            "dry_run": self.dry_run,
        }
