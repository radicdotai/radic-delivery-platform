"""Writes a validated change-note record locally (research.md D4).

The real `gs://radicai-release-records/...` upload is out of scope — this
sandbox has no bucket credentials. `upload_status` is always reported as
`not_available`, never silently omitted or faked as successful.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from radic_delivery.notes.result import WriteResult


def write(record: dict[str, Any], *, repo: str, sha: str, out_dir: Path) -> WriteResult:
    target = out_dir / "change-notes" / repo / f"{sha}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2))
    return WriteResult(local_path=str(target))
