"""Locate the repository root that holds schemas/ and policy/.

The engine is developed in-tree inside radic-delivery-platform, where
schemas/ and policy/ live at the repo root, one level above engine/. This
walks upward from both the installed package location and the current
working directory so the CLI works whether invoked from the repo root or
from engine/.
"""

from __future__ import annotations

from pathlib import Path


class RepoRootNotFoundError(RuntimeError):
    pass


def _looks_like_repo_root(candidate: Path) -> bool:
    return (candidate / "schemas").is_dir() and (candidate / "policy").is_dir()


def find_repo_root() -> Path:
    search_starts = [Path(__file__).resolve(), Path.cwd()]
    for start in search_starts:
        for candidate in (start, *start.parents):
            if _looks_like_repo_root(candidate):
                return candidate
    raise RepoRootNotFoundError(
        "Could not locate a radic-delivery-platform repo root "
        "(a directory containing both schemas/ and policy/)."
    )


def schemas_dir() -> Path:
    return find_repo_root() / "schemas"


def policy_dir() -> Path:
    return find_repo_root() / "policy"
