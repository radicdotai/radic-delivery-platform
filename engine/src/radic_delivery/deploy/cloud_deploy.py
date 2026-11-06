from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from radic_delivery.deploy import naming
from radic_delivery.deploy.gcloud import Gcloud

Env = Literal["dev", "stage", "prod"]
Command = Literal["release", "promote", "approve", "rollback", "status"]
TERMINAL_FAIL = {"FAILED", "CANCELLED", "APPROVAL_REJECTED", "HALTED"}
POLL_SECONDS = 10


class InvalidInput(ValueError):
    pass


@dataclass(frozen=True)
class Target:
    deployable: str
    service: str
    env: Env
    pipeline: str
    target: str
    project: str
    region: str
    cloud_run_service: str
    source_dir: Path
    skaffold_file: str

    def scope(self) -> list[str]:
        return [
            f"--delivery-pipeline={self.pipeline}",
            f"--region={self.region}",
            f"--project={self.project}",
        ]


@dataclass
class DeployResult:
    command: Command
    target: Target
    release: str | None = None
    rollout: str | None = None
    state: str | None = None
    failed_job: str | None = None
    requested_digest: str | None = None
    serving_digest: str | None = None
    ready: bool | None = None
    duration_seconds: float = 0.0
    passed: bool = False
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "deployable": self.target.deployable,
            "pipeline": self.target.pipeline,
            "target": self.target.target,
            "project": self.target.project,
            "release": self.release,
            "rollout": self.rollout,
            "state": self.state,
            "failed_job": self.failed_job,
            "requested_digest": self.requested_digest,
            "serving_digest": self.serving_digest,
            "ready": self.ready,
            "duration_seconds": round(self.duration_seconds, 1),
            "outcome": "pass" if self.passed else "fail",
            "error": self.error,
            **self.extra,
        }


def resolve_target(document: dict[str, Any], repo_root: Path, env: Env, deployable: str | None) -> Target:
    cd = document["cloud_deploy"]
    items = cd["deployables"]
    if deployable is None and len(items) > 1:
        raise InvalidInput("--deployable is required when the descriptor lists more than one")
    chosen = next((d for d in items if deployable in (None, d["name"])), None)
    if chosen is None:
        raise InvalidInput(f"deployable {deployable!r} is not in the descriptor")
    pipeline_key = "dev" if env == "dev" else "rel"
    pipeline = chosen["pipelines"].get(pipeline_key)
    if pipeline is None:
        raise InvalidInput(f"deployable {chosen['name']!r} has no {pipeline_key} pipeline")
    environment = document["environments"][env]
    skaffold = Path(cd.get("skaffold_file", "deploy/skaffold.yaml"))
    return Target(
        deployable=chosen["name"],
        service=document["service"]["name"],
        env=env,
        pipeline=pipeline,
        target=f"{chosen['name']}-{env}",
        project=cd["planes"]["dev" if env == "dev" else "release"],
        region=environment["region"],
        cloud_run_service=environment["cloud_run_service"],
        source_dir=repo_root / skaffold.parent,
        skaffold_file=skaffold.name,
    )


def _basename(name: str | None) -> str | None:
    return name.rsplit("/", 1)[-1] if name else None


