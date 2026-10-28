"""Pure descriptor -> command construction (research.md D1).

Deliberately pure and filesystem-free: given a validated descriptor
document, always produces the same argv for the same input. Keeps
Principle VII intact — every branch below is a fixed, reviewed argv list
keyed off an already schema-constrained enum or pattern, never a
descriptor-supplied shell string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from radic_delivery.gate.result import CheckName


@dataclass(frozen=True)
class ToolInvocation:
    check_name: CheckName
    argv: list[str]


def _lint_command(descriptor: dict[str, Any]) -> ToolInvocation:
    tool = descriptor["quality"]["lint"]["tool"]
    if tool == "ruff":
        argv = ["uv", "run", "ruff", "check", "."]
    elif tool == "eslint":
        argv = ["npm", "run", "lint"]
    else:  # pragma: no cover - unreachable, schema constrains the enum
        raise ValueError(f"Unsupported quality.lint.tool: {tool!r}")
    return ToolInvocation(check_name="lint", argv=argv)


def _typecheck_command(descriptor: dict[str, Any]) -> ToolInvocation:
    tool = descriptor["quality"]["typecheck"]["tool"]
    if tool == "mypy":
        argv = ["uv", "run", "mypy", "."]
    elif tool == "tsc":
        argv = ["npm", "run", "typecheck"]
    else:  # pragma: no cover - unreachable, schema constrains the enum
        raise ValueError(f"Unsupported quality.typecheck.tool: {tool!r}")
    return ToolInvocation(check_name="typecheck", argv=argv)


def _unit_command(descriptor: dict[str, Any]) -> ToolInvocation:
    unit = descriptor["quality"]["unit"]
    runner = unit["runner"]
    if runner == "pytest":
        argv = ["uv", "run", "pytest", "--cov", "-q"]
        marker_expr = unit.get("marker_expr")
        if marker_expr:
            argv += ["-m", marker_expr]
    elif runner == "vitest":
        script = unit.get("script")
        if script:
            argv = ["npm", "run", script]
        else:
            argv = ["npx", "vitest", "run", "--coverage"]
    else:  # pragma: no cover - unreachable, schema constrains the enum
        raise ValueError(f"Unsupported quality.unit.runner: {runner!r}")
    return ToolInvocation(check_name="unit", argv=argv)


def build_commands(descriptor: dict[str, Any]) -> list[ToolInvocation]:
    """Return the lint, typecheck, and unit ToolInvocations for a descriptor."""
    return [
        _lint_command(descriptor),
        _typecheck_command(descriptor),
        _unit_command(descriptor),
    ]
