"""CLI-level gate tests: exit codes, --format parity, and real end-to-end
runs against the sample-repo fixtures (real subprocess calls to the
fixtures' own ruff/mypy/pytest — no network access needed, since those
tools are the fixtures' own already-installed dev dependencies)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import NOT_IMPLEMENTED_EXIT_CODE, ExitCode

SAMPLE_REPOS = Path(__file__).parent.parent / "fixtures" / "sample-repos"

runner = CliRunner()


def _descriptor(name: str) -> str:
    return str(SAMPLE_REPOS / name / ".radic" / "service.yml")


def test_passing_sample_exits_ok() -> None:
    result = runner.invoke(app, ["gate", "evaluate", "--descriptor", _descriptor("python-sample")])
    assert result.exit_code == int(ExitCode.OK)


def test_broken_sample_exits_policy_failure() -> None:
    result = runner.invoke(
        app, ["gate", "evaluate", "--descriptor", _descriptor("python-sample-broken-lint")]
    )
    assert result.exit_code == int(ExitCode.POLICY_FAILURE)


def test_release_gate_mode_exits_not_implemented() -> None:
    result = runner.invoke(
        app,
        [
            "gate",
            "evaluate",
            "--descriptor",
            _descriptor("python-sample"),
            "--mode",
            "release-gate",
        ],
    )
    assert result.exit_code == NOT_IMPLEMENTED_EXIT_CODE


def test_json_and_text_formats_report_the_same_overall_result() -> None:
    json_result = runner.invoke(
        app, ["gate", "evaluate", "--descriptor", _descriptor("python-sample"), "--format", "json"]
    )
    text_result = runner.invoke(
        app, ["gate", "evaluate", "--descriptor", _descriptor("python-sample"), "--format", "text"]
    )
    payload = json.loads(json_result.stdout)
    overall = payload["overall"]
    assert overall in text_result.stdout.lower() or overall.upper() in text_result.stdout


def test_broken_lint_fixture_fails_only_lint() -> None:
    result = runner.invoke(
        app,
        ["gate", "evaluate", "--descriptor", _descriptor("python-sample-broken-lint"), "--format", "json"],
    )
    payload = json.loads(result.stdout)
    checks = {c["name"]: c["status"] for c in payload["checks"]}
    assert checks["lint"] == "fail"
    assert checks["typecheck"] == "pass"
    assert checks["unit"] == "pass"
    assert checks["coverage"] == "pass"
    assert checks["skip_budget"] == "pass"


def test_broken_type_fixture_fails_only_typecheck() -> None:
    result = runner.invoke(
        app,
        ["gate", "evaluate", "--descriptor", _descriptor("python-sample-broken-type"), "--format", "json"],
    )
    checks = {c["name"]: c["status"] for c in json.loads(result.stdout)["checks"]}
    assert checks["typecheck"] == "fail"
    assert checks["lint"] == "pass"
    assert checks["unit"] == "pass"
    assert checks["coverage"] == "pass"


def test_broken_test_fixture_fails_only_unit() -> None:
    result = runner.invoke(
        app,
        ["gate", "evaluate", "--descriptor", _descriptor("python-sample-broken-test"), "--format", "json"],
    )
    checks = {c["name"]: c["status"] for c in json.loads(result.stdout)["checks"]}
    assert checks["unit"] == "fail"
    assert checks["lint"] == "pass"
    assert checks["typecheck"] == "pass"
    assert checks["coverage"] == "pass"


def test_broken_coverage_fixture_fails_only_coverage() -> None:
    result = runner.invoke(
        app,
        [
            "gate",
            "evaluate",
            "--descriptor",
            _descriptor("python-sample-broken-coverage"),
            "--format",
            "json",
        ],
    )
    checks = {c["name"]: c["status"] for c in json.loads(result.stdout)["checks"]}
    assert checks["coverage"] == "fail"
    assert checks["lint"] == "pass"
    assert checks["typecheck"] == "pass"
    assert checks["unit"] == "pass"


def test_broken_skip_fixture_fails_only_skip_budget() -> None:
    result = runner.invoke(
        app,
        ["gate", "evaluate", "--descriptor", _descriptor("python-sample-broken-skip"), "--format", "json"],
    )
    payload = json.loads(result.stdout)
    checks = {c["name"]: c["status"] for c in payload["checks"]}
    assert checks["skip_budget"] == "fail"
    assert checks["lint"] == "pass"
    assert checks["typecheck"] == "pass"
    assert checks["coverage"] == "pass"
    assert payload["skipped_count"] == 1
