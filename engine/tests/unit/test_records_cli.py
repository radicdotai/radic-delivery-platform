"""CLI-level tests for `radic-delivery records put-test-result`."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode

runner = CliRunner()

_VALID_STAGE_RECORD = {
    "schema_version": 1,
    "repo": "radicdotai/frontend-v2",
    "environment": "stage",
    "release_id": "2026.11.03-1",
    "digest": "sha256:" + "0" * 64,
    "commit": "1" * 40,
    "suite": "e2e-full-stage",
    "runner": "playwright",
    "scope": "full",
    "started_at": "2026-11-03T09:12:04Z",
    "finished_at": "2026-11-03T09:38:51Z",
    "result": "pass",
    "counts": {"total": 14, "passed": 14, "failed": 0, "skipped": 0, "quarantined": 0},
    "skip_budget": {"allowed": 0, "exceptions": []},
    "run_url": "https://github.com/radicdotai/frontend-v2/actions/runs/1",
    "cloud_deploy": {
        "pipeline": "frontend-rel",
        "release": "r-2026-11-03-1-1111111",
        "rollout": "frontend-rel-r-2026-11-03-1-1111111-to-frontend-stage-0001",
        "rollout_state": "SUCCEEDED",
        "verify": "pass",
    },
}


def _write_file(tmp_path: Path, name: str, record: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(record))
    return path


def test_valid_record_exits_ok_and_writes_a_real_file(tmp_path: Path) -> None:
    record_file = _write_file(tmp_path, "record.json", _VALID_STAGE_RECORD)
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "records", "put-test-result",
            "--file", str(record_file),
            "--release-id", "2026.11.03-1",
            "--out-dir", str(out_dir),
            "--format", "json",
        ],
    )
    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["result"] == "pass"
    assert payload["upload_status"] == "not_available"
    assert Path(payload["local_path"]).is_file()


def test_skip_budget_violation_exits_invalid_input_and_writes_nothing(tmp_path: Path) -> None:
    record = copy.deepcopy(_VALID_STAGE_RECORD)
    record["counts"]["skipped"] = 1
    record["result"] = "pass"
    record_file = _write_file(tmp_path, "record.json", record)
    out_dir = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "records", "put-test-result",
            "--file", str(record_file),
            "--release-id", "2026.11.03-1",
            "--out-dir", str(out_dir),
            "--format", "json",
        ],
    )
    assert result.exit_code == int(ExitCode.INVALID_INPUT)
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert not out_dir.exists() or not any(out_dir.rglob("*.json"))


def test_stage_record_missing_scope_exits_invalid_input(tmp_path: Path) -> None:
    record = copy.deepcopy(_VALID_STAGE_RECORD)
    del record["scope"]
    record_file = _write_file(tmp_path, "record.json", record)

    result = runner.invoke(
        app,
        [
            "records", "put-test-result",
            "--file", str(record_file),
            "--release-id", "2026.11.03-1",
            "--out-dir", str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == int(ExitCode.INVALID_INPUT)


def test_release_id_mismatch_exits_invalid_input(tmp_path: Path) -> None:
    record_file = _write_file(tmp_path, "record.json", _VALID_STAGE_RECORD)

    result = runner.invoke(
        app,
        [
            "records", "put-test-result",
            "--file", str(record_file),
            "--release-id", "2099.01.01-9",
            "--out-dir", str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == int(ExitCode.INVALID_INPUT)
