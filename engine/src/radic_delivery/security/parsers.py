"""Parse gitleaks/hadolint/trivy-config JSON output into Findings
(research.md D1 for the verified output shapes, D2 for severity mapping).
"""

from __future__ import annotations

import json
from typing import Any

from radic_delivery.security.result import Finding, Severity

_HADOLINT_LEVEL_TO_SEVERITY: dict[str, Severity] = {
    "error": "high",
    "warning": "medium",
    "info": "low",
    "style": "low",
}

_TRIVY_SEVERITY_TO_SEVERITY: dict[str, Severity] = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "UNKNOWN": "low",
}


def parse_gitleaks(stdout: str) -> list[Finding]:
    """Every gitleaks finding is a secret, so every one is critical
    (research.md D2) — the raw secret value is never included in the
    description (data-model.md's Security note)."""
    entries: list[dict[str, Any]] = json.loads(stdout or "[]")
    return [
        Finding(
            tool="gitleaks",
            severity="critical",
            rule_id=entry["RuleID"],
            file=entry["File"],
            line=entry.get("StartLine"),
            description=entry["Description"],
        )
        for entry in entries
    ]


def parse_hadolint(stdout: str) -> list[Finding]:
    entries: list[dict[str, Any]] = json.loads(stdout or "[]")
    return [
        Finding(
            tool="hadolint",
            severity=_HADOLINT_LEVEL_TO_SEVERITY.get(entry["level"], "low"),
            rule_id=entry["code"],
            file=entry["file"],
            line=entry.get("line"),
            description=entry["message"],
        )
        for entry in entries
    ]


def parse_trivy_config(stdout: str) -> list[Finding]:
    report: dict[str, Any] = json.loads(stdout or "{}")
    findings: list[Finding] = []
    for result in report.get("Results", []):
        target = result.get("Target", "")
        for misconfig in result.get("Misconfigurations", []):
            cause = misconfig.get("CauseMetadata", {})
            findings.append(
                Finding(
                    tool="trivy-config",
                    severity=_TRIVY_SEVERITY_TO_SEVERITY.get(misconfig.get("Severity", "UNKNOWN"), "low"),
                    rule_id=misconfig["ID"],
                    file=target,
                    line=cause.get("StartLine"),
                    description=misconfig["Message"],
                )
            )
    return findings
