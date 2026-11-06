from __future__ import annotations

import json
import subprocess
from typing import Any, Protocol


class GcloudError(RuntimeError):
    pass


class Gcloud(Protocol):
    def json(self, args: list[str]) -> Any: ...

    def text(self, args: list[str]) -> str: ...


class SubprocessGcloud:
    def __init__(self, timeout_seconds: int = 600) -> None:
        self._timeout = timeout_seconds

    def _run(self, argv: list[str]) -> str:
        try:
            result = subprocess.run(
                ["gcloud", *argv], capture_output=True, text=True, check=False, timeout=self._timeout
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
            raise GcloudError(f"gcloud {argv[:3]} could not run: {exc}") from exc
        if result.returncode != 0:
            raise GcloudError(result.stderr.strip() or f"gcloud exited {result.returncode}")
        return result.stdout

    def json(self, args: list[str]) -> Any:
        out = self._run([*args, "--format=json"])
        if not out.strip():
            return None
        try:
            return json.loads(out)
        except json.JSONDecodeError as exc:
            raise GcloudError(f"gcloud {args[:3]} returned unparsable output") from exc

    def text(self, args: list[str]) -> str:
        return self._run(args)
