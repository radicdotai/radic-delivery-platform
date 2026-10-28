import pytest

from sample import add, greeting


def test_add() -> None:
    assert add(2, 3) == 5


def test_greeting() -> None:
    assert greeting("world") == "hello, world"


@pytest.mark.skip(reason="deliberately skipped, seeded for the gate's skip-budget test")
def test_add_again() -> None:
    # Coverage of add() is already provided by test_add above, so skipping
    # this one seeds an isolated skip-budget failure without also dropping
    # measured coverage below the descriptor's floor.
    assert add(10, 20) == 30
