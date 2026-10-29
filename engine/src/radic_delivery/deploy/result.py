"""ManifestCheck/DeployLintResult (data-model.md).

Unlike GateResult (gate/result.py) or SecurityScanResult
(security/result.py), there is no report-only concept here: a manifest
Cloud Deploy applies as-is being wrong is simply wrong (spec FR-007's
"binary correctness check", not an advisory scan).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Rule = Literal["image_placeholder", "no_traffic_key", "startup_probe", "no_inline_secret", "parity"]
CheckStatus = Literal["pass", "fail", "missing_file", "parse_error", "not_applicable"]


@dataclass(frozen=True)
class ManifestCheck:
    deployable: str
    rule: Rule
    status: CheckStatus
    file: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployable": self.deployable,
            "rule": self.rule,
            "status": self.status,
            "file": self.file,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DeployLintResult:
    checks: list[ManifestCheck] = field(default_factory=list)

    @property
    def overall(self) -> Literal["pass", "fail"]:
        if all(c.status in ("pass", "not_applicable") for c in self.checks):
            return "pass"
        return "fail"

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "checks": [c.to_dict() for c in self.checks],
        }
