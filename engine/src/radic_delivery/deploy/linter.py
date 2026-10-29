"""Orchestrates loading a descriptor's declared manifests, running the
per-file content rules (rules.py), the secret rule (reusing specs/003's
gitleaks integration), and the cross-environment parity rule (parity.py)
into one DeployLintResult.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from radic_delivery.deploy.parity import check_parity
from radic_delivery.deploy.result import DeployLintResult, ManifestCheck, Rule
from radic_delivery.deploy.rules import check_image_placeholder, check_no_traffic_key, check_startup_probe
from radic_delivery.security import runner as security_runner
from radic_delivery.security.parsers import parse_gitleaks
from radic_delivery.security.runner import RunOutcome
from radic_delivery.security.tools import ToolInvocation

RunFn = Callable[[ToolInvocation, Path], RunOutcome]

_CONTENT_RULES: list[Rule] = ["image_placeholder", "no_traffic_key", "startup_probe", "no_inline_secret"]
_ENVS = ("dev", "stage", "prod")


def _load_manifest(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Returns (manifest, error_status) — error_status is "missing_file" or
    "parse_error" when manifest is None, else None."""
    if not path.is_file():
        return None, "missing_file"
    try:
        with path.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError:
        return None, "parse_error"
    if not isinstance(raw, dict):
        return None, "parse_error"
    return raw, None


def _check_no_inline_secret(
    deployable: str, file: str, full_path: Path, run_fn: RunFn, repo_root: Path
) -> ManifestCheck:
    invocation = ToolInvocation(
        tool="gitleaks",
        scope="source",
        argv=[
            "gitleaks",
            "detect",
            "--source",
            str(full_path),
            "--no-git",
            "--report-format",
            "json",
            "--report-path",
            "-",
            "--exit-code",
            "0",
        ],
    )
    outcome = run_fn(invocation, repo_root)
    if not outcome.launched:
        return ManifestCheck(
            deployable=deployable,
            rule="no_inline_secret",
            status="fail",
            file=file,
            detail=f"Could not run gitleaks against this manifest: {outcome.stderr or 'launch failed'}",
        )
    findings = parse_gitleaks(outcome.stdout)
    if findings:
        rules_hit = ", ".join(sorted({f.rule_id for f in findings}))
        return ManifestCheck(
            deployable=deployable,
            rule="no_inline_secret",
            status="fail",
            file=file,
            detail=f"gitleaks found {len(findings)} potential secret(s) ({rules_hit}).",
        )
    return ManifestCheck(
        deployable=deployable,
        rule="no_inline_secret",
        status="pass",
        file=file,
        detail="No secrets detected.",
    )


def _error_checks(deployable: str, file: str, status: str, detail: str) -> list[ManifestCheck]:
    return [
        ManifestCheck(deployable=deployable, rule=rule, status=status, file=file, detail=detail)  # type: ignore[arg-type]
        for rule in _CONTENT_RULES
    ]


def lint(
    descriptor: dict[str, Any], repo_root: Path, run_fn: RunFn = security_runner.run
) -> DeployLintResult:
    checks: list[ManifestCheck] = []

    for deployable in descriptor.get("cloud_deploy", {}).get("deployables", []):
        name = deployable["name"]
        service_yaml = deployable.get("service_yaml")

        if not service_yaml:
            checks.append(
                ManifestCheck(
                    deployable=name,
                    rule="image_placeholder",
                    status="not_applicable",
                    file="(none)",
                    detail="This deployable declares no service_yaml "
                    "(job-only deployables are not linted yet).",
                )
            )
            continue

        manifests: dict[str, dict[str, Any]] = {}
        load_failed = False
        for env in _ENVS:
            rel_path = service_yaml.get(env)
            file_label = rel_path or f"(no {env} path declared)"
            if not rel_path:
                checks.extend(
                    _error_checks(name, file_label, "missing_file", f"No service_yaml.{env} declared.")
                )
                load_failed = True
                continue

            full_path = repo_root / rel_path
            manifest, error_status = _load_manifest(full_path)
            if error_status is not None:
                detail = (
                    "File does not exist."
                    if error_status == "missing_file"
                    else "File is not valid YAML."
                )
                checks.extend(_error_checks(name, rel_path, error_status, detail))
                load_failed = True
                continue

            assert manifest is not None
            manifests[env] = manifest
            checks.append(check_image_placeholder(name, rel_path, manifest))
            checks.append(check_no_traffic_key(name, rel_path, manifest))
            checks.append(check_startup_probe(name, rel_path, manifest))
            checks.append(_check_no_inline_secret(name, rel_path, full_path, run_fn, repo_root))

        if not load_failed and len(manifests) == len(_ENVS):
            allow = deployable.get("parity", {}).get("allow", [])
            checks.extend(check_parity(name, manifests, allow))

    return DeployLintResult(checks=checks)
