"""Candidate / Selection / ProposeResult (data-model.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Candidate:
    sha: str
    jira_key: str
    pr_number: int | None = None
    title: str = ""


@dataclass(frozen=True)
class ProposedTicket:
    key: str
    title: str
    commits: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "origin": "bot-proposal",
            "commits": [{"dev_sha": sha} for sha in self.commits],
        }


@dataclass(frozen=True)
class HeldBackTicket:
    key: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "reason": self.reason}


@dataclass(frozen=True)
class NonJiraPr:
    pr_number: int
    commits: list[str]
    reason: str = "MISSING"
    second_approver: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pr": self.pr_number,
            "reason": self.reason,
            "second_approver": self.second_approver,
            "commits": [{"dev_sha": sha} for sha in self.commits],
        }


@dataclass(frozen=True)
class Selection:
    tickets: list[ProposedTicket] = field(default_factory=list)
    held_back: list[HeldBackTicket] = field(default_factory=list)
    non_jira_prs: list[NonJiraPr] = field(default_factory=list)
    non_jira_prs_not_found: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class ManifestIssue:
    path: str
    message: str


@dataclass(frozen=True)
class ProposeResult:
    ok: bool
    manifest: dict[str, Any] | None
    issues: list[ManifestIssue] = field(default_factory=list)
    non_jira_prs_not_found: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "manifest": self.manifest,
            "issues": [{"path": issue.path, "message": issue.message} for issue in self.issues],
            "non_jira_prs_not_found": self.non_jira_prs_not_found,
        }
