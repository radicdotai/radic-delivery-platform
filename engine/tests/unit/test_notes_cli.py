"""CLI-level tests for `radic-delivery notes write` and `notes check`."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode

runner = CliRunner()

_VALID_WRITE_ARGS = [
    "--repo", "radicdotai/web-bff",
    "--sha", "2222222222222222222222222222222222222222",
    "--pr", "123",
    "--type", "fix",
    "--audience", "customer",
    "--title", "Return a clear error when the upstream is unavailable",
    "--summary", "The BFF now answers 503 with a retry hint instead of a generic 500.",
    "--jira-key", "RAD-1234",
]


def test_valid_notes_write_exits_ok_and_writes_a_real_file(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["notes", "write", *_VALID_WRITE_ARGS, "--out-dir", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["upload_status"] == "not_available"
    assert Path(payload["local_path"]).is_file()


def test_invalid_notes_write_exits_invalid_input_and_writes_nothing(tmp_path: Path) -> None:
    args = [*_VALID_WRITE_ARGS]
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
