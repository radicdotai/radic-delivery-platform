from __future__ import annotations

import re

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
IMAGE_REF_RE = re.compile(
    r"^[a-z0-9.-]+-docker\.pkg\.dev/[a-z][a-z0-9-]{4,28}[a-z0-9]/[a-z0-9._-]+/[a-z0-9._/-]+@(sha256:[0-9a-f]{64})$"
)
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
RELEASE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,40}$")
_NAME_RE = re.compile(r"^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$")


class NamingError(ValueError):
    pass


def digest_of(image_ref: str) -> str:
    match = IMAGE_REF_RE.match(image_ref)
    if not match:
        raise NamingError(
            f"image must be <registry>/<project>/<repo>/<name>@sha256:<64 hex>, got {image_ref!r}"
        )
    return match.group(1)


def _checked(name: str) -> str:
    if not _NAME_RE.match(name):
        raise NamingError(f"invalid Cloud Deploy resource name {name!r}")
    return name


def _sha(commit: str) -> str:
    if not SHA40_RE.match(commit):
        raise NamingError(f"commit must be 40 lowercase hex, got {commit!r}")
    return commit


def dev_release_name(commit: str, run_number: int) -> str:
    return _checked(f"d-{_sha(commit)[:7]}-{run_number}")


def rel_release_name(release_id: str, commit: str) -> str:
    if not RELEASE_ID_RE.match(release_id):
        raise NamingError(f"invalid release id {release_id!r}")
    return _checked(f"r-{release_id.replace('.', '-')}-{_sha(commit)[:7]}")


def rollback_rollout_id(epoch_seconds: int) -> str:
    return _checked(f"rb-{epoch_seconds}")


def labels(service: str, commit: str, release_id: str | None) -> dict[str, str]:
    out = {"svc": service, "commit": _sha(commit)[:7]}
    if release_id:
        out["release-id"] = release_id.replace(".", "-")
    return out


def release_annotations(commit: str, digest: str, run_url: str, initiator: str) -> dict[str, str]:
    out = {"commit": _sha(commit), "digest": digest, "initiator": initiator}
    if run_url:
        out["run-url"] = run_url
    for key, value in out.items():
        if "," in value or "=" in value:
            raise NamingError(f"annotation {key} may not contain ',' or '='")
    return out


def kv_flag(pairs: dict[str, str]) -> str:
    return ",".join(f"{k}={v}" for k, v in pairs.items())
