"""radic-delivery: the single supported CLI for radic-delivery-platform.

Registers every command group from the approved architecture so the full
intended surface is discoverable via --help from day one (spec FR-002);
command groups not implemented by this feature respond with a clear,
distinct "not implemented yet" outcome (spec FR-003) rather than an
unhandled error or a silent no-op.
"""

from __future__ import annotations

import json
import sys
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
from radic_delivery.notes.builder import build_record
from radic_delivery.notes.check import classify as classify_pr_body
from radic_delivery.notes.result import build_check_result
from radic_delivery.notes.writer import write as write_change_note
from radic_delivery.policy.exceptions import ExceptionsFileError
from radic_delivery.policy.exceptions import check as check_exception
from radic_delivery.records.validator import validate as validate_test_result
from radic_delivery.records.writer import write as write_test_result
from radic_delivery.release.candidates import load_candidates
from radic_delivery.release.cut import cut as cut_release
from radic_delivery.release.git_history import GitHistoryError, reachable_shas, resolve_ref
from radic_delivery.release.manifest import build_manifest
from radic_delivery.release.selector import select as select_release_candidates
from radic_delivery.release_commands.authorization import authorize as authorize_command
from radic_delivery.release_commands.grammar import parse as parse_command
from radic_delivery.release_commands.result import CommandCheckResult
from radic_delivery.release_commands.workflow_outcome import map_outcome
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


# --- release -------------------------------------------------------------

release_app = typer.Typer(help="Parse and authorize release-PR slash commands.")
app.add_typer(release_app, name="release")


def _emit_command_check_result(format: OutputFormat, result: CommandCheckResult) -> None:
    outcome = map_outcome(result)
    payload = {
        **result.to_dict(),
        "workflow_command": outcome.command,
        "workflow_outcome": outcome.outcome,
        "reply_body": outcome.reply_body,
    }
    if format is OutputFormat.json:
        _emit(format, payload, [])
        return
    text_lines = [f"Release command: {result.classification}"]
    if result.form is not None:
        text_lines.append(f"  form: {result.form}")
    if result.args:
        text_lines.append(f"  args: {result.args}")
    if result.detail:
        text_lines.append(f"  detail: {result.detail}")
    text_lines.append(f"  workflow_command: {outcome.command}")
    text_lines.append(f"  workflow_outcome: {outcome.outcome}")
    if outcome.reply_body is not None:
        text_lines.append(f"  reply_body: {outcome.reply_body}")
    _emit(format, payload, text_lines)


@release_app.command("command")
def release_command(
    comment_file: Path | None = typer.Option(
        None, "--comment-file", help="Path to a file containing the raw PR comment text. Omit to read stdin."
    ),
    actor: str = typer.Option(
        ..., "--actor", help="GitHub username of the comment's author (Confluence Reference 3's flag name)."
    ),
    release_managers: str = typer.Option(
        ..., "--release-managers", help="Comma-separated GitHub usernames on the release-managers team."
    ),
    tech_lead: str = typer.Option(..., "--tech-lead", help="GitHub username of the current Tech Lead."),
    format: OutputFormat = FormatOption,
) -> None:
    """Classify a PR comment as not-a-command, malformed, unauthorized, or accepted.

    The comment text is read from a file or stdin only — never from a CLI
    text argument — so a workflow never has to interpolate an untrusted
    comment body into a shell command (research.md D4).
    """
    comment_body = comment_file.read_text() if comment_file is not None else sys.stdin.read()
    release_manager_list = [name.strip() for name in release_managers.split(",") if name.strip()]

    parsed = parse_command(comment_body)
    result = authorize_command(parsed, actor, release_manager_list, tech_lead)
    _emit_command_check_result(format, result)

    if result.classification in ("not_a_command", "accepted"):
        raise typer.Exit(code=int(ExitCode.OK))
    if result.classification == "malformed":
        raise typer.Exit(code=int(ExitCode.INVALID_INPUT))
    raise typer.Exit(code=int(ExitCode.POLICY_FAILURE))  # unauthorized


