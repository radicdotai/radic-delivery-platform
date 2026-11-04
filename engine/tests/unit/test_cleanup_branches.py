"""Real-git-fixture tests for cleanup/branches.py: merged, expired
release branch deletion, with unconditional protection of main/dev/the
checked-out branch (research.md D1-D6)."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from radic_delivery.cleanup.branches import cleanup_branches
from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode

runner = CliRunner()
DAY = 86400


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


def _commit(repo_dir: Path, filename: str, content: str, message: str) -> None:
    (repo_dir / filename).write_text(content)
    _git(repo_dir, "add", filename)
    _git(repo_dir, "commit", "-q", "-m", message)


def _make_release_branch(repo_dir: Path, name: str, *, merge_into_main: bool) -> None:
    _git(repo_dir, "checkout", "-q", "-b", name)
    _commit(repo_dir, f"{name.replace('/', '_')}.txt", "content", f"commit for {name}")
    _git(repo_dir, "checkout", "-q", "main")
    if merge_into_main:
        _git(repo_dir, "merge", "-q", "--ff-only", name)


def test_merged_old_branch_is_deleted(repo: Path) -> None:
    _make_release_branch(repo, "release/2026.09.01-1", merge_into_main=True)
    now = int(time.time())

    result = cleanup_branches(repo_dir=repo, retention_days=14, dry_run=False, as_of=now + 30 * DAY)

    assert result.deleted == ["release/2026.09.01-1"]
    assert result.kept == []
    branches = _git(repo, "branch").split()
    assert "release/2026.09.01-1" not in branches


def test_merged_but_recent_branch_is_kept(repo: Path) -> None:
    _make_release_branch(repo, "release/2026.11.01-1", merge_into_main=True)
    now = int(time.time())

    result = cleanup_branches(repo_dir=repo, retention_days=14, dry_run=False, as_of=now)

    assert result.deleted == []
    assert len(result.kept) == 1
    assert result.kept[0].name == "release/2026.11.01-1"
    assert result.kept[0].reason == "too_recent"
    branches = _git(repo, "branch").split()
    assert "release/2026.11.01-1" in branches


def test_unmerged_branch_is_kept(repo: Path) -> None:
    _make_release_branch(repo, "release/2026.11.04-1", merge_into_main=False)
    now = int(time.time())

    result = cleanup_branches(repo_dir=repo, retention_days=14, dry_run=False, as_of=now + 30 * DAY)

    assert result.deleted == []
    assert len(result.kept) == 1
    assert result.kept[0].name == "release/2026.11.04-1"
    assert result.kept[0].reason == "not_yet_merged"


def test_checked_out_branch_is_never_a_candidate(repo: Path) -> None:
    _make_release_branch(repo, "release/2026.08.01-1", merge_into_main=True)
    _git(repo, "checkout", "-q", "release/2026.08.01-1")
    now = int(time.time())

    result = cleanup_branches(repo_dir=repo, retention_days=14, dry_run=False, as_of=now + 30 * DAY)

    assert result.deleted == []
    assert result.kept == []
    assert "main" not in result.deleted and "main" not in [k.name for k in result.kept]
    assert "dev" not in result.deleted and "dev" not in [k.name for k in result.kept]


def test_dry_run_reports_same_as_real_run_but_deletes_nothing(repo: Path) -> None:
    _make_release_branch(repo, "release/2026.07.01-1", merge_into_main=True)
    now = int(time.time())

    result = cleanup_branches(repo_dir=repo, retention_days=14, dry_run=True, as_of=now + 30 * DAY)

    assert result.deleted == ["release/2026.07.01-1"]
    assert result.dry_run is True
    branches = _git(repo, "branch").split()
    assert "release/2026.07.01-1" in branches  # still exists — dry run only suppressed the delete


def test_zero_release_branches_reports_empty_result(repo: Path) -> None:
    result = cleanup_branches(repo_dir=repo, retention_days=14, dry_run=False)

    assert result.deleted == []
    assert result.kept == []


def test_all_unmerged_branches_reports_all_kept(repo: Path) -> None:
    _make_release_branch(repo, "release/2026.11.02-1", merge_into_main=False)
    _make_release_branch(repo, "release/2026.11.03-1", merge_into_main=False)
    now = int(time.time())

    result = cleanup_branches(repo_dir=repo, retention_days=14, dry_run=False, as_of=now + 30 * DAY)

    assert result.deleted == []
    assert {k.name for k in result.kept} == {"release/2026.11.02-1", "release/2026.11.03-1"}
    assert all(k.reason == "not_yet_merged" for k in result.kept)


# --- CLI-level tests -----------------------------------------------------


def test_cli_real_run_deletes_and_exits_ok(repo: Path) -> None:
    _make_release_branch(repo, "release/2026.06.01-1", merge_into_main=True)

    result = runner.invoke(
        app,
        [
            "cleanup", "branches",
            "--repo-dir", str(repo),
            "--retention-days", "0",
            "--no-dry-run",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["deleted"] == ["release/2026.06.01-1"]
    assert payload["dry_run"] is False


def test_cli_dry_run_is_the_default(repo: Path) -> None:
    _make_release_branch(repo, "release/2026.05.01-1", merge_into_main=True)

    result = runner.invoke(
        app,
        [
            "cleanup", "branches",
            "--repo-dir", str(repo),
            "--retention-days", "0",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    branches = _git(repo, "branch").split()
    assert "release/2026.05.01-1" in branches


def test_cli_unresolvable_repo_dir_exits_infra_error(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "cleanup", "branches",
            "--repo-dir", str(tmp_path / "does-not-exist"),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.INFRA_ERROR)
