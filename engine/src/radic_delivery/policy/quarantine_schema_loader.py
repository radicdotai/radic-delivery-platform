"""Loads and caches schemas/quarantine.schema.json."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, cast

from radic_delivery.paths import schemas_dir


@lru_cache(maxsize=1)
def load_quarantine_schema() -> dict[str, Any]:
    path = schemas_dir() / "quarantine.schema.json"
    with path.open(encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))
