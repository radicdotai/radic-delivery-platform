"""Real-git-fixture tests for release/backport.py: partial-conflict
tolerant cherry-pick backporting (research.md D1-D3)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode
from radic_delivery.release.backport import backport
from radic_delivery.release.git_history import GitHistoryError

runner = CliRunner()
REPO = "radicdotai/web-bff"


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


def _manifest(*, release_id: str, release_shas: list[str]) -> dict:
    return {
        "schema_version": 1,
        "release_id": release_id,
        "kind": "hotfix",
        "status": "prod-deployed",
        "repo": REPO,
        "created_at": "2026-11-03T00:00:00Z",
        "initiator": "alice",
        "base": {"branch": "main", "sha": "0" * 40},
        "selection": {
            "tickets": [
                {
                    "key": "RAD-1234",
                    "origin": "bot-proposal",
                    "commits": [
                        {"dev_sha": sha, "release_sha": sha, "cherry_pick_x": True} for sha in release_shas
                    ],
                }
            ],
            "held_back": [],
        },
    }


def test_clean_commit_backports_successfully(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "release/2026.11.03-1-hf")
    sha = _write_and_commit(repo, "fix.txt", "fix", "RAD-1234 hotfix")
    _git(repo, "checkout", "-q", "main")

    manifest = _manifest(release_id="2026.11.03-1-hf", release_shas=[sha])
    result = backport(manifest, repo_dir=repo, into="main")

    assert result.branch == "backport/2026.11.03-1-hf"
    assert result.picked_commits == [sha]
    assert result.conflicted_commits == []
    assert result.conflicts is False
    assert (repo / "fix.txt").read_text() == "fix"


def test_one_conflicting_commit_does_not_block_the_others(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    _write_and_commit(repo, "shared.txt", "original", "add shared file")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "dev")

    _git(repo, "checkout", "-q", "-b", "release/2026.11.04-1-hf")
    clean_sha = _write_and_commit(repo, "unrelated.txt", "clean", "RAD-1111 clean fix")
    conflict_sha = _write_and_commit(repo, "shared.txt", "hotfix version", "RAD-5555 conflicting hotfix")
    _git(repo, "checkout", "-q", "main")
    _write_and_commit(repo, "shared.txt", "main diverged", "unrelated main change")

    manifest = _manifest(release_id="2026.11.04-1-hf", release_shas=[clean_sha, conflict_sha])
    result = backport(manifest, repo_dir=repo, into="main")

    assert result.picked_commits == [clean_sha]
    assert result.conflicted_commits == [conflict_sha]
    assert result.conflicts is True
    assert (repo / "unrelated.txt").read_text() == "clean"


def test_only_commit_conflicting_still_creates_the_branch(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    _write_and_commit(repo, "shared.txt", "original", "add shared file")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "dev")

    _git(repo, "checkout", "-q", "-b", "release/2026.11.05-1-hf")
    conflict_sha = _write_and_commit(repo, "shared.txt", "hotfix version", "RAD-9999 conflicting hotfix")
    _git(repo, "checkout", "-q", "main")
    _write_and_commit(repo, "shared.txt", "main diverged", "unrelated main change")

    manifest = _manifest(release_id="2026.11.05-1-hf", release_shas=[conflict_sha])
    result = backport(manifest, repo_dir=repo, into="main")

    assert result.picked_commits == []
    assert result.conflicted_commits == [conflict_sha]
    assert result.conflicts is True
    assert _git(repo, "rev-parse", "--verify", "backport/2026.11.05-1-hf") != ""


def test_zero_commits_reports_empty_non_error_result(repo: Path) -> None:
    manifest = _manifest(release_id="2026.11.06-1-hf", release_shas=[])
    result = backport(manifest, repo_dir=repo, into="main")

    assert result.picked_commits == []
    assert result.conflicted_commits == []
    assert result.conflicts is False


def test_existing_branch_name_is_refused(repo: Path) -> None:
    _git(repo, "branch", "backport/2026.11.07-1-hf")
    manifest = _manifest(release_id="2026.11.07-1-hf", release_shas=[])

    with pytest.raises(GitHistoryError):  # reused from create_branch_from's own existing behaviour
        backport(manifest, repo_dir=repo, into="main")


# --- CLI-level tests -----------------------------------------------------


def test_cli_clean_backport_exits_ok(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "release/2026.11.08-1-hf")
    sha = _write_and_commit(repo, "fix.txt", "fix", "RAD-1234 hotfix")
    _git(repo, "checkout", "-q", "main")

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest(release_id="2026.11.08-1-hf", release_shas=[sha]))
    )

    result = runner.invoke(
        app,
        [
            "release", "backport",
            "--manifest", str(manifest_path),
            "--repo-dir", str(repo),
            "--into", "main",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)


def test_cli_conflict_still_exits_ok(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    _write_and_commit(repo, "shared.txt", "original", "add shared file")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "dev")
    _git(repo, "checkout", "-q", "-b", "release/2026.11.09-1-hf")
    conflict_sha = _write_and_commit(repo, "shared.txt", "hotfix version", "RAD-1 conflicting")
    _git(repo, "checkout", "-q", "main")
    _write_and_commit(repo, "shared.txt", "main diverged", "unrelated main change")

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest(release_id="2026.11.09-1-hf", release_shas=[conflict_sha]))
    )

    result = runner.invoke(
        app,
        [
            "release", "backport",
            "--manifest", str(manifest_path),
            "--repo-dir", str(repo),
            "--into", "main",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["conflicts"] is True


def test_cli_unresolvable_into_exits_infra_error(repo: Path, tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest(release_id="2026.11.10-1-hf", release_shas=[]))
    )

    result = runner.invoke(
        app,
        [
            "release", "backport",
            "--manifest", str(manifest_path),
            "--repo-dir", str(repo),
            "--into", "does-not-exist-branch",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.INFRA_ERROR)
