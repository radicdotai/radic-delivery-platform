"""Tests for release/render_pr_body.py: every acceptance scenario, the
determinism guarantee, and the deploy-files-changed computation
(research.md D2)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode
from radic_delivery.release.render_pr_body import render

runner = CliRunner()

REPO = "radicdotai/web-bff"
BASE_SHA = "0" * 40


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
    (repo_dir / "README.md").write_text("init\n")
    _git(repo_dir, "add", "README.md")
    _git(repo_dir, "commit", "-q", "-m", "initial")
    return repo_dir


def _write_change_note(change_notes_dir: Path, repo: str, sha: str, *, title: str, type_: str) -> None:
    path = change_notes_dir / "change-notes" / repo / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repo": repo,
                "sha": sha,
                "type": type_,
                "audience": "customer",
                "title": title,
                "summary": "...",
                "jira_key": "RAD-1234",
            }
        )
    )


def _manifest(**overrides: object) -> dict:
    manifest = {
        "schema_version": 1,
        "release_id": "2026.11.03-1",
        "kind": "release",
        "status": "proposed",
        "repo": REPO,
        "created_at": "2026-11-03T00:00:00Z",
        "initiator": "alice",
        "base": {"branch": "dev", "sha": BASE_SHA},
        "selection": {"tickets": [], "held_back": []},
    }
    manifest.update(overrides)
    return manifest


def test_selection_table_lists_tickets_no_non_jira_section(tmp_path: Path) -> None:
    sha = "1" * 40
    _write_change_note(tmp_path, REPO, sha, title="Fix the thing", type_="fix")
    sha2 = "2" * 40
    _write_change_note(tmp_path, REPO, sha2, title="Improve the other thing", type_="improvement")
    manifest = _manifest(
        selection={
            "tickets": [
                {"key": "RAD-1234", "origin": "bot-proposal", "commits": [{"dev_sha": sha}]},
                {"key": "RAD-1250", "origin": "bot-proposal", "commits": [{"dev_sha": sha2}]},
            ],
            "held_back": [],
        }
    )

    result = render(manifest, change_notes_dir=tmp_path, repo_dir=tmp_path, migrations_chain=[])

    assert "RAD-1234" in result.body
    assert "Fix the thing" in result.body
    assert "RAD-1250" in result.body
    assert "Improve the other thing" in result.body
    assert "Released without a Jira key" not in result.body


def test_non_jira_pr_with_missing_reason_shown_and_gate_unsatisfied() -> None:
    manifest = _manifest(
        selection={
            "tickets": [],
            "held_back": [],
            "non_jira_prs": [{"pr": 142, "reason": "MISSING", "commits": [{"dev_sha": "3" * 40}]}],
        }
    )

    result = render(manifest, change_notes_dir=Path("/nonexistent"), repo_dir=Path("."), migrations_chain=[])

    assert "Released without a Jira key" in result.body
    assert "MISSING" in result.body
    gate_line = next(
        line for line in result.body.splitlines() if line.startswith("- [") and "second approver" in line
    )
    assert gate_line.startswith("- [ ]")


def test_held_back_ticket_rendered_with_reason_and_remover() -> None:
    manifest = _manifest(
        selection={
            "tickets": [],
            "held_back": [{"key": "RAD-1260", "reason": "not verified on dev", "removed_by": "alice"}],
        }
    )

    result = render(manifest, change_notes_dir=Path("/nonexistent"), repo_dir=Path("."), migrations_chain=[])

    assert "RAD-1260" in result.body
    assert "not verified on dev" in result.body
    assert "alice" in result.body


def test_release_pr_approved_gate_checked_when_approver_present() -> None:
    manifest = _manifest(approvals={"release_pr": {"number": 42, "approver": "bob"}})

    result = render(manifest, change_notes_dir=Path("/nonexistent"), repo_dir=Path("."), migrations_chain=[])

    gate_line = next(line for line in result.body.splitlines() if "Release PR approved" in line)
    assert gate_line.startswith("- [x]")


def test_release_pr_approval_gate_unchecked_when_absent() -> None:
    manifest = _manifest()

    result = render(manifest, change_notes_dir=Path("/nonexistent"), repo_dir=Path("."), migrations_chain=[])

    gate_line = next(line for line in result.body.splitlines() if "Release PR approved" in line)
    assert gate_line.startswith("- [ ]")


def test_release_gate_and_stage_regression_gates_checked_when_passing() -> None:
    manifest = _manifest(
        gates={"release_gate": {"result": "pass"}, "stage_regression": {"result": "pass"}}
    )

    result = render(manifest, change_notes_dir=Path("/nonexistent"), repo_dir=Path("."), migrations_chain=[])

    release_gate_line = next(line for line in result.body.splitlines() if "release-gate green" in line)
    stage_line = next(line for line in result.body.splitlines() if "Stage full regression record" in line)
    assert release_gate_line.startswith("- [x]")
    assert stage_line.startswith("- [x]")


def test_rendering_is_deterministic() -> None:
    manifest = _manifest(
        selection={
            "tickets": [{"key": "RAD-1234", "origin": "bot-proposal", "commits": [{"dev_sha": "1" * 40}]}],
            "held_back": [],
        }
    )

    first = render(manifest, change_notes_dir=Path("/nonexistent"), repo_dir=Path("."), migrations_chain=[])
    second = render(manifest, change_notes_dir=Path("/nonexistent"), repo_dir=Path("."), migrations_chain=[])

    assert first.body == second.body


def test_empty_selection_renders_table_not_omitted() -> None:
    manifest = _manifest()

    result = render(manifest, change_notes_dir=Path("/nonexistent"), repo_dir=Path("."), migrations_chain=[])

    assert "### Selection (bot proposal, edited by release managers)" in result.body


def test_missing_change_note_renders_unknown_rather_than_raising() -> None:
    manifest = _manifest(
        selection={
            "tickets": [{"key": "RAD-9999", "origin": "bot-proposal", "commits": [{"dev_sha": "9" * 40}]}],
            "held_back": [],
        }
    )

    result = render(manifest, change_notes_dir=Path("/nonexistent"), repo_dir=Path("."), migrations_chain=[])

    assert "RAD-9999 | (unknown) | (unknown)" in result.body


def test_no_release_head_reports_deploy_files_not_determinable() -> None:
    manifest = _manifest()

    result = render(manifest, change_notes_dir=Path("/nonexistent"), repo_dir=Path("."), migrations_chain=[])

    assert result.deploy_files_changed is None
    assert "not yet determinable" in result.body


def test_release_head_with_real_diff_reports_deploy_files_changed(repo: Path) -> None:
    base_sha = _git(repo, "rev-parse", "HEAD")
    (repo / "deploy" / "run").mkdir(parents=True)
    (repo / "deploy" / "run" / "stage.yaml").write_text("a: 1")
    _git(repo, "add", "deploy/run/stage.yaml")
    _git(repo, "commit", "-q", "-m", "touch stage yaml")
    release_head = _git(repo, "rev-parse", "HEAD")

    manifest = _manifest(base={"branch": "dev", "sha": base_sha}, release_head=release_head)

    result = render(manifest, change_notes_dir=Path("/nonexistent"), repo_dir=repo, migrations_chain=[])

    assert result.deploy_files_changed == ["deploy/run/stage.yaml"]
    assert "deploy/run/stage.yaml" in result.body
    assert "yes" in next(line for line in result.body.splitlines() if "Changes to deploy" in line)


def test_migrations_chain_rendered_when_provided() -> None:
    manifest = _manifest()

    result = render(
        manifest, change_notes_dir=Path("/nonexistent"), repo_dir=Path("."), migrations_chain=["0001", "0002"]
    )

    migrations_line = next(line for line in result.body.splitlines() if "Contains migrations" in line)
    assert "yes" in migrations_line
    assert "0001, 0002" in migrations_line


# --- CLI-level tests -----------------------------------------------------


def test_cli_readable_manifest_exits_ok(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()))

    result = runner.invoke(
        app,
        [
            "release", "render-pr-body",
            "--manifest", str(manifest_path),
            "--change-notes-dir", str(tmp_path),
            "--repo-dir", str(tmp_path),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert "## Release" in payload["body"]


def test_cli_unreadable_manifest_exits_invalid_input(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "release", "render-pr-body",
            "--manifest", str(tmp_path / "does-not-exist.json"),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.INVALID_INPUT)


def test_cli_manifest_missing_required_field_exits_invalid_input(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    incomplete = _manifest()
    del incomplete["initiator"]
    manifest_path.write_text(json.dumps(incomplete))

    result = runner.invoke(
        app,
        ["release", "render-pr-body", "--manifest", str(manifest_path), "--format", "json"],
    )

    assert result.exit_code == int(ExitCode.INVALID_INPUT)


def test_cli_text_and_json_formats_report_the_same_body(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()))

    json_result = runner.invoke(
        app,
        [
            "release", "render-pr-body",
            "--manifest", str(manifest_path),
            "--change-notes-dir", str(tmp_path),
            "--repo-dir", str(tmp_path),
            "--format", "json",
        ],
    )
    text_result = runner.invoke(
        app,
        [
            "release", "render-pr-body",
            "--manifest", str(manifest_path),
            "--change-notes-dir", str(tmp_path),
            "--repo-dir", str(tmp_path),
        ],
    )

    payload = json.loads(json_result.stdout)
    assert payload["body"].strip() == text_result.stdout.strip()


def test_cli_out_option_writes_a_real_file(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_manifest()))
    out_path = tmp_path / "body.md"

    result = runner.invoke(
        app,
        [
            "release", "render-pr-body",
            "--manifest", str(manifest_path),
            "--change-notes-dir", str(tmp_path),
            "--repo-dir", str(tmp_path),
            "--out", str(out_path),
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    assert out_path.is_file()
    assert "## Release" in out_path.read_text()
