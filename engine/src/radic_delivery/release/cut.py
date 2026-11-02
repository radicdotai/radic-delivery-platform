"""Orchestrates `release cut`: validate the manifest, re-verify change-note
records, cherry-pick in chronological order, roll back cleanly on
conflict (research.md D1-D7).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from radic_delivery.release.git_history import (
    abort_cherry_pick,
    checkout,
    cherry_pick,
    commit_timestamp,
    create_branch_from,
    current_branch,
    delete_branch,
    resolve_ref,
)
from radic_delivery.release.result import CutReason, CutResult

_PROD_BRANCH = "main"


def _refused(
    manifest: dict[str, Any], reason: CutReason, detail: str, dry_run: bool, failed_sha: str | None = None
) -> CutResult:
    return CutResult(
        ok=False, manifest=manifest, reason=reason, detail=detail, failed_sha=failed_sha, dry_run=dry_run
    )


def _selected_shas(manifest: dict[str, Any]) -> list[str]:
    shas: list[str] = []
    for ticket in manifest["selection"]["tickets"]:
        shas.extend(commit["dev_sha"] for commit in ticket["commits"])
    for pr in manifest["selection"]["non_jira_prs"]:
        shas.extend(commit["dev_sha"] for commit in pr["commits"])
    return shas


def _missing_change_note(change_notes_dir: Path, repo: str, sha: str) -> bool:
    return not (change_notes_dir / "change-notes" / repo / f"{sha}.json").is_file()


def cut(
    manifest: dict[str, Any],
    *,
    repo_dir: Path,
    change_notes_dir: Path,
    release_id: str,
    hotfix: bool,
    dry_run: bool,
) -> CutResult:
    if manifest["release_id"] != release_id:
        return _refused(
            manifest,
            "release_id_mismatch",
            f"--release-id '{release_id}' does not match the manifest's release_id "
            f"'{manifest['release_id']}'.",
            dry_run,
        )

    manifest_is_hotfix = manifest["kind"] == "hotfix"
    if manifest_is_hotfix != hotfix:
        return _refused(
            manifest,
            "hotfix_mismatch",
            f"--hotfix={hotfix} does not match the manifest's kind '{manifest['kind']}'.",
            dry_run,
        )

    if manifest["status"] != "proposed":
        return _refused(
            manifest,
            "status_mismatch",
            f"manifest status is '{manifest['status']}', expected 'proposed'.",
            dry_run,
        )

    repo = manifest["repo"]
    all_shas = _selected_shas(manifest)
    for sha in all_shas:
        if _missing_change_note(change_notes_dir, repo, sha):
            return _refused(
                manifest,
                "missing_change_note",
                f"commit {sha} has no change-note record under {change_notes_dir}.",
                dry_run,
                failed_sha=sha,
            )

    ordered_shas = sorted(all_shas, key=lambda sha: commit_timestamp(repo_dir, sha))
    branch_name = f"release/{release_id}"

    if dry_run:
        return CutResult(ok=True, manifest=manifest, dry_run=True)

    original_branch = current_branch(repo_dir)
    create_branch_from(repo_dir, branch_name, _PROD_BRANCH)

    release_shas: dict[str, str] = {}
    for sha in ordered_shas:
        outcome = cherry_pick(repo_dir, sha)
        if outcome == "conflict":
            abort_cherry_pick(repo_dir)
            checkout(repo_dir, original_branch)
            delete_branch(repo_dir, branch_name)
            return _refused(
                manifest,
                "cherry_pick_conflict",
                f"cherry-picking {sha} onto {branch_name} conflicted.",
                dry_run=False,
                failed_sha=sha,
            )
        release_shas[sha] = resolve_ref(repo_dir, "HEAD")

    release_head = release_shas[ordered_shas[-1]] if ordered_shas else resolve_ref(repo_dir, "HEAD")

    updated = copy.deepcopy(manifest)
    updated["status"] = "cut"
    updated["release_branch"] = branch_name
    updated["release_head"] = release_head
    for ticket in updated["selection"]["tickets"]:
        for commit in ticket["commits"]:
            commit["release_sha"] = release_shas[commit["dev_sha"]]
            commit["cherry_pick_x"] = True
    for pr in updated["selection"]["non_jira_prs"]:
        for commit in pr["commits"]:
            commit["release_sha"] = release_shas[commit["dev_sha"]]
            commit["cherry_pick_x"] = True

    return CutResult(ok=True, manifest=updated, dry_run=False)