@release_app.command("propose")
def release_propose(
    repo: str = typer.Option(..., "--repo", help="e.g. radicdotai/web-bff."),
    base: str = typer.Option(..., "--base", help="dev or main."),
    repo_dir: Path = typer.Option(
        Path("."), "--repo-dir", help="Local git checkout to inspect (same flag name as `tests inventory`)."
    ),
    change_notes_dir: Path = typer.Option(
        Path("."), "--change-notes-dir", help="Root of the local change-notes/ tree `notes write` produces."
    ),
    tickets: str | None = typer.Option(
        None, "--tickets", help="Comma-separated ticket keys considered ready for this release."
    ),
    non_jira_prs: str | None = typer.Option(
        None, "--non-jira-prs", help="Comma-separated PR numbers merged without a Jira key to include."
    ),
    dev_green_failed: str | None = typer.Option(
        None,
        "--dev-green-failed",
        help="Comma-separated commit SHAs known to have failed the pre-release regression check.",
    ),
    since_sha: str | None = typer.Option(
        None,
        "--since-sha",
        help="Exclude commits already an ancestor of this SHA (the previous release marker).",
    ),
    release_id: str | None = typer.Option(None, "--release-id", help="Override; default <today>-1."),
    kind: str = typer.Option("release", "--kind", help="release|hotfix."),
    initiator: str = typer.Option(..., "--initiator"),
    out_dir: Path = typer.Option(
        Path("."), "--out-dir", help="Local root to write the manifest under."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Never write the manifest locally (research.md D6)."
    ),
    format: OutputFormat = FormatOption,
) -> None:
    """Select ready tickets/commits and write a draft release manifest.

    Ticket readiness and dev-green status are explicit inputs — this
    command never queries Jira or a test-results store itself (FR-003,
    FR-004, FR-010).
    """
    ready = {key.strip() for key in tickets.split(",") if key.strip()} if tickets else set()
    non_jira = {int(pr.strip()) for pr in non_jira_prs.split(",") if pr.strip()} if non_jira_prs else set()
    failed_shas = (
        {sha.strip() for sha in dev_green_failed.split(",") if sha.strip()} if dev_green_failed else set()
    )

    try:
        base_sha = resolve_ref(repo_dir, base)
        reachable = reachable_shas(repo_dir, base=base, since_sha=since_sha)
    except GitHistoryError as exc:
        payload = {"ok": False, "error": str(exc)}
        _emit(format, payload, [f"INFRA ERROR: {exc}"])
        raise typer.Exit(code=int(ExitCode.INFRA_ERROR)) from exc

    candidates, load_issues = load_candidates(change_notes_dir, repo)
    candidates = [candidate for candidate in candidates if candidate.sha in reachable]

    if load_issues:
        payload = {
            "ok": False,
            "issues": [{"path": issue.path, "message": issue.message} for issue in load_issues],
        }
        _emit(format, payload, [f"INVALID: {len(load_issues)} change-note record(s) could not be read."])
        raise typer.Exit(code=int(ExitCode.INVALID_INPUT))

    selection = select_release_candidates(
        candidates, ready_tickets=ready, dev_green_failed=failed_shas, non_jira_prs=non_jira
    )
    resolved_release_id = release_id or f"{date.today():%Y.%m.%d}-1"
    result = build_manifest(
        selection,
        repo=repo,
        base_branch=base,
        base_sha=base_sha,
        release_id=resolved_release_id,
        initiator=initiator,
        kind=kind,
    )

    if not result.ok:
        _emit(
            format,
            result.to_dict(),
            [f"INVALID: {len(result.issues)} issue(s) found."]
            + [f"  [{issue.path}] {issue.message}" for issue in result.issues],
        )
        raise typer.Exit(code=int(ExitCode.INVALID_INPUT))

    local_path = None
    if not dry_run:
        assert result.manifest is not None
        target = out_dir / "releases" / f"{resolved_release_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result.manifest, indent=2))
        local_path = str(target)

    payload = result.to_dict()
    if local_path is not None:
        payload["local_path"] = local_path
    text_lines = [
        "OK: release proposal computed.",
        f"  proposed tickets: {len(selection.tickets)}",
        f"  held back: {len(selection.held_back)}",
        f"  non-jira PRs included: {len(selection.non_jira_prs)}",
    ]
    if local_path is not None:
        text_lines.append(f"  local_path: {local_path}")
    _emit(format, payload, text_lines)
    raise typer.Exit(code=int(ExitCode.OK))


