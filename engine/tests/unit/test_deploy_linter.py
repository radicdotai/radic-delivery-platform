"""Orchestration tests for deploy/linter.py.

The no-inline-secret rule uses the real gitleaks binary (same precedent as
specs/003) — no fake runner needed here, since gitleaks is the only
subprocess this feature invokes and it is fast against single small files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from radic_delivery.deploy.linter import lint

_CLEAN_MANIFEST = """\
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: svc-{env}
spec:
  template:
    metadata:
      annotations: {{}}
    spec:
      serviceAccountName: sa@x.iam.gserviceaccount.com
      containerConcurrency: 80
      timeoutSeconds: 300
      containers:
        - image: app
          env:
            - name: LOG_LEVEL
              value: debug
          startupProbe:
            httpGet: {{path: /health, port: 8080}}
          livenessProbe:
            httpGet: {{path: /health, port: 8080}}
"""


def _write_clean_manifests(repo_root: Path) -> None:
    run_dir = repo_root / "deploy" / "run"
    run_dir.mkdir(parents=True)
    for env in ("dev", "stage", "prod"):
        (run_dir / f"{env}.yaml").write_text(_CLEAN_MANIFEST.format(env=env))


_SERVICE_YAML = {
    "dev": "deploy/run/dev.yaml",
    "stage": "deploy/run/stage.yaml",
    "prod": "deploy/run/prod.yaml",
}


def _descriptor(service_yaml: dict[str, str] | None, parity_allow: list[str] | None = None) -> dict[str, Any]:
    deployable: dict[str, Any] = {"name": "svc"}
    if service_yaml is not None:
        deployable["service_yaml"] = service_yaml
    if parity_allow is not None:
        deployable["parity"] = {"allow": parity_allow}
    return {"cloud_deploy": {"deployables": [deployable]}}


def test_clean_manifests_pass_every_rule(tmp_path: Path) -> None:
    _write_clean_manifests(tmp_path)
    service_yaml = _SERVICE_YAML
    result = lint(_descriptor(service_yaml, ["service_name"]), repo_root=tmp_path)
    assert result.overall == "pass"


def test_real_gitleaks_detects_a_planted_secret_in_a_manifest(tmp_path: Path) -> None:
    _write_clean_manifests(tmp_path)
    dev_path = tmp_path / "deploy" / "run" / "dev.yaml"
    dev_path.write_text(dev_path.read_text().replace("value: debug", "value: debug-AKIAABCDEFGHIJKLMNOP"))

    service_yaml = _SERVICE_YAML
    result = lint(_descriptor(service_yaml, ["service_name"]), repo_root=tmp_path)

    assert result.overall == "fail"
    secret_checks = [c for c in result.checks if c.rule == "no_inline_secret"]
    assert any(c.status == "fail" and "dev.yaml" in c.file for c in secret_checks)
    assert all(c.status == "pass" for c in secret_checks if "dev.yaml" not in c.file)


def test_missing_manifest_file_is_a_distinct_status(tmp_path: Path) -> None:
    _write_clean_manifests(tmp_path)
    (tmp_path / "deploy" / "run" / "prod.yaml").unlink()

    service_yaml = _SERVICE_YAML
    result = lint(_descriptor(service_yaml), repo_root=tmp_path)

    assert result.overall == "fail"
    prod_checks = [c for c in result.checks if "prod.yaml" in c.file]
    assert prod_checks
    assert all(c.status == "missing_file" for c in prod_checks)
    assert not any(c.status == "fail" for c in prod_checks)


def test_invalid_yaml_manifest_is_a_distinct_status(tmp_path: Path) -> None:
    _write_clean_manifests(tmp_path)
    (tmp_path / "deploy" / "run" / "prod.yaml").write_text("not: valid: yaml: at: all:")

    service_yaml = _SERVICE_YAML
    result = lint(_descriptor(service_yaml), repo_root=tmp_path)

    prod_checks = [c for c in result.checks if "prod.yaml" in c.file]
    assert prod_checks
    assert all(c.status == "parse_error" for c in prod_checks)


def test_multiple_deployables_are_all_checked(tmp_path: Path) -> None:
    _write_clean_manifests(tmp_path)
    (tmp_path / "deploy" / "run" / "worker-dev.yaml").write_text(_CLEAN_MANIFEST.format(env="worker-dev"))
    (tmp_path / "deploy" / "run" / "worker-stage.yaml").write_text(_CLEAN_MANIFEST.format(env="worker-stage"))
    (tmp_path / "deploy" / "run" / "worker-prod.yaml").write_text(_CLEAN_MANIFEST.format(env="worker-prod"))

    descriptor = {
        "cloud_deploy": {
            "deployables": [
                {
                    "name": "svc",
                    "service_yaml": {
                        "dev": "deploy/run/dev.yaml",
                        "stage": "deploy/run/stage.yaml",
                        "prod": "deploy/run/prod.yaml",
                    },
                    "parity": {"allow": ["service_name"]},
                },
                {
                    "name": "worker",
                    "service_yaml": {
                        "dev": "deploy/run/worker-dev.yaml",
                        "stage": "deploy/run/worker-stage.yaml",
                        "prod": "deploy/run/worker-prod.yaml",
                    },
                    "parity": {"allow": ["service_name"]},
                },
            ]
        }
    }
    result = lint(descriptor, repo_root=tmp_path)
    deployables_checked = {c.deployable for c in result.checks}
    assert deployables_checked == {"svc", "worker"}


def test_job_only_deployable_is_not_applicable(tmp_path: Path) -> None:
    result = lint(_descriptor(service_yaml=None), repo_root=tmp_path)
    assert all(c.status == "not_applicable" for c in result.checks)
    assert result.overall == "pass"
