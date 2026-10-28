"""Orchestration tests using a fake runner — no real subprocess involved."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from radic_delivery.gate.commands import ToolInvocation
from radic_delivery.gate.evaluator import evaluate
from radic_delivery.gate.result import GateResult
from radic_delivery.gate.runner import RunOutcome


def _descriptor(coverage_floor: dict[str, float] | None = None) -> dict[str, object]:
    return {
        "service": {"name": "sample"},
        "quality": {
            "lint": {"tool": "ruff"},
            "typecheck": {"tool": "mypy", "blocking": True},
            "unit": {"runner": "pytest"},
            "coverage_floor": coverage_floor or {"global": 90},
        },
    }


def _ok(_inv: ToolInvocation, _cwd: Path) -> RunOutcome:
    return RunOutcome(launched=True, exit_code=0, stdout="TOTAL 10 0 100%\n2 passed in 0.01s\n", stderr="")


def _make_runner(overrides: dict[str, RunOutcome]) -> Any:
    def _run(inv: ToolInvocation, cwd: Path) -> RunOutcome:
        return overrides.get(inv.check_name, _ok(inv, cwd))

    return _run


def _run_gate(overrides: dict[str, RunOutcome] | None = None, **kwargs: Any) -> GateResult:
    kwargs.setdefault("mode", "ci-gate")
    kwargs.setdefault("run_mutation", False)
    kwargs.setdefault("repo_root", Path("."))
    kwargs.setdefault("run_fn", _make_runner(overrides or {}))
    return evaluate(_descriptor(kwargs.pop("coverage_floor", None)), **kwargs)


def test_all_checks_pass() -> None:
    result = _run_gate()
    assert result.overall == "pass"
    assert {c.name for c in result.checks} == {"lint", "typecheck", "unit", "coverage", "skip_budget"}
    assert all(c.status == "pass" for c in result.checks)


def test_lint_failure_fails_the_gate() -> None:
    overrides = {"lint": RunOutcome(launched=True, exit_code=1, stdout="", stderr="")}
    result = _run_gate(overrides)
    assert result.overall == "fail"
    assert next(c for c in result.checks if c.name == "lint").status == "fail"


def test_typecheck_failure_fails_the_gate() -> None:
    overrides = {"typecheck": RunOutcome(launched=True, exit_code=1, stdout="", stderr="")}
    result = _run_gate(overrides)
    assert result.overall == "fail"
    assert next(c for c in result.checks if c.name == "typecheck").status == "fail"


def test_unit_failure_fails_the_gate() -> None:
    stdout = "TOTAL 10 0 100%\n1 failed, 1 passed in 0.01s\n"
    overrides = {"unit": RunOutcome(launched=True, exit_code=1, stdout=stdout, stderr="")}
    result = _run_gate(overrides)
    assert result.overall == "fail"
    assert next(c for c in result.checks if c.name == "unit").status == "fail"


def test_missing_tool_is_not_executable_not_fail() -> None:
    overrides = {"lint": RunOutcome(launched=False, exit_code=None, stdout="", stderr="not found")}
    result = _run_gate(overrides)
    assert result.overall == "fail"
    lint_check = next(c for c in result.checks if c.name == "lint")
    assert lint_check.status == "not_executable"
    assert lint_check.status != "fail"


def test_release_gate_mode_is_not_implemented() -> None:
    result = _run_gate(mode="release-gate")
    assert result.overall == "not_implemented"
    assert result.checks == []


def test_run_mutation_is_reported_not_implemented_and_does_not_fail_the_gate() -> None:
    result = _run_gate(run_mutation=True)
    assert result.overall == "pass"
    assert result.mutation == {"status": "not_implemented"}


def test_deploy_lint_and_test_inventory_are_placeholders() -> None:
    result = _run_gate()
    assert result.deploy_lint == {"status": "not_available"}
    assert result.test_inventory_uri == {"status": "not_available"}


def test_coverage_below_floor_fails_independent_of_passing_tests() -> None:
    stdout = "TOTAL 10 7 30%\n2 passed in 0.01s\n"
    overrides = {"unit": RunOutcome(launched=True, exit_code=0, stdout=stdout, stderr="")}
    result = _run_gate(overrides)
    assert result.overall == "fail"
    assert next(c for c in result.checks if c.name == "coverage").status == "fail"
    assert next(c for c in result.checks if c.name == "unit").status == "pass"


def test_coverage_at_or_above_floor_passes() -> None:
    stdout = "TOTAL 10 1 90%\n2 passed in 0.01s\n"
    overrides = {"unit": RunOutcome(launched=True, exit_code=0, stdout=stdout, stderr="")}
    result = _run_gate(overrides)
    assert next(c for c in result.checks if c.name == "coverage").status == "pass"


def test_coverage_is_reported_regardless_of_pass_or_fail() -> None:
    stdout = "TOTAL 10 7 30%\n2 passed in 0.01s\n"
    overrides = {"unit": RunOutcome(launched=True, exit_code=0, stdout=stdout, stderr="")}
    result = _run_gate(overrides)
    assert result.coverage is not None
    assert result.coverage.global_ == 30.0


def _skip_outcome() -> dict[str, RunOutcome]:
    stdout = "TOTAL 10 0 100%\n2 passed, 1 skipped in 0.01s\n"
    return {"unit": RunOutcome(launched=True, exit_code=0, stdout=stdout, stderr="")}


def test_skipped_test_with_no_exception_fails_the_gate() -> None:
    def fake_checker(scope: str, owner: str, as_of: date | None) -> str:
        return "not_found"

    result = _run_gate(_skip_outcome(), exception_checker=fake_checker)
    assert result.overall == "fail"
    assert next(c for c in result.checks if c.name == "skip_budget").status == "fail"


def test_skipped_test_covered_by_active_exception_does_not_fail_the_gate() -> None:
    def fake_checker(scope: str, owner: str, as_of: date | None) -> str:
        assert scope == "quality.unit.skip"
        assert owner == "sample"
        return "active"

    result = _run_gate(_skip_outcome(), exception_checker=fake_checker)
    assert result.overall == "pass"
    assert next(c for c in result.checks if c.name == "skip_budget").status == "pass"


def test_skipped_count_is_reported_regardless_of_pass_or_fail() -> None:
    def fake_checker(scope: str, owner: str, as_of: date | None) -> str:
        return "active"

    result = _run_gate(_skip_outcome(), exception_checker=fake_checker)
    assert result.skipped_count == 1
