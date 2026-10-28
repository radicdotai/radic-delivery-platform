"""Execute a ToolInvocation via subprocess, capturing its outcome.

Distinguishes "the tool could not be launched at all" (not_executable) from
"the tool ran and reported a result via its exit code" — a launch failure
(e.g. FileNotFoundError when the executable isn't on PATH) must never be
mistaken for the tool having run and found a problem (spec FR-010).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from radic_delivery.gate.commands import ToolInvocation


@dataclass(frozen=True)
class RunOutcome:
    launched: bool
    exit_code: int | None
    stdout: str
    stderr: str


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
