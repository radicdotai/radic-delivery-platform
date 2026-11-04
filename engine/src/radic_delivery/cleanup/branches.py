"""`radic-delivery cleanup branches` — deletes merged, expired
`release/**` branches (research.md D1-D6). `main`, `dev`, and the
currently checked-out branch are never candidates, regardless of ancestry
or age (research.md D4)."""

from __future__ import annotations

import time
from pathlib import Path

from radic_delivery.cleanup.result import CleanupBranchesResult, KeptBranch
from radic_delivery.release.git_history import (
    commit_timestamp,
    current_branch,
    delete_branch,
    is_ancestor,
    list_branches,
    resolve_ref,
)

_PROTECTED_BRANCHES = {"main", "dev"}


def cleanup_branches(
    *,
    repo_dir: Path,
    retention_days: int,
    dry_run: bool,
    as_of: int | None = None,
) -> CleanupBranchesResult:
    now = as_of if as_of is not None else int(time.time())
    retention_seconds = retention_days * 86400
    protected = _PROTECTED_BRANCHES | {current_branch(repo_dir)}

    deleted: list[str] = []
    kept: list[KeptBranch] = []
    for branch in list_branches(repo_dir, "release/*"):
        if branch in protected:
            continue
        tip = resolve_ref(repo_dir, branch)
        if not is_ancestor(repo_dir, tip, "main"):
            kept.append(KeptBranch(name=branch, reason="not_yet_merged"))
            continue
        age_seconds = now - commit_timestamp(repo_dir, tip)
        if age_seconds < retention_seconds:
            kept.append(KeptBranch(name=branch, reason="too_recent"))
            continue
        deleted.append(branch)
        if not dry_run:
            delete_branch(repo_dir, branch)

    return CleanupBranchesResult(dry_run=dry_run, deleted=deleted, kept=kept)
