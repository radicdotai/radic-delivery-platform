"""Execute a security ToolInvocation via subprocess, capturing its outcome.

Reuses the same launched/exit_code/stdout/stderr shape as gate/runner.py,
and the same "launch failure is distinct from a nonzero exit" principle
(gitleaks and hadolint both exit non-zero when they find something — that
is a normal outcome here, never a run failure).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from radic_delivery.gate.runner import RunOutcome as RunOutcome
from radic_delivery.security.tools import ToolInvocation


def run(invocation: ToolInvocation, cwd: Path) -> RunOutcome:
    try:
        completed = subprocess.run(
            invocation.argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, PermissionError) as exc:
        return RunOutcome(launched=False, exit_code=None, stdout="", stderr=str(exc))
    return RunOutcome(
        launched=True,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
