"""A tiny, deliberately trivial sample service used to exercise `gate evaluate`."""

from __future__ import annotations

import os  # deliberately unused import -- a real ruff violation, seeded for the gate's lint test


def add(a: int, b: int) -> int:
    return a + b


def greeting(name: str) -> str:
    return f"hello, {name}"
