"""End-to-end CLI tests: exit codes (FR-015), output formats (FR-014), and
`descriptor show` refusing an invalid descriptor (Acceptance Scenario 2)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import NOT_IMPLEMENTED_EXIT_CODE, ExitCode

FIXTURES = Path(__file__).parent.parent / "fixtures"
BROKEN = FIXTURES / "broken"

runner = CliRunner()


def test_validate_ok_exit_code() -> None:
    result = runner.invoke(app, ["descriptor", "validate", str(FIXTURES / "web-bff.yml")])
    assert result.exit_code == int(ExitCode.OK)


def test_validate_invalid_exit_code() -> None:
    result = runner.invoke(app, ["descriptor", "validate", str(BROKEN / "invalid-enum.yml")])
    assert result.exit_code == int(ExitCode.INVALID_INPUT)


def test_show_refuses_invalid_descriptor() -> None:
    result = runner.invoke(app, ["descriptor", "show", str(BROKEN / "invalid-enum.yml"), "--format", "json"])
    assert result.exit_code == int(ExitCode.INVALID_INPUT)
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert "resolved" not in payload


def test_show_valid_descriptor_returns_resolved_json() -> None:
    result = runner.invoke(
        app, ["descriptor", "show", str(FIXTURES / "image-studio.yml"), "--format", "json"]
    )
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert "resolved" in payload
    assert payload["resolved"]["service"]["name"] == "image-studio"


def test_json_and_text_formats_report_the_same_facts() -> None:
    json_result = runner.invoke(
        app, ["policy", "exceptions", "check", "EXC-0001", "--format", "json"]
    )
    text_result = runner.invoke(
        app, ["policy", "exceptions", "check", "EXC-0001", "--format", "text"]
    )
    json_payload = json.loads(json_result.stdout)
    assert json_payload["status"] in text_result.stdout


def test_not_implemented_command_group_has_distinct_exit_code() -> None:
    """spec Edge Case / FR-003: not-yet-implemented commands are not success,
    not a crash, and not confused with the four real exit codes.

    `gate` was this feature's example when this test was written; it has
    since been implemented (specs/002-ci-gate-workflow), so this now
    targets `notes`, a group still stubbed as of this feature."""
    result = runner.invoke(app, ["notes", "write"])
    assert result.exit_code == NOT_IMPLEMENTED_EXIT_CODE
    assert result.exit_code not in {int(c) for c in ExitCode}


def test_help_lists_every_architecture_command_group() -> None:
    """SC-003: every command group is discoverable on day one."""
    result = runner.invoke(app, ["--help"])
    for group in [
        "descriptor",
        "policy",
        "gate",
        "notes",
        "tests",
        "release",
        "deploy",
        "records",
        "rollback",
        "migrations",
    ]:
        assert group in result.stdout
