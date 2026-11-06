"""Real git subprocess calls: which commit SHAs are reachable from `base`'s
HEAD, excluding anything already an ancestor of `since_sha` (research.md D2).

Every git invocation here is a fixed, parameterised ancestry query
(Principle VII) — never a caller-supplied command string.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal


class GitHistoryError(RuntimeError):
    pass


def _git_log_shas(repo_dir: Path, ref: str) -> set[str]:
    try:
        result = subprocess.run(
            ["git", "log", "--format=%H", ref],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"git log failed for ref '{ref}' in {repo_dir}: {exc}") from exc
    return {line for line in result.stdout.splitlines() if line}


def reachable_shas(repo_dir: Path, base: str, since_sha: str | None = None) -> set[str]:
    base_shas = _git_log_shas(repo_dir, base)
    if since_sha is None:
        return base_shas
    excluded_shas = _git_log_shas(repo_dir, since_sha)
    return base_shas - excluded_shas


def resolve_ref(repo_dir: Path, ref: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", ref], cwd=repo_dir, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"could not resolve ref '{ref}' in {repo_dir}: {exc}") from exc
    return result.stdout.strip()


def commit_timestamp(repo_dir: Path, sha: str) -> int:
    try:
        result = subprocess.run(
            ["git", "show", "-s", "--format=%ct", sha],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"could not read commit timestamp for '{sha}' in {repo_dir}: {exc}") from exc
    return int(result.stdout.strip())


def current_branch(repo_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"could not determine current branch in {repo_dir}: {exc}") from exc
    return result.stdout.strip()


def create_branch_from(repo_dir: Path, branch_name: str, base_ref: str) -> None:
    """Create and check out `branch_name` from `base_ref`. `base_ref` is
    always a fixed value this platform controls (research.md D1) — never
    a caller-suppliable arbitrary string passed through unchecked."""
    try:
        subprocess.run(
            ["git", "checkout", "-b", branch_name, base_ref],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(
            f"could not create branch '{branch_name}' from '{base_ref}' in {repo_dir}: {exc}"
        ) from exc


def checkout(repo_dir: Path, ref: str) -> None:
    try:
        subprocess.run(
            ["git", "checkout", ref], cwd=repo_dir, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"could not check out '{ref}' in {repo_dir}: {exc}") from exc


def cherry_pick(repo_dir: Path, sha: str) -> Literal["ok", "conflict"]:
    """`git cherry-pick -x` — the `-x` records the original SHA in the
    resulting commit message (the manifest schema's `cherry_pick_x` field
    name, Reference 3). A conflict is a distinguished, expected outcome,
    not raised as an error — any other failure is."""
    result = subprocess.run(
        ["git", "cherry-pick", "-x", sha], cwd=repo_dir, capture_output=True, text=True
    )
    if result.returncode == 0:
        return "ok"
    combined_output = result.stdout + result.stderr
    if "CONFLICT" in combined_output or "after resolving the conflicts" in combined_output:
        return "conflict"
    raise GitHistoryError(f"git cherry-pick -x {sha} failed in {repo_dir}: {combined_output}")


def abort_cherry_pick(repo_dir: Path) -> None:
    try:
        subprocess.run(
            ["git", "cherry-pick", "--abort"], cwd=repo_dir, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"could not abort cherry-pick in {repo_dir}: {exc}") from exc


def delete_branch(repo_dir: Path, branch_name: str) -> None:
    try:
        subprocess.run(
            ["git", "branch", "-D", branch_name], cwd=repo_dir, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"could not delete branch '{branch_name}' in {repo_dir}: {exc}") from exc


def tree_sha(repo_dir: Path, commit: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", f"{commit}^{{tree}}"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"could not resolve tree for commit '{commit}' in {repo_dir}: {exc}") from exc
    return result.stdout.strip()


def is_ancestor(repo_dir: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode in (0, 1):
        return result.returncode == 0
    raise GitHistoryError(
        f"could not check ancestry of '{ancestor}' -> '{descendant}' in {repo_dir}: "
        f"{result.stdout + result.stderr}"
    )


def tag_exists_at(repo_dir: Path, tag: str, commit: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    tag_commit = subprocess.run(
        ["git", "rev-list", "-n", "1", tag],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return tag_commit == resolve_ref(repo_dir, commit)


def list_version_tags(repo_dir: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "tag", "--list", "v*"], cwd=repo_dir, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"could not list version tags in {repo_dir}: {exc}") from exc
    return sorted(line for line in result.stdout.splitlines() if line)


def create_tag(repo_dir: Path, tag: str, commit: str) -> None:
    try:
        subprocess.run(
            ["git", "tag", tag, commit], cwd=repo_dir, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"could not create tag '{tag}' at '{commit}' in {repo_dir}: {exc}") from exc


def changed_paths(repo_dir: Path, base: str, head: str) -> set[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base, head],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"could not diff '{base}'..'{head}' in {repo_dir}: {exc}") from exc
    return {line for line in result.stdout.splitlines() if line}


def added_paths(repo_dir: Path, base: str, head: str) -> set[str]:
    """Paths genuinely added between `base` and `head` — unlike
    `changed_paths`, a modified or deleted file is never included
    (specs/017 research.md D2)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=A", base, head],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"could not diff '{base}'..'{head}' in {repo_dir}: {exc}") from exc
    return {line for line in result.stdout.splitlines() if line}


def list_branches(repo_dir: Path, pattern: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname:short)", f"refs/heads/{pattern}"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        raise GitHistoryError(f"could not list branches matching '{pattern}' in {repo_dir}: {exc}") from exc
    return [line for line in result.stdout.splitlines() if line]


def fast_forward_branch(repo_dir: Path, branch: str, target: str) -> Literal["ok", "not_fast_forward"]:
    """Checks out `branch` and fast-forward-merges `target` into it.
    `--ff-only` is git's own independent re-enforcement of the same
    ancestry guarantee this feature's own pre-check already confirms
    (research.md D3) — never a forced or three-way merge."""
    checkout(repo_dir, branch)
    result = subprocess.run(
        ["git", "merge", "--ff-only", target], cwd=repo_dir, capture_output=True, text=True
    )
    if result.returncode == 0:
        return "ok"
    return "not_fast_forward"
