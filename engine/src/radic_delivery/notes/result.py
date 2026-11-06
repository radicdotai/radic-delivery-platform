"""ChangeNoteBuildResult / WriteResult / ReleaseNoteCheckResult (data-model.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Classification = Literal["has_jira_key", "explicit_none", "incomplete"]


@dataclass(frozen=True)
class BuildIssue:
    path: str
    message: str


@dataclass(frozen=True)
class ChangeNoteBuildResult:
    ok: bool
    record: dict[str, Any] | None
    issues: list[BuildIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "record": self.record,
            "issues": [{"path": issue.path, "message": issue.message} for issue in self.issues],
        }


@dataclass(frozen=True)
class WriteResult:
    local_path: str
    upload_status: Literal["not_available"] = "not_available"

    def to_dict(self) -> dict[str, Any]:
        return {"local_path": self.local_path, "upload_status": self.upload_status}


MigrationFlag = Literal["none", "expand", "contract"]


@dataclass(frozen=True)
class MigrationCheckResult:
    """Cross-checks a computed migration flag against an optional
    `Migrations:` PR-body declaration (specs/017 research.md D5). Unlike
    `ReleaseNoteCheckResult`, there is no blocking/non-blocking mode: a
    real mismatch always fails."""

    computed: MigrationFlag
    declared: MigrationFlag | None
    matched: bool
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "computed": self.computed,
            "declared": self.declared,
            "matched": self.matched,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ReleaseNoteCheckResult:
    classification: Classification
    jira_key: str | None
    blocking: bool
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "jira_key": self.jira_key,
            "blocking": self.blocking,
            "passed": self.passed,
            "detail": self.detail,
        }


def build_check_result(
    classification: Classification, jira_key: str | None, blocking: bool
) -> ReleaseNoteCheckResult:
    """research.md D5: classification never changes between modes; only
    whether an `incomplete` result passes depends on `blocking`."""
    if classification == "incomplete":
        passed = not blocking
        detail = (
            "No Jira reference found (expected a 'Jira: KEY' line) and no explicit "
            "'Jira: None' opt-out was given."
        )
    else:
        passed = True
        detail = ""
    return ReleaseNoteCheckResult(
        classification=classification,
        jira_key=jira_key,
        blocking=blocking,
        passed=passed,
        detail=detail,
    )
