"""Orchestrates command construction, execution, and parsing into a GateResult.

`release-gate` mode and `run_mutation` are visibly deferred (spec FR-011,
FR-012) — this module never silently treats `release-gate` as `ci-gate`,
and never lets `run_mutation: true` affect the overall result by itself.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from radic_delivery.gate import runner as runner_module
from radic_delivery.gate.commands import ToolInvocation, build_commands
from radic_delivery.gate.parsers import parse_coverage, parse_test_run
from radic_delivery.gate.result import (
    CheckResult,
    CheckStatus,
    CoverageResult,
    GateResult,
    Mode,
    overall_from_checks,
)
from radic_delivery.gate.runner import RunOutcome
from radic_delivery.policy.exceptions import ExceptionStatus
from radic_delivery.policy.exceptions import load as default_exceptions_loader

RunFn = Callable[[ToolInvocation, Path], RunOutcome]
# Looks up the skip-budget exception status for (scope, owner) as of a date.
# Defaults to filtering policy/exceptions.yml's real ledger (data-model.md's
# documented "scope: quality.unit.skip, owner: <service.name>" convention);
# tests inject a fake covering a fabricated ledger instead.
ExceptionCheckerFn = Callable[[str, str, date | None], ExceptionStatus]

_SKIP_EXCEPTION_SCOPE = "quality.unit.skip"


def default_skip_exception_checker(scope: str, owner: str, as_of: date | None) -> ExceptionStatus:
    as_of_date = as_of if as_of is not None else date.today()
    matches = [e for e in default_exceptions_loader() if e.scope == scope and e.owner == owner]
    if not matches:
        return "not_found"
    if any(e.expires >= as_of_date for e in matches):
        return "active"
    return "expired"


def _check_from_outcome(
    check_name: str, outcome: RunOutcome, pass_detail: str, fail_detail: str
) -> CheckResult:
    if not outcome.launched:
        return CheckResult(
            name=check_name,  # type: ignore[arg-type]
            status="not_executable",
            detail=f"Could not execute the {check_name} tool: {outcome.stderr or 'launch failed'}",
        )
    if outcome.exit_code == 0:
        return CheckResult(name=check_name, status="pass", detail=pass_detail)  # type: ignore[arg-type]
    return CheckResult(name=check_name, status="fail", detail=fail_detail)  # type: ignore[arg-type]


def _coverage_floor_shape(floor: dict[str, Any]) -> str:
    return "global" if "global" in floor else "four-figure"


def _check_coverage(floor: dict[str, Any], measured: CoverageResult | None) -> CheckResult:
    if measured is None:
        return CheckResult(
            name="coverage",
            status="fail",
            detail="Could not measure coverage from the unit-test run's output.",
        )

    shape = _coverage_floor_shape(floor)
    if shape == "global":
        if measured.global_ is None:
            return CheckResult(
                name="coverage",
                status="fail",
                detail="Descriptor declares a global coverage floor but no global "
                "coverage figure could be measured.",
            )
        if measured.global_ >= floor["global"]:
            return CheckResult(
                name="coverage",
                status="pass",
                detail=f"Measured coverage {measured.global_}% meets the floor of {floor['global']}%.",
            )
        return CheckResult(
            name="coverage",
            status="fail",
            detail=f"Measured coverage {measured.global_}% is below the floor of {floor['global']}%.",
        )

    figures = {
        "statements": measured.statements,
        "branches": measured.branches,
        "functions": measured.functions,
        "lines": measured.lines,
    }
    if any(value is None for value in figures.values()):
        return CheckResult(
            name="coverage",
            status="fail",
            detail="Descriptor declares a per-figure coverage floor but not every "
            "figure (statements/branches/functions/lines) could be measured.",
        )
    below = {k: v for k, v in figures.items() if v is not None and v < floor[k]}
    if below:
        return CheckResult(
            name="coverage",
            status="fail",
            detail=f"Measured coverage below floor for: {below} (floor: {floor}).",
        )
    return CheckResult(
        name="coverage",
        status="pass",
        detail=f"Measured coverage {figures} meets the floor {floor}.",
    )


def _check_skip_budget(
    skipped: int,
    service_name: str,
    exception_checker: ExceptionCheckerFn,
    as_of: date | None,
) -> CheckResult:
    if skipped == 0:
        return CheckResult(name="skip_budget", status="pass", detail="No tests were skipped.")

    status = exception_checker(_SKIP_EXCEPTION_SCOPE, service_name, as_of)
    if status == "active":
        return CheckResult(
            name="skip_budget",
            status="pass",
            detail=f"{skipped} test(s) skipped, covered by an active exception.",
        )
    return CheckResult(
        name="skip_budget",
        status="fail",
        detail=f"{skipped} test(s) skipped with no active covering exception (exception status: {status}).",
    )


def evaluate(
    descriptor: dict[str, Any],
    mode: Mode,
    run_mutation: bool,
    repo_root: Path,
    run_fn: RunFn = runner_module.run,
    exception_checker: ExceptionCheckerFn = default_skip_exception_checker,
    as_of: date | None = None,
) -> GateResult:
    del run_mutation  # accepted per FR-012; mutation.status is always "not_implemented" below

    if mode == "release-gate":
        return GateResult(mode=mode, overall="not_implemented", checks=[])

    invocations = {inv.check_name: inv for inv in build_commands(descriptor)}

    lint_outcome = run_fn(invocations["lint"], repo_root)
    typecheck_outcome = run_fn(invocations["typecheck"], repo_root)
    unit_outcome = run_fn(invocations["unit"], repo_root)

    checks = [
        _check_from_outcome(
            "lint", lint_outcome, "Lint passed.", "Lint reported one or more violations."
        ),
        _check_from_outcome(
            "typecheck",
            typecheck_outcome,
            "Type-checking passed.",
            "Type-checking reported one or more errors.",
        ),
    ]

    coverage: CoverageResult | None = None
    skipped_count: int | None = None

    if not unit_outcome.launched:
        checks.append(
            CheckResult(
                name="unit",
                status="not_executable",
                detail=f"Could not execute the unit test tool: {unit_outcome.stderr or 'launch failed'}",
            )
        )
        checks.append(
            CheckResult(
                name="coverage",
                status="not_executable",
                detail="Coverage could not be measured because the unit test tool did not run.",
            )
        )
        checks.append(
            CheckResult(
                name="skip_budget",
                status="not_executable",
                detail="Skip budget could not be evaluated because the unit test tool did not run.",
            )
        )
    else:
        test_run = parse_test_run(descriptor["quality"]["unit"]["runner"], unit_outcome.stdout)
        skipped_count = test_run.skipped
        unit_status: CheckStatus = "pass" if unit_outcome.exit_code == 0 else "fail"
        checks.append(
            CheckResult(
                name="unit",
                status=unit_status,
                detail=f"{test_run.passed} passed, {test_run.failed} failed, {test_run.skipped} skipped.",
            )
        )

        coverage = parse_coverage(descriptor["quality"]["unit"]["runner"], unit_outcome.stdout)
        checks.append(_check_coverage(descriptor["quality"]["coverage_floor"], coverage))

        checks.append(
            _check_skip_budget(test_run.skipped, descriptor["service"]["name"], exception_checker, as_of)
        )

    return GateResult(
        mode=mode,
        overall=overall_from_checks(checks),
        checks=checks,
        coverage=coverage,
        skipped_count=skipped_count,
    )
