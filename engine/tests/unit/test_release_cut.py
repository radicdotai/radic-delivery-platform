"""Real-git-fixture tests for release/cut.py's full orchestration:
validation, change-note re-verification, ordering, cherry-picking,
conflict rollback (research.md D1-D7)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from radic_delivery.release.cut import cut

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


def _write_note(notes_dir: Path, sha: str, jira_key: str = "RAD-1234") -> None:
    path = notes_dir / "change-notes" / REPO / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repo": REPO,
                "sha": sha,
                "type": "fix",
                "audience": "customer",
                "title": "A title",
                "summary": "A summary.",
                "jira_key": jira_key,
            }
        )
    )


def _manifest(
    *, release_id: str = "2026.11.03-1", kind: str = "release", status: str = "proposed", shas: list[str]
) -> dict:
    return {
        "schema_version": 1,
        "release_id": release_id,
        "kind": kind,
        "status": status,
        "repo": REPO,
        "created_at": "2026-11-03T00:00:00Z",
        "initiator": "alice",
        "base": {"branch": "dev", "sha": shas[-1] if shas else "0" * 40},
        "selection": {
            "tickets": [
                {"key": "RAD-1234", "origin": "bot-proposal", "commits": [{"dev_sha": sha} for sha in shas]}
            ],
            "held_back": [],
            "non_jira_prs": [],
        },
    }


# --- US1: correct branch + cherry-pick ---------------------------------------


def test_two_commits_cut_successfully_in_order(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    sha_b = _write_and_commit(repo, "b.txt", "2", "second")
    _git(repo, "checkout", "-q", "main")

    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha_a)
    _write_note(notes_dir, sha_b)

    manifest = _manifest(shas=[sha_a, sha_b])
    result = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=False,
    )

    assert result.ok is True
    commits = result.manifest["selection"]["tickets"][0]["commits"]
    assert commits[0]["dev_sha"] == sha_a
    assert commits[1]["dev_sha"] == sha_b
    assert commits[0]["cherry_pick_x"] is True
    assert commits[0]["release_sha"] != sha_a
    assert (repo / "a.txt").read_text() == "1"
    assert (repo / "b.txt").read_text() == "2"


def test_successful_cut_moves_status_and_records_branch(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha_a)

    manifest = _manifest(shas=[sha_a])
    result = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=False,
    )

    assert result.manifest["status"] == "cut"
    assert result.manifest["release_branch"] == "release/2026.11.03-1"
    assert result.manifest["release_head"]


def test_hotfix_manifest_requires_hotfix_flag(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha_a)

    manifest = _manifest(release_id="2026.11.03-1-hf", kind="hotfix", shas=[sha_a])

    mismatched = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1-hf",
        hotfix=False,
        dry_run=False,
    )
    assert mismatched.ok is False
    assert mismatched.reason == "hotfix_mismatch"
    assert mismatched.manifest == manifest

    matched = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1-hf",
        hotfix=True,
        dry_run=False,
    )
    assert matched.ok is True
    assert matched.manifest["release_branch"] == "release/2026.11.03-1-hf"


def test_release_id_mismatch_is_refused(repo: Path, tmp_path: Path) -> None:
    manifest = _manifest(shas=[])
    result = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=tmp_path / "notes",
        release_id="not-the-right-id",
        hotfix=False,
        dry_run=False,
    )
    assert result.ok is False
    assert result.reason == "release_id_mismatch"
    assert result.manifest == manifest


def test_status_mismatch_is_refused(repo: Path, tmp_path: Path) -> None:
    manifest = _manifest(status="cut", shas=[])
    result = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=tmp_path / "notes",
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=False,
    )
    assert result.ok is False
    assert result.reason == "status_mismatch"
    assert "cut" in result.detail


def test_dry_run_changes_nothing(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha_a)

    manifest = _manifest(shas=[sha_a])
    result = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=True,
    )

    assert result.ok is True
    assert result.dry_run is True
    assert result.manifest == manifest
    branches = _git(repo, "branch", "--list", "release/*")
    assert branches == ""


# --- US2: cherry-pick conflict aborts cleanly --------------------------------


def test_cherry_pick_conflict_aborts_cleanly(repo: Path, tmp_path: Path) -> None:
    (repo / "shared.txt").write_text("line1\n")
    _git(repo, "add", "shared.txt")
    _git(repo, "commit", "-q", "-m", "add shared.txt")

    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "shared.txt", "dev change\n", "dev changes shared.txt")
    _git(repo, "checkout", "-q", "main")
    _write_and_commit(repo, "shared.txt", "main change\n", "main changes shared.txt")

    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha_a)
    manifest = _manifest(shas=[sha_a])

    result = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=False,
    )

    assert result.ok is False
    assert result.reason == "cherry_pick_conflict"
    assert result.failed_sha == sha_a
    assert result.manifest == manifest


def test_cherry_pick_conflict_leaves_no_branch_and_restores_head(repo: Path, tmp_path: Path) -> None:
    (repo / "shared.txt").write_text("line1\n")
    _git(repo, "add", "shared.txt")
    _git(repo, "commit", "-q", "-m", "add shared.txt")

    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "shared.txt", "dev change\n", "dev changes shared.txt")
    _git(repo, "checkout", "-q", "main")
    _write_and_commit(repo, "shared.txt", "main change\n", "main changes shared.txt")
    original_head = _git(repo, "rev-parse", "HEAD")
    original_branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")

    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha_a)
    manifest = _manifest(shas=[sha_a])

    cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=False,
    )

    assert _git(repo, "branch", "--list", "release/*") == ""
    assert _git(repo, "status", "--porcelain") == ""
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == original_branch
    assert _git(repo, "rev-parse", "HEAD") == original_head


# --- US3: missing change-note record stops the cut before anything happens --


def test_missing_change_note_record_stops_before_any_branch(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")

    manifest = _manifest(shas=[sha_a])
    result = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=tmp_path / "notes",
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=False,
    )

    assert result.ok is False
    assert result.reason == "missing_change_note"
    assert result.failed_sha == sha_a
    assert result.manifest == manifest
    assert _git(repo, "branch", "--list", "release/*") == ""


def test_present_change_note_records_do_not_block(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha_a)

    manifest = _manifest(shas=[sha_a])
    result = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=False,
    )
    assert result.ok is True


# --- US1 (specs/018): cut-time open-release guard ----------------------------


def _other_manifest(*, release_id: str, repo: str = REPO, status: str) -> dict:
    return {"release_id": release_id, "repo": repo, "status": status}


def _cut_with_others(
    repo: Path, notes_dir: Path, sha: str, *, other_manifests: list[dict] | None
):
    manifest = _manifest(shas=[sha])
    return cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=False,
        other_manifests=other_manifests,
    )


def test_an_open_other_manifest_for_the_same_repo_refuses_before_any_branch(
    repo: Path, tmp_path: Path
) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha_a)

    other = _other_manifest(release_id="2026.11.01-1", status="stage-verified")
    result = _cut_with_others(repo, notes_dir, sha_a, other_manifests=[other])

    assert result.ok is False
    assert result.reason == "release_already_open"
    assert "2026.11.01-1" in result.detail
    assert "stage-verified" in result.detail
    assert _git(repo, "branch", "--list", "release/*") == ""


@pytest.mark.parametrize("status", ["finalised", "aborted", "failed"])
def test_a_closed_other_manifest_does_not_block(repo: Path, tmp_path: Path, status: str) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha_a)

    other = _other_manifest(release_id="2026.11.01-1", status=status)
    result = _cut_with_others(repo, notes_dir, sha_a, other_manifests=[other])

    assert result.ok is True


def test_an_open_other_manifest_for_a_different_repo_does_not_block(
    repo: Path, tmp_path: Path
) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha_a)

    other = _other_manifest(release_id="2026.11.01-1", repo="radicdotai/frontend-v2", status="stage-verified")
    result = _cut_with_others(repo, notes_dir, sha_a, other_manifests=[other])

    assert result.ok is True


@pytest.mark.parametrize("other_manifests", [None, []])
def test_no_other_manifests_is_identical_to_pre_feature_behaviour(
    repo: Path, tmp_path: Path, other_manifests: list[dict] | None
) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha_a)

    result = _cut_with_others(repo, notes_dir, sha_a, other_manifests=other_manifests)
    assert result.ok is True


def test_an_other_manifest_with_the_same_release_id_never_blocks_itself(
    repo: Path, tmp_path: Path
) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha_a = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note(notes_dir, sha_a)

    other = _other_manifest(release_id="2026.11.03-1", status="stage-verified")
    result = _cut_with_others(repo, notes_dir, sha_a, other_manifests=[other])

    assert result.ok is True


# --- US2 (specs/019): Depends-on confirming guard ----------------------------


def _write_note_with_depends_on(notes_dir: Path, sha: str, jira_key: str, depends_on: list[str]) -> None:
    path = notes_dir / "change-notes" / REPO / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "repo": REPO,
                "sha": sha,
                "type": "fix",
                "audience": "customer",
                "title": "A title",
                "summary": "A summary.",
                "jira_key": jira_key,
                "depends_on": depends_on,
            }
        )
    )


def _manifest_with_tickets(tickets: list[dict], *, release_id: str = "2026.11.03-1") -> dict:
    all_shas = [c["dev_sha"] for t in tickets for c in t["commits"]]
    return {
        "schema_version": 1,
        "release_id": release_id,
        "kind": "release",
        "status": "proposed",
        "repo": REPO,
        "created_at": "2026-11-03T00:00:00Z",
        "initiator": "alice",
        "base": {"branch": "dev", "sha": all_shas[-1] if all_shas else "0" * 40},
        "selection": {"tickets": tickets, "held_back": [], "non_jira_prs": []},
    }


def test_unmet_dependency_refuses_before_any_branch(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note_with_depends_on(notes_dir, sha, "RAD-12", depends_on=["RAD-11"])

    manifest = _manifest_with_tickets(
        [{"key": "RAD-12", "origin": "bot-proposal", "commits": [{"dev_sha": sha}]}]
    )
    result = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=False,
    )

    assert result.ok is False
    assert result.reason == "unmet_dependency"
    assert "RAD-12" in result.detail
    assert "RAD-11" in result.detail
    assert _git(repo, "branch", "--list", "release/*") == ""


def test_dependency_already_in_the_selection_does_not_block(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha_11 = _write_and_commit(repo, "a.txt", "1", "first")
    sha_12 = _write_and_commit(repo, "b.txt", "2", "second")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note_with_depends_on(notes_dir, sha_11, "RAD-11", depends_on=[])
    _write_note_with_depends_on(notes_dir, sha_12, "RAD-12", depends_on=["RAD-11"])

    manifest = _manifest_with_tickets(
        [
            {"key": "RAD-11", "origin": "bot-proposal", "commits": [{"dev_sha": sha_11}]},
            {"key": "RAD-12", "origin": "bot-proposal", "commits": [{"dev_sha": sha_12}]},
        ]
    )
    result = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=False,
    )

    assert result.ok is True


def test_dependency_supplied_as_known_prod_ticket_does_not_block(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note_with_depends_on(notes_dir, sha, "RAD-12", depends_on=["RAD-11"])

    manifest = _manifest_with_tickets(
        [{"key": "RAD-12", "origin": "bot-proposal", "commits": [{"dev_sha": sha}]}]
    )
    result = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=False,
        known_prod_tickets=["RAD-11"],
    )

    assert result.ok is True


def test_ticket_depending_on_itself_is_never_unsatisfied(repo: Path, tmp_path: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "dev")
    sha = _write_and_commit(repo, "a.txt", "1", "first")
    _git(repo, "checkout", "-q", "main")
    notes_dir = tmp_path / "notes"
    _write_note_with_depends_on(notes_dir, sha, "RAD-12", depends_on=["RAD-12"])

    manifest = _manifest_with_tickets(
        [{"key": "RAD-12", "origin": "bot-proposal", "commits": [{"dev_sha": sha}]}]
    )
    result = cut(
        manifest,
        repo_dir=repo,
        change_notes_dir=notes_dir,
        release_id="2026.11.03-1",
        hotfix=False,
        dry_run=False,
    )

    assert result.ok is True
