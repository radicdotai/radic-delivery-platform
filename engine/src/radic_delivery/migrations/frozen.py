"""`migrations check`'s `migrations_frozen`: a faithful local port of
`check_migrations_frozen.py` — confirms every workflow file the
descriptor names as carrying the platform's migration-freeze safeguard
still exists and still contains the expected migration job (research.md
D3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from radic_delivery.migrations.result import FreezeCheck, MigrationFreezeResult


def _job_names(workflow: dict[str, Any]) -> list[str]:
    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, dict):
        return []
    names = []
    for job_id, job in jobs.items():
        if isinstance(job, dict) and "name" in job:
            names.append(job["name"])
        else:
            names.append(job_id)
    return names


def check_frozen(descriptor: dict[str, Any], repo_dir: Path) -> MigrationFreezeResult:
    job_name = descriptor["migrations"]["job_name"]
    checks: list[FreezeCheck] = []

    for relative_path in descriptor["migrations"]["frozen_check_workflow_files"]:
        workflow_path = repo_dir / relative_path
        if not workflow_path.is_file():
            checks.append(
                FreezeCheck(
                    file=relative_path,
                    status="missing",
                    detail=f"'{relative_path}' does not exist under {repo_dir}.",
                )
            )
            continue

        workflow = yaml.safe_load(workflow_path.read_text())
        if job_name in _job_names(workflow):
            checks.append(
                FreezeCheck(file=relative_path, status="intact", detail=f"job '{job_name}' is present.")
            )
        else:
            checks.append(
                FreezeCheck(
                    file=relative_path,
                    status="altered",
                    detail=f"'{relative_path}' no longer contains a job named '{job_name}'.",
                )
            )

    return MigrationFreezeResult(checks=checks)
