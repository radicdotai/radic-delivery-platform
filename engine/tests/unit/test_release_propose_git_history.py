"""Real, unmocked git subprocess tests for release/git_history.py."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from radic_delivery.release.git_history import reachable_shas


def _git(repo_dir: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo_dir, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _git(repo_dir, "init", "-q", "-b", "dev")
    _git(repo_dir, "config", "user.email", "test@example.com")
    _git(repo_dir, "config", "user.name", "Test")
    return repo_dir


def _commit(repo_dir: Path, message: str) -> str:
    _git(repo_dir, "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo_dir, "rev-parse", "HEAD")


def test_all_commits_reachable_from_base_are_returned(repo: Path) -> None:
    sha_a = _commit(repo, "first")
    sha_b = _commit(repo, "second")

    result = reachable_shas(repo, base="dev")
    assert result == {sha_a, sha_b}


def test_since_sha_excludes_its_own_ancestors(repo: Path) -> None:
    sha_a = _commit(repo, "first")
    sha_b = _commit(repo, "second")
    sha_c = _commit(repo, "third")

    result = reachable_shas(repo, base="dev", since_sha=sha_b)
    assert result == {sha_c}
    assert sha_a not in result
    assert sha_b not in result


def test_since_sha_equal_to_base_head_excludes_everything(repo: Path) -> None:
    sha_a = _commit(repo, "only commit")
    result = reachable_shas(repo, base="dev", since_sha=sha_a)
    assert result == set()
