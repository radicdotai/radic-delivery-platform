"""A tiny, deliberately trivial sample service used to exercise `gate evaluate`."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    return a + b


def greeting(name: str) -> str:
    return f"hello, {name}"


def untested_branch(x: int) -> str:
    # Deliberately uncovered code, seeded for the gate's coverage-floor test:
    # all existing tests still pass, but this function is never exercised,
    # dropping measured coverage below the descriptor's floor.
    if x > 0:
        return "positive"
    elif x < 0:
        return "negative"
    else:
        return "zero"
