"""Real, unmocked filesystem write tests for notes/writer.py."""

from __future__ import annotations

import json
from pathlib import Path

from radic_delivery.notes.writer import write

_SHA_A = "2222222222222222222222222222222222222222"
_SHA_B = "3333333333333333333333333333333333333333"
_SHA_C = "4444444444444444444444444444444444444444"


def test_write_creates_the_expected_local_path_and_content(tmp_path: Path) -> None:
    record = {"schema_version": 1, "repo": "radicdotai/web-bff", "sha": _SHA_A}
    result = write(record, repo="radicdotai/web-bff", sha=_SHA_A, out_dir=tmp_path)

    expected_path = tmp_path / "change-notes" / "radicdotai" / "web-bff" / f"{_SHA_A}.json"
    assert Path(result.local_path) == expected_path
    assert expected_path.is_file()
    assert json.loads(expected_path.read_text()) == record


def test_write_always_reports_upload_not_available(tmp_path: Path) -> None:
    record = {"schema_version": 1}
    result = write(record, repo="radicdotai/web-bff", sha=_SHA_B, out_dir=tmp_path)
    assert result.upload_status == "not_available"


def test_write_creates_missing_parent_directories(tmp_path: Path) -> None:
    out_dir = tmp_path / "does" / "not" / "exist" / "yet"
    record = {"schema_version": 1}
    result = write(record, repo="radicdotai/frontend-v2", sha=_SHA_C, out_dir=out_dir)
    assert Path(result.local_path).is_file()
