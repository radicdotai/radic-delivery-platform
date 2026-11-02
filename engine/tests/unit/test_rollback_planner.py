"""Pure tests for `rollback/planner.py` — no I/O, no git (research.md D4,
D6)."""

from __future__ import annotations

from radic_delivery.rollback.planner import plan


def test_plan_names_environment_current_and_target_exactly() -> None:
    result = plan(
        environment="prod",
        current_release="r-2026-11-03-1-4444444",
        current_digest="sha256:" + "3" * 64,
        target_release="r-2026-10-20-1-aaaaaaa",
        target_digest="sha256:" + "4" * 64,
    )

    assert result.environment == "prod"
    assert result.current_release == "r-2026-11-03-1-4444444"
    assert result.current_digest == "sha256:" + "3" * 64
    assert result.target_release == "r-2026-10-20-1-aaaaaaa"
    assert result.target_digest == "sha256:" + "4" * 64
    assert result.no_op is False


def test_same_inputs_produce_identical_plan_each_time() -> None:
    kwargs = dict(
        environment="stage",
        current_release="r-A",
        current_digest="sha256:" + "1" * 64,
        target_release="r-B",
        target_digest="sha256:" + "2" * 64,
        estimated_minutes=7,
        migrations_reverted=True,
    )

    first = plan(**kwargs)
    second = plan(**kwargs)

    assert first.to_dict() == second.to_dict()


def test_estimated_minutes_and_migrations_reverted_defaults() -> None:
    result = plan(
        environment="prod",
        current_release="r-A",
        current_digest="sha256:" + "1" * 64,
        target_release="r-B",
        target_digest="sha256:" + "2" * 64,
    )

    assert result.estimated_minutes == 5
    assert result.migrations_reverted is False


def test_estimated_minutes_and_migrations_reverted_carried_through() -> None:
    result = plan(
        environment="prod",
        current_release="r-A",
        current_digest="sha256:" + "1" * 64,
        target_release="r-B",
        target_digest="sha256:" + "2" * 64,
        estimated_minutes=20,
        migrations_reverted=True,
    )

    assert result.estimated_minutes == 20
    assert result.migrations_reverted is True


def test_identical_current_and_target_release_is_a_no_op() -> None:
    result = plan(
        environment="prod",
        current_release="r-same",
        current_digest="sha256:" + "1" * 64,
        target_release="r-same",
        target_digest="sha256:" + "1" * 64,
    )

    assert result.no_op is True
