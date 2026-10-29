"""CLI-level deploy lint tests: real end-to-end runs against the
sample-repo fixtures, plus exit-code and --format parity checks."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode

SAMPLE_REPOS = Path(__file__).parent.parent / "fixtures" / "sample-repos"

runner = CliRunner()


def _descriptor(name: str) -> str:
    return str(SAMPLE_REPOS / name / ".radic" / "service.yml")


def test_clean_fixture_exits_ok() -> None:
    result = runner.invoke(app, ["deploy", "lint", "--descriptor", _descriptor("python-sample")])
    assert result.exit_code == int(ExitCode.OK)


def test_bad_deploy_fixture_exits_invalid_input() -> None:
    result = runner.invoke(app, ["deploy", "lint", "--descriptor", _descriptor("python-sample-bad-deploy")])
    assert result.exit_code == int(ExitCode.INVALID_INPUT)


def test_bad_deploy_fixture_fails_only_the_secret_rule() -> None:
    result = runner.invoke(
        app, ["deploy", "lint", "--descriptor", _descriptor("python-sample-bad-deploy"), "--format", "json"]
    )
    payload = json.loads(result.stdout)
    assert payload["overall"] == "fail"
    failing_rules = {c["rule"] for c in payload["checks"] if c["status"] not in ("pass", "not_applicable")}
    assert failing_rules == {"no_inline_secret"}


def test_invalid_descriptor_exits_invalid_input() -> None:
    broken = Path(__file__).parent.parent / "fixtures" / "broken" / "invalid-enum.yml"
    result = runner.invoke(app, ["deploy", "lint", "--descriptor", str(broken)])
    assert result.exit_code == int(ExitCode.INVALID_INPUT)


def test_json_and_text_formats_report_the_same_overall_result() -> None:
    json_result = runner.invoke(
        app, ["deploy", "lint", "--descriptor", _descriptor("python-sample"), "--format", "json"]
    )
    text_result = runner.invoke(
        app, ["deploy", "lint", "--descriptor", _descriptor("python-sample"), "--format", "text"]
    )
    payload = json.loads(json_result.stdout)
    assert payload["overall"].upper() in text_result.stdout


def test_deploy_release_subcommand_is_not_implemented() -> None:
    from radic_delivery.exit_codes import NOT_IMPLEMENTED_EXIT_CODE

    result = runner.invoke(app, ["deploy", "release"])
    assert result.exit_code == NOT_IMPLEMENTED_EXIT_CODE
