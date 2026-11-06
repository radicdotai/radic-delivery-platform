from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from radic_delivery import cli
from radic_delivery.deploy import naming
from radic_delivery.deploy.cloud_deploy import CloudDeploy, InvalidInput, Target, resolve_target
from radic_delivery.deploy.drift import compare
from radic_delivery.deploy.gcloud import GcloudError
from radic_delivery.descriptor.validator import validate
from radic_delivery.exit_codes import ExitCode

FIXTURES = Path(__file__).parent.parent / "fixtures"
SANDBOX = FIXTURES / "operations-console-cdpoc.yml"
SHA = "a" * 40
DIGEST = "sha256:" + "b" * 64
OTHER = "sha256:" + "c" * 64
IMAGE = f"us-central1-docker.pkg.dev/radicai/ops-console-cdpoc/operations-console@{DIGEST}"
PREFIX = "projects/radicai/locations/us-central1/deliveryPipelines/p/releases/"

Handler = Callable[[list[str]], Any]


class FakeGcloud:
    def __init__(self, routes: dict[str, Handler | Any]) -> None:
        self.routes = routes
        self.calls: list[list[str]] = []

    def _answer(self, args: list[str]) -> Any:
        self.calls.append(args)
        key = " ".join(args[:3])
        if key not in self.routes:
            return None
        answer = self.routes[key]
        if isinstance(answer, Exception):
            raise answer
        return answer(args) if callable(answer) else answer

    def json(self, args: list[str]) -> Any:
        return self._answer(args)

    def text(self, args: list[str]) -> str:
        return str(self._answer(args))

    def verbs(self) -> list[str]:
        return [" ".join(c[:3]) for c in self.calls]


def _target(env: str) -> Target:
    doc = yaml.safe_load(SANDBOX.read_text())
    return resolve_target(doc, Path("/repo"), env, None)  # type: ignore[arg-type]


def _rollout(release: str, rid: str, target: str, state: str, end: str = "") -> dict[str, Any]:
    return {
        "name": f"{PREFIX}{release}/rollouts/{rid}",
        "targetId": target,
        "state": state,
        "createTime": end,
        "deployEndTime": end,
    }


def _serving(digest: str = DIGEST, ready: str = "True") -> dict[str, Any]:
    return {
        "run services describe": {
            "status": {"latestReadyRevisionName": "rev-1", "conditions": [{"type": "Ready", "status": ready}]}
        },
        "run revisions describe": {"status": {"imageDigest": f"repo@{digest}"}},
    }


def _cd(fake: FakeGcloud, ticks: list[float] | None = None) -> CloudDeploy:
    clock = iter(ticks or [0.0] * 100)
    return CloudDeploy(fake, clock=lambda: next(clock), sleep=lambda _s: None, now=lambda: 1700000000.0)


def test_sandbox_descriptor_is_valid_and_resolves_names() -> None:
    assert validate(SANDBOX).ok
    dev, stage, prod = _target("dev"), _target("stage"), _target("prod")
    assert (dev.pipeline, dev.target, dev.cloud_run_service) == (
        "ops-console-cdpoc-dev",
        "ops-console-cdpoc-dev",
        "ops-console-cdpoc-dev",
    )
    assert (stage.pipeline, prod.target, prod.project) == (
        "ops-console-cdpoc-rel",
        "ops-console-cdpoc-prod",
        "radicai",
    )
    assert dev.scope() == [
        "--delivery-pipeline=ops-console-cdpoc-dev",
        "--region=us-central1",
        "--project=radicai",
    ]


def test_real_descriptor_cannot_use_the_dev_project_as_release_plane(tmp_path: Path) -> None:
    doc = yaml.safe_load((FIXTURES / "operations-console.yml").read_text())
    doc["cloud_deploy"]["planes"]["release"] = "radicai"
    bad = tmp_path / ".radic" / "service.yml"
    bad.parent.mkdir()
    bad.write_text(yaml.safe_dump(doc))
    assert not validate(bad).ok


