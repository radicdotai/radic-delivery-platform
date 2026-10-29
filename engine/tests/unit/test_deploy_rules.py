"""Pure per-manifest content rule tests (no filesystem or subprocess)."""

from __future__ import annotations

from radic_delivery.deploy.rules import check_image_placeholder, check_no_traffic_key, check_startup_probe

_CLEAN_MANIFEST = {
    "spec": {
        "template": {
            "spec": {
                "containers": [
                    {
                        "image": "app",
                        "startupProbe": {"httpGet": {"path": "/health", "port": 8080}},
                    }
                ]
            }
        }
    }
}


def test_image_placeholder_passes_with_app() -> None:
    check = check_image_placeholder("svc", "dev.yaml", _CLEAN_MANIFEST)
    assert check.status == "pass"


def test_image_placeholder_fails_with_real_image_ref() -> None:
    real_image = "us-central1-docker.pkg.dev/x/y@sha256:abc"
    manifest = {"spec": {"template": {"spec": {"containers": [{"image": real_image}]}}}}
    check = check_image_placeholder("svc", "dev.yaml", manifest)
    assert check.status == "fail"
    assert check.rule == "image_placeholder"


def test_no_traffic_key_passes_without_traffic() -> None:
    check = check_no_traffic_key("svc", "dev.yaml", _CLEAN_MANIFEST)
    assert check.status == "pass"


def test_no_traffic_key_fails_with_traffic_present() -> None:
    manifest = {"spec": {"traffic": [{"percent": 100, "latestRevision": True}]}}
    check = check_no_traffic_key("svc", "dev.yaml", manifest)
    assert check.status == "fail"
    assert check.rule == "no_traffic_key"


def test_startup_probe_passes_when_declared() -> None:
    check = check_startup_probe("svc", "dev.yaml", _CLEAN_MANIFEST)
    assert check.status == "pass"


def test_startup_probe_fails_when_missing() -> None:
    manifest = {"spec": {"template": {"spec": {"containers": [{"image": "app"}]}}}}
    check = check_startup_probe("svc", "dev.yaml", manifest)
    assert check.status == "fail"
    assert check.rule == "startup_probe"
