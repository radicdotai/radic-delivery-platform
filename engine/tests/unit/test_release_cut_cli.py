"""CLI-level tests for `radic-delivery release cut`: real local git repo +
real local manifest file, exit codes, --dry-run, --format."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode

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


def _write_note(notes_dir: Path, sha: str) -> None:
    path = notes_dir / "change-notes" / REPO / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repo": REPO,
                "sha": sha,
                "type": "fix",
                "audience": "customer",
                "title": "A title",
                "summary": "A summary.",
                "jira_key": "RAD-1234",
            }
        )
    )


def _write_manifest(path: Path, sha: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_id": "2026.11.03-1",
                "kind": "release",
                "status": "proposed",
                "repo": REPO,
                "created_at": "2026-11-03T00:00:00Z",
                "initiator": "alice",
                "base": {"branch": "dev", "sha": sha},
                "selection": {
                    "tickets": [
                        {"key": "RAD-1234", "origin": "bot-proposal", "commits": [{"dev_sha": sha}]}
                    ],
                    "held_back": [],
                    "non_jira_prs": [],
                },
            }
        )
    )


def test_valid_cut_exits_ok_and_updates_manifest_on_disk(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")

    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha)
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, sha)

    result = runner.invoke(
        app,
        [
            "release", "cut",
            "--manifest", str(manifest_path),
            "--release-id", "2026.11.03-1",
            "--repo-dir", str(repo),
            "--change-notes-dir", str(notes_dir),
            "--format", "json",
        ],
    )
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["manifest"]["status"] == "cut"

    on_disk = json.loads(manifest_path.read_text())
    assert on_disk["status"] == "cut"


def test_missing_change_note_record_exits_invalid_input(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")

    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, sha)

    result = runner.invoke(
        app,
        [
            "release", "cut",
            "--manifest", str(manifest_path),
            "--release-id", "2026.11.03-1",
            "--repo-dir", str(repo),
            "--change-notes-dir", str(tmp_path / "notes"),
        ],
    )
    assert result.exit_code == int(ExitCode.INVALID_INPUT)
    on_disk = json.loads(manifest_path.read_text())
    assert on_disk["status"] == "proposed"


def test_cherry_pick_conflict_exits_infra_error_and_manifest_unchanged(repo: Path, tmp_path: Path) -> None:
    (repo / "shared.txt").write_text("line1\n")
    _git(repo, "add", "shared.txt")
    _git(repo, "commit", "-q", "-m", "add shared.txt")

    _git(repo, "checkout", "-q", "-b", "dev")
    sha = _write_and_commit(repo, "shared.txt", "dev change\n", "dev changes shared.txt")
    _git(repo, "checkout", "-q", "main")
    _write_and_commit(repo, "shared.txt", "main change\n", "main changes shared.txt")

    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha)
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, sha)
    original_bytes = manifest_path.read_bytes()

    result = runner.invoke(
        app,
        [
            "release", "cut",
            "--manifest", str(manifest_path),
            "--release-id", "2026.11.03-1",
            "--repo-dir", str(repo),
            "--change-notes-dir", str(notes_dir),
        ],
    )
    assert result.exit_code == int(ExitCode.INFRA_ERROR)
    assert manifest_path.read_bytes() == original_bytes


def test_dry_run_does_not_touch_manifest_or_repo(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")

    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha)
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, sha)
    original_bytes = manifest_path.read_bytes()

    result = runner.invoke(
        app,
        [
            "release", "cut",
            "--manifest", str(manifest_path),
            "--release-id", "2026.11.03-1",
            "--repo-dir", str(repo),
            "--change-notes-dir", str(notes_dir),
            "--dry-run",
            "--format", "json",
        ],
    )
    assert result.exit_code == int(ExitCode.OK)
    assert manifest_path.read_bytes() == original_bytes
    assert _git(repo, "branch", "--list", "release/*") == ""
