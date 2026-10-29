"""radic-delivery: the single supported CLI for radic-delivery-platform.

Registers every command group from the approved architecture so the full
intended surface is discoverable via --help from day one (spec FR-002);
command groups not implemented by this feature respond with a clear,
distinct "not implemented yet" outcome (spec FR-003) rather than an
unhandled error or a silent no-op.
"""

from __future__ import annotations

import json
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

import typer

from radic_delivery.deploy.linter import lint as lint_deploy
from radic_delivery.deploy.result import DeployLintResult
from radic_delivery.descriptor.resolver import resolve as resolve_descriptor
from radic_delivery.descriptor.schema_loader import load_service_schema
from radic_delivery.descriptor.validator import ValidationResult
from radic_delivery.descriptor.validator import validate as validate_descriptor
from radic_delivery.exit_codes import NOT_IMPLEMENTED_EXIT_CODE, ExitCode
from radic_delivery.gate.evaluator import evaluate as evaluate_gate
from radic_delivery.gate.result import GateResult
from radic_delivery.policy.exceptions import ExceptionsFileError
from radic_delivery.policy.exceptions import check as check_exception
from radic_delivery.security.aggregator import scan as scan_security
from radic_delivery.security.result import SecurityScanResult

app = typer.Typer(
    name="radic-delivery",
    help="Centralised CI/CD engine CLI for radic-delivery-platform.",
    no_args_is_help=True,
)


class OutputFormat(StrEnum):
    json = "json"
    text = "text"


FormatOption = typer.Option(OutputFormat.text, "--format", help="Output format.")


def _emit(format: OutputFormat, payload: dict[str, Any], text_lines: list[str]) -> None:
    if format is OutputFormat.json:
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        for line in text_lines:
            typer.echo(line)


def _emit_validation_result(format: OutputFormat, result: ValidationResult) -> None:
    payload = {
        "ok": result.ok,
        "issues": [
            {"path": issue.path, "message": issue.message, "category": issue.category}
            for issue in result.issues
        ],
    }
    if result.ok:
        text_lines = ["OK: descriptor is valid."]
    else:
        text_lines = [f"INVALID: {len(result.issues)} issue(s) found."]
        text_lines += [f"  [{issue.category}] {issue.path}: {issue.message}" for issue in result.issues]
    _emit(format, payload, text_lines)


# --- descriptor ------------------------------------------------------------

descriptor_app = typer.Typer(help="Validate and inspect .radic/service.yml descriptors.")
app.add_typer(descriptor_app, name="descriptor")


@descriptor_app.command("validate")
def descriptor_validate(
    path: Path = typer.Argument(..., help="Path to a .radic/service.yml descriptor."),
    format: OutputFormat = FormatOption,
) -> None:
    """Validate a service descriptor against schemas/service.schema.json."""
    result = validate_descriptor(path)
    _emit_validation_result(format, result)
    raise typer.Exit(code=int(ExitCode.OK if result.ok else ExitCode.INVALID_INPUT))


@descriptor_app.command("show")
def descriptor_show(
    path: Path = typer.Argument(..., help="Path to a .radic/service.yml descriptor."),
    format: OutputFormat = FormatOption,
) -> None:
    """Show a descriptor fully resolved, with schema defaults applied."""
    result = validate_descriptor(path)
    if not result.ok:
        _emit_validation_result(format, result)
        raise typer.Exit(code=int(ExitCode.INVALID_INPUT))

    assert result.document is not None
    schema = load_service_schema()
    resolved, defaulted = resolve_descriptor(result.document, schema)

    payload = {"resolved": resolved, "defaulted_fields": sorted(defaulted)}
    text_lines = [json.dumps(resolved, indent=2, default=str), "", "Defaulted fields:"]
    text_lines += [f"  - {field}" for field in sorted(defaulted)] or ["  (none)"]
    _emit(format, payload, text_lines)
    raise typer.Exit(code=int(ExitCode.OK))


# --- gate --------------------------------------------------------------

gate_app = typer.Typer(help="Evaluate a service's quality gate.")
app.add_typer(gate_app, name="gate")


class GateMode(StrEnum):
    ci_gate = "ci-gate"
    release_gate = "release-gate"


