"""Pure command-construction tests (spec Acceptance Scenario 5, research.md D1).

No real toolchain is invoked here — these tests only assert on the argv
`commands.py` would construct from a descriptor fragment.
"""

from __future__ import annotations

from radic_delivery.gate.commands import build_commands


def _descriptor(**quality_overrides: object) -> dict[str, object]:
    quality: dict[str, object] = {
        "lint": {"tool": "ruff"},
        "typecheck": {"tool": "mypy", "blocking": True},
        "unit": {"runner": "pytest"},
    }
    quality.update(quality_overrides)
    return {"quality": quality}


def test_python_uv_toolchain_commands() -> None:
    commands = {c.check_name: c.argv for c in build_commands(_descriptor())}
    assert commands["lint"] == ["uv", "run", "ruff", "check", "."]
    assert commands["typecheck"] == ["uv", "run", "mypy", "."]
    assert commands["unit"] == ["uv", "run", "pytest", "--cov", "-q"]


def test_python_uv_unit_with_marker_expr() -> None:
    descriptor = _descriptor(unit={"runner": "pytest", "marker_expr": "not slow"})
    commands = {c.check_name: c.argv for c in build_commands(descriptor)}
    assert commands["unit"] == ["uv", "run", "pytest", "--cov", "-q", "-m", "not slow"]


def test_node_toolchain_commands_without_script() -> None:
    descriptor = _descriptor(
        lint={"tool": "eslint"},
        typecheck={"tool": "tsc", "blocking": True},
        unit={"runner": "vitest"},
    )
    commands = {c.check_name: c.argv for c in build_commands(descriptor)}
    assert commands["lint"] == ["npm", "run", "lint"]
    assert commands["typecheck"] == ["npm", "run", "typecheck"]
    assert commands["unit"] == ["npx", "vitest", "run", "--coverage"]


def test_node_unit_with_script() -> None:
    descriptor = _descriptor(unit={"runner": "vitest", "script": "test:coverage"})
    commands = {c.check_name: c.argv for c in build_commands(descriptor)}
    assert commands["unit"] == ["npm", "run", "test:coverage"]
