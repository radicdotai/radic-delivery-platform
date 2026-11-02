"""Real git subprocess calls: which commit SHAs are reachable from `base`'s
HEAD, excluding anything already an ancestor of `since_sha` (research.md D2).

Every git invocation here is a fixed, parameterised ancestry query
(Principle VII) — never a caller-supplied command string.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


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