@release_app.command("cut")
def release_cut(
    manifest_path: Path = typer.Option(..., "--manifest", help="Path to the draft (proposed) manifest."),
    release_id: str = typer.Option(..., "--release-id"),
    hotfix: bool = typer.Option(False, "--hotfix/--no-hotfix"),
    repo_dir: Path = typer.Option(Path("."), "--repo-dir", help="Local git checkout to cut from."),
    change_notes_dir: Path = typer.Option(
        Path("."), "--change-notes-dir", help="Root of the local change-notes/ tree `notes write` produces."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Validate and resolve everything without touching the repo or the manifest."
    ),
    format: OutputFormat = FormatOption,
) -> None:
    """Create release/<id> from main and cherry-pick the manifest's
    selection onto it (FR-001 through FR-009).

    Never branches from anything but the fixed production line, never
    cherry-picks in anything but the commits' own chronological order,
    and never leaves a partial branch or an unchanged-but-claimed-cut
    manifest behind on failure.
    """
    manifest = json.loads(manifest_path.read_text())

    try:
        result = cut_release(
            manifest,
            repo_dir=repo_dir,
            change_notes_dir=change_notes_dir,
            release_id=release_id,
            hotfix=hotfix,
            dry_run=dry_run,
        )
    except GitHistoryError as exc:
        payload = {"ok": False, "error": str(exc)}
        _emit(format, payload, [f"INFRA ERROR: {exc}"])
        raise typer.Exit(code=int(ExitCode.INFRA_ERROR)) from exc

    if not result.ok:
        text_lines = [f"FAILED: {result.reason}", f"  detail: {result.detail}"]
        if result.failed_sha:
            text_lines.append(f"  failed_sha: {result.failed_sha}")
        _emit(format, result.to_dict(), text_lines)
        if result.reason == "cherry_pick_conflict":
            raise typer.Exit(code=int(ExitCode.INFRA_ERROR))
        raise typer.Exit(code=int(ExitCode.INVALID_INPUT))

    if not dry_run:
        manifest_path.write_text(json.dumps(result.manifest, indent=2))

    text_lines = ["OK: release cut." if not dry_run else "OK: dry run — nothing was changed."]
    if not dry_run:
        text_lines.append(f"  release_branch: {result.manifest['release_branch']}")
        text_lines.append(f"  release_head: {result.manifest['release_head']}")
    _emit(format, result.to_dict(), text_lines)
    raise typer.Exit(code=int(ExitCode.OK))


_RELEASE_NOT_IMPLEMENTED = ["verify-promotion", "finalise"]


def _make_release_stub(subcommand_name: str) -> Any:
    def _stub(ctx: typer.Context) -> None:
        typer.echo(
            f"'release {subcommand_name}' is a planned subcommand (see the approved architecture) "
            "that is not implemented yet by this feature.",
            err=True,
        )
        raise typer.Exit(code=NOT_IMPLEMENTED_EXIT_CODE)

    return _stub


for _subcommand_name in _RELEASE_NOT_IMPLEMENTED:
    release_app.command(
        name=_subcommand_name,
        help=f"(not implemented yet) release {_subcommand_name}.",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )(_make_release_stub(_subcommand_name))


# --- notes ---------------------------------------------------------------

notes_app = typer.Typer(help="Capture change-note records and check release-note completeness.")
app.add_typer(notes_app, name="notes")


@notes_app.command("write")
def notes_write(
    repo: str = typer.Option(..., "--repo", help="e.g. radicdotai/web-bff."),
    sha: str = typer.Option(..., "--sha", help="40-character commit SHA."),
    pr: int | None = typer.Option(None, "--pr", help="Pull request number."),
    bucket: str | None = typer.Option(
        None,
        "--bucket",
        help="Accepted for contract compatibility; the real GCS upload is not implemented yet.",
    ),
    type_: str = typer.Option(
        ..., "--type", help="feature|fix|improvement|chore|security|docs|internal."
    ),
    audience: str = typer.Option(..., "--audience", help="customer|internal|none."),
    title: str = typer.Option(..., "--title"),
    summary: str = typer.Option(..., "--summary"),
    jira_key: str = typer.Option(
        ..., "--jira-key", help="A Jira key (e.g. RAD-1234), or the literal 'None'."
    ),
    linked_prs: str | None = typer.Option(
        None, "--linked-prs", help="Comma-separated cross-repo refs, e.g. radicdotai/frontend-v2#456."
    ),
    migration: bool = typer.Option(False, "--migration/--no-migration"),
    uat_escape: bool = typer.Option(False, "--uat-escape/--no-uat-escape"),
    regression_test_added: bool = typer.Option(False, "--regression-test-added/--no-regression-test-added"),
    author: str | None = typer.Option(None, "--author"),
    merged_at: str | None = typer.Option(None, "--merged-at", help="ISO 8601 date-time."),
    out_dir: Path = typer.Option(Path("."), "--out-dir", help="Local root to write the record under."),
    format: OutputFormat = FormatOption,
) -> None:
    """Build, validate, and write one change-note record (FR-001 through FR-004).

    Never fetches a pull request's details from GitHub itself — every
    field is explicit input (FR-010). The real GCS upload is not
    implemented; `upload_status` always reports `not_available`.
    """
    build_result = build_record(
        repo=repo,
        sha=sha,
        pr_number=pr,
        type=type_,
        audience=audience,
        title=title,
        summary=summary,
        jira_key=jira_key,
        linked_prs=[item.strip() for item in linked_prs.split(",") if item.strip()] if linked_prs else None,
        migration=migration,
        uat_escape=uat_escape,
        regression_test_added=regression_test_added,
        author=author,
        merged_at=merged_at,
    )

    if not build_result.ok:
        _emit(
            format,
            build_result.to_dict(),
            [f"INVALID: {len(build_result.issues)} issue(s) found."]
            + [f"  [{issue.path}] {issue.message}" for issue in build_result.issues],
        )
        raise typer.Exit(code=int(ExitCode.INVALID_INPUT))

    assert build_result.record is not None
    write_result = write_change_note(build_result.record, repo=repo, sha=sha, out_dir=out_dir)
    payload = {**build_result.to_dict(), **write_result.to_dict()}
    _emit(
        format,
        payload,
        [
            "OK: change-note record written.",
            f"  local_path: {write_result.local_path}",
            f"  upload_status: {write_result.upload_status}",
        ],
    )
    raise typer.Exit(code=int(ExitCode.OK))


