"""Resolve a validated descriptor to its fully-defaulted form (spec FR-008).

`descriptor show` must refuse to resolve an invalid descriptor (Acceptance
Scenario 2), so this module only ever operates on documents that
descriptor/validator.py has already accepted.
"""

from __future__ import annotations

from typing import Any, cast

import jsonschema
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


def _deref(subschema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    if "$ref" not in subschema:
        return subschema
    pointer = subschema["$ref"]
    assert pointer.startswith("#/"), f"Only local $ref pointers are supported, got: {pointer}"
    node: Any = root
    for part in pointer[2:].split("/"):
        node = node[part]
    return cast(dict[str, Any], node)


def _pick_matching_oneof(
    value: Any, branches: list[dict[str, Any]], root: dict[str, Any]
) -> dict[str, Any] | None:
    registry = Registry().with_resource(
        "root", Resource.from_contents(root, default_specification=DRAFT202012)
    )
    for branch in branches:
        validator = jsonschema.Draft202012Validator(branch, registry=registry)
        if validator.is_valid(value):
            return branch
    return None


def _walk(
    value: Any, subschema: dict[str, Any], path: str, root: dict[str, Any], defaulted: list[str]
) -> Any:
    subschema = _deref(subschema, root)

    if "oneOf" in subschema:
        branch = _pick_matching_oneof(value, subschema["oneOf"], root)
        if branch is not None:
            return _walk(value, branch, path, root, defaulted)
        return value

    is_object_schema = subschema.get("type") == "object" or "properties" in subschema
    if is_object_schema and isinstance(value, dict):
        result = dict(value)
        for key, prop_schema in subschema.get("properties", {}).items():
            child_path = f"{path}.{key}" if path else key
            if key in result:
                result[key] = _walk(result[key], prop_schema, child_path, root, defaulted)
            elif "default" in prop_schema:
                result[key] = prop_schema["default"]
                defaulted.append(child_path)
        return result

    if subschema.get("type") == "array" and isinstance(value, list) and "items" in subschema:
        items_schema = subschema["items"]
        return [_walk(v, items_schema, f"{path}[{i}]", root, defaulted) for i, v in enumerate(value)]

    return value


def resolve(document: dict[str, Any], schema: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return (resolved_document, defaulted_field_paths).

    defaulted_field_paths lists every dotted field path that was filled in
    from the schema's `default` rather than set explicitly by the author.
    """
    defaulted: list[str] = []
    resolved = _walk(document, schema, "", schema, defaulted)
    return resolved, defaulted