def test_sandbox_descriptor_must_use_cdpoc_names(tmp_path: Path) -> None:
    doc = yaml.safe_load(SANDBOX.read_text())
    doc["cloud_deploy"]["deployables"][0]["pipelines"]["dev"] = "operations-console-dev"
    bad = tmp_path / ".radic" / "service.yml"
    bad.parent.mkdir()
    bad.write_text(yaml.safe_dump(doc))
    assert not validate(bad).ok


def test_naming() -> None:
    assert naming.dev_release_name(SHA, 12) == "d-aaaaaaa-12"
    assert naming.rel_release_name("2026.11.06-1", SHA) == "r-2026-11-06-1-aaaaaaa"
    assert naming.digest_of(IMAGE) == DIGEST
    for bad in ("repo/x:latest", IMAGE.replace("@sha256", ":sha256"), IMAGE[:-1]):
        with pytest.raises(naming.NamingError):
            naming.digest_of(bad)
    with pytest.raises(naming.NamingError):
        naming.dev_release_name("abc", 1)


def test_tag_image_is_refused_before_any_gcloud_call() -> None:
    fake = FakeGcloud({})
    with pytest.raises(naming.NamingError):
        _cd(fake).release(_target("dev"), "repo/x:latest", SHA, 1, None, "", "me", 60)
    assert fake.calls == []


def test_dev_release_succeeds_when_serving_digest_matches() -> None:
    t = _target("dev")
    fake = FakeGcloud(
        {
            "deploy releases create": None,
            "deploy rollouts list": [_rollout("d-aaaaaaa-1", "ro-1", t.target, "IN_PROGRESS")],
            "deploy rollouts describe": _rollout("d-aaaaaaa-1", "ro-1", t.target, "SUCCEEDED"),
            **_serving(),
        }
    )
    r = _cd(fake).release(t, IMAGE, SHA, 1, None, "https://github.com/x/runs/1", "aditya", 60)
    assert r.passed and r.state == "SUCCEEDED" and r.serving_digest == DIGEST and r.rollout == "ro-1"
    create = fake.calls[0]
    assert create[:4] == ["deploy", "releases", "create", "d-aaaaaaa-1"]
    assert f"--images=app={IMAGE}" in create
    assert "--source=/repo/deploy" in create and "--skaffold-file=skaffold.yaml" in create
    assert not any(a.startswith("--to-target") for a in create)


def test_release_fails_when_serving_digest_differs() -> None:
    t = _target("dev")
    fake = FakeGcloud(
        {
            "deploy rollouts list": [_rollout("d-aaaaaaa-1", "ro-1", t.target, "IN_PROGRESS")],
            "deploy rollouts describe": _rollout("d-aaaaaaa-1", "ro-1", t.target, "SUCCEEDED"),
            **_serving(OTHER),
        }
    )
    assert not _cd(fake).release(t, IMAGE, SHA, 1, None, "", "me", 60).passed


def test_stage_release_targets_stage_on_rel_pipeline() -> None:
    t = _target("stage")
    fake = FakeGcloud(
        {
            "deploy rollouts list": [_rollout("r", "ro-1", t.target, "IN_PROGRESS")],
            "deploy rollouts describe": _rollout("r", "ro-1", t.target, "SUCCEEDED"),
            **_serving(),
        }
    )
    r = _cd(fake).release(t, IMAGE, SHA, None, "2026.11.06-1", "", "me", 60)
    assert r.passed and r.release == "r-2026-11-06-1-aaaaaaa"
    assert "--to-target=ops-console-cdpoc-stage" in fake.calls[0]
    assert "--delivery-pipeline=ops-console-cdpoc-rel" in fake.calls[0]


def test_release_to_prod_is_refused() -> None:
    with pytest.raises(InvalidInput):
        _cd(FakeGcloud({})).release(_target("prod"), IMAGE, SHA, 1, None, "", "me", 60)


