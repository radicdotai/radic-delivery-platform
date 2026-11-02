"""Load candidate change-note records from a local directory (research.md D3).

Reads the exact local layout `notes write --out-dir` already produces
(specs/007): `<change_notes_dir>/change-notes/<repo>/<sha>.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

from radic_delivery.release.result import Candidate, ManifestIssue


def load_candidates(change_notes_dir: Path, repo: str) -> tuple[list[Candidate], list[ManifestIssue]]:
    repo_dir = change_notes_dir / "change-notes" / repo
    if not repo_dir.is_dir():
        return [], []

    candidates: list[Candidate] = []
    issues: list[ManifestIssue] = []
    for path in sorted(repo_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            issues.append(ManifestIssue(path=str(path), message=f"Not valid JSON: {exc}"))
            continue

        if record.get("repo") != repo:
            continue

        candidates.append(
            Candidate(
                sha=record["sha"],
                jira_key=record["jira_key"],
                pr_number=record.get("pr_number"),
                title=record.get("title", ""),
            )
        )
    return candidates, issues
