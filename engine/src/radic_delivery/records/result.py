"""RecordIssue / PutResult (data-model.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RecordIssue:
    path: str
    message: str


@dataclass(frozen=True)
class PutResult:
    ok: bool
    local_path: str | None = None
    result: str | None = None
    issues: list[RecordIssue] = field(default_factory=list)
    upload_status: str = "not_available"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "local_path": self.local_path,
            "result": self.result,
            "issues": [{"path": issue.path, "message": issue.message} for issue in self.issues],
            "upload_status": self.upload_status,
        }