def test_failed_rollout_reports_cause() -> None:
    t = _target("dev")
    failed = {**_rollout("d", "ro-1", t.target, "FAILED"), "deployFailureCause": "CLOUD_BUILD_REQUEST_FAILED"}
    fake = FakeGcloud({"deploy rollouts list": [failed], "deploy rollouts describe": failed})
    r = _cd(fake).release(t, IMAGE, SHA, 1, None, "", "me", 60)
    assert not r.passed and r.state == "FAILED" and r.failed_job == "CLOUD_BUILD_REQUEST_FAILED"


def test_timeout_is_a_failure() -> None:
    t = _target("dev")
    fake = FakeGcloud(
        {
            "deploy rollouts list": [_rollout("d", "ro-1", t.target, "IN_PROGRESS")],
            "deploy rollouts describe": _rollout("d", "ro-1", t.target, "IN_PROGRESS"),
        }
    )
    r = _cd(fake, ticks=[0.0, 0.0, 30.0, 61.0]).release(t, IMAGE, SHA, 1, None, "", "me", 60)
    assert not r.passed and r.state == "TIMED_OUT"


def test_promote_stops_at_pending_approval_and_never_approves() -> None:
    t = _target("prod")
    pending = _rollout("r1", "ro-p", t.target, "PENDING_APPROVAL")
    fake = FakeGcloud(
        {
            "deploy releases describe": {"buildArtifacts": [{"image": "app", "tag": f"repo@{DIGEST}"}]},
            "deploy rollouts list": [pending],
            "deploy rollouts describe": pending,
        }
    )
    r = _cd(fake).promote(t, "r1", 60)
    assert r.passed and r.state == "PENDING_APPROVAL" and r.rollout == "ro-p"
    assert "deploy rollouts approve" not in fake.verbs()
    assert "--to-target=ops-console-cdpoc-prod" in fake.calls[1]


def test_promote_that_deploys_without_approval_fails() -> None:
    t = _target("prod")
    done = _rollout("r1", "ro-p", t.target, "SUCCEEDED")
    fake = FakeGcloud({"deploy rollouts list": [done], "deploy rollouts describe": done})
    assert not _cd(fake).promote(t, "r1", 60).passed


def test_approve_waits_for_success() -> None:
    t = _target("prod")
    fake = FakeGcloud(
        {
            "deploy releases describe": {"buildArtifacts": [{"tag": f"repo@{DIGEST}"}]},
            "deploy rollouts describe": _rollout("r1", "ro-p", t.target, "SUCCEEDED"),
            **_serving(),
        }
    )
    r = _cd(fake).approve(t, "r1", "ro-p", 60)
    assert r.passed and "deploy rollouts approve" in fake.verbs()


def test_rollback_digest_mismatch_is_refused_before_any_change() -> None:
    t = _target("stage")
    fake = FakeGcloud({"deploy releases describe": {"buildArtifacts": [{"tag": f"repo@{OTHER}"}]}})
    with pytest.raises(InvalidInput):
        _cd(fake).rollback(t, "r1", DIGEST, 60)
    assert "deploy targets rollback" not in fake.verbs()


def test_rollback_without_release_finds_its_rollout() -> None:
    t = _target("dev")
    rb = _rollout("d-old", "rb-1700000000", t.target, "SUCCEEDED")
    fake = FakeGcloud(
        {
            "deploy releases list": [{"name": f"{PREFIX}d-new"}, {"name": f"{PREFIX}d-old"}],
            "deploy rollouts list": lambda a: [rb] if "--release=d-old" in a else [],
            "deploy rollouts describe": rb,
            "deploy releases describe": {"buildArtifacts": [{"tag": f"repo@{DIGEST}"}]},
            **_serving(),
        }
    )
    r = _cd(fake).rollback(t, None, None, 60)
    assert r.passed and r.release == "d-old" and r.rollout == "rb-1700000000"
    rollback_call = next(c for c in fake.calls if c[:3] == ["deploy", "targets", "rollback"])
    assert "--rollout-id=rb-1700000000" in rollback_call