def _emit_gate_result(format: OutputFormat, result: GateResult) -> None:
    payload = result.to_dict()
    if format is OutputFormat.json:
        _emit(format, payload, [])
        return
    text_lines = [f"Gate ({result.mode}): {result.overall.upper()}"]
    for check in result.checks:
        text_lines.append(f"  [{check.status}] {check.name}: {check.detail}")
    if result.coverage is not None:
        text_lines.append(f"  coverage: {result.coverage.to_dict()}")
    if result.skipped_count is not None:
        text_lines.append(f"  skipped_count: {result.skipped_count}")
    text_lines.append(f"  mutation: {result.mutation}")
    text_lines.append(f"  deploy_lint: {result.deploy_lint}")
    text_lines.append(f"  test_inventory_uri: {result.test_inventory_uri}")
    _emit(format, payload, text_lines)


@gate_app.command("evaluate")
def gate_evaluate(
    descriptor: Path = typer.Option(
        Path(".radic/service.yml"), "--descriptor", help="Path to the service descriptor."
    ),
    mode: GateMode = typer.Option(GateMode.ci_gate, "--mode", help="Which gate mode to evaluate."),
    run_mutation: bool = typer.Option(
        False, "--run-mutation", help="Request mutation testing (not implemented yet; never fails the gate)."
    ),
    format: OutputFormat = FormatOption,
) -> None:
    """Evaluate the quality gate for a service (FR-002 through FR-013)."""
    validation = validate_descriptor(descriptor)
    if not validation.ok:
        _emit_validation_result(format, validation)
        raise typer.Exit(code=int(ExitCode.INVALID_INPUT))

    assert validation.document is not None
    repo_root = descriptor.resolve().parent.parent
    result = evaluate_gate(
        validation.document,
        mode=mode.value,
        run_mutation=run_mutation,
        repo_root=repo_root,
    )
    _emit_gate_result(format, result)

    if result.overall == "pass":
        raise typer.Exit(code=int(ExitCode.OK))
    if result.overall == "not_implemented":
        raise typer.Exit(code=NOT_IMPLEMENTED_EXIT_CODE)
    # A gate failure (lint/typecheck/unit/coverage/skip-budget not met) is a
    # policy rejection, distinct from the descriptor itself being malformed
    # (that case already exited INVALID_INPUT above, before any check ran).
    raise typer.Exit(code=int(ExitCode.POLICY_FAILURE))


# --- security ------------------------------------------------------------

security_app = typer.Typer(help="Scan a service for security findings (report-only).")
app.add_typer(security_app, name="security")


class SecurityScope(StrEnum):
    source = "source"
    iac = "iac"
    all = "all"


def _emit_security_result(format: OutputFormat, result: SecurityScanResult) -> None:
    payload = result.to_dict()
    if format is OutputFormat.json:
        _emit(format, payload, [])
        return
    text_lines = [f"Security scan: {result.scan_result} (report-only, never blocks)"]
    for scope_result in result.scopes:
        text_lines.append(f"  [{scope_result.status}] scope={scope_result.scope}")
        for finding in scope_result.findings:
            text_lines.append(
                f"    ({finding.severity}) {finding.tool}:{finding.rule_id} "
                f"{finding.file}:{finding.line} — {finding.description}"
            )
    text_lines.append(f"  counts: {result.counts}")
    text_lines.append(f"  snyk_status: {result.snyk_status}")
    _emit(format, payload, text_lines)


@security_app.command("scan")
def security_scan(
    descriptor: Path = typer.Option(
        Path(".radic/service.yml"), "--descriptor", help="Path to the service descriptor."
    ),
    scope: SecurityScope = typer.Option(SecurityScope.all, "--scope", help="Which scope(s) to scan."),
    format: OutputFormat = FormatOption,
) -> None:
    """Scan a service for secrets and Dockerfile/IaC misconfigurations.

    Report-only: this command always exits OK once the descriptor itself
    validates, regardless of what it finds (spec FR-006). Image scanning
    and Snyk are always reported as not-yet-available (FR-007, FR-008).
    """
    validation = validate_descriptor(descriptor)
    if not validation.ok:
        _emit_validation_result(format, validation)
        raise typer.Exit(code=int(ExitCode.INVALID_INPUT))

    assert validation.document is not None
    repo_root = descriptor.resolve().parent.parent
    result = scan_security(validation.document, scopes=[scope.value], repo_root=repo_root)
    _emit_security_result(format, result)
    raise typer.Exit(code=int(ExitCode.OK))


# --- deploy ------------------------------------------------------------

deploy_app = typer.Typer(help="Lint and (eventually) manage a service's Cloud Deploy manifests.")
app.add_typer(deploy_app, name="deploy")


