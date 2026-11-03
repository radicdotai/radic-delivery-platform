"""CLI-level tests for `gate evaluate --mode release-gate` and
`migrations check`: exit codes and --format json|text parity."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode

runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "fixtures"
SAMPLE_REPOS = FIXTURES / "sample-repos"
MIGRATIONS_FIXTURES = FIXTURES / "migrations"
ENGINE_ROOT = Path(__file__).parent.parent.parent
DIGEST = "sha256:" + "3" * 64


def _write_stage_record(path: Path, **overrides: dict | str | int) -> None:
    record = {
        "schema_version": 1,
        "repo": "radicdotai/sample",
        "environment": "stage",
        "release_id": "2026.11.03-1",
        "digest": DIGEST,
        "commit": "1" * 40,
        "suite": "e2e-full-stage",
        "runner": "playwright",
        "scope": "full",
        "started_at": "2026-11-03T00:00:00Z",
        "finished_at": "2026-11-03T00:10:00Z",
        "result": "pass",
        "counts": {"total": 10, "passed": 10, "failed": 0, "skipped": 0, "quarantined": 0},
        "skip_budget": {"allowed": 0, "exceptions": []},
        "run_url": "https://github.com/radicdotai/sample/actions/runs/1",
        "cloud_deploy": {
            "pipeline": "sample-rel",
            "release": "r-2026-11-03-1-1111111",
            "rollout": "sample-rel-r-2026-11-03-1-1111111-to-sample-stage-0001",
            "rollout_state": "SUCCEEDED",
            "verify": "pass",
        },
    }
    record.update(overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record))


# --- gate evaluate --mode release-gate --------------------------------------


def test_release_gate_full_pass_exits_ok(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    _write_stage_record(results_dir / "releases" / "2026.11.03-1" / "test-results" / "stage-sample.json")

    result = runner.invoke(
        app,
        [
            "gate", "evaluate", "--mode", "release-gate",
            "--descriptor", str(SAMPLE_REPOS / "python-sample" / ".radic" / "service.yml"),
            "--results-dir", str(results_dir),
            "--digest", DIGEST,
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["overall"] == "pass"


def test_release_gate_missing_record_exits_policy_failure(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "gate", "evaluate", "--mode", "release-gate",
            "--descriptor", str(SAMPLE_REPOS / "python-sample" / ".radic" / "service.yml"),
            "--results-dir", str(results_dir),
            "--digest", DIGEST,
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.POLICY_FAILURE)
    payload = json.loads(result.stdout)
    assert payload["overall"] == "fail"
    stage_check = next(c for c in payload["checks"] if c["name"] == "stage_regression")
    assert stage_check["status"] == "fail"


def test_release_gate_invalid_descriptor_exits_invalid_input() -> None:
    result = runner.invoke(
        app,
        [
            "gate", "evaluate", "--mode", "release-gate",
            "--descriptor", str(FIXTURES / "broken" / "invalid-enum.yml"),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.INVALID_INPUT)


def test_release_gate_text_format_reports_every_check(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    _write_stage_record(results_dir / "releases" / "2026.11.03-1" / "test-results" / "stage-sample.json")

    result = runner.invoke(
        app,
        [
            "gate", "evaluate", "--mode", "release-gate",
            "--descriptor", str(SAMPLE_REPOS / "python-sample" / ".radic" / "service.yml"),
            "--results-dir", str(results_dir),
            "--digest", DIGEST,
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    assert "stage_regression" in result.stdout


# --- migrations check --------------------------------------------------


def test_migrations_check_graph_sound_exits_ok() -> None:
    result = runner.invoke(
        app,
        [
            "migrations", "check",
            "--descriptor", str(MIGRATIONS_FIXTURES / "descriptor.yml"),
            "--migrations-dir", str(MIGRATIONS_FIXTURES / "sound"),
            "--checks", "migration_graph",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["migration_graph"]["sound"] is True


def test_migrations_check_graph_forked_exits_policy_failure() -> None:
    result = runner.invoke(
        app,
        [
            "migrations", "check",
            "--descriptor", str(MIGRATIONS_FIXTURES / "descriptor.yml"),
            "--migrations-dir", str(MIGRATIONS_FIXTURES / "forked"),
            "--checks", "migration_graph",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.POLICY_FAILURE)


def test_migrations_check_frozen_intact_exits_ok() -> None:
    result = runner.invoke(
        app,
        [
            "migrations", "check",
            "--descriptor", str(MIGRATIONS_FIXTURES / "descriptor.yml"),
            "--repo-dir", str(ENGINE_ROOT),
            "--checks", "migrations_frozen",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["migrations_frozen"]["ok"] is True


def test_migrations_check_alembic_check_alone_exits_ok(tmp_path: Path) -> None:
    """A requested-but-not_available check is never a failure on its own
    (Acceptance Scenario 6, research.md D3)."""
    result = runner.invoke(
        app,
        [
            "migrations", "check",
            "--descriptor", str(MIGRATIONS_FIXTURES / "descriptor.yml"),
            "--repo-dir", str(ENGINE_ROOT),
            "--checks", "alembic_check",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["alembic_check"] == "not_available"


def test_migrations_check_not_enabled_exits_ok(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "migrations", "check",
            "--descriptor", str(SAMPLE_REPOS / "python-sample" / ".radic" / "service.yml"),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["enabled"] is False


def test_migrations_check_text_format_reports_every_category() -> None:
    result = runner.invoke(
        app,
        [
            "migrations", "check",
            "--descriptor", str(MIGRATIONS_FIXTURES / "descriptor.yml"),
            "--migrations-dir", str(MIGRATIONS_FIXTURES / "sound"),
            "--checks", "migration_graph",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    assert "migration_graph" in result.stdout
