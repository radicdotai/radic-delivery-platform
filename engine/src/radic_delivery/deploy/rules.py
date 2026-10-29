"""Pure per-manifest content rules (research.md D1).

Each function takes one already-parsed manifest dict and the deployable
name/file path it came from (for the resulting ManifestCheck), and returns
a single ManifestCheck — no filesystem or subprocess access here.
"""

from __future__ import annotations

from typing import Any

from radic_delivery.deploy.result import ManifestCheck


def _container(manifest: dict[str, Any]) -> dict[str, Any] | None:
    containers = manifest.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
    return containers[0] if containers else None


def check_image_placeholder(deployable: str, file: str, manifest: dict[str, Any]) -> ManifestCheck:
    container = _container(manifest)
    image = container.get("image") if container else None
    if image == "app":
        return ManifestCheck(
            deployable=deployable,
            rule="image_placeholder",
            status="pass",
            file=file,
            detail="Uses the required placeholder image reference.",
        )
    return ManifestCheck(
        deployable=deployable,
        rule="image_placeholder",
        status="fail",
        file=file,
        detail=f"Expected image: 'app', found: {image!r}. "
        "The real image digest is substituted only at deploy time by Cloud Deploy.",
    )


def check_no_traffic_key(deployable: str, file: str, manifest: dict[str, Any]) -> ManifestCheck:
    if "traffic" in manifest.get("spec", {}):
        return ManifestCheck(
            deployable=deployable,
            rule="no_traffic_key",
            status="fail",
            file=file,
            detail="spec.traffic is present; traffic management belongs to Cloud Deploy, never the manifest.",
        )
    return ManifestCheck(
        deployable=deployable, rule="no_traffic_key", status="pass", file=file, detail="No spec.traffic key."
    )


def check_startup_probe(deployable: str, file: str, manifest: dict[str, Any]) -> ManifestCheck:
    container = _container(manifest)
    if container and "startupProbe" in container:
        return ManifestCheck(
            deployable=deployable,
            rule="startup_probe",
            status="pass",
            file=file,
            detail="startupProbe is declared.",
        )
    return ManifestCheck(
        deployable=deployable,
        rule="startup_probe",
        status="fail",
        file=file,
        detail="No startupProbe declared on the container.",
    )
