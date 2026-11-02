"""Real, unmocked filesystem write tests for records/writer.py (research.md D2)."""

from __future__ import annotations

import json
from pathlib import Path

from radic_delivery.records.writer import write


def test_write_mirrors_the_real_path_for_a_release_record(tmp_path: Path) -> None:
    record = {
        "release_id": "2026.11.03-1",
        "environment": "stage",
        "repo": "radicdotai/frontend-v2",
        "suite": "e2e-full-stage",
    }
    local_path = write(record, out_dir=tmp_path)

    expected = (
        tmp_path / "releases" / "2026.11.03-1" / "test-results" / "stage-frontend-v2-e2e-full-stage.json"
    )
    assert Path(local_path) == expected
    assert expected.is_file()
    assert json.loads(expected.read_text()) == record


def test_write_uses_the_dev_segment_for_a_release_less_record(tmp_path: Path) -> None:
    record = {
        "release_id": None,
        "environment": "dev",
        "repo": "radicdotai/web-bff",
        "suite": "unit",
    }
    local_path = write(record, out_dir=tmp_path)

    expected = tmp_path / "releases" / "dev" / "test-results" / "dev-web-bff-unit.json"
    assert Path(local_path) == expected
    assert expected.is_file()