def test_status_uses_newest_successful_rollout_including_rollbacks() -> None:
    t = _target("dev")
    rows = {
        "d-new": [_rollout("d-new", "ro-n", t.target, "SUCCEEDED", "2026-11-06T10:00:00Z")],
        "d-old": [_rollout("d-old", "rb-1", t.target, "SUCCEEDED", "2026-11-06T11:00:00Z")],
    }
    fake = FakeGcloud(
        {
            "deploy releases list": [{"name": f"{PREFIX}d-new"}, {"name": f"{PREFIX}d-old"}],
            "deploy rollouts list": lambda a: rows[a[3].split("=", 1)[1]],
            "deploy releases describe": lambda a: {
                "buildArtifacts": [{"tag": f"repo@{DIGEST if a[3] == 'd-old' else OTHER}"}]
            },
            **_serving(),
        }
    )
    r = _cd(fake).status(t)
    assert r.passed and r.release == "d-old" and r.rollout == "rb-1"


def test_drift_compares_fields_and_hides_env_values() -> None:
    def svc(image: str, env_value: str, cpu: str) -> dict[str, Any]:
        return {
            "spec": {
                "template": {
                    "metadata": {"annotations": {"autoscaling.knative.dev/maxScale": "2"}},
                    "spec": {
                        "serviceAccountName": "cdpoc-runtime@radicai.iam.gserviceaccount.com",
                        "containers": [
                            {
                                "image": image,
                                "env": [{"name": "BFF_URL", "value": env_value}],
                                "resources": {"limits": {"cpu": cpu}},
                            }
                        ],
                    },
                }
            }
        }

    rendered = svc(IMAGE, "https://bff", "1")
    live = svc(IMAGE, "https://bff", "1")
    live["spec"]["template"]["metadata"]["annotations"]["run.googleapis.com/operation-id"] = "x"
    assert compare(rendered, live) == []
    changed = svc(IMAGE, "https://evil", "2")
    diffs = compare(rendered, changed)
    assert {d["field"] for d in diffs} == {"container.resources", "container.env.BFF_URL"}
    assert "https://evil" not in json.dumps(diffs)


def test_cli_maps_gcloud_error_to_infra_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGcloud({"deploy releases list": GcloudError("PERMISSION_DENIED")})
    monkeypatch.setattr(cli, "_cloud_deploy", lambda: CloudDeploy(fake))
    result = CliRunner().invoke(
        cli.app, ["deploy", "status", "--env", "dev", "--descriptor", str(SANDBOX), "--format", "json"]
    )
    assert result.exit_code == int(ExitCode.INFRA_ERROR)
    assert json.loads(result.stdout)["error"] == "PERMISSION_DENIED"


def test_cli_refuses_tag_image_with_invalid_input(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeGcloud({})
    monkeypatch.setattr(cli, "_cloud_deploy", lambda: CloudDeploy(fake))
    result = CliRunner().invoke(
        cli.app,
        [
            "deploy",
            "release",
            "--env",
            "dev",
            "--image",
            "x:latest",
            "--commit",
            SHA,
            "--run-number",
            "1",
            "--descriptor",
            str(SANDBOX),
        ],
    )
    assert result.exit_code == int(ExitCode.INVALID_INPUT) and fake.calls == []


def test_cli_release_success_json(monkeypatch: pytest.MonkeyPatch) -> None:
    t = _target("dev")
    fake = FakeGcloud(
        {
            "deploy rollouts list": [_rollout("d", "ro-1", t.target, "IN_PROGRESS")],
            "deploy rollouts describe": _rollout("d", "ro-1", t.target, "SUCCEEDED"),
            **_serving(),
        }
    )
    monkeypatch.setattr(cli, "_cloud_deploy", lambda: _cd(fake))
    result = CliRunner().invoke(
        cli.app,
        [
            "deploy",
            "release",
            "--env",
            "dev",
            "--image",
            IMAGE,
            "--commit",
            SHA,
            "--run-number",
            "7",
            "--descriptor",
            str(SANDBOX),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == int(ExitCode.OK), result.stdout
    payload = json.loads(result.stdout)
    assert payload["outcome"] == "pass" and payload["release"] == "d-aaaaaaa-7"
    assert payload["serving_digest"] == DIGEST
