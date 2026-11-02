"""Pure candidate-loading tests: a change-notes directory -> list[Candidate]."""

from __future__ import annotations

import json
from pathlib import Path

from radic_delivery.release.candidates import load_candidates

_SHA_A = "1111111111111111111111111111111111111111"
_SHA_B = "2222222222222222222222222222222222222222"
_SHA_C = "3333333333333333333333333333333333333333"


def _write_note(root: Path, repo: str, sha: str, **extra: object) -> None:
    path = root / "change-notes" / repo / f"{sha}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": 1,
        "repo": repo,
        "sha": sha,
        "type": "fix",
        "audience": "customer",
        "title": "A title",
        "summary": "A summary.",
        "jira_key": "RAD-1234",
        **extra,
    }
    path.write_text(json.dumps(record))


def test_loads_only_records_for_the_requested_repo(tmp_path: Path) -> None:
    _write_note(tmp_path, "radicdotai/web-bff", _SHA_A)
    _write_note(tmp_path, "radicdotai/frontend-v2", _SHA_B)

    candidates, issues = load_candidates(tmp_path, "radicdotai/web-bff")

    assert issues == []
    assert len(candidates) == 1
    assert candidates[0].sha == _SHA_A
    assert candidates[0].jira_key == "RAD-1234"


def test_pr_number_and_title_are_carried_through(tmp_path: Path) -> None:
    _write_note(tmp_path, "radicdotai/web-bff", _SHA_A, pr_number=142, title="Bump the thing")

    candidates, _ = load_candidates(tmp_path, "radicdotai/web-bff")
    assert candidates[0].pr_number == 142
    assert candidates[0].title == "Bump the thing"


def test_no_matching_records_returns_an_empty_list(tmp_path: Path) -> None:
    candidates, issues = load_candidates(tmp_path, "radicdotai/web-bff")
    assert candidates == []
    assert issues == []


def test_malformed_record_is_reported_not_raised(tmp_path: Path) -> None:
    path = tmp_path / "change-notes" / "radicdotai" / "web-bff" / f"{_SHA_C}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json")

    candidates, issues = load_candidates(tmp_path, "radicdotai/web-bff")
    assert candidates == []
    assert len(issues) == 1
    assert str(path) == issues[0].path
