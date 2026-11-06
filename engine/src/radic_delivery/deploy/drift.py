from __future__ import annotations

from typing import Any

import yaml

from radic_delivery.deploy.cloud_deploy import CloudDeploy, Target
from radic_delivery.deploy.gcloud import Gcloud

_CONTAINER_FIELDS = ("image", "resources", "ports", "startupProbe", "livenessProbe", "command", "args")
_SPEC_FIELDS = ("serviceAccountName", "containerConcurrency", "timeoutSeconds")


def _template(service: dict[str, Any]) -> dict[str, Any]:
    return service.get("spec", {}).get("template", {}) or {}


def _covers(expected: Any, live: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(live, dict) and all(_covers(v, live.get(k)) for k, v in expected.items())
    if isinstance(expected, list):
        return (
            isinstance(live, list)
            and len(expected) == len(live)
            and all(_covers(e, v) for e, v in zip(expected, live, strict=True))
        )
    return bool(str(expected) == str(live)) if expected is not None and live is not None else expected == live


def _env_map(container: dict[str, Any]) -> dict[str, Any]:
    return {e["name"]: {k: v for k, v in e.items() if k != "name"} for e in container.get("env", []) or []}


def compare(rendered: dict[str, Any], live: dict[str, Any]) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    want_t, have_t = _template(rendered), _template(live)
    want_ann = (want_t.get("metadata", {}) or {}).get("annotations", {}) or {}
    have_ann = (have_t.get("metadata", {}) or {}).get("annotations", {}) or {}
    for key, value in want_ann.items():
        if have_ann.get(key) != value:
            diffs.append(
                {"field": f"template.annotations.{key}", "expected": value, "live": have_ann.get(key)}
            )
    want_s, have_s = want_t.get("spec", {}) or {}, have_t.get("spec", {}) or {}
    for key in _SPEC_FIELDS:
        if key in want_s and not _covers(want_s.get(key), have_s.get(key)):
            diffs.append({"field": f"spec.{key}", "expected": want_s.get(key), "live": have_s.get(key)})
    want_c = (want_s.get("containers") or [{}])[0]
    have_c = (have_s.get("containers") or [{}])[0]
    for key in _CONTAINER_FIELDS:
        if key in want_c and not _covers(want_c.get(key), have_c.get(key)):
            diffs.append({"field": f"container.{key}", "expected": want_c.get(key), "live": have_c.get(key)})
    want_env, have_env = _env_map(want_c), _env_map(have_c)
    for name in sorted(want_env.keys() | have_env.keys()):
        if not _covers(want_env.get(name), have_env.get(name)):
            diffs.append(
                {
                    "field": f"container.env.{name}",
                    "changed": True,
                    "expected": "set" if name in want_env else "absent",
                    "live": ("value differs" if name in want_env else "set")
                    if name in have_env
                    else "absent",
                }
            )
    return diffs


def drift(gcloud: Gcloud, cd: CloudDeploy, t: Target) -> dict[str, Any]:
    out: dict[str, Any] = {"deployable": t.deployable, "target": t.target, "project": t.project}
    found = cd.last_succeeded(t)
    if found is None:
        return {
            **out,
            "release": None,
            "rollout": None,
            "differences": [],
            "outcome": "fail",
            "error": "no successful rollout to compare against",
        }
    release, row = found
    rel = gcloud.json(["deploy", "releases", "describe", release, *t.scope()]) or {}
    artifact = rel.get("targetArtifacts", {}).get(t.target, {})
    manifest_path = artifact.get("manifestPath") or (
        artifact.get("phaseArtifacts", {}).get("stable", {}).get("manifestPath")
    )
    if not artifact.get("artifactUri") or not manifest_path:
        return {
            **out,
            "release": release,
            "rollout": row.get("name"),
            "differences": [],
            "outcome": "fail",
            "error": "release has no rendered manifest for the target",
        }
    rendered = (
        yaml.safe_load(gcloud.text(["storage", "cat", f"{artifact['artifactUri']}/{manifest_path}"])) or {}
    )
    live = (
        gcloud.json(
            [
                "run",
                "services",
                "describe",
                t.cloud_run_service,
                f"--region={t.region}",
                f"--project={t.project}",
            ]
        )
        or {}
    )
    differences = compare(rendered, live)
    return {
        **out,
        "release": release,
        "rollout": (row.get("name") or "").rsplit("/", 1)[-1],
        "differences": differences,
        "outcome": "pass" if not differences else "fail",
    }
