"""Real-git-fixture test for release/git_history.py's changed_paths()
(research.md D2)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from radic_delivery.release.git_history import changed_paths


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
    (repo_dir / filename).parent.mkdir(parents=True, exist_ok=True)
    (repo_dir / filename).write_text(content)
    _git(repo_dir, "add", filename)
    _git(repo_dir, "commit", "-q", "-m", message)
    return _git(repo_dir, "rev-parse", "HEAD")


def test_changed_paths_reports_exactly_what_differs(repo: Path) -> None:
    base_sha = _git(repo, "rev-parse", "HEAD")
    _write_and_commit(repo, "deploy/run/stage.yaml", "a: 1", "touch stage service yaml")
    _write_and_commit(repo, "src/app.py", "print(1)", "unrelated app change")
    head_sha = _git(repo, "rev-parse", "HEAD")

    result = changed_paths(repo, base_sha, head_sha)

    assert result == {"deploy/run/stage.yaml", "src/app.py"}


def test_changed_paths_empty_for_identical_commits(repo: Path) -> None:
    sha = _git(repo, "rev-parse", "HEAD")
    assert changed_paths(repo, sha, sha) == set()
