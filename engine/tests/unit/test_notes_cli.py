"""CLI-level tests for `radic-delivery notes write` and `notes check`."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode

runner = CliRunner()


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


def _valid_write_args(repo_dir: Path, *, add_expand_migration: bool = False) -> list[str]:
    base = _git(repo_dir, "rev-parse", "HEAD")
    if add_expand_migration:
        (repo_dir / "migrations" / "versions").mkdir(parents=True, exist_ok=True)
        (repo_dir / "migrations/versions/0001_expand.py").write_text('revision = "0001"\n')
        _git(repo_dir, "add", "-A")
        _git(repo_dir, "commit", "-q", "-m", "add expand migration")
    head = _git(repo_dir, "rev-parse", "HEAD")
    return [
        "--repo", "radicdotai/web-bff",
        "--sha", "2222222222222222222222222222222222222222",
        "--pr", "123",
        "--type", "fix",
        "--audience", "customer",
        "--title", "Return a clear error when the upstream is unavailable",
        "--summary", "The BFF now answers 503 with a retry hint instead of a generic 500.",
        "--jira-key", "RAD-1234",
        "--repo-dir", str(repo_dir),
        "--base", base,
        "--head", head,
    ]


def test_valid_notes_write_exits_ok_and_writes_a_real_file(repo: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["notes", "write", *_valid_write_args(repo), "--out-dir", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["upload_status"] == "not_available"
    assert Path(payload["local_path"]).is_file()


def test_notes_write_computes_migration_from_the_real_diff(repo: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "notes", "write",
            *_valid_write_args(repo, add_expand_migration=True),
            "--out-dir", str(tmp_path), "--format", "json",
        ],
    )
    assert result.exit_code == int(ExitCode.OK)
    assert json.loads(result.stdout)["record"]["migration"] == "expand"


def test_invalid_notes_write_exits_invalid_input_and_writes_nothing(repo: Path, tmp_path: Path) -> None:
    args = _valid_write_args(repo)
    type_index = args.index("--type") + 1
    args[type_index] = "not-a-real-type"
    result = runner.invoke(app, ["notes", "write", *args, "--out-dir", str(tmp_path), "--format", "json"])
    assert result.exit_code == int(ExitCode.INVALID_INPUT)
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert not any(tmp_path.rglob("*.json"))


def _write_pr_body(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "pr-body.txt"
    path.write_text(content)
    return path


def test_notes_check_with_jira_key_passes_in_json_and_text(tmp_path: Path) -> None:
    pr_body_file = _write_pr_body(tmp_path, "Kind: fix\nJira: RAD-1234\n")
    check_args = ["notes", "check", "--pr-body-file", str(pr_body_file)]
    json_result = runner.invoke(app, [*check_args, "--format", "json"])
    text_result = runner.invoke(app, [*check_args, "--format", "text"])
    assert json_result.exit_code == int(ExitCode.OK)
    payload = json.loads(json_result.stdout)
    assert payload["classification"] == "has_jira_key"
    assert payload["jira_key"] == "RAD-1234"
    assert "has_jira_key" in text_result.stdout


def test_notes_check_with_explicit_none_passes(tmp_path: Path) -> None:
    pr_body_file = _write_pr_body(tmp_path, "Jira: None\n")
    result = runner.invoke(app, ["notes", "check", "--pr-body-file", str(pr_body_file), "--format", "json"])
    assert result.exit_code == int(ExitCode.OK)
    assert json.loads(result.stdout)["classification"] == "explicit_none"


def test_notes_check_incomplete_without_require_flag_warns_but_exits_ok(tmp_path: Path) -> None:
    pr_body_file = _write_pr_body(tmp_path, "No ticket reference here.\n")
    result = runner.invoke(app, ["notes", "check", "--pr-body-file", str(pr_body_file), "--format", "json"])
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["classification"] == "incomplete"
    assert payload["passed"] is True


def test_notes_check_incomplete_with_require_flag_exits_policy_failure(tmp_path: Path) -> None:
    pr_body_file = _write_pr_body(tmp_path, "No ticket reference here.\n")
    result = runner.invoke(
        app, ["notes", "check", "--pr-body-file", str(pr_body_file), "--require-jira-key", "--format", "json"]
    )
    assert result.exit_code == int(ExitCode.POLICY_FAILURE)
    assert json.loads(result.stdout)["passed"] is False


def test_notes_check_complete_body_still_passes_with_require_flag(tmp_path: Path) -> None:
    pr_body_file = _write_pr_body(tmp_path, "Jira: RAD-9999\n")
    result = runner.invoke(
        app, ["notes", "check", "--pr-body-file", str(pr_body_file), "--require-jira-key", "--format", "json"]
    )
    assert result.exit_code == int(ExitCode.OK)
    assert json.loads(result.stdout)["passed"] is True


def test_notes_check_without_repo_dir_preserves_jira_only_behaviour(tmp_path: Path) -> None:
    pr_body_file = _write_pr_body(tmp_path, "Jira: RAD-1234\nMigrations: none\n")
    result = runner.invoke(app, ["notes", "check", "--pr-body-file", str(pr_body_file), "--format", "json"])
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert "migration" not in payload
    assert payload["classification"] == "has_jira_key"


def test_notes_check_with_repo_dir_reports_both_checks_and_fails_on_mismatch(
    repo: Path, tmp_path: Path
) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "migrations" / "versions").mkdir(parents=True)
    (repo / "migrations/versions/0001_expand.py").write_text('revision = "0001"\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add expand migration")
    head = _git(repo, "rev-parse", "HEAD")

    pr_body_file = _write_pr_body(tmp_path, "Jira: RAD-1234\nMigrations: none\n")
    result = runner.invoke(
        app,
        [
            "notes", "check", "--pr-body-file", str(pr_body_file),
            "--repo-dir", str(repo), "--base", base, "--head", head,
            "--format", "json",
        ],
    )
    assert result.exit_code == int(ExitCode.POLICY_FAILURE)
    payload = json.loads(result.stdout)
    assert payload["classification"] == "has_jira_key"
    assert payload["migration"]["computed"] == "expand"
    assert payload["migration"]["declared"] == "none"
    assert payload["migration"]["passed"] is False
