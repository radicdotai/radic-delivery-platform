"""Orchestrates tool selection, execution, and parsing into a
SecurityScanResult. `image` scanning and Snyk are always reported as
not-yet-available, regardless of what was requested (spec FR-007, FR-008).
`scan_result` is always "completed" — a finding, at any severity, never
changes that (spec FR-006).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from radic_delivery.security import runner as runner_module
from radic_delivery.security.parsers import parse_gitleaks, parse_hadolint, parse_trivy_config
from radic_delivery.security.result import Finding, ScopeResult, SecurityScanResult
from radic_delivery.security.runner import RunOutcome
from radic_delivery.security.tools import ToolInvocation, applicable_scopes, select_tools

RunFn = Callable[[ToolInvocation, Path], RunOutcome]

_PARSERS: dict[str, Callable[[str], list[Finding]]] = {
    "gitleaks": parse_gitleaks,
    "hadolint": parse_hadolint,
    "trivy-config": parse_trivy_config,
}


def _source_scope_result(invocations: list[ToolInvocation], repo_root: Path, run_fn: RunFn) -> ScopeResult:
    source_invocations = [inv for inv in invocations if inv.scope == "source"]
    if not source_invocations:
        return ScopeResult(scope="source", status="not_applicable")

    findings: list[Finding] = []
    for inv in source_invocations:
        outcome = run_fn(inv, repo_root)
        if not outcome.launched:
            return ScopeResult(scope="source", status="not_executable")
        findings.extend(_PARSERS[inv.tool](outcome.stdout))
    return ScopeResult(scope="source", status="checked", findings=findings)


def _iac_scope_result(
    invocations: list[ToolInvocation], applicable: dict[str, bool], repo_root: Path, run_fn: RunFn
) -> ScopeResult:
    if not applicable.get("iac", False):
        return ScopeResult(scope="iac", status="not_applicable")

    iac_invocations = [inv for inv in invocations if inv.scope == "iac"]
    findings: list[Finding] = []
    for inv in iac_invocations:
        outcome = run_fn(inv, repo_root)
        if not outcome.launched:
            # Conservative: if either tool in this scope can't even launch,
            # the scope as a whole is not reliably checked, not silently
            # partial (never silently under-report what was actually run).
            return ScopeResult(scope="iac", status="not_executable")
        findings.extend(_PARSERS[inv.tool](outcome.stdout))
    return ScopeResult(scope="iac", status="checked", findings=findings)


def scan(
    descriptor: dict[str, Any],
    scopes: list[str],
    repo_root: Path,
    run_fn: RunFn = runner_module.run,
) -> SecurityScanResult:
    invocations = select_tools(descriptor, scopes, repo_root)
    applicable = applicable_scopes(descriptor, scopes, repo_root)

    scope_results: list[ScopeResult] = []
    if "source" in applicable:
        scope_results.append(_source_scope_result(invocations, repo_root, run_fn))
    if "iac" in applicable:
        scope_results.append(_iac_scope_result(invocations, applicable, repo_root, run_fn))

    # image is always reported, regardless of what was requested (FR-007).
    scope_results.append(ScopeResult(scope="image", status="not_available"))

    return SecurityScanResult(scopes=scope_results)
