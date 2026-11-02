"""CLI-level tests for `radic-delivery release propose`: real local git
repo + real local change-note files, exit codes, --dry-run, --format."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode

runner = CliRunner()

_INITIATOR_ARGS = ["--initiator", "alice"]


def _git(repo_dir: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo_dir, capture_output=True, text=True, check=True)
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _git(repo_dir, "init", "-q", "-b", "dev")
    _git(repo_dir, "config", "user.email", "test@example.com")
    _git(repo_dir, "config", "user.name", "Test")
    return repo_dir


def _commit(repo_dir: Path) -> str:
    _git(repo_dir, "commit", "-q", "--allow-empty", "-m", "a commit")
    return _git(repo_dir, "rev-parse", "HEAD")


def _write_note(
    notes_dir: Path, repo_slug: str, sha: str, jira_key: str, pr_number: int | None = None
) -> None:
    path = notes_dir / "change-notes" / repo_slug / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": 1,
        "repo": repo_slug,
        "sha": sha,
        "type": "fix",
        "audience": "customer",
        "title": "A title",
        "summary": "A summary.",
        "jira_key": jira_key,
    }
    if pr_number is not None:
        record["pr_number"] = pr_number
    path.write_text(json.dumps(record))


def test_ready_ticket_is_proposed_end_to_end(repo: Path, tmp_path: Path) -> None:
    sha = _commit(repo)
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, "radicdotai/web-bff", sha, "RAD-1234")

    result = runner.invoke(
        app,
        [
            "release", "propose",
            "--repo", "radicdotai/web-bff",
            "--base", "dev",
            "--repo-dir", str(repo),
            "--change-notes-dir", str(notes_dir),
            "--tickets", "RAD-1234",
            *_INITIATOR_ARGS,
            "--dry-run",
            "--format", "json",
        ],
    )
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["manifest"]["selection"]["tickets"][0]["key"] == "RAD-1234"


def test_not_ready_ticket_is_held_back_end_to_end(repo: Path, tmp_path: Path) -> None:
    sha = _commit(repo)
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, "radicdotai/web-bff", sha, "RAD-1234")

    result = runner.invoke(
        app,
        [
            "release", "propose",
            "--repo", "radicdotai/web-bff",
            "--base", "dev",
            "--repo-dir", str(repo),
            "--change-notes-dir", str(notes_dir),
            *_INITIATOR_ARGS,
            "--dry-run",
            "--format", "json",
        ],
    )
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    held_back = payload["manifest"]["selection"]["held_back"]
    assert held_back == [{"key": "RAD-1234", "reason": "not Ready for Review"}]


def test_dev_green_failed_commit_is_held_back_distinctly(repo: Path, tmp_path: Path) -> None:
    sha = _commit(repo)
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, "radicdotai/web-bff", sha, "RAD-1234")

    result = runner.invoke(
        app,
        [
            "release", "propose",
            "--repo", "radicdotai/web-bff",
            "--base", "dev",
            "--repo-dir", str(repo),
            "--change-notes-dir", str(notes_dir),
            "--tickets", "RAD-1234",
            "--dev-green-failed", sha,
            *_INITIATOR_ARGS,
            "--dry-run",
            "--format", "json",
        ],
    )
    payload = json.loads(result.stdout)
    held_back = payload["manifest"]["selection"]["held_back"]
    assert held_back[0]["key"] == "RAD-1234"
    assert "dev-green" in held_back[0]["reason"]


def test_non_jira_pr_explicitly_listed_is_included(repo: Path, tmp_path: Path) -> None:
    sha = _commit(repo)
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, "radicdotai/web-bff", sha, "None", pr_number=142)

    result = runner.invoke(
        app,
        [
            "release", "propose",
            "--repo", "radicdotai/web-bff",
            "--base", "dev",
            "--repo-dir", str(repo),
            "--change-notes-dir", str(notes_dir),
            "--non-jira-prs", "142",
            *_INITIATOR_ARGS,
            "--dry-run",
            "--format", "json",
        ],
    )
    payload = json.loads(result.stdout)
    non_jira = payload["manifest"]["selection"]["non_jira_prs"]
    assert non_jira[0]["pr"] == 142
    assert non_jira[0]["reason"] == "MISSING"
    assert non_jira[0]["second_approver"] is None


def test_dry_run_does_not_write_a_local_manifest(repo: Path, tmp_path: Path) -> None:
    sha = _commit(repo)
    notes_dir = tmp_path / "notes"
    out_dir = tmp_path / "out"
    _write_note(notes_dir, "radicdotai/web-bff", sha, "RAD-1234")

    runner.invoke(
        app,
        [
            "release", "propose",
            "--repo", "radicdotai/web-bff",
            "--base", "dev",
            "--repo-dir", str(repo),
            "--change-notes-dir", str(notes_dir),
            "--tickets", "RAD-1234",
            "--out-dir", str(out_dir),
            *_INITIATOR_ARGS,
            "--dry-run",
        ],
    )
    assert not out_dir.exists() or not any(out_dir.rglob("*.json"))


def test_without_dry_run_the_manifest_is_written_locally(repo: Path, tmp_path: Path) -> None:
    sha = _commit(repo)
    notes_dir = tmp_path / "notes"
    out_dir = tmp_path / "out"
    _write_note(notes_dir, "radicdotai/web-bff", sha, "RAD-1234")

    result = runner.invoke(
        app,
        [
            "release", "propose",
            "--repo", "radicdotai/web-bff",
            "--base", "dev",
            "--repo-dir", str(repo),
            "--change-notes-dir", str(notes_dir),
            "--tickets", "RAD-1234",
            "--out-dir", str(out_dir),
            *_INITIATOR_ARGS,
            "--format", "json",
        ],
    )
    assert result.exit_code == int(ExitCode.OK)
    written = list(out_dir.rglob("releases/*.json"))
    assert len(written) == 1
    assert json.loads(written[0].read_text())["status"] == "proposed"


def test_invalid_repo_dir_exits_infra_error(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "release", "propose",
            "--repo", "radicdotai/web-bff",
            "--base", "dev",
            "--repo-dir", str(tmp_path / "not-a-git-repo"),
            "--change-notes-dir", str(tmp_path / "notes"),
            *_INITIATOR_ARGS,
            "--dry-run",
        ],
    )
    assert result.exit_code == int(ExitCode.INFRA_ERROR)
