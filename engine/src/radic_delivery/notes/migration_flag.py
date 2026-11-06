"""Compute a change-note's migration value from a real diff, never accept
it as free caller input (specs/017 research.md D1-D3; Confluence RAITSDA
Reference 3 §2, review comment C4).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from radic_delivery.release.git_history import added_paths

_CONTRACT_MARKER = "# phase: contract"
_MIGRATIONS_VERSIONS_PREFIX = "migrations/versions/"

MigrationFlag = Literal["none", "expand", "contract"]


def _is_qualifying(path: str, legacy_dir: str) -> bool:
    if not path.startswith(_MIGRATIONS_VERSIONS_PREFIX):
        return False
    legacy_prefix = legacy_dir.rstrip("/") + "/"
    return not path.startswith(legacy_prefix)


def _first_non_blank_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _has_contract_marker(repo_dir: Path, path: str) -> bool:
    content = (repo_dir / path).read_text()
    return _first_non_blank_line(content) == _CONTRACT_MARKER


def compute(
    repo_dir: Path,
    base: str,
    head: str,
    *,
    legacy_dir: str = "migrations/legacy",
    phase_header_required: bool = True,
) -> MigrationFlag:
    qualifying = [p for p in added_paths(repo_dir, base, head) if _is_qualifying(p, legacy_dir)]
    if not qualifying:
        return "none"
    if not phase_header_required:
        return "expand"
    if any(_has_contract_marker(repo_dir, path) for path in qualifying):
        return "contract"
    return "expand"
