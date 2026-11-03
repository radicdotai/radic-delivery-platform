"""CLI-level tests for `tests inventory` and `policy rulesets-diff`:
exit codes and --format json|text parity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode

runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "fixtures" / "sample-repos"


# --- tests inventory --------------------------------------------------------


def test_inventory_clean_fixture_exits_ok_json() -> None:
    result = runner.invoke(
        app,
        ["tests", "inventory", "--repo-dir", str(FIXTURES / "python-sample"), "--format", "json"],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["launched"] is True
    assert payload["total"] == 2
    assert payload["passed"] == 2


def test_inventory_invalid_descriptor_exits_invalid_input(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    (repo_dir / ".radic").mkdir(parents=True)
    (repo_dir / ".radic" / "service.yml").write_text("not: a valid descriptor\n")

    result = runner.invoke(
        app, ["tests", "inventory", "--repo-dir", str(repo_dir), "--format", "json"]
    )

    assert result.exit_code == int(ExitCode.INVALID_INPUT)


def test_inventory_missing_descriptor_exits_invalid_input(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["tests", "inventory", "--repo-dir", str(tmp_path / "does-not-exist"), "--format", "json"],
    )

    assert result.exit_code == int(ExitCode.INVALID_INPUT)


def test_inventory_unlaunchable_command_exits_infra_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # A valid descriptor, but an empty PATH means even "uv" itself cannot
    # be resolved — a real, deterministic launch failure (research.md D3).
    monkeypatch.setenv("PATH", "")

    result = runner.invoke(
        app,
        ["tests", "inventory", "--repo-dir", str(FIXTURES / "python-sample"), "--format", "json"],
    )

    assert result.exit_code == int(ExitCode.INFRA_ERROR)
    payload = json.loads(result.stdout)
    assert payload["launched"] is False


def test_inventory_text_format_reports_every_field() -> None:
    result = runner.invoke(
        app, ["tests", "inventory", "--repo-dir", str(FIXTURES / "python-sample")]
    )

    assert result.exit_code == int(ExitCode.OK)
    assert "total" in result.stdout
    assert "quarantined_active" in result.stdout
    assert "within_quarantine_share_cap" in result.stdout


def test_inventory_quarantine_file_option(tmp_path: Path) -> None:
    ledger_path = tmp_path / "quarantine.yml"
    ledger_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "quarantine": [
                    {
                        "service": "sample",
                        "test_id": "tests/test_sample.py::test_add_again",
                        "reason": "flaky",
                        "jira_key": "RAD-9001",
                        "quarantined_since": "2026-10-30",
                    }
                ],
            }
        )
    )

    result = runner.invoke(
        app,
        [
            "tests", "inventory",
            "--repo-dir", str(FIXTURES / "python-sample-broken-skip"),
            "--quarantine-file", str(ledger_path),
            "--as-of", "2026-11-03",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["quarantined_active"] == 1
    assert payload["quarantined_expired"] == 0


def test_inventory_out_option_writes_a_real_file(tmp_path: Path) -> None:
    out_path = tmp_path / "inventory.json"
    result = runner.invoke(
        app,
        [
            "tests", "inventory",
            "--repo-dir", str(FIXTURES / "python-sample"),
            "--out", str(out_path),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    assert out_path.is_file()
    assert json.loads(out_path.read_text())["total"] == 2


# --- policy rulesets-diff ---------------------------------------------------


def _write_ruleset(path: Path, name: str) -> None:
    path.write_text(
        json.dumps(
            {
                "name": name,
                "target": "branch",
                "enforcement": "active",
                "conditions": {},
                "bypass_actors": [],
                "rules": [{"type": "deletion"}],
            }
        )
    )


def test_rulesets_diff_no_drift_exits_ok(tmp_path: Path) -> None:
    committed_dir = tmp_path / "rulesets"
    committed_dir.mkdir()
    _write_ruleset(committed_dir / "dev-trunk.json", "dev-trunk")

    live_file = tmp_path / "live.json"
    live_file.write_text(json.dumps([json.loads((committed_dir / "dev-trunk.json").read_text())]))

    result = runner.invoke(
        app,
        [
            "policy", "rulesets-diff",
            "--repo", "radicdotai/web-bff",
            "--dir", str(committed_dir),
            "--live-file", str(live_file),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["unchanged"] == ["dev-trunk"]


def test_rulesets_diff_with_drift_still_exits_ok(tmp_path: Path) -> None:
    committed_dir = tmp_path / "rulesets"
    committed_dir.mkdir()
    _write_ruleset(committed_dir / "dev-trunk.json", "dev-trunk")

    live_file = tmp_path / "live.json"
    live_file.write_text(json.dumps([]))  # missing from live

    result = runner.invoke(
        app,
        [
            "policy", "rulesets-diff",
            "--repo", "radicdotai/web-bff",
            "--dir", str(committed_dir),
            "--live-file", str(live_file),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["missing_from_live"] == ["dev-trunk"]


def test_rulesets_diff_duplicate_name_exits_invalid_input(tmp_path: Path) -> None:
    committed_dir = tmp_path / "rulesets"
    committed_dir.mkdir()
    _write_ruleset(committed_dir / "a.json", "dev-trunk")
    _write_ruleset(committed_dir / "b.json", "dev-trunk")

    live_file = tmp_path / "live.json"
    live_file.write_text(json.dumps([]))

    result = runner.invoke(
        app,
        [
            "policy", "rulesets-diff",
            "--repo", "radicdotai/web-bff",
            "--dir", str(committed_dir),
            "--live-file", str(live_file),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.INVALID_INPUT)


def test_rulesets_diff_unreadable_live_file_exits_infra_error(tmp_path: Path) -> None:
    committed_dir = tmp_path / "rulesets"
    committed_dir.mkdir()
    _write_ruleset(committed_dir / "dev-trunk.json", "dev-trunk")

    result = runner.invoke(
        app,
        [
            "policy", "rulesets-diff",
            "--repo", "radicdotai/web-bff",
            "--dir", str(committed_dir),
            "--live-file", str(tmp_path / "does-not-exist.json"),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.INFRA_ERROR)


def test_rulesets_diff_text_format_reports_every_category(tmp_path: Path) -> None:
    committed_dir = tmp_path / "rulesets"
    committed_dir.mkdir()
    _write_ruleset(committed_dir / "dev-trunk.json", "dev-trunk")
    live_file = tmp_path / "live.json"
    live_file.write_text(json.dumps([json.loads((committed_dir / "dev-trunk.json").read_text())]))

    result = runner.invoke(
        app,
        [
            "policy", "rulesets-diff",
            "--repo", "radicdotai/web-bff",
            "--dir", str(committed_dir),
            "--live-file", str(live_file),
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    assert "unchanged" in result.stdout
    assert "missing_from_live" in result.stdout
    assert "added_in_live" in result.stdout
