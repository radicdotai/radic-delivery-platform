"""Parser tests against captured sample tool JSON output (research.md D1/D2).

No subprocess is invoked here — these are the exact JSON shapes confirmed
by running the real tools during research (research.md D1).
"""

from __future__ import annotations

import json

from radic_delivery.security.parsers import parse_gitleaks, parse_hadolint, parse_trivy_config

_GITLEAKS_SAMPLE = json.dumps(
    [
        {
            "RuleID": "aws-access-token",
            "Description": "Identified a pattern that may indicate AWS credentials.",
            "StartLine": 6,
            "File": "src/sample/_legacy_config.py",
            "Secret": "AKIAABCDEFGHIJKLMNOP",
            "Fingerprint": "src/sample/_legacy_config.py:aws-access-token:6",
        }
    ]
)

_HADOLINT_SAMPLE = json.dumps(
    [
        {
            "code": "DL3013",
            "file": "Dockerfile",
            "level": "warning",
            "line": 2,
            "message": "Pin versions in pip.",
        },
        {
            "code": "DL3020",
            "file": "Dockerfile",
            "level": "error",
            "line": 4,
            "message": "Use COPY instead of ADD.",
        },
        {
            "code": "DL3066",
            "file": "Dockerfile",
            "level": "info",
            "line": 3,
            "message": "Non-numeric user id.",
        },
    ]
)

_TRIVY_SAMPLE = json.dumps(
    {
        "Results": [
            {
                "Target": "Dockerfile",
                "Misconfigurations": [
                    {
                        "ID": "DS-0002",
                        "Severity": "HIGH",
                        "Message": "Last USER command in Dockerfile should not be 'root'",
                        "CauseMetadata": {"StartLine": 3},
                    },
                    {
                        "ID": "DS-0005",
                        "Severity": "LOW",
                        "Message": "Consider using COPY instead of ADD",
                        "CauseMetadata": {"StartLine": 4},
                    },
                ],
            }
        ]
    }
)


def test_parse_gitleaks_every_finding_is_critical() -> None:
    findings = parse_gitleaks(_GITLEAKS_SAMPLE)
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert findings[0].tool == "gitleaks"
    assert findings[0].rule_id == "aws-access-token"
    assert findings[0].file == "src/sample/_legacy_config.py"
    assert findings[0].line == 6


def test_parse_gitleaks_never_includes_the_raw_secret_value() -> None:
    """data-model.md's Security note: the Secret field must never leak into
    a Finding's description."""
    findings = parse_gitleaks(_GITLEAKS_SAMPLE)
    assert "AKIAABCDEFGHIJKLMNOP" not in findings[0].description
    assert "AKIAABCDEFGHIJKLMNOP" not in findings[0].to_dict().values()


def test_parse_gitleaks_empty_array_is_no_findings() -> None:
    assert parse_gitleaks("[]") == []


def test_parse_hadolint_level_to_severity_mapping() -> None:
    findings = {f.rule_id: f for f in parse_hadolint(_HADOLINT_SAMPLE)}
    assert findings["DL3013"].severity == "medium"  # warning
    assert findings["DL3020"].severity == "high"  # error
    assert findings["DL3066"].severity == "low"  # info


def test_parse_hadolint_empty_array_is_no_findings() -> None:
    assert parse_hadolint("[]") == []


def test_parse_trivy_config_severity_mapping() -> None:
    findings = {f.rule_id: f for f in parse_trivy_config(_TRIVY_SAMPLE)}
    assert findings["DS-0002"].severity == "high"
    assert findings["DS-0005"].severity == "low"
    assert findings["DS-0002"].file == "Dockerfile"
    assert findings["DS-0002"].line == 3


def test_parse_trivy_config_no_results_key_is_no_findings() -> None:
    assert parse_trivy_config(json.dumps({"SchemaVersion": 2})) == []
