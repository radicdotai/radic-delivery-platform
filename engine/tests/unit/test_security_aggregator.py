"""Orchestration tests using a fake runner — no real subprocess involved."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from radic_delivery.security.aggregator import scan
from radic_delivery.security.runner import RunOutcome
from radic_delivery.security.tools import ToolInvocation


def _descriptor() -> dict[str, object]:
    return {"build": {"dockerfile": "Dockerfile"}}


def _ok(stdout: str) -> RunOutcome:
    return RunOutcome(launched=True, exit_code=0, stdout=stdout, stderr="")


_CLEAN_STDOUT = {"gitleaks": "[]", "hadolint": "[]", "trivy-config": "{}"}


def _make_runner(overrides: dict[str, RunOutcome]) -> Any:
    def _run(inv: ToolInvocation, cwd: Path) -> RunOutcome:
        return overrides.get(inv.tool, _ok(_CLEAN_STDOUT[inv.tool]))

    return _run


def test_clean_scan_reports_zero_counts_and_completed(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
    result = scan(_descriptor(), ["all"], tmp_path, run_fn=_make_runner({}))
    assert result.scan_result == "completed"
    assert result.counts == {"critical": 0, "high": 0, "medium": 0, "low": 0}


def test_critical_finding_never_changes_scan_result(tmp_path: Path) -> None:
    """FR-006: a finding, at any severity, never changes scan_result."""
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
    gitleaks_hit = json.dumps(
        [{"RuleID": "aws-access-token", "Description": "x", "StartLine": 1, "File": "f"}]
    )
    overrides = {"gitleaks": _ok(gitleaks_hit)}
    result = scan(_descriptor(), ["all"], tmp_path, run_fn=_make_runner(overrides))
    assert result.scan_result == "completed"
    assert result.counts["critical"] == 1


def test_known_mix_of_findings_produces_exact_counts(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
    gitleaks_hit = json.dumps(
        [
            {"RuleID": "a", "Description": "x", "StartLine": 1, "File": "f"},
            {"RuleID": "b", "Description": "y", "StartLine": 2, "File": "f"},
        ]
    )
    hadolint_hit = json.dumps(
        [{"code": "DL1", "file": "Dockerfile", "level": "error", "line": 1, "message": "m"}]
    )
    trivy_misconfig = {"ID": "T1", "Severity": "LOW", "Message": "m"}
    trivy_hit = json.dumps({"Results": [{"Target": "Dockerfile", "Misconfigurations": [trivy_misconfig]}]})
    overrides = {
        "gitleaks": _ok(gitleaks_hit),
        "hadolint": _ok(hadolint_hit),
        "trivy-config": _ok(trivy_hit),
    }
    result = scan(_descriptor(), ["all"], tmp_path, run_fn=_make_runner(overrides))
    assert result.counts == {"critical": 2, "high": 1, "medium": 0, "low": 1}


def test_tool_that_cannot_launch_is_not_executable(tmp_path: Path) -> None:
    overrides = {"gitleaks": RunOutcome(launched=False, exit_code=None, stdout="", stderr="not found")}
    result = scan(_descriptor(), ["source"], tmp_path, run_fn=_make_runner(overrides))
    source_result = next(s for s in result.scopes if s.scope == "source")
    assert source_result.status == "not_executable"
    assert result.scan_result == "completed"  # still never fails


def test_iac_scope_without_dockerfile_is_not_applicable(tmp_path: Path) -> None:
    result = scan(_descriptor(), ["iac"], tmp_path, run_fn=_make_runner({}))
    iac_result = next(s for s in result.scopes if s.scope == "iac")
    assert iac_result.status == "not_applicable"
    assert iac_result.findings == []


def test_image_scope_is_always_reported_not_available(tmp_path: Path) -> None:
    result = scan(_descriptor(), ["source"], tmp_path, run_fn=_make_runner({}))
    image_result = next(s for s in result.scopes if s.scope == "image")
    assert image_result.status == "not_available"


def test_snyk_status_is_always_reported_not_available(tmp_path: Path) -> None:
    result = scan(_descriptor(), ["all"], tmp_path, run_fn=_make_runner({}))
    assert result.snyk_status == {"status": "not_available"}
