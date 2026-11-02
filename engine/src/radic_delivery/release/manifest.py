"""Pure manifest construction + schema validation (data-model.md)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import jsonschema

from radic_delivery.release.result import ManifestIssue, ProposeResult, Selection
from radic_delivery.release.schema_loader import load_release_manifest_schema


def build_manifest(
    selection: Selection,
    *,
    repo: str,
    base_branch: str,
    base_sha: str,
    release_id: str,
    initiator: str,
    kind: str,
) -> ProposeResult:
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "release_id": release_id,
        "kind": kind,
        "status": "proposed",
        "repo": repo,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "initiator": initiator,
        "base": {"branch": base_branch, "sha": base_sha},
        "selection": {
            "tickets": [ticket.to_dict() for ticket in selection.tickets],
            "held_back": [ticket.to_dict() for ticket in selection.held_back],
            "non_jira_prs": [pr.to_dict() for pr in selection.non_jira_prs],
        },
    }

    schema = load_release_manifest_schema()
    validator = jsonschema.Draft202012Validator(schema)
    issues = [
        ManifestIssue(path=".".join(str(p) for p in error.absolute_path) or "(root)", message=error.message)
        for error in sorted(validator.iter_errors(manifest), key=lambda e: list(e.absolute_path))
    ]
    if issues:
        return ProposeResult(ok=False, manifest=None, issues=issues)
    return ProposeResult(
        ok=True, manifest=manifest, issues=[], non_jira_prs_not_found=selection.non_jira_prs_not_found
    )
