"""Pure construction+validation tests: explicit fields -> ChangeNoteBuildResult."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from radic_delivery.notes.builder import build_record


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


def _valid_kwargs(repo_dir: Path) -> dict:
    base = _git(repo_dir, "rev-parse", "HEAD")
    (repo_dir / "migrations" / "versions").mkdir(parents=True, exist_ok=True)
    (repo_dir / "migrations/versions/0001_expand.py").write_text('revision = "0001"\n')
    _git(repo_dir, "add", "-A")
    _git(repo_dir, "commit", "-q", "-m", "add expand migration")
    head = _git(repo_dir, "rev-parse", "HEAD")
    return {
        "repo": "radicdotai/web-bff",
        "sha": "2222222222222222222222222222222222222222",
        "pr_number": 123,
        "type": "fix",
        "audience": "customer",
        "title": "Return a clear error when the upstream is unavailable",
        "summary": "The BFF now answers 503 with a retry hint instead of a generic 500.",
        "jira_key": "RAD-1234",
        "repo_dir": repo_dir,
        "base": base,
        "head": head,
    }


def test_complete_valid_inputs_build_a_schema_valid_record(repo: Path) -> None:
    result = build_record(**_valid_kwargs(repo))
    assert result.ok is True
    assert result.issues == []
    assert result.record is not None
    assert result.record["schema_version"] == 1
    assert result.record["repo"] == "radicdotai/web-bff"
    assert result.record["jira_key"] == "RAD-1234"


@pytest.mark.parametrize("jira_key", ["None", "none", "NONE", "NoNe"])
def test_explicit_none_jira_key_is_accepted_and_normalised(repo: Path, jira_key: str) -> None:
    kwargs = {**_valid_kwargs(repo), "jira_key": jira_key}
    result = build_record(**kwargs)
    assert result.ok is True
    assert result.record is not None
    assert result.record["jira_key"] == "None"


def test_invalid_type_is_rejected_naming_the_field(repo: Path) -> None:
    kwargs = {**_valid_kwargs(repo), "type": "not-a-real-type"}
    result = build_record(**kwargs)
    assert result.ok is False
    assert result.record is None
    assert any("type" in issue.path for issue in result.issues)


def test_empty_title_is_rejected(repo: Path) -> None:
    kwargs = {**_valid_kwargs(repo), "title": "x"}
    result = build_record(**kwargs)
    assert result.ok is False
    assert any("title" in issue.path for issue in result.issues)


def test_jira_key_matching_neither_pattern_nor_none_is_rejected(repo: Path) -> None:
    kwargs = {**_valid_kwargs(repo), "jira_key": "not-a-ticket"}
    result = build_record(**kwargs)
    assert result.ok is False
    assert any("jira_key" in issue.path for issue in result.issues)


def test_missing_required_field_is_rejected(repo: Path) -> None:
    kwargs = _valid_kwargs(repo)
    kwargs["summary"] = ""
    result = build_record(**kwargs)
    assert result.ok is False
    assert any("summary" in issue.path for issue in result.issues)


def test_migration_is_always_computed_from_the_real_diff(repo: Path) -> None:
    result = build_record(
        **_valid_kwargs(repo),
        linked_prs=["radicdotai/frontend-v2#456"],
        uat_escape=True,
        regression_test_added=True,
        author="example-user",
        merged_at="2026-11-02T14:03:11Z",
    )
    assert result.ok is True
    assert result.record is not None
    assert result.record["linked_prs"] == ["radicdotai/frontend-v2#456"]
    # _valid_kwargs' fixture diff adds migrations/versions/0001_expand.py.
    assert result.record["migration"] == "expand"
    assert result.record["author"] == "example-user"


def test_pr_body_populates_prereqs_and_depends_on(repo: Path) -> None:
    pr_body = "Prereqs:\n- [x] flag created\n\nDepends-on: RAD-11\n"
    result = build_record(**_valid_kwargs(repo), pr_body=pr_body)
    assert result.ok is True
    assert result.record is not None
    assert result.record["prereqs"] == [{"item": "flag created", "done": True}]
    assert result.record["depends_on"] == ["RAD-11"]


def test_omitted_pr_body_leaves_prereqs_and_depends_on_empty(repo: Path) -> None:
    result = build_record(**_valid_kwargs(repo))
    assert result.ok is True
    assert result.record is not None
    assert result.record["prereqs"] == []
    assert result.record["depends_on"] == []


def test_invalid_linked_pr_reference_is_rejected(repo: Path) -> None:
    kwargs = {**_valid_kwargs(repo), "linked_prs": ["456"]}
    result = build_record(**kwargs)
    assert result.ok is False
    assert any("linked_prs" in issue.path for issue in result.issues)
