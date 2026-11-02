"""Real-git-fixture tests for the six primitives added to
release/git_history.py by specs/011 (research.md D1/D3): tree_sha,
is_ancestor, tag_exists_at, list_version_tags, create_tag,
fast_forward_branch."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from radic_delivery.release.git_history import (
    create_tag,
    fast_forward_branch,
    is_ancestor,
    list_version_tags,
    tag_exists_at,
    tree_sha,
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
    (repo_dir / "README.md").write_text("init\n")
    _git(repo_dir, "add", "README.md")
    _git(repo_dir, "commit", "-q", "-m", "initial")
    return repo_dir


def _write_and_commit(repo_dir: Path, filename: str, content: str, message: str) -> str:
    (repo_dir / filename).write_text(content)
    _git(repo_dir, "add", filename)
    _git(repo_dir, "commit", "-q", "-m", message)
    return _git(repo_dir, "rev-parse", "HEAD")


# --- tree_sha -----------------------------------------------------------


def test_tree_sha_equal_for_identical_content(repo: Path) -> None:
    sha_a = _write_and_commit(repo, "a.txt", "same", "first")
    _git(repo, "checkout", "-q", "-b", "other", sha_a)
    sha_b = _write_and_commit(repo, "unrelated.txt", "noise", "second")
    _git(repo, "rm", "-q", "unrelated.txt")
    _git(repo, "commit", "-q", "-m", "revert noise")
    sha_c = _git(repo, "rev-parse", "HEAD")
    assert tree_sha(repo, sha_a) == tree_sha(repo, sha_c)
    assert tree_sha(repo, sha_a) != tree_sha(repo, sha_b)


def test_tree_sha_differs_for_different_content(repo: Path) -> None:
    sha_a = _write_and_commit(repo, "a.txt", "one", "first")
    sha_b = _write_and_commit(repo, "a.txt", "two", "second")
    assert tree_sha(repo, sha_a) != tree_sha(repo, sha_b)


# --- is_ancestor ----------------------------------------------------------


def test_is_ancestor_true_for_real_ancestor(repo: Path) -> None:
    base_sha = _git(repo, "rev-parse", "HEAD")
    descendant_sha = _write_and_commit(repo, "a.txt", "1", "second")
    assert is_ancestor(repo, base_sha, descendant_sha) is True


def test_is_ancestor_false_for_unrelated_branch(repo: Path) -> None:
    base_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side", base_sha)
    side_sha = _write_and_commit(repo, "side.txt", "1", "side commit")
    _git(repo, "checkout", "-q", "main")
    forward_sha = _write_and_commit(repo, "main.txt", "1", "main commit")
    assert is_ancestor(repo, side_sha, forward_sha) is False


# --- tag_exists_at ----------------------------------------------------------


def test_tag_exists_at_true_when_tag_points_at_commit(repo: Path) -> None:
    sha = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "tag", "v1.0.0", sha)
    assert tag_exists_at(repo, "v1.0.0", sha) is True


def test_tag_exists_at_false_when_missing(repo: Path) -> None:
    sha = _write_and_commit(repo, "a.txt", "1", "first")
    assert tag_exists_at(repo, "no-such-tag", sha) is False


def test_tag_exists_at_false_when_pointing_elsewhere(repo: Path) -> None:
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "tag", "v1.0.0", sha_a)
    sha_b = _write_and_commit(repo, "a.txt", "2", "second")
    assert tag_exists_at(repo, "v1.0.0", sha_b) is False


# --- list_version_tags -------------------------------------------------


def test_list_version_tags_returns_only_v_pattern_sorted(repo: Path) -> None:
    sha = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "tag", "v1.0.0", sha)
    _git(repo, "tag", "v1.2.0", sha)
    _git(repo, "tag", "not-a-version", sha)
    assert list_version_tags(repo) == ["v1.0.0", "v1.2.0"]


def test_list_version_tags_empty_when_none_exist(repo: Path) -> None:
    assert list_version_tags(repo) == []


# --- create_tag --------------------------------------------------------


def test_create_tag_creates_a_real_readable_tag(repo: Path) -> None:
    sha = _write_and_commit(repo, "a.txt", "1", "first")
    create_tag(repo, "v2.0.0", sha)
    assert tag_exists_at(repo, "v2.0.0", sha) is True


# --- fast_forward_branch -------------------------------------------------


def test_fast_forward_branch_moves_branch_on_clean_ancestor(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    target_sha = _write_and_commit(repo, "a.txt", "1", "ahead")
    _git(repo, "checkout", "-q", "main")

    outcome = fast_forward_branch(repo, "main", target_sha)

    assert outcome == "ok"
    assert _git(repo, "rev-parse", "main") == target_sha


def test_fast_forward_branch_refuses_when_not_a_fast_forward(repo: Path) -> None:
    root_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side", root_sha)
    side_sha = _write_and_commit(repo, "side.txt", "1", "side commit")
    _git(repo, "checkout", "-q", "main")
    main_sha = _write_and_commit(repo, "main.txt", "1", "main's own, separate commit")

    outcome = fast_forward_branch(repo, "main", side_sha)

    assert outcome == "not_fast_forward"
    assert _git(repo, "rev-parse", "main") == main_sha
