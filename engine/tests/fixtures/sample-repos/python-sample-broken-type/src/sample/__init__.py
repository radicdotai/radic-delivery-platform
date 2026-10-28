"""A tiny, deliberately trivial sample service used to exercise `gate evaluate`."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    return a + b


def greeting(name: str) -> str:
    return f"hello, {name}"


def mistyped(x: int) -> str:
    # Deliberate type error for the gate's typecheck test: returns an int
    # where the annotation promises a str. Never called by any test, so
    # this seeds a mypy failure without affecting lint, tests, or coverage.
    return x
