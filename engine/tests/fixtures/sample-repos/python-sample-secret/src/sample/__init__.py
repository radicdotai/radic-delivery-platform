"""A tiny, deliberately trivial sample service used to exercise `gate evaluate`."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    return a + b


def greeting(name: str) -> str:
    return f"hello, {name}"
