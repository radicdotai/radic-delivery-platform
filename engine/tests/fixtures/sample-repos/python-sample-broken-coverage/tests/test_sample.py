from sample import add, greeting


def test_add() -> None:
    assert add(2, 3) == 5


def test_greeting() -> None:
    assert greeting("world") == "hello, world"
