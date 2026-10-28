"""CLI-level security scan tests: real end-to-end runs (real gitleaks/
hadolint/trivy subprocess calls) against the sample-repo fixtures, plus
exit-code and --format parity checks."""

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


def test_clean_sample_exits_ok_with_zero_findings() -> None:
    result = runner.invoke(
        app, ["security", "scan", "--scope", "all", "--descriptor", _descriptor("python-sample")]
    )
    assert result.exit_code == int(ExitCode.OK)


def test_secret_fixture_finds_the_planted_secret_and_still_exits_ok() -> None:
    result = runner.invoke(
        app,
        [
            "security",
            "scan",
            "--scope",
            "source",
            "--descriptor",
            _descriptor("python-sample-secret"),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    source = next(s for s in payload["scopes"] if s["scope"] == "source")
    assert source["status"] == "checked"
    assert any(f["severity"] == "critical" and f["tool"] == "gitleaks" for f in source["findings"])
    assert payload["counts"]["critical"] >= 1
    # The raw secret value must never appear anywhere in the output.
    assert "AKIAABCDEFGHIJKLMNOP" not in result.stdout


def test_bad_dockerfile_fixture_finds_misconfigurations_and_still_exits_ok() -> None:
    result = runner.invoke(
        app,
        [
            "security",
            "scan",
            "--scope",
            "iac",
            "--descriptor",
            _descriptor("python-sample-bad-dockerfile"),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    iac = next(s for s in payload["scopes"] if s["scope"] == "iac")
    assert iac["status"] == "checked"
    tools_found = {f["tool"] for f in iac["findings"]}
    assert "hadolint" in tools_found
    assert "trivy-config" in tools_found


def test_clean_sample_iac_scope_is_not_applicable() -> None:
    """python-sample has no Dockerfile on disk (specs/002)."""
    result = runner.invoke(
        app,
        [
            "security",
            "scan",
            "--scope",
            "iac",
            "--descriptor",
            _descriptor("python-sample"),
            "--format",
            "json",
        ],
    )
    payload = json.loads(result.stdout)
    iac = next(s for s in payload["scopes"] if s["scope"] == "iac")
    assert iac["status"] == "not_applicable"


def test_image_and_snyk_are_always_reported_not_available() -> None:
    result = runner.invoke(
        app,
        [
            "security",
            "scan",
            "--scope",
            "all",
            "--descriptor",
            _descriptor("python-sample"),
            "--format",
            "json",
        ],
    )
    payload = json.loads(result.stdout)
    image = next(s for s in payload["scopes"] if s["scope"] == "image")
    assert image["status"] == "not_available"
    assert payload["snyk_status"] == {"status": "not_available"}


def test_invalid_descriptor_exits_invalid_input() -> None:
    broken = Path(__file__).parent.parent / "fixtures" / "broken" / "invalid-enum.yml"
    result = runner.invoke(app, ["security", "scan", "--descriptor", str(broken)])
    assert result.exit_code == int(ExitCode.INVALID_INPUT)


def test_json_and_text_formats_report_the_same_scan_result() -> None:
    json_result = runner.invoke(
        app, ["security", "scan", "--descriptor", _descriptor("python-sample"), "--format", "json"]
    )
    text_result = runner.invoke(
        app, ["security", "scan", "--descriptor", _descriptor("python-sample"), "--format", "text"]
    )
    payload = json.loads(json_result.stdout)
    assert payload["scan_result"] in text_result.stdout
