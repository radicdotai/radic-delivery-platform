"""Real-git-fixture tests for `release/finalise.py`: fast-forward `main`,
tag it, close out the manifest, refusing cleanly on any mismatch
(research.md D3)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from radic_delivery.release.finalise import finalise

REPO = "radicdotai/web-bff"
RELEASE_ID = "2026.11.03-1"


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


def _manifest(*, release_head: str, status: str = "prod-deployed", digests: dict | None = None) -> dict:
    manifest = {
        "schema_version": 1,
        "release_id": RELEASE_ID,
        "kind": "release",
        "status": status,
        "repo": REPO,
        "created_at": "2026-11-03T00:00:00Z",
        "initiator": "alice",
        "base": {"branch": "dev", "sha": "0" * 40},
        "release_branch": f"release/{RELEASE_ID}",
        "release_head": release_head,
        "selection": {"tickets": [], "held_back": [], "non_jira_prs": []},
    }
    if digests is not None:
        manifest["digests"] = digests
    return manifest


_DIGEST = "sha256:" + "0" * 64


def test_valid_prod_deployed_manifest_is_finalised(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}")
    release_head = _write_and_commit(repo, "fix.txt", "fix", "a prod fix")
    _git(repo, "checkout", "-q", "main")

    manifest = _manifest(release_head=release_head)
    result = finalise(manifest, repo_dir=repo, release_id=RELEASE_ID, prod_digest=_DIGEST)

    assert result.ok is True
    assert result.tag == "v1.0.0"
    assert result.manifest["status"] == "finalised"
    assert result.manifest["main"]["fast_forwarded_to"] == release_head
    assert result.manifest["main"]["tag"] == "v1.0.0"
    assert result.manifest["digests"]["prod"] == _DIGEST
    assert _git(repo, "rev-parse", "main") == release_head
    assert _git(repo, "tag", "--list", "v1.0.0") == "v1.0.0"


def test_already_finalised_manifest_is_refused(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}")
    release_head = _write_and_commit(repo, "fix.txt", "fix", "a prod fix")
    _git(repo, "checkout", "-q", "main")
    main_sha_before = _git(repo, "rev-parse", "main")

    manifest = _manifest(release_head=release_head, status="finalised")
    result = finalise(manifest, repo_dir=repo, release_id=RELEASE_ID, prod_digest=_DIGEST)

    assert result.ok is False
    assert result.reason == "status_mismatch"
    assert "finalised" in result.detail
    assert _git(repo, "rev-parse", "main") == main_sha_before


def test_release_not_ahead_of_main_is_refused(repo: Path) -> None:
    root_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side", root_sha)
    side_sha = _write_and_commit(repo, "side.txt", "1", "unrelated side commit")
    _git(repo, "checkout", "-q", "main")
    main_sha_before = _write_and_commit(repo, "main.txt", "1", "main's own, separate commit")

    manifest = _manifest(release_head=side_sha)
    result = finalise(manifest, repo_dir=repo, release_id=RELEASE_ID, prod_digest=_DIGEST)

    assert result.ok is False
    assert result.reason == "not_fast_forward"
    assert _git(repo, "rev-parse", "main") == main_sha_before
    assert _git(repo, "tag", "--list") == ""


def test_unresolvable_release_head_is_refused_as_git_error(repo: Path) -> None:
    manifest = _manifest(release_head="f" * 40)
    result = finalise(manifest, repo_dir=repo, release_id=RELEASE_ID, prod_digest=_DIGEST)

    assert result.ok is False
    assert result.reason == "git_error"


def test_release_id_mismatch_is_refused(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}")
    release_head = _write_and_commit(repo, "fix.txt", "fix", "a prod fix")

    manifest = _manifest(release_head=release_head)
    result = finalise(manifest, repo_dir=repo, release_id="some-other-id", prod_digest=_DIGEST)

    assert result.ok is False
    assert result.reason == "release_id_mismatch"


def test_tag_auto_bump_patch_by_default(repo: Path) -> None:
    _git(repo, "tag", "v1.2.3")
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}")
    release_head = _write_and_commit(repo, "fix.txt", "fix", "a prod fix")
    _git(repo, "checkout", "-q", "main")

    manifest = _manifest(release_head=release_head)
    result = finalise(manifest, repo_dir=repo, release_id=RELEASE_ID, prod_digest=_DIGEST)

    assert result.tag == "v1.2.4"


def test_tag_auto_bump_minor_and_major(repo: Path) -> None:
    _git(repo, "tag", "v1.2.3")
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}")
    release_head = _write_and_commit(repo, "fix.txt", "fix", "a prod fix")
    _git(repo, "checkout", "-q", "main")

    manifest = _manifest(release_head=release_head)
    minor_result = finalise(
        manifest, repo_dir=repo, release_id=RELEASE_ID, prod_digest=_DIGEST, bump="minor"
    )
    assert minor_result.tag == "v1.3.0"


def test_explicit_tag_overrides_auto_bump(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}")
    release_head = _write_and_commit(repo, "fix.txt", "fix", "a prod fix")
    _git(repo, "checkout", "-q", "main")

    manifest = _manifest(release_head=release_head)
    result = finalise(
        manifest, repo_dir=repo, release_id=RELEASE_ID, prod_digest=_DIGEST, tag="v9.9.9"
    )
    assert result.tag == "v9.9.9"


def test_digest_mismatch_against_recorded_digest_is_refused(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}")
    release_head = _write_and_commit(repo, "fix.txt", "fix", "a prod fix")
    _git(repo, "checkout", "-q", "main")

    manifest = _manifest(release_head=release_head, digests={"prod": _DIGEST})
    other_digest = "sha256:" + "1" * 64
    result = finalise(manifest, repo_dir=repo, release_id=RELEASE_ID, prod_digest=other_digest)

    assert result.ok is False
    assert result.reason == "digest_mismatch"


def test_matching_recorded_digest_succeeds(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", f"release/{RELEASE_ID}")
    release_head = _write_and_commit(repo, "fix.txt", "fix", "a prod fix")
    _git(repo, "checkout", "-q", "main")

    manifest = _manifest(release_head=release_head, digests={"prod": _DIGEST})
    result = finalise(manifest, repo_dir=repo, release_id=RELEASE_ID, prod_digest=_DIGEST)

    assert result.ok is True
