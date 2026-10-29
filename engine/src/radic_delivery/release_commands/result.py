"""ParsedCommand/CommandCheckResult (data-model.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ParseStatus = Literal["not_a_command", "malformed", "recognized"]
Classification = Literal["not_a_command", "malformed", "unauthorized", "accepted"]
Form = Literal[
    "release_remove",
    "release_add",
    "release_nonjira",
    "release_abort",
    "release_waive_dev_green",
    "research_close",
]


@dataclass(frozen=True)
class ParsedCommand:
    status: ParseStatus
    form: Form | None = None
    args: dict[str, str] = field(default_factory=dict)
    detail: str = ""


@dataclass(frozen=True)
class CommandCheckResult:
    classification: Classification
    form: Form | None = None
    args: dict[str, str] = field(default_factory=dict)
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "form": self.form,
            "args": self.args,
            "detail": self.detail,
        }
