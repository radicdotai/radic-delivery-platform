"""Tests for migrations/graph.py: Alembic-style migration-chain
soundness checking against this feature's own real fixture directories
(research.md D3, D5)."""

from __future__ import annotations

from pathlib import Path

from radic_delivery.migrations.graph import check_graph

FIXTURES = Path(__file__).parent.parent / "fixtures" / "migrations"


def test_sound_chain_reports_sound_with_correct_root() -> None:
    result = check_graph(FIXTURES / "sound")

    assert result.sound is True
    assert result.root == "0001_initial.py"
    assert result.forks == []
    assert result.cycles == []


def test_forked_chain_reports_fork_naming_both_files() -> None:
    result = check_graph(FIXTURES / "forked")

    assert result.sound is False
    assert len(result.forks) == 1
    assert result.forks[0].down_revision == "0001"
    assert result.forks[0].files == ["0002a_branch_a.py", "0002b_branch_b.py"]
    assert result.cycles == []


def test_cyclical_chain_reports_a_cycle() -> None:
    result = check_graph(FIXTURES / "cyclical")

    assert result.sound is False
    assert result.forks == []
    assert len(result.cycles) == 1
    assert set(result.cycles[0]) == {"0001_a.py", "0002_b.py"}


def test_empty_directory_is_trivially_sound(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = check_graph(empty_dir)

    assert result.sound is True
    assert result.root is None
