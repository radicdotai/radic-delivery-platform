"""`release finalise`: fast-forward `main`, tag it, and close out a
release manifest after prod success (research.md D3).

Validates manifest/status/digest consistency *before* touching git at
all; the fast-forward pre-check and `git merge --ff-only`'s own refusal
both have to agree before `main` or any tag changes (defense in depth).
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from radic_delivery.release.git_history import (
    GitHistoryError,
    create_tag,
    fast_forward_branch,
    is_ancestor,
    list_version_tags,
)
from radic_delivery.release.result import FinaliseReason, FinaliseResult

_PROD_BRANCH = "main"


def _refused(manifest: dict[str, Any], reason: FinaliseReason, detail: str) -> FinaliseResult:
    return FinaliseResult(ok=False, manifest=manifest, reason=reason, detail=detail)


def _next_tag(repo_dir: Path, bump: str) -> str:
    existing = list_version_tags(repo_dir)
    if not existing:
        return "v1.0.0"
    major, minor, patch = (int(part) for part in existing[-1].removeprefix("v").split("."))
    if bump == "major":
        return f"v{major + 1}.0.0"
    if bump == "minor":
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def finalise(
    manifest: dict[str, Any],
    *,
    repo_dir: Path,
    release_id: str,
    prod_digest: str,
    tag: str | None = None,
    bump: str = "patch",
) -> FinaliseResult:
    if manifest["release_id"] != release_id:
        return _refused(
            manifest,
            "release_id_mismatch",
            f"--release-id '{release_id}' does not match the manifest's release_id "
            f"'{manifest['release_id']}'.",
        )

    if manifest["status"] != "prod-deployed":
        return _refused(
            manifest,
            "status_mismatch",
            f"manifest status is '{manifest['status']}', expected 'prod-deployed'.",
        )

    existing_prod_digest = manifest.get("digests", {}).get("prod")
    if existing_prod_digest is not None and existing_prod_digest != prod_digest:
        return _refused(
            manifest,
            "digest_mismatch",
            f"--prod-digest '{prod_digest}' does not match the manifest's recorded "
            f"digests.prod '{existing_prod_digest}'.",
        )

    release_head = manifest["release_head"]

    try:
        ancestry_ok = is_ancestor(repo_dir, _PROD_BRANCH, release_head)
    except GitHistoryError as exc:
        return _refused(manifest, "git_error", str(exc))

    if not ancestry_ok:
        return _refused(
            manifest,
            "not_fast_forward",
            f"'{_PROD_BRANCH}' is not an ancestor of release_head '{release_head}'; "
            "finalising would not be a clean forward move.",
        )

    outcome = fast_forward_branch(repo_dir, _PROD_BRANCH, release_head)
    if outcome != "ok":
        return _refused(
            manifest,
            "not_fast_forward",
            f"'{_PROD_BRANCH}' could not be fast-forwarded to release_head '{release_head}'.",
        )

    chosen_tag = tag if tag is not None else _next_tag(repo_dir, bump)
    create_tag(repo_dir, chosen_tag, release_head)

    updated = copy.deepcopy(manifest)
    updated["status"] = "finalised"
    updated.setdefault("digests", {})["prod"] = prod_digest
    updated["main"] = {
        "fast_forwarded_to": release_head,
        "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tag": chosen_tag,
    }

    return FinaliseResult(ok=True, manifest=updated, tag=chosen_tag)
