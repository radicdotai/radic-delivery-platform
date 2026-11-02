"""`release verify-promotion`: ancestry/tree/tag, each reported
independently, plus an always-`not_available` Cloud-Deploy-digest fact
(research.md D1/D2).

Every check here is a real, local git fact computed against the same
release manifest `propose`/`cut` already produce — never a second,
inconsistent source of truth, and never a live GCP call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from radic_delivery.release.git_history import is_ancestor, tag_exists_at, tree_sha
from radic_delivery.release.result import PromotionVerification


def _commit_pairs(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for ticket in manifest["selection"]["tickets"]:
        pairs.extend((commit["dev_sha"], commit["release_sha"]) for commit in ticket["commits"])
    for pr in manifest["selection"]["non_jira_prs"]:
        pairs.extend((commit["dev_sha"], commit["release_sha"]) for commit in pr["commits"])
    return pairs


def verify_promotion(
    manifest: dict[str, Any],
    *,
    repo_dir: Path,
    release_head: str,
    expected_tag: str,
    cd_release: str | None = None,
) -> PromotionVerification:
    detail: list[str] = []

    ancestry_verified = is_ancestor(repo_dir, manifest["base"]["sha"], release_head)
    if not ancestry_verified:
        detail.append(
            f"release head '{release_head}' is not a descendant of base.sha "
            f"'{manifest['base']['sha']}'."
        )

    tree_verified = True
    for dev_sha, release_sha in _commit_pairs(manifest):
        if tree_sha(repo_dir, dev_sha) != tree_sha(repo_dir, release_sha):
            tree_verified = False
            detail.append(f"tree mismatch between dev_sha '{dev_sha}' and release_sha '{release_sha}'.")

    tag_verified = tag_exists_at(repo_dir, expected_tag, release_head)
    if not tag_verified:
        detail.append(
            f"expected tag '{expected_tag}' does not exist or does not point at release head "
            f"'{release_head}'."
        )

    return PromotionVerification(
        ancestry_verified=ancestry_verified,
        tree_verified=tree_verified,
        tag_verified=tag_verified,
        detail=detail,
    )
