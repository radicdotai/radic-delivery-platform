"""Orchestrates command construction, execution, and parsing into a GateResult.

`release-gate` mode and `run_mutation` are visibly deferred (spec FR-011,
FR-012) — this module never silently treats `release-gate` as `ci-gate`,
and never lets `run_mutation: true` affect the overall result by itself.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, cast

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


def _check_stage_regression(results_dir: Path | None, digest: str | None) -> CheckResult:
    """release-gate only: a local stage test-result record (specs/010's
    own output tree) must exist for the exact digest being evaluated, be
    scoped as a full regression, and pass cleanly (research.md D2)."""
    if results_dir is None or digest is None:
        return CheckResult(
            name="stage_regression",
            status="not_executable",
            detail="release-gate requires --results-dir and --digest to evaluate the stage regression.",
        )

    record: dict[str, Any] | None = None
    for path in sorted(results_dir.rglob("*.json")):
        try:
            candidate = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if candidate.get("environment") == "stage" and candidate.get("digest") == digest:
            record = candidate
            break

    if record is None:
        return CheckResult(
            name="stage_regression",
            status="fail",
            detail=f"no stage test-result record found for digest {digest}.",
        )

    if record.get("scope") != "full":
        return CheckResult(
            name="stage_regression",
            status="fail",
            detail=f"stage record for digest {digest} is not scoped as a full regression.",
        )
    if record.get("result") != "pass":
        return CheckResult(
            name="stage_regression",
            status="fail",
            detail=f"stage record for digest {digest} did not pass (result: {record.get('result')}).",
        )
    skipped = record.get("counts", {}).get("skipped", 0)
    if skipped:
        return CheckResult(
            name="stage_regression",
            status="fail",
            detail=f"stage record for digest {digest} has {skipped} skipped test(s).",
        )

    return CheckResult(
        name="stage_regression",
        status="pass",
        detail=f"stage record for digest {digest} is a full, clean pass.",
    )


def _read_change_note(change_notes_dir: Path, repo: str, sha: str) -> dict[str, Any] | None:
    path = change_notes_dir / "change-notes" / repo / f"{sha}.json"
    if not path.is_file():
        return None
    try:
        return cast(dict[str, Any], json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError):
        return None


def _check_prereqs(manifest: dict[str, Any], change_notes_dir: Path | None) -> CheckResult:
    """release-gate only: every selected ticket's Prereqs checklist must
    be fully ticked (specs/019 research.md D5). Only ever called when a
    manifest was supplied (research.md D5, corrected) — an existing
    release-gate caller that never passes `--manifest` gets no new check
    appended at all, never a `not_executable` that would fail the overall
    result for something it never opted into."""
    if change_notes_dir is None:
        return CheckResult(
            name="prereqs",
            status="not_executable",
            detail="release-gate requires --change-notes-dir (alongside --manifest) to evaluate Prereqs.",
        )

    repo = manifest["repo"]
    for ticket in manifest["selection"]["tickets"]:
        for commit in ticket.get("commits", []):
            note = _read_change_note(change_notes_dir, repo, commit["dev_sha"])
            if note is None:
                continue
            for item in note.get("prereqs", []):
                if not item.get("done"):
                    return CheckResult(
                        name="prereqs",
                        status="fail",
                        detail=f"ticket {ticket['key']} has an unticked Prereqs item: "
                        f"{item.get('item', '(unnamed)')!r}.",
                    )
    return CheckResult(name="prereqs", status="pass", detail="every selected ticket's Prereqs are ticked.")


def _check_depends_on(
    manifest: dict[str, Any], change_notes_dir: Path | None, known_prod_tickets: list[str] | None
) -> CheckResult:
    """release-gate only: every selected ticket's Depends-on tickets must
    be in the selection or already known to be in production (specs/019
    research.md D5). Only ever called when a manifest was supplied — see
    `_check_prereqs`'s own docstring for why."""
    if change_notes_dir is None:
        return CheckResult(
            name="depends_on",
            status="not_executable",
            detail="release-gate requires --change-notes-dir (alongside --manifest) to evaluate Depends-on.",
        )

    repo = manifest["repo"]
    selected_keys = {ticket["key"] for ticket in manifest["selection"]["tickets"]}
    known = set(known_prod_tickets or [])
    for ticket in manifest["selection"]["tickets"]:
        for commit in ticket.get("commits", []):
            note = _read_change_note(change_notes_dir, repo, commit["dev_sha"])
            if note is None:
                continue
            for dep in note.get("depends_on", []):
                if dep == ticket["key"] or dep in selected_keys or dep in known:
                    continue
                return CheckResult(
                    name="depends_on",
                    status="fail",
                    detail=f"ticket {ticket['key']} depends on {dep}, which is neither selected "
                    "nor known to be in production.",
                )
    return CheckResult(
        name="depends_on", status="pass", detail="every selected ticket's Depends-on tickets are satisfied."
    )


def evaluate(
    descriptor: dict[str, Any],
    mode: Mode,
    run_mutation: bool,
    repo_root: Path,
    run_fn: RunFn = runner_module.run,
    exception_checker: ExceptionCheckerFn = default_skip_exception_checker,
    as_of: date | None = None,
    results_dir: Path | None = None,
    digest: str | None = None,
    manifest: dict[str, Any] | None = None,
    change_notes_dir: Path | None = None,
    known_prod_tickets: list[str] | None = None,
) -> GateResult:
    del run_mutation  # accepted per FR-012; mutation.status is always "not_implemented" below

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

    if mode == "release-gate":
        checks.append(_check_stage_regression(results_dir, digest))
        if manifest is not None:
            checks.append(_check_prereqs(manifest, change_notes_dir))
            checks.append(_check_depends_on(manifest, change_notes_dir, known_prod_tickets))

    return GateResult(
        mode=mode,
        overall=overall_from_checks(checks),
        checks=checks,
        coverage=coverage,
        skipped_count=skipped_count,
    )