@notes_app.command("check")
def notes_check(
    pr_body_file: Path = typer.Option(
        ..., "--pr-body-file", help="Path to a file containing the raw pull request body text."
    ),
    require_jira_key: bool = typer.Option(
        False, "--require-jira-key", help="Block (exit 3) on an incomplete body instead of only warning."
    ),
    format: OutputFormat = FormatOption,
) -> None:
    """Classify a PR body's Jira-reference completeness (FR-006 through FR-009).

    The PR body is read from a file, never a raw CLI text argument, since
    it is attacker-influenced free text (FR-005).
    """
    classification, jira_key = classify_pr_body(pr_body_file.read_text())
    result = build_check_result(classification, jira_key, blocking=require_jira_key)

    payload = result.to_dict()
    text_lines = [f"Release-note check: {result.classification}"]
    if result.jira_key is not None:
        text_lines.append(f"  jira_key: {result.jira_key}")
    if result.detail:
        text_lines.append(f"  detail: {result.detail}")
    text_lines.append(f"  passed: {result.passed}")
    _emit(format, payload, text_lines)

    raise typer.Exit(code=int(ExitCode.OK if result.passed else ExitCode.POLICY_FAILURE))


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


# --- records ---------------------------------------------------------------

records_app = typer.Typer(help="Validate and store test-result records.")
app.add_typer(records_app, name="records")


@records_app.command("put-test-result")
def records_put_test_result(
    file: Path = typer.Option(..., "--file", help="Path to a complete test-result record (JSON)."),
    release_id: str | None = typer.Option(
        None, "--release-id", help="Cross-checked against the record's own release_id, if present."
    ),
    out_dir: Path = typer.Option(Path("."), "--out-dir", help="Local root to write the record under."),
    format: OutputFormat = FormatOption,
) -> None:
    """Validate and store one test-result record (FR-001 through FR-009).

    Never fetches or verifies anything live (no Jira/GitHub/GCP call) —
    every field, including `cloud_deploy`, is trusted, structurally-
    validated input (FR-010).
    """
    record = json.loads(file.read_text())
    issues = validate_test_result(record, release_id)

    if issues:
        payload: dict[str, Any] = {
            "ok": False,
            "local_path": None,
            "result": None,
            "issues": [{"path": issue.path, "message": issue.message} for issue in issues],
            "upload_status": None,
        }
        _emit(
            format,
            payload,
            [f"INVALID: {len(issues)} issue(s) found."]
            + [f"  [{issue.path}] {issue.message}" for issue in issues],
        )
        raise typer.Exit(code=int(ExitCode.INVALID_INPUT))

    local_path = write_test_result(record, out_dir=out_dir)
    payload = {
        "ok": True,
        "local_path": local_path,
        "result": record["result"],
        "issues": [],
        "upload_status": "not_available",
    }
    _emit(
        format,
        payload,
        [
            "OK: test-result record stored.",
            f"  result: {record['result']}",
            f"  local_path: {local_path}",
            "  upload_status: not_available",
        ],
    )
    raise typer.Exit(code=int(ExitCode.OK))


# --- not-yet-implemented command groups ------------------------------------
# Declared explicitly so the full intended surface (Reference 3: Schemas,
# Identity and Commands) is discoverable from --help on day one.

_NOT_IMPLEMENTED_GROUPS = ["tests", "rollback", "migrations"]


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
