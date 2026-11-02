"""Computes a rollback plan from fully explicit input (research.md D4).

No git, no file I/O, no external call — "the previous release" and "the
current release" are supplied by the caller, never resolved here.
"""

from __future__ import annotations

from radic_delivery.rollback.result import RollbackPlan


def plan(
    *,
    environment: str,
    current_release: str,
    current_digest: str,
    target_release: str,
    target_digest: str,
    estimated_minutes: int = 5,
    migrations_reverted: bool = False,
) -> RollbackPlan:
    return RollbackPlan(
        environment=environment,
        current_release=current_release,
        current_digest=current_digest,
        target_release=target_release,
        target_digest=target_digest,
        estimated_minutes=estimated_minutes,
        migrations_reverted=migrations_reverted,
        no_op=current_release == target_release,
    )
