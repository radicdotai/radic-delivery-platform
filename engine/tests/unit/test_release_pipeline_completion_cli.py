"""CLI-level tests for `release verify-promotion`, `release finalise`,
and `rollback plan`: exit codes and --format json|text parity."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from radic_delivery.cli import app
from radic_delivery.exit_codes import ExitCode

runner = CliRunner()
REPO = "radicdotai/web-bff"
RELEASE_ID = "2026.11.03-1"
_DIGEST = "sha256:" + "0" * 64


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


def _write_and_commit(repo_dir: Path, filename: str, content: str, message: str) -> str:
    (repo_dir / filename).write_text(content)
    _git(repo_dir, "add", filename)
    _git(repo_dir, "commit", "-q", "-m", message)
    return _git(repo_dir, "rev-parse", "HEAD")


def _write_manifest(tmp_path: Path, manifest: dict) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


# --- release verify-promotion --------------------------------------------


def _verify_promotion_manifest(*, base_sha: str, dev_sha: str, release_sha: str) -> dict:
    return {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "kind": "release",
        "status": "stage-deployed",
        "repo": REPO,
        "created_at": "2026-11-03T00:00:00Z",
        "initiator": "alice",
        "base": {"branch": "dev", "sha": base_sha},
        "selection": {
            "tickets": [
                {
                    "key": "RAD-1234",
                    "origin": "bot-proposal",
                    "commits": [{"dev_sha": dev_sha, "release_sha": release_sha}],
                }
            ],
            "held_back": [],
            "non_jira_prs": [],
        },
    }


def test_verify_promotion_full_pass_exits_ok(repo: Path, tmp_path: Path) -> None:
    root_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "dev")
    dev_sha = _write_and_commit(repo, "fix.txt", "fix", "RAD-1234 fix")
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}", root_sha)
    _git(repo, "cherry-pick", "-x", dev_sha)
    release_head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "tag", "build-" + RELEASE_ID, release_head)

    manifest_path = _write_manifest(
        tmp_path, _verify_promotion_manifest(base_sha=root_sha, dev_sha=dev_sha, release_sha=release_head)
    )

    result = runner.invoke(
        app,
        [
            "release", "verify-promotion",
            "--manifest", str(manifest_path),
            "--repo-dir", str(repo),
            "--release-head", release_head,
            "--expected-tag", "build-" + RELEASE_ID,
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["ancestry_verified"] is True
    assert payload["tree_verified"] is True
    assert payload["tag_verified"] is True
    assert payload["release_digest_equals_stage_digest"] == "not_available"


def test_verify_promotion_failing_check_exits_policy_failure(repo: Path, tmp_path: Path) -> None:
    root_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "dev")
    dev_sha = _write_and_commit(repo, "fix.txt", "fix", "RAD-1234 fix")
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}", root_sha)
    _git(repo, "cherry-pick", "-x", dev_sha)
    release_head = _git(repo, "rev-parse", "HEAD")

    manifest_path = _write_manifest(
        tmp_path, _verify_promotion_manifest(base_sha=root_sha, dev_sha=dev_sha, release_sha=release_head)
    )

    result = runner.invoke(
        app,
        [
            "release", "verify-promotion",
            "--manifest", str(manifest_path),
            "--repo-dir", str(repo),
            "--release-head", release_head,
            "--expected-tag", "no-such-tag",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.POLICY_FAILURE)
    payload = json.loads(result.stdout)
    assert payload["tag_verified"] is False


def test_verify_promotion_unresolvable_commit_exits_infra_error(repo: Path, tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path, _verify_promotion_manifest(base_sha="0" * 40, dev_sha="1" * 40, release_sha="2" * 40)
    )

    result = runner.invoke(
        app,
        [
            "release", "verify-promotion",
            "--manifest", str(manifest_path),
            "--repo-dir", str(repo),
            "--release-head", "f" * 40,
            "--expected-tag", "whatever",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.INFRA_ERROR)


def test_verify_promotion_text_format_reports_all_four_facts(repo: Path, tmp_path: Path) -> None:
    root_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "dev")
    dev_sha = _write_and_commit(repo, "fix.txt", "fix", "RAD-1234 fix")
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}", root_sha)
    _git(repo, "cherry-pick", "-x", dev_sha)
    release_head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "tag", "build-" + RELEASE_ID, release_head)

    manifest_path = _write_manifest(
        tmp_path, _verify_promotion_manifest(base_sha=root_sha, dev_sha=dev_sha, release_sha=release_head)
    )

    result = runner.invoke(
        app,
        [
            "release", "verify-promotion",
            "--manifest", str(manifest_path),
            "--repo-dir", str(repo),
            "--release-head", release_head,
            "--expected-tag", "build-" + RELEASE_ID,
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    assert "ancestry_verified" in result.stdout
    assert "tree_verified" in result.stdout
    assert "tag_verified" in result.stdout
    assert "release_digest_equals_stage_digest" in result.stdout


# --- release finalise -----------------------------------------------------


def _finalise_manifest(*, release_head: str) -> dict:
    return {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "kind": "release",
        "status": "prod-deployed",
        "repo": REPO,
        "created_at": "2026-11-03T00:00:00Z",
        "initiator": "alice",
        "base": {"branch": "dev", "sha": "0" * 40},
        "release_branch": f"release/{RELEASE_ID}",
        "release_head": release_head,
        "selection": {"tickets": [], "held_back": [], "non_jira_prs": []},
    }


def test_finalise_success_exits_ok(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}")
    release_head = _write_and_commit(repo, "fix.txt", "fix", "a prod fix")
    _git(repo, "checkout", "-q", "main")

    manifest_path = _write_manifest(tmp_path, _finalise_manifest(release_head=release_head))

    result = runner.invoke(
        app,
        [
            "release", "finalise",
            "--manifest", str(manifest_path),
            "--release-id", RELEASE_ID,
            "--prod-digest", _DIGEST,
            "--repo-dir", str(repo),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["tag"] == "v1.0.0"
    assert manifest_path.read_text() != ""
    assert json.loads(manifest_path.read_text())["status"] == "finalised"


def test_finalise_status_mismatch_exits_invalid_input(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}")
    release_head = _write_and_commit(repo, "fix.txt", "fix", "a prod fix")
    _git(repo, "checkout", "-q", "main")

    manifest = _finalise_manifest(release_head=release_head)
    manifest["status"] = "finalised"
    manifest_path = _write_manifest(tmp_path, manifest)

    result = runner.invoke(
        app,
        [
            "release", "finalise",
            "--manifest", str(manifest_path),
            "--release-id", RELEASE_ID,
            "--prod-digest", _DIGEST,
            "--repo-dir", str(repo),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.INVALID_INPUT)
    payload = json.loads(result.stdout)
    assert payload["reason"] == "status_mismatch"


def test_finalise_non_fast_forward_exits_infra_error(repo: Path, tmp_path: Path) -> None:
    root_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side", root_sha)
    side_sha = _write_and_commit(repo, "side.txt", "1", "unrelated side commit")
    _git(repo, "checkout", "-q", "main")
    _write_and_commit(repo, "main.txt", "1", "main's own, separate commit")

    manifest_path = _write_manifest(tmp_path, _finalise_manifest(release_head=side_sha))

    result = runner.invoke(
        app,
        [
            "release", "finalise",
            "--manifest", str(manifest_path),
            "--release-id", RELEASE_ID,
            "--prod-digest", _DIGEST,
            "--repo-dir", str(repo),
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.INFRA_ERROR)


# --- rollback plan ---------------------------------------------------------


def test_rollback_plan_always_exits_ok_json() -> None:
    result = runner.invoke(
        app,
        [
            "rollback", "plan",
            "--env", "prod",
            "--current-release", "r-2026-11-03-1-4444444",
            "--current-digest", "sha256:" + "3" * 64,
            "--target-release", "r-2026-10-20-1-aaaaaaa",
            "--target-digest", "sha256:" + "4" * 64,
            "--estimated-minutes", "6",
            "--format", "json",
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    payload = json.loads(result.stdout)
    assert payload["environment"] == "prod"
    assert payload["estimated_minutes"] == 6
    assert payload["no_op"] is False


def test_rollback_plan_always_exits_ok_text() -> None:
    result = runner.invoke(
        app,
        [
            "rollback", "plan",
            "--env", "prod",
            "--current-release", "r-A",
            "--current-digest", "sha256:" + "1" * 64,
            "--target-release", "r-A",
            "--target-digest", "sha256:" + "1" * 64,
        ],
    )

    assert result.exit_code == int(ExitCode.OK)
    assert "no_op: true" in result.stdout
