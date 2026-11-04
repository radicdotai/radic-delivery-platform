"""`release backport`: cherry-picks a succeeded hotfix's already-cut
commits back onto `dev` (or another target), continuing past any
individually-conflicting commit rather than aborting the whole operation
(research.md D1-D3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from radic_delivery.release.git_history import (
    abort_cherry_pick,
    cherry_pick,
    commit_timestamp,
    create_branch_from,
)


@dataclass(frozen=True)
class BackportResult:
    branch: str
    picked_commits: list[str] = field(default_factory=list)
    conflicted_commits: list[str] = field(default_factory=list)

    @property
    def conflicts(self) -> bool:
        return len(self.conflicted_commits) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "picked_commits": self.picked_commits,
            "conflicted_commits": self.conflicted_commits,
            "conflicts": self.conflicts,
        }


def _selected_release_shas(manifest: dict[str, Any]) -> list[str]:
    shas: list[str] = []
    for ticket in manifest["selection"]["tickets"]:
        shas.extend(commit["release_sha"] for commit in ticket["commits"])
    for pr in manifest["selection"].get("non_jira_prs", []):
        shas.extend(commit["release_sha"] for commit in pr["commits"])
    return shas


def backport(manifest: dict[str, Any], *, repo_dir: Path, into: str = "dev") -> BackportResult:
    release_id = manifest["release_id"]
    branch_name = f"backport/{release_id}"

    shas = _selected_release_shas(manifest)
    ordered_shas = sorted(set(shas), key=lambda sha: commit_timestamp(repo_dir, sha))

    create_branch_from(repo_dir, branch_name, into)

    picked: list[str] = []
    conflicted: list[str] = []
    for sha in ordered_shas:
        outcome = cherry_pick(repo_dir, sha)
        if outcome == "conflict":
            abort_cherry_pick(repo_dir)
            conflicted.append(sha)
        else:
            picked.append(sha)

    return BackportResult(branch=branch_name, picked_commits=picked, conflicted_commits=conflicted)
