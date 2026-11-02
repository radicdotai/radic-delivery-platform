"""Real-git-fixture tests for `release/verify_promotion.py`: ancestry,
tree, tag, each reported independently; the Cloud-Deploy-digest fact
always `not_available` (research.md D1/D2)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from radic_delivery.release.git_history import GitHistoryError
from radic_delivery.release.verify_promotion import verify_promotion

REPO = "radicdotai/web-bff"


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


def _manifest(*, base_sha: str, commit_pairs: list[tuple[str, str]]) -> dict:
    return {
        "schema_version": 1,
        "release_id": "2026.11.03-1",
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
                    "commits": [
                        {"dev_sha": dev_sha, "release_sha": release_sha}
                        for dev_sha, release_sha in commit_pairs
                    ],
                }
            ],
            "held_back": [],
            "non_jira_prs": [],
        },
    }


@pytest.fixture
def scenario(repo: Path) -> dict:
    """A real cherry-picked release: `dev_sha`'s content is preserved
    exactly onto `release_head`, which is a real descendant of `root_sha`.
    `side_sha` shares only the root commit with `release_head` — not an
    ancestor of it."""
    root_sha = _git(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-q", "-b", "dev")
    dev_sha = _write_and_commit(repo, "fix.txt", "fix", "RAD-1234 fix")

    _git(repo, "checkout", "-q", "-b", "release/2026.11.03-1", root_sha)
    assert _git(repo, "cherry-pick", "-x", dev_sha) is not None
    release_head = _git(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-q", "-b", "side", root_sha)
    side_sha = _write_and_commit(repo, "unrelated.txt", "noise", "unrelated side commit")

    _git(repo, "checkout", "-q", "main")

    return {
        "root_sha": root_sha,
        "dev_sha": dev_sha,
        "release_head": release_head,
        "side_sha": side_sha,
    }


def test_all_three_checks_pass_when_everything_matches(repo: Path, scenario: dict) -> None:
    manifest = _manifest(
        base_sha=scenario["root_sha"],
        commit_pairs=[(scenario["dev_sha"], scenario["release_head"])],
    )
    _git(repo, "tag", "build-2026.11.03-1", scenario["release_head"])

    result = verify_promotion(
        manifest,
        repo_dir=repo,
        release_head=scenario["release_head"],
        expected_tag="build-2026.11.03-1",
    )

    assert result.ancestry_verified is True
    assert result.tree_verified is True
    assert result.tag_verified is True
    assert result.ok is True
    assert result.detail == []


def test_ancestry_check_fails_independently(repo: Path, scenario: dict) -> None:
    manifest = _manifest(
        base_sha=scenario["side_sha"],
        commit_pairs=[(scenario["dev_sha"], scenario["release_head"])],
    )
    _git(repo, "tag", "build-2026.11.03-1", scenario["release_head"])

    result = verify_promotion(
        manifest,
        repo_dir=repo,
        release_head=scenario["release_head"],
        expected_tag="build-2026.11.03-1",
    )

    assert result.ancestry_verified is False
    assert result.tree_verified is True
    assert result.tag_verified is True
    assert result.ok is False


def test_tag_check_fails_when_tag_missing(repo: Path, scenario: dict) -> None:
    manifest = _manifest(
        base_sha=scenario["root_sha"],
        commit_pairs=[(scenario["dev_sha"], scenario["release_head"])],
    )

    result = verify_promotion(
        manifest,
        repo_dir=repo,
        release_head=scenario["release_head"],
        expected_tag="no-such-tag",
    )

    assert result.ancestry_verified is True
    assert result.tree_verified is True
    assert result.tag_verified is False
    assert result.ok is False


def test_tag_check_fails_when_tag_points_elsewhere(repo: Path, scenario: dict) -> None:
    manifest = _manifest(
        base_sha=scenario["root_sha"],
        commit_pairs=[(scenario["dev_sha"], scenario["release_head"])],
    )
    _git(repo, "tag", "build-2026.11.03-1", scenario["dev_sha"])

    result = verify_promotion(
        manifest,
        repo_dir=repo,
        release_head=scenario["release_head"],
        expected_tag="build-2026.11.03-1",
    )

    assert result.tag_verified is False
    assert result.ancestry_verified is True
    assert result.tree_verified is True


def test_cloud_deploy_digest_fact_always_not_available(repo: Path, scenario: dict) -> None:
    manifest = _manifest(
        base_sha=scenario["root_sha"],
        commit_pairs=[(scenario["dev_sha"], scenario["release_head"])],
    )
    _git(repo, "tag", "build-2026.11.03-1", scenario["release_head"])

    without_cd_release = verify_promotion(
        manifest, repo_dir=repo, release_head=scenario["release_head"], expected_tag="build-2026.11.03-1"
    )
    with_cd_release = verify_promotion(
        manifest,
        repo_dir=repo,
        release_head=scenario["release_head"],
        expected_tag="build-2026.11.03-1",
        cd_release="some-cd-release-name",
    )

    assert without_cd_release.release_digest_equals_stage_digest == "not_available"
    assert with_cd_release.release_digest_equals_stage_digest == "not_available"


def test_empty_selection_trivially_passes_tree_check(repo: Path, scenario: dict) -> None:
    manifest = _manifest(base_sha=scenario["root_sha"], commit_pairs=[])
    _git(repo, "tag", "build-2026.11.03-1", scenario["release_head"])

    result = verify_promotion(
        manifest, repo_dir=repo, release_head=scenario["release_head"], expected_tag="build-2026.11.03-1"
    )

    assert result.tree_verified is True


def test_unresolvable_commit_raises_git_history_error(repo: Path, scenario: dict) -> None:
    manifest = _manifest(
        base_sha="0" * 40,
        commit_pairs=[(scenario["dev_sha"], scenario["release_head"])],
    )

    with pytest.raises(GitHistoryError):
        verify_promotion(
            manifest, repo_dir=repo, release_head=scenario["release_head"], expected_tag="build-2026.11.03-1"
        )
