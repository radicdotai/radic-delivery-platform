"""Finding/ScopeResult/SecurityScanResult (data-model.md).

scan_result is always "completed": this feature's whole point is that a
finding, at any severity, never changes that (spec FR-006, research.md D4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["critical", "high", "medium", "low"]
Tool = Literal["gitleaks", "hadolint", "trivy-config"]
Scope = Literal["source", "iac", "image"]
ScopeStatus = Literal["checked", "not_applicable", "not_executable", "not_available"]


@dataclass(frozen=True)
class Finding:
    tool: Tool
    severity: Severity
    rule_id: str
    file: str
    line: int | None
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "severity": self.severity,
            "rule_id": self.rule_id,
            "file": self.file,
            "line": self.line,
            "description": self.description,
        }


@dataclass(frozen=True)
class ScopeResult:
    scope: Scope
    status: ScopeStatus
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass(frozen=True)
class SecurityScanResult:
    scopes: list[ScopeResult] = field(default_factory=list)
    snyk_status: dict[str, str] = field(default_factory=lambda: {"status": "not_available"})
    scan_result: str = "completed"

    @property
    def counts(self) -> dict[str, int]:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for scope_result in self.scopes:
            if scope_result.status != "checked":
                continue
            for finding in scope_result.findings:
                counts[finding.severity] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_result": self.scan_result,
            "scopes": [s.to_dict() for s in self.scopes],
            "counts": self.counts,
            "snyk_status": self.snyk_status,
        }
