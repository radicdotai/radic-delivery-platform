"""Real-git-fixture tests for notes/migration_flag.py (spec.md Acceptance
Scenarios 1-6, Edge Cases)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from radic_delivery.notes.migration_flag import compute

CONTRACT_MARKER = "# phase: contract"


def _git(repo_dir: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo_dir, capture_output=True, text=True, check=True)
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _git(repo_dir, "init", "-q", "-b", "main")
    _git(repo_dir, "config", "user.email", "test@example.com")
    _git(repo_dir, "config", "user.name", "Test")
    (repo_dir / "migrations" / "versions").mkdir(parents=True)
    (repo_dir / "migrations" / "legacy").mkdir(parents=True)
    (repo_dir / "README.md").write_text("init\n")
    _git(repo_dir, "add", "-A")
    _git(repo_dir, "commit", "-q", "-m", "initial")
    return repo_dir


def _write_and_commit(repo_dir: Path, filename: str, content: str, message: str) -> str:
    path = repo_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo_dir, "add", "-A")
    _git(repo_dir, "commit", "-q", "-m", message)
    return _git(repo_dir, "rev-parse", "HEAD")


def test_no_migration_file_added_computes_none(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    head = _write_and_commit(repo, "README.md", "init\nmore\n", "unrelated change")
    assert compute(repo, base, head) == "none"


def test_expand_phase_migration_computes_expand(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    head = _write_and_commit(
        repo, "migrations/versions/0001_expand.py", 'revision = "0001"\ndown_revision = None\n', "add expand"
    )
    assert compute(repo, base, head) == "expand"


def test_contract_phase_migration_computes_contract(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    head = _write_and_commit(
        repo,
        "migrations/versions/0002_contract.py",
        f'{CONTRACT_MARKER}\nrevision = "0002"\ndown_revision = "0001"\n',
        "add contract",
    )
    assert compute(repo, base, head) == "contract"


def test_legacy_dir_migration_is_excluded_entirely(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    head = _write_and_commit(
        repo,
        "migrations/legacy/0099_old.py",
        f'{CONTRACT_MARKER}\nrevision = "0099"\n',
        "add legacy-dir file",
    )
    assert compute(repo, base, head) == "none"


def test_mixed_expand_and_contract_in_one_diff_computes_contract(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "migrations/versions/0001_expand.py").write_text('revision = "0001"\ndown_revision = None\n')
    (repo / "migrations/versions/0002_contract.py").write_text(
        f'{CONTRACT_MARKER}\nrevision = "0002"\ndown_revision = "0001"\n'
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "mixed migration PR")
    head = _git(repo, "rev-parse", "HEAD")
    assert compute(repo, base, head) == "contract"


def test_phase_header_not_required_always_yields_expand(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    head = _write_and_commit(
        repo,
        "migrations/versions/0002_contract.py",
        f'{CONTRACT_MARKER}\nrevision = "0002"\n',
        "add contract-marked file",
    )
    assert compute(repo, base, head, phase_header_required=False) == "expand"


def test_modified_not_added_migration_file_is_not_a_qualifying_addition(repo: Path) -> None:
    _write_and_commit(
        repo, "migrations/versions/0001_expand.py", 'revision = "0001"\ndown_revision = None\n', "add expand"
    )
    base = _git(repo, "rev-parse", "HEAD")
    head = _write_and_commit(
        repo,
        "migrations/versions/0001_expand.py",
        'revision = "0001"\ndown_revision = None\n# a trailing comment\n',
        "modify expand (not an addition)",
    )
    assert compute(repo, base, head) == "none"


def test_contract_marker_after_a_leading_docstring_is_not_detected(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    head = _write_and_commit(
        repo,
        "migrations/versions/0003_docstring.py",
        f'"""Add a widgets table."""\n{CONTRACT_MARKER}\nrevision = "0003"\n',
        "add migration with a leading docstring before the marker",
    )
    assert compute(repo, base, head) == "expand"
