"""Real, unmocked git subprocess tests for release/git_history.py's
branch/cherry-pick operations (research.md D1)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from radic_delivery.release.git_history import (
    GitHistoryError,
    abort_cherry_pick,
    checkout,
    cherry_pick,
    commit_timestamp,
    create_branch_from,
    current_branch,
    delete_branch,
)


def _git(repo_dir: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo_dir, capture_output=True, text=True, check=True)
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _git(repo_dir, "init", "-q", "-b", "main")
    _git(repo_dir, "config", "user.email", "test@example.com")
    _git(repo_dir, "config", "user.name", "Test")
    return repo_dir


def _write_and_commit(repo_dir: Path, filename: str, content: str, message: str) -> str:
    (repo_dir / filename).write_text(content)
    _git(repo_dir, "add", filename)
    _git(repo_dir, "commit", "-q", "-m", message)
    return _git(repo_dir, "rev-parse", "HEAD")


def test_create_branch_from_checks_out_the_new_branch_from_the_base(repo: Path) -> None:
    _write_and_commit(repo, "a.txt", "1", "first")
    create_branch_from(repo, "release/test-1", "main")
    assert current_branch(repo) == "release/test-1"


def test_cherry_pick_succeeds_for_a_clean_commit(repo: Path) -> None:
    _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-b", "dev")
    sha = _write_and_commit(repo, "b.txt", "2", "second")
    _git(repo, "checkout", "main")
    create_branch_from(repo, "release/test-2", "main")

    outcome = cherry_pick(repo, sha)
    assert outcome == "ok"
    assert (repo / "b.txt").read_text() == "2"


def test_commit_timestamp_orders_sequential_commits_correctly(repo: Path) -> None:
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    sha_b = _write_and_commit(repo, "b.txt", "2", "second")
    assert commit_timestamp(repo, sha_a) <= commit_timestamp(repo, sha_b)


def test_checkout_and_current_branch_round_trip(repo: Path) -> None:
    _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "branch", "other")
    checkout(repo, "other")
    assert current_branch(repo) == "other"
    checkout(repo, "main")
    assert current_branch(repo) == "main"


def test_delete_branch_removes_it(repo: Path) -> None:
    _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "branch", "throwaway")
    delete_branch(repo, "throwaway")
    branches = _git(repo, "branch", "--list", "throwaway")
    assert branches == ""


def test_abort_cherry_pick_after_a_conflict_restores_clean_state(repo: Path) -> None:
    _write_and_commit(repo, "a.txt", "line1\n", "first")
    _git(repo, "checkout", "-b", "dev")
    sha = _write_and_commit(repo, "a.txt", "dev change\n", "dev changes a.txt")
    _git(repo, "checkout", "main")
    _write_and_commit(repo, "a.txt", "main change\n", "main changes a.txt")

    outcome = cherry_pick(repo, sha)
    assert outcome == "conflict"
    abort_cherry_pick(repo)
    status = _git(repo, "status", "--porcelain")
    assert status == ""


def test_invalid_repo_dir_raises_git_history_error(tmp_path: Path) -> None:
    with pytest.raises(GitHistoryError):
        current_branch(tmp_path / "not-a-repo")
