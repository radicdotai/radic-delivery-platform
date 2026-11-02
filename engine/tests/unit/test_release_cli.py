"""CLI-level tests for `radic-delivery release command`: stdin/file input,
exit codes, and --format parity. No fixtures, no subprocess."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode

runner = CliRunner()

_COMMON_ARGS = ["--actor", "alice", "--release-managers", "alice,bob", "--tech-lead", "bob"]


def test_authorized_command_on_stdin_exits_ok_and_reports_accepted() -> None:
    result = runner.invoke(
        app,
        ["release", "command", *_COMMON_ARGS, "--format", "json"],
        input="/release remove RAD-123",
    )
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["classification"] == "accepted"
    assert payload["form"] == "release_remove"
    assert payload["args"] == {"key": "RAD-123"}


def test_accepted_command_json_includes_additive_workflow_fields() -> None:
    result = runner.invoke(
        app,
        ["release", "command", *_COMMON_ARGS, "--format", "json"],
        input="/release remove RAD-123",
    )
    payload = json.loads(result.stdout)
    assert payload["classification"] == "accepted"
    assert payload["form"] == "release_remove"
    assert payload["args"] == {"key": "RAD-123"}
    assert payload["workflow_command"] == "remove"
    assert payload["workflow_outcome"] == "applied"
    assert payload["reply_body"]


def test_json_and_text_formats_report_the_same_classification() -> None:
    json_result = runner.invoke(
        app, ["release", "command", *_COMMON_ARGS, "--format", "json"], input="/release remove RAD-123"
    )
    text_result = runner.invoke(
        app, ["release", "command", *_COMMON_ARGS, "--format", "text"], input="/release remove RAD-123"
    )
    payload = json.loads(json_result.stdout)
    assert payload["classification"] in text_result.stdout


def test_ordinary_text_on_stdin_exits_ok_and_reports_not_a_command() -> None:
    result = runner.invoke(
        app, ["release", "command", *_COMMON_ARGS, "--format", "json"], input="looks good to me!"
    )
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["classification"] == "not_a_command"


def test_malformed_command_exits_invalid_input() -> None:
    result = runner.invoke(app, ["release", "command", *_COMMON_ARGS], input="/release add RAD-123")
    assert result.exit_code == int(ExitCode.INVALID_INPUT)


def test_malformed_command_json_includes_additive_workflow_fields() -> None:
    result = runner.invoke(
        app, ["release", "command", *_COMMON_ARGS, "--format", "json"], input="/release add RAD-123"
    )
    payload = json.loads(result.stdout)
    assert payload["classification"] == "malformed"
    assert payload["workflow_command"] == "none"
    assert payload["workflow_outcome"] == "rejected"
    assert payload["reply_body"]


def test_unauthorized_author_exits_policy_failure() -> None:
    result = runner.invoke(
        app,
        [
            "release",
            "command",
            "--actor",
            "eve",
            "--release-managers",
            "alice,bob",
            "--tech-lead",
            "bob",
        ],
        input="/release remove RAD-123",
    )
    assert result.exit_code == int(ExitCode.POLICY_FAILURE)


def test_unauthorized_command_json_includes_additive_workflow_fields() -> None:
    result = runner.invoke(
        app,
        [
            "release",
            "command",
            "--actor",
            "eve",
            "--release-managers",
            "alice,bob",
            "--tech-lead",
            "bob",
            "--format",
            "json",
        ],
        input="/release remove RAD-123",
    )
    payload = json.loads(result.stdout)
    assert payload["classification"] == "unauthorized"
    assert payload["workflow_command"] == "remove"
    assert payload["workflow_outcome"] == "rejected"
    assert payload["reply_body"]


def test_comment_file_input_is_equivalent_to_stdin(tmp_path: Path) -> None:
    comment_file = tmp_path / "comment.txt"
    comment_file.write_text("/research close\n")

    result = runner.invoke(
        app,
        ["release", "command", "--comment-file", str(comment_file), *_COMMON_ARGS, "--format", "json"],
    )
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["classification"] == "accepted"
    assert payload["form"] == "research_close"
