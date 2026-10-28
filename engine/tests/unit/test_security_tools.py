"""Pure tool-selection tests (spec Acceptance Scenario, research.md D3).

No real scanner is invoked here — these tests only assert on which
ToolInvocations `tools.py` would construct for a descriptor + scope.
"""

from __future__ import annotations

from pathlib import Path

from radic_delivery.security.tools import applicable_scopes, select_tools


def _descriptor(dockerfile: str | None = "Dockerfile") -> dict[str, object]:
    build: dict[str, object] = {}
    if dockerfile is not None:
        build["dockerfile"] = dockerfile
    return {"build": build}


def test_scope_source_selects_only_gitleaks(tmp_path: Path) -> None:
    invocations = select_tools(_descriptor(), ["source"], tmp_path)
    assert [inv.tool for inv in invocations] == ["gitleaks"]


def test_scope_iac_with_dockerfile_on_disk_selects_hadolint_and_trivy(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
    invocations = select_tools(_descriptor(), ["iac"], tmp_path)
    assert {inv.tool for inv in invocations} == {"hadolint", "trivy-config"}


def test_scope_iac_without_dockerfile_on_disk_selects_nothing(tmp_path: Path) -> None:
    """Edge Case: build.dockerfile is a required schema field with a
    default, so every descriptor "declares" one — applicability must be
    judged by the file's real presence on disk, not the descriptor field."""
    invocations = select_tools(_descriptor(), ["iac"], tmp_path)
    assert invocations == []


def test_scope_all_with_dockerfile_selects_all_three(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
    invocations = select_tools(_descriptor(), ["all"], tmp_path)
    assert {inv.tool for inv in invocations} == {"gitleaks", "hadolint", "trivy-config"}


def test_applicable_scopes_reports_iac_not_applicable_without_dockerfile(tmp_path: Path) -> None:
    applicable = applicable_scopes(_descriptor(), ["source", "iac"], tmp_path)
    assert applicable == {"source": True, "iac": False}


def test_applicable_scopes_reports_iac_applicable_with_dockerfile(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
    applicable = applicable_scopes(_descriptor(), ["iac"], tmp_path)
    assert applicable == {"iac": True}
