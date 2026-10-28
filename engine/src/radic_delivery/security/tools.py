"""Pure descriptor+scope -> tool selection (research.md D3).

Mirrors gate/commands.py's pure, filesystem-free design: given a validated
descriptor and a requested scope, always produces the same argv for the
same input. Every argv path is relative to the repo root, which the
runner (not this module) supplies as a subprocess cwd.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from radic_delivery.security.result import Scope, Tool


@dataclass(frozen=True)
class ToolInvocation:
    tool: Tool
    scope: Scope
    argv: list[str]


def _gitleaks_invocation() -> ToolInvocation:
    return ToolInvocation(
        tool="gitleaks",
        scope="source",
        argv=[
            "gitleaks",
            "detect",
            "--source",
            ".",
            "--no-git",
            "--report-format",
            "json",
            "--report-path",
            "-",
            "--exit-code",
            "0",
        ],
    )


def _hadolint_invocation(dockerfile: str) -> ToolInvocation:
    return ToolInvocation(tool="hadolint", scope="iac", argv=["hadolint", "--format", "json", dockerfile])


def _trivy_config_invocation() -> ToolInvocation:
    return ToolInvocation(tool="trivy-config", scope="iac", argv=["trivy", "config", "--format", "json", "."])


def _dockerfile_exists(descriptor: dict[str, Any], repo_root: Path) -> bool:
    """`build.dockerfile` is a *required* schema field with a default
    (feature 001) — every valid descriptor "declares" one, so descriptor
    presence alone can never signal "no Dockerfile." What actually varies
    is whether that file exists in the service's own repo; this performs
    the one filesystem check this module needs to answer that honestly.
    """
    dockerfile = descriptor.get("build", {}).get("dockerfile")
    if not dockerfile:
        return False
    return bool((repo_root / str(dockerfile)).is_file())


def select_tools(
    descriptor: dict[str, Any], requested_scopes: list[str], repo_root: Path
) -> list[ToolInvocation]:
    """Return the ToolInvocations that apply for the requested scopes.

    `image` is never included (not implemented — security/result.py always
    reports it separately as not_available, regardless of what is requested).
    """
    invocations: list[ToolInvocation] = []

    if "source" in requested_scopes or "all" in requested_scopes:
        invocations.append(_gitleaks_invocation())

    if ("iac" in requested_scopes or "all" in requested_scopes) and _dockerfile_exists(descriptor, repo_root):
        dockerfile = descriptor["build"]["dockerfile"]
        invocations.append(_hadolint_invocation(dockerfile))
        invocations.append(_trivy_config_invocation())

    return invocations


def applicable_scopes(
    descriptor: dict[str, Any], requested_scopes: list[str], repo_root: Path
) -> dict[str, bool]:
    """Whether each requested non-image scope actually applies to this descriptor."""
    result: dict[str, bool] = {}
    if "source" in requested_scopes or "all" in requested_scopes:
        result["source"] = True
    if "iac" in requested_scopes or "all" in requested_scopes:
        result["iac"] = _dockerfile_exists(descriptor, repo_root)
    return result
