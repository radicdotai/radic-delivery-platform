"""MigrationGraphResult / MigrationFreezeResult / MigrationsCheckResult
(data-model.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

FreezeStatus = Literal["intact", "missing", "altered"]


@dataclass(frozen=True)
class Fork:
    down_revision: str
    files: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"down_revision": self.down_revision, "files": self.files}


@dataclass(frozen=True)
class MigrationGraphResult:
    sound: bool
    root: str | None = None
    forks: list[Fork] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sound": self.sound,
            "root": self.root,
            "forks": [fork.to_dict() for fork in self.forks],
            "cycles": self.cycles,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class FreezeCheck:
    file: str
    status: FreezeStatus
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"file": self.file, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class MigrationFreezeResult:
    checks: list[FreezeCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.status == "intact" for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "checks": [check.to_dict() for check in self.checks]}


@dataclass(frozen=True)
class MigrationsCheckResult:
    enabled: bool
    migrations_frozen: MigrationFreezeResult | None = None
    migration_graph: MigrationGraphResult | None = None
    alembic_check: Literal["not_available"] | None = None
    schema_check: Literal["not_available"] | None = None

    @property
    def ok(self) -> bool:
        if self.migrations_frozen is not None and not self.migrations_frozen.ok:
            return False
        if self.migration_graph is not None and not self.migration_graph.sound:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "enabled": self.enabled,
            "migrations_frozen": self.migrations_frozen.to_dict() if self.migrations_frozen else None,
            "migration_graph": self.migration_graph.to_dict() if self.migration_graph else None,
            "alembic_check": self.alembic_check,
            "schema_check": self.schema_check,
        }
