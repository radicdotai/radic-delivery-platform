"""Cross-environment parity rule tests (research.md D3's mapping table)."""

from __future__ import annotations

from typing import Any

from radic_delivery.deploy.parity import check_parity


def _manifest(name: str, env_entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    env_entries = env_entries or [
        {"name": "LOG_LEVEL", "value": "debug"},
        {"name": "DATABASE_URL", "valueFrom": {"secretKeyRef": {"name": "x", "key": "latest"}}},
    ]
    return {
        "metadata": {"name": name},
        "spec": {
            "template": {
                "metadata": {"annotations": {"autoscaling.knative.dev/minScale": "0"}},
                "spec": {
                    "serviceAccountName": "sa@x.iam.gserviceaccount.com",
                    "containerConcurrency": 80,
                    "timeoutSeconds": 300,
                    "containers": [
                        {
                            "image": "app",
                            "env": env_entries,
                            "startupProbe": {"httpGet": {"path": "/health", "port": 8080}},
                            "livenessProbe": {"httpGet": {"path": "/health", "port": 8080}},
                        }
                    ],
                },
            }
        },
    }


def _manifests(**names: str) -> dict[str, dict[str, Any]]:
    return {env: _manifest(name) for env, name in names.items()}


def test_name_difference_passes_when_allowed() -> None:
    manifests = _manifests(dev="sample-dev", stage="sample-stage", prod="sample")
    checks = check_parity("sample", manifests, ["service_name"])
    name_check = next(c for c in checks if "metadata.name" in c.detail)
    assert name_check.status == "pass"


def test_name_difference_fails_when_not_allowed() -> None:
    manifests = _manifests(dev="sample-dev", stage="sample-stage", prod="sample")
    checks = check_parity("sample", manifests, [])
    name_check = next(c for c in checks if "metadata.name" in c.detail)
    assert name_check.status == "fail"


def test_secret_var_membership_difference_passes_when_allowed() -> None:
    dev_env = [{"name": "DATABASE_URL", "valueFrom": {"secretKeyRef": {"name": "x", "key": "latest"}}}]
    prod_env = dev_env + [{"name": "API_KEY", "valueFrom": {"secretKeyRef": {"name": "y", "key": "latest"}}}]
    manifests = {
        "dev": _manifest("sample", dev_env),
        "stage": _manifest("sample", dev_env),
        "prod": _manifest("sample", prod_env),
    }
    checks = check_parity("sample", manifests, ["secret_count"])
    secret_check = next(
        c for c in checks if "secretKeyRef-sourced" in c.detail or "Secret-sourced" in c.detail
    )
    assert secret_check.status == "pass"


def test_secret_var_membership_difference_fails_when_not_allowed() -> None:
    dev_env = [{"name": "DATABASE_URL", "valueFrom": {"secretKeyRef": {"name": "x", "key": "latest"}}}]
    prod_env = dev_env + [{"name": "API_KEY", "valueFrom": {"secretKeyRef": {"name": "y", "key": "latest"}}}]
    manifests = {
        "dev": _manifest("sample", dev_env),
        "stage": _manifest("sample", dev_env),
        "prod": _manifest("sample", prod_env),
    }
    checks = check_parity("sample", manifests, [])
    secret_check = next(
        c for c in checks if "secretKeyRef-sourced" in c.detail or "Secret-sourced" in c.detail
    )
    assert secret_check.status == "fail"


def test_plain_env_var_name_difference_always_fails() -> None:
    """parity.allow never covers plain config vars (research.md D3)."""
    dev_env = [{"name": "LOG_LEVEL", "value": "debug"}]
    prod_env = [{"name": "LOG_LEVEL", "value": "warn"}, {"name": "EXTRA_FLAG", "value": "1"}]
    manifests = {
        "dev": _manifest("sample", dev_env),
        "stage": _manifest("sample", dev_env),
        "prod": _manifest("sample", prod_env),
    }
    checks = check_parity("sample", manifests, ["service_name", "secret_count"])
    plain_check = next(c for c in checks if "Plain" in c.detail)
    assert plain_check.status == "fail"


def test_service_account_difference_always_fails() -> None:
    manifests = _manifests(dev="sample", stage="sample", prod="sample")
    manifests["prod"]["spec"]["template"]["spec"]["serviceAccountName"] = "other-sa@x.iam.gserviceaccount.com"
    checks = check_parity("sample", manifests, ["service_name", "secret_count"])
    sa_check = next(c for c in checks if "serviceAccountName" in c.detail)
    assert sa_check.status == "fail"


def test_fully_consistent_manifests_pass_every_check() -> None:
    manifests = _manifests(dev="sample", stage="sample", prod="sample")
    checks = check_parity("sample", manifests, [])
    assert all(c.status == "pass" for c in checks)