class CloudDeploy:
    def __init__(
        self,
        gcloud: Gcloud,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._g = gcloud
        self._clock = clock
        self._sleep = sleep
        self._now = now

    def _rollouts(self, t: Target, release: str) -> list[dict[str, Any]]:
        rows = self._g.json(["deploy", "rollouts", "list", f"--release={release}", *t.scope()]) or []
        rows = [r for r in rows if r.get("targetId") == t.target]
        return sorted(rows, key=lambda r: r.get("createTime", ""))

    def _describe_rollout(self, t: Target, release: str, rollout: str) -> dict[str, Any]:
        return (
            self._g.json(["deploy", "rollouts", "describe", rollout, f"--release={release}", *t.scope()])
            or {}
        )

    def _wait(self, t: Target, release: str, rollout: str, until: set[str], timeout: int) -> dict[str, Any]:
        deadline = self._clock() + timeout
        while True:
            row = self._describe_rollout(t, release, rollout)
            state = row.get("state")
            if state in until or state in TERMINAL_FAIL or state == "SUCCEEDED":
                return row
            if self._clock() >= deadline:
                return {**row, "state": "TIMED_OUT"}
            self._sleep(POLL_SECONDS)

    def serving(self, t: Target) -> tuple[str | None, bool | None]:
        svc = (
            self._g.json(
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
        conditions = svc.get("status", {}).get("conditions", [])
        ready = next((c.get("status") == "True" for c in conditions if c.get("type") == "Ready"), None)
        revision = svc.get("status", {}).get("latestReadyRevisionName")
        if not revision:
            return None, ready
        rev = (
            self._g.json(
                ["run", "revisions", "describe", revision, f"--region={t.region}", f"--project={t.project}"]
            )
            or {}
        )
        image_digest = rev.get("status", {}).get("imageDigest", "")
        return (image_digest.rsplit("@", 1)[-1] or None), ready

    def release_digest(self, t: Target, release: str) -> str | None:
        rel = self._g.json(["deploy", "releases", "describe", release, *t.scope()]) or {}
        for artifact in rel.get("buildArtifacts", []):
            tag = artifact.get("tag", "")
            if "@sha256:" in tag:
                return str(tag.rsplit("@", 1)[-1])
        return None

    def _finish(self, r: DeployResult, row: dict[str, Any], expect: str, digest: str | None) -> DeployResult:
        r.rollout = _basename(row.get("name")) or r.rollout
        r.state = row.get("state")
        if r.state in TERMINAL_FAIL:
            r.failed_job = row.get("deployFailureCause") or row.get("failureReason")
        if r.state == "SUCCEEDED" and expect == "SUCCEEDED":
            r.serving_digest, r.ready = self.serving(r.target)
            r.passed = bool(r.ready) and digest is not None and r.serving_digest == digest
        else:
            r.passed = r.state == expect
        return r

    def release(
        self,
        t: Target,
        image: str,
        commit: str,
        run_number: int | None,
        release_id: str | None,
        run_url: str,
        initiator: str,
        timeout: int,
    ) -> DeployResult:
        digest = naming.digest_of(image)
        if t.env == "dev":
            if run_number is None:
                raise InvalidInput("--run-number is required for --env dev")
            name = naming.dev_release_name(commit, run_number)
        elif t.env == "stage":
            if not release_id:
                raise InvalidInput("--release-id is required for --env stage")
            name = naming.rel_release_name(release_id, commit)
        else:
            raise InvalidInput("deploy release only targets dev or stage; prod is reached by promote")
        r = DeployResult("release", t, release=name, requested_digest=digest)
        args = [
            "deploy",
            "releases",
            "create",
            name,
            *t.scope(),
            f"--source={t.source_dir}",
            f"--skaffold-file={t.skaffold_file}",
            f"--images=app={image}",
            f"--labels={naming.kv_flag(naming.labels(t.service, commit, release_id))}",
            f"--annotations={naming.kv_flag(naming.release_annotations(commit, digest, run_url, initiator))}",
        ]
        if t.env == "stage":
            args.append(f"--to-target={t.target}")
        self._g.json(args)
        rows = self._rollouts(t, name)
        if not rows:
            r.state = "FAILED"
            r.failed_job = "no rollout was created for the target"
            return r
        row = self._wait(t, name, _basename(rows[-1]["name"]) or "", set(), timeout)
        return self._finish(r, row, "SUCCEEDED", digest)

    def promote(self, t: Target, release: str, timeout: int) -> DeployResult:
        if t.env != "prod":
            raise InvalidInput("promote only targets prod")
        r = DeployResult("promote", t, release=release, requested_digest=self.release_digest(t, release))
        self._g.json(
            [
                "deploy",
                "releases",
                "promote",
                f"--release={release}",
                f"--to-target={t.target}",
                *t.scope(),
                "--quiet",
            ]
        )
        rows = self._rollouts(t, release)
        if not rows:
            r.state = "FAILED"
            r.failed_job = "no rollout was created for the target"
            return r
        row = self._wait(t, release, _basename(rows[-1]["name"]) or "", {"PENDING_APPROVAL"}, timeout)
        return self._finish(r, row, "PENDING_APPROVAL", None)

    def approve(self, t: Target, release: str, rollout: str, timeout: int) -> DeployResult:
        r = DeployResult(
            "approve", t, release=release, rollout=rollout, requested_digest=self.release_digest(t, release)
        )
        self._g.json(
            ["deploy", "rollouts", "approve", rollout, f"--release={release}", *t.scope(), "--quiet"]
        )
        row = self._wait(t, release, rollout, set(), timeout)
        return self._finish(r, row, "SUCCEEDED", r.requested_digest)

    def _recent_releases(self, t: Target) -> list[str]:
        rows = (
            self._g.json(["deploy", "releases", "list", *t.scope(), "--sort-by=~createTime", "--limit=10"])
            or []
        )
        return [n for n in (_basename(r.get("name")) for r in rows) if n]

    def last_succeeded(self, t: Target) -> tuple[str, dict[str, Any]] | None:
        best: tuple[str, dict[str, Any]] | None = None
        for release in self._recent_releases(t):
            for row in self._rollouts(t, release):
                if row.get("state") != "SUCCEEDED":
                    continue
                if best is None or row.get("deployEndTime", "") > best[1].get("deployEndTime", ""):
                    best = (release, row)
        return best

    def rollback(
        self, t: Target, release: str | None, expect_digest: str | None, timeout: int
    ) -> DeployResult:
        r = DeployResult("rollback", t, release=release, requested_digest=expect_digest)
        if expect_digest is not None:
            if not naming.DIGEST_RE.match(expect_digest):
                raise InvalidInput("--expect-digest must be sha256:<64 hex>")
            if release is None:
                raise InvalidInput("--expect-digest needs --release")
            actual = self.release_digest(t, release)
            if actual != expect_digest:
                raise InvalidInput(f"release {release} carries {actual}, not {expect_digest}")
        rollout_id = naming.rollback_rollout_id(int(self._now()))
        args = [
            "deploy",
            "targets",
            "rollback",
            t.target,
            *t.scope(),
            f"--rollout-id={rollout_id}",
            "--quiet",
        ]
        if release:
            args.append(f"--release={release}")
        self._g.json(args)
        owner = release or next(
            (
                rel
                for rel in self._recent_releases(t)
                if any(_basename(x.get("name")) == rollout_id for x in self._rollouts(t, rel))
            ),
            None,
        )
        if owner is None:
            r.state = "FAILED"
            r.failed_job = f"rollback rollout {rollout_id} not found"
            return r
        r.release = owner
        r.requested_digest = expect_digest or self.release_digest(t, owner)
        row = self._wait(t, owner, rollout_id, set(), timeout)
        return self._finish(r, row, "SUCCEEDED", r.requested_digest)

    def status(self, t: Target) -> DeployResult:
        r = DeployResult("status", t)
        found = self.last_succeeded(t)
        r.serving_digest, r.ready = self.serving(t)
        if found is None:
            r.state = None
            return r
        r.release, row = found
        r.rollout = _basename(row.get("name"))
        r.state = row.get("state")
        r.requested_digest = self.release_digest(t, r.release)
        r.passed = bool(r.ready) and r.serving_digest is not None and r.serving_digest == r.requested_digest
        return r