def _emit_deploy_lint_result(format: OutputFormat, result: DeployLintResult) -> None:
    payload = result.to_dict()
    if format is OutputFormat.json:
        _emit(format, payload, [])
        return
    text_lines = [f"Deploy lint: {result.overall.upper()}"]
    for check in result.checks:
        text_lines.append(
            f"  [{check.status}] {check.deployable}/{check.rule} ({check.file}): {check.detail}"
        )
    _emit(format, payload, text_lines)


@deploy_app.command("lint")
def deploy_lint(
    descriptor: Path = typer.Option(
        Path(".radic/service.yml"), "--descriptor", help="Path to the service descriptor."
    ),
    format: OutputFormat = FormatOption,
) -> None:
    """Lint a service's Cloud Run deploy manifests (FR-002 through FR-011).

    A binary correctness check, not an advisory scan: a bad manifest is
    invalid input to a deploy that must not happen, so a lint failure and
    an invalid descriptor both exit INVALID_INPUT.
    """
    validation = validate_descriptor(descriptor)
    if not validation.ok:
        _emit_validation_result(format, validation)
        raise typer.Exit(code=int(ExitCode.INVALID_INPUT))

    assert validation.document is not None
    repo_root = descriptor.resolve().parent.parent
    result = lint_deploy(validation.document, repo_root=repo_root)
    _emit_deploy_lint_result(format, result)
    raise typer.Exit(code=int(ExitCode.OK if result.overall == "pass" else ExitCode.INVALID_INPUT))


_DEPLOY_NOT_IMPLEMENTED = ["release", "promote", "approve", "rollback", "status", "drift"]


def _make_deploy_stub(subcommand_name: str) -> Any:
    def _stub(ctx: typer.Context) -> None:
        typer.echo(
            f"'deploy {subcommand_name}' is a planned subcommand (see the approved architecture) "
            "that is not implemented yet by this feature — it would call real Cloud Deploy.",
            err=True,
        )
        raise typer.Exit(code=NOT_IMPLEMENTED_EXIT_CODE)

    return _stub


for _subcommand_name in _DEPLOY_NOT_IMPLEMENTED:
    deploy_app.command(
        name=_subcommand_name,
        help=f"(not implemented yet) deploy {_subcommand_name}.",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )(_make_deploy_stub(_subcommand_name))


# --- policy ------------------------------------------------------------

policy_app = typer.Typer(help="Inspect the policy/exceptions.yml ledger.")
app.add_typer(policy_app, name="policy")

exceptions_app = typer.Typer(help="Check policy exception status.")
policy_app.add_typer(exceptions_app, name="exceptions")


@exceptions_app.command("check")
def exceptions_check(
    exception_id: str = typer.Argument(..., help="Exception id, e.g. EXC-0001."),
    as_of: str | None = typer.Option(None, "--as-of", help="ISO date to check against (default: today)."),
    format: OutputFormat = FormatOption,
) -> None:
    """Report whether a policy exception is active, expired, or not recorded."""
    as_of_date = date.fromisoformat(as_of) if as_of else None
    try:
        status = check_exception(exception_id, as_of=as_of_date)
    except ExceptionsFileError as exc:
        payload = {"ok": False, "error": str(exc)}
        _emit(format, payload, [f"INVALID: {exc}"])
        raise typer.Exit(code=int(ExitCode.INVALID_INPUT)) from exc

    payload = {"id": exception_id, "status": status}
    _emit(format, payload, [f"{exception_id}: {status}"])
    exit_code = ExitCode.OK if status == "active" else ExitCode.POLICY_FAILURE
    raise typer.Exit(code=int(exit_code))


# --- not-yet-implemented command groups ------------------------------------
# Declared explicitly so the full intended surface (Reference 3: Schemas,
# Identity and Commands) is discoverable from --help on day one.

_NOT_IMPLEMENTED_GROUPS = ["notes", "tests", "release", "records", "rollback", "migrations"]


def _make_stub(group_name: str) -> Any:
    def _stub(ctx: typer.Context) -> None:
        typer.echo(
            f"'{group_name}' is a planned command group (see the approved architecture) "
            "that is not implemented yet by this feature.",
            err=True,
        )
        raise typer.Exit(code=NOT_IMPLEMENTED_EXIT_CODE)

    return _stub


for _group_name in _NOT_IMPLEMENTED_GROUPS:
    app.command(
        name=_group_name,
        help=f"(not implemented yet) {_group_name} command group.",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )(_make_stub(_group_name))


if __name__ == "__main__":
    app()
