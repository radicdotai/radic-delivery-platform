"""Cross-environment parity rule (research.md D3's explicit mapping table).

Compares a deployable's dev/stage/prod manifests against each other.
`parity.allow` only ever tolerates the two specific differences the table
names; every other difference is an unconditional failure, with zero
tolerance when `parity.allow` is empty (spec Edge Case).
"""

from __future__ import annotations

from typing import Any, cast

from radic_delivery.deploy.result import ManifestCheck

_ENVS = ("dev", "stage", "prod")
_FILE_JOIN = ", "


def _container(manifest: dict[str, Any]) -> dict[str, Any]:
    spec = manifest.get("spec", {}).get("template", {}).get("spec", {})
    containers = spec.get("containers", [])
    return containers[0] if containers else {}


def _env_name_sets(manifest: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Returns (plain_var_names, secret_sourced_var_names)."""
    plain: set[str] = set()
    secret: set[str] = set()
    for entry in _container(manifest).get("env", []):
        name = entry.get("name")
        if "valueFrom" in entry and "secretKeyRef" in entry.get("valueFrom", {}):
            secret.add(name)
        else:
            plain.add(name)
    return plain, secret


def _probe_shape(manifest: dict[str, Any], probe_name: str) -> Any:
    probe = _container(manifest).get(probe_name, {})
    http_get = probe.get("httpGet", {})
    return (http_get.get("path"), http_get.get("port"))


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, set)):
        return tuple(sorted(_freeze(v) for v in value))
    return value


def _scalar_check(deployable: str, files: str, label: str, values: dict[str, Any]) -> ManifestCheck:
    if len(set(map(_freeze, values.values()))) == 1:
        return ManifestCheck(
            deployable=deployable,
            rule="parity",
            status="pass",
            file=files,
            detail=f"{label} matches across dev/stage/prod.",
        )
    return ManifestCheck(
        deployable=deployable,
        rule="parity",
        status="fail",
        file=files,
        detail=f"{label} differs across environments and is not covered by parity.allow: {values}",
    )


def _name_check(
    deployable: str, files: str, manifests: dict[str, dict[str, Any]], allow: list[str]
) -> ManifestCheck:
    names = {env: m.get("metadata", {}).get("name") for env, m in manifests.items()}
    if len(set(names.values())) > 1 and "service_name" not in allow:
        return ManifestCheck(
            deployable=deployable,
            rule="parity",
            status="fail",
            file=files,
            detail=f"metadata.name differs across environments ({names}) and parity.allow "
            "does not include 'service_name'.",
        )
    return ManifestCheck(
        deployable=deployable,
        rule="parity",
        status="pass",
        file=files,
        detail="metadata.name is consistent or explicitly allowed to differ.",
    )


def _plain_env_check(deployable: str, files: str, manifests: dict[str, dict[str, Any]]) -> ManifestCheck:
    plain_sets = {env: _env_name_sets(m)[0] for env, m in manifests.items()}
    if len(set(map(_freeze, plain_sets.values()))) > 1:
        return ManifestCheck(
            deployable=deployable,
            rule="parity",
            status="fail",
            file=files,
            detail=f"Plain (non-secret) env var names differ across environments: {plain_sets}. "
            "parity.allow never covers plain config vars.",
        )
    return ManifestCheck(
        deployable=deployable,
        rule="parity",
        status="pass",
        file=files,
        detail="Plain env var names are consistent.",
    )


def _secret_env_check(
    deployable: str, files: str, manifests: dict[str, dict[str, Any]], allow: list[str]
) -> ManifestCheck:
    secret_sets = {env: _env_name_sets(m)[1] for env, m in manifests.items()}
    if len(set(map(_freeze, secret_sets.values()))) > 1 and "secret_count" not in allow:
        return ManifestCheck(
            deployable=deployable,
            rule="parity",
            status="fail",
            file=files,
            detail=f"secretKeyRef-sourced env var names differ across environments ({secret_sets}) "
            "and parity.allow does not include 'secret_count'.",
        )
    return ManifestCheck(
        deployable=deployable,
        rule="parity",
        status="pass",
        file=files,
        detail="Secret-sourced env var names are consistent or explicitly allowed to differ.",
    )


def check_parity(
    deployable: str, manifests: dict[str, dict[str, Any]], allow: list[str]
) -> list[ManifestCheck]:
    files = _FILE_JOIN.join(f"run/{env}.yaml" for env in _ENVS if env in manifests)

    checks = [
        _name_check(deployable, files, manifests, allow),
        _plain_env_check(deployable, files, manifests),
        _secret_env_check(deployable, files, manifests, allow),
    ]

    def spec(m: dict[str, Any]) -> dict[str, Any]:
        return cast(dict[str, Any], m.get("spec", {}).get("template", {}).get("spec", {}))

    def annotations(m: dict[str, Any]) -> dict[str, Any]:
        return cast(
            dict[str, Any], m.get("spec", {}).get("template", {}).get("metadata", {}).get("annotations", {})
        )

    scalar_fields: list[tuple[str, dict[str, Any]]] = [
        ("serviceAccountName", {e: spec(m).get("serviceAccountName") for e, m in manifests.items()}),
        ("containerConcurrency", {e: spec(m).get("containerConcurrency") for e, m in manifests.items()}),
        ("timeoutSeconds", {e: spec(m).get("timeoutSeconds") for e, m in manifests.items()}),
        ("template annotations", {e: annotations(m) for e, m in manifests.items()}),
        ("startupProbe", {e: _probe_shape(m, "startupProbe") for e, m in manifests.items()}),
        ("livenessProbe", {e: _probe_shape(m, "livenessProbe") for e, m in manifests.items()}),
    ]
    for label, values in scalar_fields:
        checks.append(_scalar_check(deployable, files, label, values))

    return checks
