from sample import add, greeting


def test_add() -> None:
    # Deliberately wrong assertion, seeded for the gate's unit-test check.
    assert add(2, 3) == 999


def test_greeting() -> None:
    assert greeting("world") == "hello, world"
