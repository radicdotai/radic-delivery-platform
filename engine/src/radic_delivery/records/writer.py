"""Writes a validated test-result record locally, mirroring the real
`releases/<id>/test-results/<environment>-<repo>-<suite>.json` key
structure exactly (research.md D2). A release-less (dev) record is
written under a fixed `dev` segment in place of `<id>`.

The real `radicdotai/delivery-records` upload is out of scope — reported
`not_available` by the caller, never attempted here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write(record: dict[str, Any], *, out_dir: Path) -> str:
    release_segment = record["release_id"] or "dev"
    repo_segment = record["repo"].split("/", 1)[-1]
    filename = f"{record['environment']}-{repo_segment}-{record['suite']}.json"

    target = out_dir / "releases" / release_segment / "test-results" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2))
    return str(target)
