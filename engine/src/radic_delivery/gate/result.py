"""GateResult/CheckResult/CoverageResult/TestRunResult (data-model.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CheckName = Literal["lint", "typecheck", "unit", "coverage", "skip_budget"]
CheckStatus = Literal["pass", "fail", "not_executable", "not_implemented"]
Mode = Literal["ci-gate", "release-gate"]
Overall = Literal["pass", "fail", "not_implemented"]


@dataclass(frozen=True)
class CheckResult:
    name: CheckName
    status: CheckStatus
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class CoverageResult:
    global_: float | None = None
    statements: float | None = None
    branches: float | None = None
    functions: float | None = None
    lines: float | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.global_ is not None:
            return {"global": self.global_}
        return {
            "statements": self.statements,
            "branches": self.branches,
            "functions": self.functions,
            "lines": self.lines,
        }


@dataclass(frozen=True)
class TestRunResult:
    passed: int
    failed: int
    skipped: int
    skipped_test_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateResult:
    mode: Mode
    overall: Overall
    checks: list[CheckResult] = field(default_factory=list)
    coverage: CoverageResult | None = None
    skipped_count: int | None = None
    mutation: dict[str, str] = field(default_factory=lambda: {"status": "not_implemented"})
    deploy_lint: dict[str, str] = field(default_factory=lambda: {"status": "not_available"})
    test_inventory_uri: dict[str, str] = field(default_factory=lambda: {"status": "not_available"})

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "overall": self.overall,
            "checks": [c.to_dict() for c in self.checks],
            "coverage": self.coverage.to_dict() if self.coverage is not None else None,
            "skipped_count": self.skipped_count,
            "mutation": self.mutation,
            "deploy_lint": self.deploy_lint,
            "test_inventory_uri": self.test_inventory_uri,
        }


def overall_from_checks(checks: list[CheckResult]) -> Overall:
    """GateResult.overall: pass only if every CheckResult is pass."""
    if all(c.status == "pass" for c in checks):
        return "pass"
    return "fail"
