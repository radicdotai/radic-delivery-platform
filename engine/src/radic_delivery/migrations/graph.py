"""`migrations check`'s `migration_graph`: parses Alembic-style migration
files (a `revision`/`down_revision` literal pair per file) and checks the
chain is a single, linear sequence — no fork, no cycle (research.md D3).

Each file is parsed with `ast`, never executed (Principle VII).
"""

from __future__ import annotations

import ast
from pathlib import Path

from radic_delivery.migrations.result import Fork, MigrationGraphResult


def _parse_revision_pair(path: Path) -> tuple[str | None, str | None]:
    tree = ast.parse(path.read_text(), filename=str(path))
    revision: str | None = None
    down_revision: str | None = None
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            value = ast.literal_eval(node.value)
        except ValueError:
            continue
        if target.id == "revision":
            revision = value
        elif target.id == "down_revision":
            down_revision = value
    return revision, down_revision


def check_graph(migrations_dir: Path) -> MigrationGraphResult:
    files = sorted(migrations_dir.glob("*.py"))
    if not files:
        return MigrationGraphResult(sound=True, root=None, detail="No migration files found.")

    by_file: dict[str, tuple[str | None, str | None]] = {
        path.name: _parse_revision_pair(path) for path in files
    }
    revision_to_file = {rev: name for name, (rev, _down) in by_file.items() if rev is not None}

    down_revision_to_files: dict[str, list[str]] = {}
    roots: list[str] = []
    for name, (_rev, down) in by_file.items():
        if down is None:
            roots.append(name)
        else:
            down_revision_to_files.setdefault(down, []).append(name)

    forks = [
        Fork(down_revision=down, files=sorted(names))
        for down, names in sorted(down_revision_to_files.items())
        if len(names) > 1
    ]

    cycles: list[list[str]] = []
    visited: set[str] = set()
    for name in by_file:
        if name in visited:
            continue
        path_so_far: list[str] = []
        seen_this_walk: set[str] = set()
        current: str | None = name
        while current is not None and current not in visited:
            if current in seen_this_walk:
                cycle_start = path_so_far.index(current)
                cycles.append(sorted(path_so_far[cycle_start:]))
                break
            seen_this_walk.add(current)
            path_so_far.append(current)
            _rev, down = by_file[current]
            current = revision_to_file.get(down) if down is not None else None
        visited.update(path_so_far)

    orphans = sorted(n for n, (_r, d) in by_file.items() if d is not None and d not in revision_to_file)

    detail_parts: list[str] = []
    if orphans:
        detail_parts.append(f"Parent revision missing for: {orphans}.")
    if len(roots) == 0:
        detail_parts.append("No root migration (down_revision = None) found.")
    elif len(roots) > 1:
        detail_parts.append(f"Multiple root migrations found: {sorted(roots)}.")
    if forks:
        detail_parts.append(f"{len(forks)} fork(s) found.")
    if cycles:
        detail_parts.append(f"{len(cycles)} cycle(s) found.")

    sound = len(roots) == 1 and not forks and not cycles and not orphans

    detail = (
        " ".join(detail_parts)
        if detail_parts
        else "The migration chain is a single, linear sequence."
    )
    return MigrationGraphResult(
        sound=sound,
        root=roots[0] if len(roots) == 1 else None,
        forks=forks,
        cycles=cycles,
        detail=detail,
    )
