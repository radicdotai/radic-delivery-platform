"""Pure change-note record construction + schema validation (data-model.md)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema

from radic_delivery.notes import migration_flag
from radic_delivery.notes.pr_body_fields import parse_depends_on, parse_prereqs
from radic_delivery.notes.result import BuildIssue, ChangeNoteBuildResult
from radic_delivery.notes.schema_loader import load_change_note_schema


def _normalise_jira_key(jira_key: str) -> str:
    return "None" if jira_key.strip().lower() == "none" else jira_key


def build_record(
    *,
    repo: str,
    sha: str,
    type: str,
    audience: str,
    title: str,
    summary: str,
    jira_key: str,
    repo_dir: Path,
    base: str,
    head: str,
    legacy_dir: str = "migrations/legacy",
    phase_header_required: bool = True,
    pr_number: int | None = None,
    linked_prs: list[str] | None = None,
    pr_body: str | None = None,
    uat_escape: bool | None = None,
    regression_test_added: bool | None = None,
    author: str | None = None,
    merged_at: str | None = None,
) -> ChangeNoteBuildResult:
    """Build a change-note record from fully-explicit inputs and validate
    it against schemas/change-note.schema.json (research.md D1) before
    reporting success — mirrors descriptor/validator.py's schema-check
    pattern exactly.

    `migration` is always computed from the real diff between `base` and
    `head` (specs/017 research.md D4) — never a free caller-supplied
    value, per Confluence Reference 3 §2 (review comment C4). `prereqs`/
    `depends_on` are likewise always computed, from `pr_body` when
    supplied, never free input (specs/019 research.md D2)."""
    record: dict[str, Any] = {
        "schema_version": 1,
        "repo": repo,
        "sha": sha,
        "type": type,
        "audience": audience,
        "title": title,
        "summary": summary,
        "jira_key": _normalise_jira_key(jira_key),
        "migration": migration_flag.compute(
            repo_dir, base, head, legacy_dir=legacy_dir, phase_header_required=phase_header_required
        ),
        "prereqs": parse_prereqs(pr_body) if pr_body is not None else [],
        "depends_on": parse_depends_on(pr_body) if pr_body is not None else [],
    }
    if pr_number is not None:
        record["pr_number"] = pr_number
    if linked_prs:
        record["linked_prs"] = linked_prs
    if uat_escape is not None:
        record["uat_escape"] = uat_escape
    if regression_test_added is not None:
        record["regression_test_added"] = regression_test_added
    if author is not None:
        record["author"] = author
    if merged_at is not None:
        record["merged_at"] = merged_at

    schema = load_change_note_schema()
    validator = jsonschema.Draft202012Validator(schema)
    issues = [
        BuildIssue(path=".".join(str(p) for p in error.absolute_path) or "(root)", message=error.message)
        for error in sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path))
    ]
    if issues:
        return ChangeNoteBuildResult(ok=False, record=None, issues=issues)
    return ChangeNoteBuildResult(ok=True, record=record, issues=[])
